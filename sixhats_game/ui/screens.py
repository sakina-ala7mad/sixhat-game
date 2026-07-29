"""
ui/screens.py
-------------
One render_xxx() function per screen. app.py just calls whichever one
matches st.session_state.screen. All game state is re-read from the DB
every single call (via src.database / src.game_engine) so this works
correctly across multiple browser tabs polling in parallel.
"""

import json
import time
import streamlit as st
import streamlit.components.v1 as components

from src import database as db
from src import hats as hats_module
from src import xp_engine
from src import evaluator
from src import game_engine as ge
from ui import components as comp
from ui import tutorial_content
from ui import mode_intro_content

PUZZLE_QUESTIONS_PER_ROUND = 5
PUZZLE_SECONDS_PER_QUESTION = 20  # quick-fire pacing, per the design spec
SCENARIO_ROUND_SECONDS = 120
PUZZLE_LEAVE_PENALTY = 15  # xp deducted for leaving a puzzle round early


def _apply_puzzle_leave_penalty(pz: dict) -> int:
    """Deducts (and returns) the leave-early XP penalty. Team-scope puzzle XP
    flows to the team pool only (see render_puzzle below, matching the
    README's own design -- 'their XP is credited to the whole team') so the
    penalty mirrors that and doesn't touch every teammate's personal XP."""
    user = st.session_state.get("user")
    scope = st.session_state.get("scope", "individual")
    penalty = min(PUZZLE_LEAVE_PENALTY, max(pz.get("score", 0), 0))
    if penalty:
        if scope == "team" and st.session_state.get("team_key"):
            db.add_team_xp(st.session_state.team_key, -penalty)
        elif user:
            db.add_user_xp(user["display_name"], -penalty, individual=True)
    return penalty


def leave_puzzle_round_and_clear(apply_penalty: bool = True):
    """Used when a player leaves a puzzle round via the SIDEBAR (Home / How
    to play / Log out) rather than the in-round 'Pause / end game' button --
    those buttons navigate straight past the round with no recap screen, so
    unlike the in-round confirm flow, this always clears session_state too.
    That fixes a round that was previously left half-answered in
    session_state silently reappearing (already time-expired) the next time
    the player started a fresh puzzle round."""
    pz = st.session_state.get("puzzle")
    if pz and apply_penalty and not pz.get("left_early"):
        penalty = _apply_puzzle_leave_penalty(pz)
        if penalty:
            st.toast(f"Left the puzzle round early — {penalty} xp penalty applied.")
    for k in list(st.session_state.keys()):
        if k == "puzzle" or k.startswith("answered_") or k.startswith("pz_"):
            del st.session_state[k]


def _goto(screen, **extra):
    st.session_state.screen = screen
    for k, v in extra.items():
        st.session_state[k] = v
    st.rerun()


# ============================================================== LOGIN =====
def render_login():
    st.markdown("<div class='sh-title' style='font-size:2rem;'><span class='sh-bounce'>🎩</span> Six Hats</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sh-soft'>Sharpen how your team thinks, decides, and communicates — "
        "one hat at a time.</div>", unsafe_allow_html=True,
    )
    st.write("")
    with st.container():
        st.markdown("<div class='sh-card'>", unsafe_allow_html=True)
        name = st.text_input("Your name", key="login_name", placeholder="e.g. Sara Adel")
        show_pw = st.checkbox("👁️ Show password", key="login_show_pw")
        pw_type = "default" if show_pw else "password"
        password = st.text_input("Password", key="login_pw", type=pw_type,
                                  help="First time using this name creates your account. "
                                       "Log back in later with the same name + password.")
        # We don't know for certain whether this name is new until submit, but
        # we can check cheaply as they type so a first-timer gets a confirm
        # field -- a typo'd password on account creation otherwise permanently
        # locks them out of that name with no way back in.
        is_new_name = bool(name.strip()) and not db.get_user(name)
        password2 = None
        if is_new_name:
            password2 = st.text_input("Confirm password (first time using this name)",
                                       key="login_pw2", type=pw_type)
        if st.button("Enter the game", type="primary", use_container_width=True):
            if not name.strip():
                st.warning("Please enter a name.")
            elif is_new_name and password != password2:
                st.error("Those two passwords don't match — please re-enter them.")
            else:
                user, err = db.create_or_login_user(name, password)
                if err:
                    st.error(err)
                else:
                    token = db.new_session_token(user["display_name"])
                    st.session_state.user = {"name_key": user["name_key"], "display_name": user["display_name"]}
                    st.session_state.session_token = token
                    if user["current_team"]:
                        st.session_state.team_key = user["current_team"]
                    if not user["seen_tutorial"]:
                        _goto("tutorial")
                    else:
                        _goto("home")
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================ TUTORIAL ====
def render_tutorial(first_time=True):
    st.markdown("<div class='sh-title'>🎓 How Six Hats Thinking Works</div>", unsafe_allow_html=True)
    components.html(tutorial_content.TUTORIAL_HTML, height=1150, scrolling=False)

    st.markdown(
        "<div class='sh-card'>"
        "<b>🧩 Puzzle Mode</b><div class='sh-soft'>Quick-fire: match short sentences to the correct "
        "hat color, beat the clock, level up. Good for warm-ups.</div><br>"
        "<b>🎭 Scenario Mode</b><div class='sh-soft'>You get a real workplace situation and ONE random "
        "hat. Write your take from that hat's point of view. In Team mode, everyone sees the same "
        "situation but a different hat — then compares answers side-by-side afterward. That comparison "
        "is where the real learning happens.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    if first_time:
        if c1.button("Got it, let's play!", type="primary", use_container_width=True):
            db.mark_tutorial_seen(st.session_state.user["display_name"])
            _goto("home")
        if c2.button("Skip", use_container_width=True):
            db.mark_tutorial_seen(st.session_state.user["display_name"])
            _goto("home")
    else:
        if st.button("Close", type="primary", use_container_width=True):
            _goto(st.session_state.get("_return_screen", "home"))


def _button_select(label: str, options: list[str], state_key: str) -> str:
    """A row of real clickable buttons acting as a single-select control
    (replaces st.radio / st.select_slider). The current choice is remembered
    in st.session_state[state_key] across reruns; the selected option is
    shown as a solid/primary button, the rest as outlined/secondary buttons.
    The whole control is wrapped in a bordered "section" frame so each
    control (Play as / Mode / Difficulty) reads as its own distinct group."""
    if state_key not in st.session_state:
        st.session_state[state_key] = options[0]
    st.markdown(f"<div class='sh-section'><div class='sh-section-label'>{label}</div>", unsafe_allow_html=True)
    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        selected = st.session_state[state_key] == opt
        with cols[i]:
            if st.button(opt, key=f"{state_key}_btn_{opt}",
                         type="primary" if selected else "secondary",
                         use_container_width=True):
                st.session_state[state_key] = opt
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state[state_key]


# ================================================================ HOME =====
def render_home():
    user = st.session_state.user
    urow = db.get_user(user["display_name"])

    st.markdown(f"<div class='sh-title'>Welcome back, {user['display_name']} <span class='sh-bounce'>👋</span></div>", unsafe_allow_html=True)
    comp.render_xp_bar(urow["total_xp"])
    relaxed = st.checkbox("🐢 Give me 50% more time on round timers (accessibility)",
                           value=bool(urow["relaxed_timing"]), key="relaxed_timing_toggle")
    if relaxed != bool(urow["relaxed_timing"]):
        db.set_relaxed_timing(user["display_name"], relaxed)
        st.rerun()
    st.write("")

    scope = _button_select("Play as", ["Individual", "Team"], "home_scope")

    if scope == "Team":
        _render_team_picker()
        team_key = st.session_state.get("team_key")
        if not team_key:
            return
        team = db.get_team(team_key)
        st.markdown(
            f"<div class='sh-card'>Your team: <b>{team['display_name']}</b> "
            f"&nbsp; <span class='sh-pill'>ID: {team['team_id']}</span> "
            f"&nbsp; Team XP: <b>{team['total_xp']}</b><br>"
            f"<span class='sh-soft'>Team password (share with teammates so they can join): "
            f"<b>{team['password']}</b></span></div>",
            unsafe_allow_html=True,
        )
        if st.button("🔑 Generate a new team password", key="reset_team_pw_btn"):
            new_pw = db.reset_team_password(team_key)
            st.success(f"New team password: {new_pw} — the old one no longer works.")
            st.rerun()
        existing = db.get_lobby_session_for_team(team_key)
        existing_active_players = []
        if existing and existing["status"] in ("lobby", "active"):
            db.mark_stale_players_left(existing["session_id"], stale_after=25.0)
            existing_active_players = [p for p in db.get_session_players(existing["session_id"]) if not p["left_game"]]

        if existing and existing["status"] in ("lobby", "active") and existing_active_players:
            st.info(f"{existing_active_players[0]['display_name']} is already in a team scenario game — jump in.")
            if st.button("Join your team game", type="primary", use_container_width=True):
                _goto("lobby", session_id=existing["session_id"])
            return

        mode = _button_select("Mode", ["Scenario (team discussion)", "Puzzle (quick-fire)"], "home_mode")
        level = _button_select("Difficulty", ["easy", "medium", "hard"], "home_level")

        # Any team member can create the game; whoever creates it becomes host.
        # Clicking this shows the "how this round works" carousel first --
        # the session itself isn't created until they tap "Ready to play".
        if st.button("🚀 Create game (become host)", key="create_team_btn", use_container_width=True):
            m = "scenario" if mode.startswith("Scenario") else "puzzle"
            _goto("mode_intro", pending_action={"scope": "team", "mode": m, "level": level, "team_key": team_key})

        if st.session_state.get("confirm_leave_team_home"):
            sole_member = db.active_member_count(team_key) <= 1
            if sole_member:
                st.warning(
                    "⚠️ You're the **last member** of this team. Leaving now will "
                    "**delete the team** and permanently lose its scenario-mode team "
                    "score -- this can't be undone. Are you sure?"
                )
            else:
                st.warning(
                    "⚠️ This leaves your team entirely, not just this round -- you'll "
                    "need the team password again to rejoin. Are you sure?"
                )
            lc1, lc2 = st.columns(2)
            if lc1.button("✅ Yes, leave the team", key="confirm_leave_team_home_yes",
                           type="primary", use_container_width=True):
                was_last = db.leave_team(team_key, user["display_name"])
                st.session_state.team_key = None
                st.session_state["confirm_leave_team_home"] = False
                if was_last:
                    st.toast("Team deleted — its score is gone, but the name is free again.")
                st.rerun()
            if lc2.button("❌ Cancel", key="confirm_leave_team_home_no", use_container_width=True):
                st.session_state["confirm_leave_team_home"] = False
                st.rerun()
        elif st.button("Leave team", key="leave_team_btn", use_container_width=True):
            st.session_state["confirm_leave_team_home"] = True
            st.rerun()

    else:
        mode = _button_select("Mode", ["Scenario (solo)", "Puzzle (quick-fire)"], "home_mode_i")
        level = _button_select("Difficulty", ["easy", "medium", "hard"], "home_level_i")
        if st.button("▶️ Start", key="start_solo_btn", use_container_width=True):
            m = "scenario" if mode.startswith("Scenario") else "puzzle"
            _goto("mode_intro", pending_action={"scope": "individual", "mode": m, "level": level})

    st.write("")
    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("🏆 Dashboard", use_container_width=True):
        _goto("dashboard")
    if c2.button("❓ How to play", use_container_width=True):
        st.session_state["_return_screen"] = "home"
        _goto("tutorial_reopen")


# =========================================================== MODE INTRO ====
def render_mode_intro():
    """A pop-out, left/right scrollable step carousel explaining exactly how
    the chosen mode works (the timer, the question, how to answer, etc.)
    shown once between clicking Start/Create and the round actually
    beginning. Nothing is created in the database until "Ready to play"."""
    pending = st.session_state.get("pending_action")
    if not pending:
        _goto("home")
        return

    mode = pending["mode"]
    is_puzzle = mode == "puzzle"

    user = st.session_state.user
    urow = db.get_user(user["display_name"])
    already_seen = bool(urow["seen_puzzle_intro"] if is_puzzle else urow["seen_scenario_intro"])
    if already_seen and not st.session_state.get("force_show_mode_intro"):
        _launch_pending_action(pending)
        return

    st.markdown(
        f"<div class='sh-title'>{'🧩' if is_puzzle else '🎭'} "
        f"How {'Puzzle' if is_puzzle else 'Scenario'} Mode Works</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='sh-soft' style='margin-bottom:0.6rem;'>Swipe or use the arrows to "
        "flip through the steps \u2014 then jump in.</div>",
        unsafe_allow_html=True,
    )

    html = mode_intro_content.PUZZLE_INTRO_HTML if is_puzzle else mode_intro_content.SCENARIO_INTRO_HTML
    components.html(html, height=430, scrolling=False)

    st.write("")
    c1, c2 = st.columns([1, 2])
    if c1.button("‹ Back", use_container_width=True):
        st.session_state.pending_action = None
        _goto("home")
    if c2.button("✅ Ready to play!", key="ready_to_play_btn", use_container_width=True):
        if is_puzzle:
            db.mark_puzzle_intro_seen(user["display_name"])
        else:
            db.mark_scenario_intro_seen(user["display_name"])
        st.session_state.pop("force_show_mode_intro", None)
        _launch_pending_action(pending)


def _launch_pending_action(pending: dict):
    """Actually creates/starts the session that render_mode_intro() was
    just previewing, then navigates into it -- this is the code that used
    to run directly on the Start/Create button click in render_home()."""
    user = st.session_state.user
    scope, mode, level = pending["scope"], pending["mode"], pending["level"]
    st.session_state.pending_action = None

    if scope == "team":
        if mode == "puzzle":
            # Puzzle mode has no lobby/host concept -- each teammate just
            # plays their own quick-fire round and the XP flows to the team.
            _goto("puzzle", level=level, scope="team")
        else:
            round_seconds = ge.effective_seconds(SCENARIO_ROUND_SECONDS, user["display_name"])
            sid = ge.start_team_lobby(pending["team_key"], user["display_name"], mode, level,
                                       round_seconds=round_seconds)
            _goto("lobby", session_id=sid)
    else:
        if mode == "puzzle":
            _goto("puzzle", level=level, scope="individual")
        else:
            # Individual mode has no lobby wait -- start instantly with a
            # hat already assigned, per the "instant start" design note.
            round_seconds = ge.effective_seconds(SCENARIO_ROUND_SECONDS, user["display_name"])
            sid = ge.start_individual_session(user["display_name"], user["display_name"], "scenario", level,
                                                round_seconds=round_seconds)
            ge.begin_round(sid, "scenario", level)
            _goto("lobby", session_id=sid)


def _render_team_picker():
    user = st.session_state.user
    urow = db.get_user(user["display_name"])
    if urow["current_team"]:
        st.session_state.team_key = urow["current_team"]
        return

    st.markdown("<div class='sh-card'>", unsafe_allow_html=True)
    teams = db.list_teams()
    if teams:
        st.write("**Join an existing team**")
        for t in teams:
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.write(f"**{t['display_name']}**  `{t['team_id']}`")
            c2.write(f"{t['member_count']}/6 members")
            with c3:
                pw = st.text_input("team password", key=f"jt_pw_{t['team_key']}", label_visibility="collapsed",
                                    placeholder="password", type="password")
                if st.button("Join", key=f"jt_btn_{t['team_key']}"):
                    ok, err = db.join_team(t["team_key"], pw, user["display_name"])
                    if ok:
                        st.session_state.team_key = t["team_key"]
                        st.rerun()
                    else:
                        st.error(err)
    else:
        st.write("No teams yet — create the first one!")

    st.write("**Or create a new team**")
    c1, c2, c3 = st.columns([3, 2, 2])
    new_name = c1.text_input("team name", key="new_team_name", label_visibility="collapsed", placeholder="Team name")
    new_pw = c2.text_input("team password", key="new_team_pw", label_visibility="collapsed",
                            placeholder="Set a password", type="password")
    if c3.button("Create team"):
        team, err = db.create_team(new_name, new_pw, user["display_name"])
        if err:
            st.error(err)
        else:
            st.session_state.team_key = team["team_key"]
            st.success(f"Team created! Share this ID so others can join: {team['team_id']}")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================== SCENARIO =====
def render_lobby():
    """Combined waiting-room + active-round screen for scenario mode
    (team or individual) -- per design, the waiting screen and the active
    screen are the same view so nothing jarring happens at start."""
    user = st.session_state.user
    session_id = st.session_state.get("session_id")
    session = db.get_session(session_id)
    if not session:
        _goto("home")
        return

    is_team = session["scope"] == "team"
    if is_team:
        team = db.get_team(session["team_key"])
        st.markdown(f"<div class='sh-title'>🎭 {team['display_name']} — Scenario Round</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='sh-title'>🎭 Solo Scenario Round</div>", unsafe_allow_html=True)

    players = db.get_session_players(session_id)
    active_players = [p for p in players if not p["left_game"]]
    is_host = db.name_key(session["host_name"] or "") == user["name_key"]
    already_joined = any(p["name_key"] == user["name_key"] for p in active_players)

    if session["status"] == "lobby":
        st.markdown(f"<span class='sh-pill'>Level: {session['level'].title()}</span>", unsafe_allow_html=True)
        st.write("")
        comp.render_lobby_slots([p["display_name"] for p in active_players],
                                 max_slots=6 if is_team else 1)
        st.markdown(
            "<div class='sh-soft' style='text-align:center;'>Hats are assigned randomly and stay hidden "
            "until the round starts.</div>", unsafe_allow_html=True,
        )
        if is_team:
            st.info(f"Team join ID: **{team['team_id']}** — teammates can join anytime, the host doesn't need "
                    f"to wait for a full team.")

        if is_team and not is_host and not already_joined:
            st.markdown("<div class='sh-soft' style='text-align:center;'>You're on this team, but not in "
                        "this round yet.</div>", unsafe_allow_html=True)
            if st.button("🎯 Play with them", key="join_round_btn", type="primary",
                         use_container_width=True):
                ge.join_scenario_round(session_id, user["display_name"])
                db.rejoin_session(session_id, user["display_name"])
                st.rerun()

        if is_host:
            if st.button("▶️ Start round", key="start_round_btn", use_container_width=True):
                ge.begin_round(session_id, "scenario", session["level"])
                st.rerun()
        else:
            if already_joined:
                st.info("Waiting for the host to start the round…")
            st.button("🔄 Refresh", use_container_width=True)

        if is_team:
            if st.session_state.get("confirm_leave_team"):
                sole_member = db.active_member_count(session["team_key"]) <= 1
                if sole_member:
                    st.warning(
                        "⚠️ You're the **last member** of this team. Leaving now will "
                        "**delete the team** and permanently lose its scenario-mode team "
                        "score -- this can't be undone. Are you sure?"
                    )
                else:
                    st.warning("⚠️ This leaves your team entirely, not just this round — you'll need "
                               "the team password again to rejoin. Are you sure?")
                lc1, lc2 = st.columns(2)
                if lc1.button("✅ Yes, leave the team", key="confirm_leave_team_yes", type="primary", use_container_width=True):
                    ge.player_leaves(session_id, user["display_name"])
                    was_last = db.leave_team(session["team_key"], user["display_name"])
                    st.session_state.team_key = None
                    st.session_state["confirm_leave_team"] = False
                    if was_last:
                        st.toast("You were the last member — this team has been deleted. "
                                 "The name is free again for a new team.")
                    _goto("home")
                if lc2.button("❌ Cancel", key="confirm_leave_team_no", use_container_width=True):
                    st.session_state["confirm_leave_team"] = False
                    st.rerun()
            elif st.button("🚪 Leave team", key="leave_lobby_btn", use_container_width=True):
                st.session_state["confirm_leave_team"] = True
                st.rerun()
        else:
            if st.button("🚪 Leave", key="leave_lobby_btn", use_container_width=True):
                ge.player_leaves(session_id, user["display_name"])
                _goto("home")
        return

    # ----- active or finished -----
    my_row = next((p for p in players if p["name_key"] == user["name_key"]), None)

    if (my_row and my_row["left_game"] and session["status"] == "active"
            and not my_row["submitted"]):
        st.warning("You were marked as having left this round (likely a brief connection or "
                   "backgrounding blip) — you can rejoin if the round is still going.")
        if st.button("↩️ Rejoin round", key="rejoin_round_btn", type="primary", use_container_width=True):
            db.rejoin_session(session_id, user["display_name"])
            st.rerun()
        return

    # Heartbeat: proves this player is still here, reaps anyone stale, and
    # auto-ends the round if nobody real is left in it.
    if my_row and not my_row["left_game"]:
        ge.refresh_presence(session_id, user["display_name"])
        session = db.get_session(session_id)     # re-read: refresh_presence may have just finished it
        players = db.get_session_players(session_id)
        my_row = next((p for p in players if p["name_key"] == user["name_key"]), None)

    scenario = hats_module.get_scenario_by_id(session["level"], session["scenario_id"])
    my_hat = my_row["hat_color"] if my_row else None
    try:
        active_hats = json.loads(session["active_hats"]) if session["active_hats"] else []
    except Exception:
        active_hats = []

    st.markdown(f"<div class='sh-card'><b>Situation — {scenario['title']}</b><br>{scenario['situation']}</div>",
                unsafe_allow_html=True)

    # Round finished (everyone submitted, or everyone left) -- freeze here,
    # no timer, no more ticking down.
    if session["status"] == "finished":
        comp.render_faces_row(
            [{"name": p["display_name"], "hat_color": p["hat_color"], "submitted": bool(p["submitted"])}
             for p in players if not p["left_game"]],
            hats_active=active_hats or None,
        )
        _render_scenario_results(session, scenario, players, is_team)
        return

    left = ge.seconds_left(session)
    tcol, _ = st.columns([1, 3])
    with tcol:
        comp.render_timer(left)

    comp.render_faces_row(
        [{"name": p["display_name"], "hat_color": p["hat_color"], "submitted": bool(p["submitted"])}
         for p in players if not p["left_game"]],
        hats_active=active_hats or None,
    )

    if ge.round_expired(session):
        if my_row and my_row["hat_color"] and not my_row["submitted"] and not my_row["left_game"]:
            draft_answer = st.session_state.get(f"answer_{session_id}", "")
            is_first = ge.is_first_submitter(session_id)
            on_topic, creativity, correction = evaluator.evaluate_scenario_answer(
                my_row["hat_color"], draft_answer, scenario
            )
            bonus = xp_engine.scenario_individual_bonus(0, creativity, is_first)
            recorded = db.submit_answer(session_id, user["display_name"], draft_answer, on_topic, correction,
                                         creativity, base_xp=0, speed_xp=bonus, first_submit=is_first)
            if recorded:
                db.add_user_xp(user["display_name"], bonus, individual=not is_team)
        ge.auto_submit_timeout(session_id, scenario, skip_name_key=user["name_key"])
        ge.maybe_finish_session(session_id)
        st.rerun()

    st.write("")
    if my_hat:
        comp.hat_role_card(my_hat)
        already = bool(my_row["submitted"])
        answer = st.text_area("Your response from this hat's point of view", max_chars=300, disabled=already,
                               key=f"answer_{session_id}", placeholder="Up to 300 characters…")
        if not already:
            st.caption("💡 Click outside the box (or press Ctrl+Enter) after typing so your draft actually "
                       "saves — if the timer runs out, whatever's saved gets submitted and scored "
                       "automatically, even if it's unfinished.")
            if st.button("✅ Submit answer", type="primary", use_container_width=True):
                secs_left = ge.seconds_left(session)
                is_first = ge.is_first_submitter(session_id)
                on_topic, creativity, correction = evaluator.evaluate_scenario_answer(my_hat, answer, scenario)
                bonus = xp_engine.scenario_individual_bonus(secs_left, creativity, is_first)
                recorded = db.submit_answer(session_id, user["display_name"], answer, on_topic, correction,
                                             creativity, base_xp=0, speed_xp=bonus, first_submit=is_first)
                if recorded:
                    db.add_user_xp(user["display_name"], bonus, individual=not is_team)
                ge.maybe_finish_session(session_id)
                st.rerun()
        else:
            st.success("Answer submitted — waiting for the rest of the team to finish…")
    else:
        st.warning("No hat assigned to you for this round (more players than active hats, or you joined late).")

    if st.button("🚪 Leave round", key="leave_round_btn", use_container_width=True):
        ge.player_leaves(session_id, user["display_name"])
        st.rerun()


def _render_scenario_results(session, scenario, players, is_team):
    session_id = session["session_id"]
    # DB-guarded (not st.session_state-guarded): every teammate's browser tab
    # renders this same screen independently, so the payout must only fire
    # once across ALL of them, not once per tab.
    if db.try_mark_session_paid(session_id):
        if is_team:
            ge.payout_team_scenario_round(session_id, session["level"], session["team_key"])
        else:
            ge.payout_individual_scenario_round(session_id, session["level"], st.session_state.user["display_name"])

    st.success(f"Round complete! Baseline round XP awarded: +{xp_engine.scenario_round_baseline(session['level'])}"
               + (" to the whole team." if is_team else "."))

    # Only show the hats that were actually in play this round -- not all 6.
    try:
        active_hats = json.loads(session["active_hats"]) if session["active_hats"] else []
    except Exception:
        active_hats = []
    round_hats = [h for h in hats_module.HAT_ORDER if h in active_hats] or hats_module.HAT_ORDER

    st.markdown(f"### 🧠 Debrief — this round's {len(round_hats)} hat"
                f"{'s' if len(round_hats) != 1 else ''}, side by side")
    st.markdown("<div class='sh-soft'>This is the real value of Six Hats: compare how each lens saw the same "
                "situation.</div>", unsafe_allow_html=True)

    num_cols = min(3, len(round_hats)) or 1
    cols = st.columns(num_cols)
    for i, hat in enumerate(round_hats):
        meta = hats_module.HATS[hat]
        bg = hats_module.HATS[hat]["color_hex"]
        text = comp.HAT_TEXT_ON_VIVID[hat]
        p = next((pp for pp in players if pp["hat_color"] == hat), None)
        with cols[i % num_cols]:
            st.markdown(
                f"""<div class='sh-card' style="background:{bg} !important;
                            border:1px solid rgba(0,0,0,0.08) !important; min-height:220px;">
                    <div style="font-size:1.8rem; line-height:1;">{meta['icon']}</div>
                    <div style="font-weight:800; font-size:1.05rem; color:{text} !important; margin-top:0.2rem;">
                        {meta['name']}
                    </div>
                    <div style="font-size:0.85rem; color:{text} !important; opacity:0.8; margin-bottom:0.5rem;">
                        {p['display_name'] if p else 'unassigned'}
                    </div>""",
                unsafe_allow_html=True,
            )
            if p and p["answer"]:
                verdict = "✅ On-topic" if p["is_correct"] else "🟡 Off-topic / partial"
                st.markdown(
                    f"<div style='color:{text}; opacity:0.85; font-size:0.82rem;'>"
                    f"{verdict} · creativity {p['creativity_score']}/10 · +{p['speed_xp']} xp</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='color:{text}; font-size:0.88rem; margin-top:0.4rem;'>"
                    f"<b>Their answer:</b> {p['answer']}</div>",
                    unsafe_allow_html=True,
                )
            elif p:
                st.markdown(
                    f"<div style='color:{text}; opacity:0.75; font-size:0.85rem;'>"
                    f"No answer submitted this round.</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"<div style='color:{text}; opacity:0.85; font-size:0.82rem; "
                f"margin-top:0.5rem; padding-top:0.4rem; border-top:1px solid rgba(0,0,0,0.08);'>"
                f"<b>Reference take:</b> {scenario['reference_answers'].get(hat, '')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns(2)
    if is_team and c1.button("🔁 Play again with same team", type="primary", use_container_width=True):
        team_key = session["team_key"]
        round_seconds = ge.effective_seconds(SCENARIO_ROUND_SECONDS, st.session_state.user["display_name"])
        sid = ge.start_team_lobby(team_key, st.session_state.user["display_name"], "scenario", session["level"],
                                   round_seconds=round_seconds)
        _goto("lobby", session_id=sid)
    if c2.button("🏠 Back to home", use_container_width=True):
        ge.player_leaves(session["session_id"], st.session_state.user["display_name"])
        _goto("home")


# ============================================================= PUZZLE =====
def render_puzzle():
    user = st.session_state.user
    level = st.session_state.get("level", "easy")
    scope = st.session_state.get("scope", "individual")

    if "puzzle" not in st.session_state:
        seconds = ge.effective_seconds(PUZZLE_SECONDS_PER_QUESTION, user["display_name"])
        st.session_state.puzzle = {
            "idx": 0, "score": 0, "log": [],
            "q": hats_module.random_puzzle_question(level),
            "q_start": time.time(),
            "exclude": set(),
            "seconds_per_q": seconds,
        }
    pz = st.session_state.puzzle

    # ---- pause / end game (leave) ----
    if st.session_state.get("confirm_leave_puzzle"):
        st.warning("⚠️ Leaving now ends this round early and reduces your score. Are you sure?")
        lc1, lc2 = st.columns(2)
        if lc1.button("✅ Yes, leave", key="confirm_leave_yes", type="primary", use_container_width=True):
            penalty = _apply_puzzle_leave_penalty(pz)
            pz["score"] -= penalty
            pz["left_early"] = True
            st.session_state["confirm_leave_puzzle"] = False
            _goto("puzzle_results")
        if lc2.button("❌ Cancel, keep playing", key="confirm_leave_no", use_container_width=True):
            st.session_state["confirm_leave_puzzle"] = False
            st.rerun()
        return

    st.markdown(f"<div class='sh-title'>🧩 Puzzle Mode — {level.title()}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sh-soft'>Question {pz['idx'] + 1} of {PUZZLE_QUESTIONS_PER_ROUND} "
                f"&nbsp;·&nbsp; scope: {scope}</div>", unsafe_allow_html=True)

    if st.button("⏸ Pause / end game", key="leave_puzzle_btn"):
        st.session_state["confirm_leave_puzzle"] = True
        st.rerun()

    elapsed = time.time() - pz["q_start"]
    left = max(0, pz.get("seconds_per_q", PUZZLE_SECONDS_PER_QUESTION) - elapsed)
    comp.render_timer(left)

    q = pz["q"]
    st.markdown(f"<div class='sh-card'>“{q['text']}”</div>", unsafe_allow_html=True)

    answered_key = f"answered_{pz['idx']}"

    # Timer ran out with no answer -- auto-submit as a miss.
    if left <= 0 and not st.session_state.get(answered_key):
        xp = xp_engine.puzzle_xp(level, False, 0)
        if scope == "team" and st.session_state.get("team_key"):
            db.add_team_xp(st.session_state.team_key, xp)
        else:
            db.add_user_xp(user["display_name"], xp, individual=True)
        pz["score"] += xp
        pz["log"].append({"question": q, "chosen": None, "correct": False, "xp": xp, "timed_out": True})
        pz["exclude"].add(q["id"])
        st.session_state[answered_key] = True

    if not st.session_state.get(answered_key):
        chosen = comp.render_hat_answer_buttons(f"pz_{pz['idx']}")
        if chosen:
            is_correct, _ = evaluator.evaluate_puzzle_answer(chosen, q["hat"])
            xp = xp_engine.puzzle_xp(level, is_correct, left)
            if scope == "team" and st.session_state.get("team_key"):
                db.add_team_xp(st.session_state.team_key, xp)
            else:
                db.add_user_xp(user["display_name"], xp, individual=True)
            pz["score"] += xp
            pz["log"].append({"question": q, "chosen": chosen, "correct": is_correct, "xp": xp})
            pz["exclude"].add(q["id"])
            st.session_state[answered_key] = True
            st.rerun()
    else:
        last = pz["log"][-1]
        if last.get("timed_out"):
            st.error(f"⏰ Time's up! The correct hat was {hats_module.HATS[q['hat']]['name']}. {last['xp']} xp")
        elif last["correct"]:
            st.success(f"✅ Correct! It was the {hats_module.HATS[q['hat']]['name']}. +{last['xp']} xp")
        else:
            st.error(f"❌ Not quite — the correct hat was {hats_module.HATS[q['hat']]['name']}. {last['xp']} xp")
        st.markdown(f"<div class='sh-soft'>{q['explanation']}</div>", unsafe_allow_html=True)
        if st.button("Next ➡️", type="primary", use_container_width=True):
            if pz["idx"] + 1 >= PUZZLE_QUESTIONS_PER_ROUND:
                _goto("puzzle_results")
            else:
                pz["idx"] += 1
                pz["q"] = hats_module.random_puzzle_question(level, exclude_ids=pz["exclude"])
                pz["q_start"] = time.time()
                st.session_state[answered_key] = False
                st.rerun()


def render_puzzle_results():
    pz = st.session_state.get("puzzle", {"log": [], "score": 0})
    st.markdown("<div class='sh-title'>🧩 Round recap</div>", unsafe_allow_html=True)
    if pz.get("left_early"):
        st.warning(f"You left this round early — a {PUZZLE_LEAVE_PENALTY} xp penalty was applied.")
    st.markdown(f"<div class='sh-card'>Total this round: <b>{pz['score']} xp</b></div>", unsafe_allow_html=True)
    for i, item in enumerate(pz["log"]):
        q = item["question"]
        icon = "✅" if item["correct"] else "❌"
        if item["correct"]:
            result_text = "your answer was right"
        elif item.get("chosen") is None:
            result_text = "time ran out — no answer"
        else:
            result_text = "you answered " + hats_module.HATS[item["chosen"]]["name"]
        st.markdown(
            f"<div class='sh-card'>{icon} <i>“{q['text']}”</i><br>"
            f"Correct hat: <b>{hats_module.HATS[q['hat']]['name']}</b> "
            f"({result_text})"
            f"<div class='sh-soft'>{q['explanation']}</div></div>",
            unsafe_allow_html=True,
        )
    c1, c2 = st.columns(2)
    if c1.button("🔁 Play again", type="primary", use_container_width=True):
        del st.session_state["puzzle"]
        for k in list(st.session_state.keys()):
            if k.startswith("answered_"):
                del st.session_state[k]
        _goto("puzzle")
    if c2.button("🏠 Home", use_container_width=True):
        del st.session_state["puzzle"]
        _goto("home")


# =========================================================== DASHBOARD ====
def render_dashboard():
    st.markdown("<div class='sh-title'>🏆 Leaderboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='sh-soft'>Weekly ranking · individual players and teams shown separately.</div>",
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 👤 Individual mode")
        rows = db.leaderboard_individual()
        if not rows:
            st.write("No individual-mode scores yet.")
        for i, r in enumerate(rows, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            st.markdown(f"<div class='sh-card'>{medal} <b>{r['display_name']}</b> — {r['xp']} xp "
                        f"<span class='sh-pill'>{r['level'].title()}</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("#### 👥 Teams")
        rows = db.leaderboard_teams()
        if not rows:
            st.write("No team scores yet.")
        for i, r in enumerate(rows, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            team_row = db.get_team_by_id(r["team_id"])
            members = db.get_team_members(team_row["team_key"]) if team_row else []
            member_names = ", ".join(m["display_name"] for m in members) or "no active members"
            st.markdown(f"<div class='sh-card'>{medal} <b>{r['display_name']}</b> "
                        f"<span class='sh-pill'>ID {r['team_id']}</span> — {r['xp']} xp"
                        f"<div class='sh-soft'>👤 {member_names}</div></div>", unsafe_allow_html=True)

    if st.button("🏠 Back to home", use_container_width=True):
        _goto("home")
