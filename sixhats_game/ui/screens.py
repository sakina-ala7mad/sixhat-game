"""
ui/screens.py
-------------
One render_xxx() function per screen. app.py just calls whichever one
matches st.session_state.screen. All game state is re-read from the DB
every single call (via core.database / core.game_engine) so this works
correctly across multiple browser tabs polling in parallel.
"""

import json
import time
import streamlit as st

from src import database as db
from src import hats as hats_module
from src import xp_engine
from src import evaluator
from src import game_engine as ge
from ui import components as comp

PUZZLE_QUESTIONS_PER_ROUND = 5
PUZZLE_SECONDS_PER_QUESTION = 15
SCENARIO_ROUND_SECONDS = 120


def _goto(screen, **extra):
    st.session_state.screen = screen
    for k, v in extra.items():
        st.session_state[k] = v
    st.rerun()


# ============================================================== LOGIN =====
def render_login():
    st.markdown("<div class='sh-title' style='font-size:2rem;'>🎩 Six Hats Arena</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sh-soft'>Sharpen how your team thinks, decides, and communicates — "
        "one hat at a time.</div>", unsafe_allow_html=True,
    )
    st.write("")
    with st.container():
        st.markdown("<div class='sh-card'>", unsafe_allow_html=True)
        name = st.text_input("Your name", key="login_name", placeholder="e.g. Sara Adel")
        password = st.text_input("Password", key="login_pw", type="password",
                                  help="First time using this name creates your account. "
                                       "Log back in later with the same name + password.")
        if st.button("Enter the game", type="primary", use_container_width=True):
            if not name.strip():
                st.warning("Please enter a name.")
            else:
                user, err = db.create_or_login_user(name, password)
                if err:
                    st.error(err)
                else:
                    st.session_state.user = {"name_key": user["name_key"], "display_name": user["display_name"]}
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
    st.markdown(
        "<div class='sh-soft'>Edward de Bono's Six Thinking Hats is a way for a group to look at "
        "one problem from six deliberately different angles — one at a time — instead of everyone "
        "arguing from a different angle at once.</div>", unsafe_allow_html=True,
    )
    st.write("")
    for hat in hats_module.HAT_ORDER:
        comp.hat_role_card(hat)

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


# ================================================================ HOME =====
def render_home():
    user = st.session_state.user
    urow = db.get_user(user["display_name"])

    st.markdown(f"<div class='sh-title'>Welcome back, {user['display_name']} 👋</div>", unsafe_allow_html=True)
    comp.render_xp_bar(urow["total_xp"])
    st.write("")

    scope = st.radio("Play as", ["Individual", "Team"], horizontal=True, key="home_scope")

    if scope == "Team":
        _render_team_picker()
        team_key = st.session_state.get("team_key")
        if not team_key:
            return
        team = db.get_team(team_key)
        st.markdown(
            f"<div class='sh-card'>Your team: <b>{team['display_name']}</b> "
            f"&nbsp; <span class='sh-pill'>ID: {team['team_id']}</span> "
            f"&nbsp; Team XP: <b>{team['total_xp']}</b></div>",
            unsafe_allow_html=True,
        )
        existing = db.get_lobby_session_for_team(team_key)
        if existing and existing["status"] in ("lobby", "active"):
            st.info("Your team already has a game open — jump back in.")
            if st.button("Rejoin game", type="primary", use_container_width=True):
                _goto("lobby", session_id=existing["session_id"])
            return

        mode = st.radio("Mode", ["Scenario (team discussion)", "Puzzle (quick-fire)"], key="home_mode")
        level = st.select_slider("Difficulty", ["easy", "medium", "hard"], key="home_level")

        # Any team member can create the game; whoever creates it becomes host.
        if st.button("🚀 Create game (become host)", type="primary", use_container_width=True):
            m = "scenario" if mode.startswith("Scenario") else "puzzle"
            if m == "puzzle":
                # Puzzle mode has no lobby/host concept -- each teammate just
                # plays their own quick-fire round and the XP flows to the team.
                _goto("puzzle", level=level, scope="team")
            else:
                sid = ge.start_team_lobby(team_key, user["display_name"], m, level,
                                           round_seconds=SCENARIO_ROUND_SECONDS)
                _goto("lobby", session_id=sid)

        if st.button("Leave team", use_container_width=True):
            db.leave_team(team_key, user["display_name"])
            st.session_state.team_key = None
            st.rerun()

    else:
        mode = st.radio("Mode", ["Scenario (solo)", "Puzzle (quick-fire)"], key="home_mode_i")
        level = st.select_slider("Difficulty", ["easy", "medium", "hard"], key="home_level_i")
        if st.button("▶️ Start", type="primary", use_container_width=True):
            m = "scenario" if mode.startswith("Scenario") else "puzzle"
            if m == "puzzle":
                _goto("puzzle", level=level, scope="individual")
            else:
                # Individual mode has no lobby wait -- start instantly with a
                # hat already assigned, per the "instant start" design note.
                sid = ge.start_individual_session(user["display_name"], user["display_name"], "scenario", level,
                                                    round_seconds=SCENARIO_ROUND_SECONDS)
                ge.begin_round(sid, "scenario", level)
                _goto("lobby", session_id=sid)

    st.write("")
    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("🏆 Dashboard", use_container_width=True):
        _goto("dashboard")
    if c2.button("❓ How to play again", use_container_width=True):
        st.session_state["_return_screen"] = "home"
        _goto("tutorial_reopen")


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
        ge.sync_team_session_players(session_id, session["team_key"])
        team = db.get_team(session["team_key"])
        st.markdown(f"<div class='sh-title'>🎭 {team['display_name']} — Scenario Round</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='sh-title'>🎭 Solo Scenario Round</div>", unsafe_allow_html=True)

    players = db.get_session_players(session_id)
    active_players = [p for p in players if not p["left_game"]]
    is_host = db.name_key(session["host_name"] or "") == user["name_key"]

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
        if is_host:
            if st.button("▶️ Start round", type="primary", use_container_width=True):
                ge.begin_round(session_id, "scenario", session["level"])
                st.rerun()
        else:
            st.info("Waiting for the host to start the round…")
            st.button("🔄 Refresh", use_container_width=True)
        if st.button("🚪 Leave", use_container_width=True):
            ge.player_leaves(session_id, user["display_name"])
            if is_team:
                db.leave_team(session["team_key"], user["display_name"])
                st.session_state.team_key = None
            _goto("home")
        return

    # ----- active or finished -----
    scenario = hats_module.get_scenario_by_id(session["level"], session["scenario_id"])
    my_row = next((p for p in players if p["name_key"] == user["name_key"]), None)
    my_hat = my_row["hat_color"] if my_row else None
    try:
        active_hats = json.loads(session["active_hats"]) if session["active_hats"] else []
    except Exception:
        active_hats = []

    st.markdown(f"<div class='sh-card'><b>Situation — {scenario['title']}</b><br>{scenario['situation']}</div>",
                unsafe_allow_html=True)

    left = ge.seconds_left(session)
    tcol, _ = st.columns([1, 3])
    with tcol:
        comp.render_timer(left)

    comp.render_faces_row(
        [{"name": p["display_name"], "hat_color": p["hat_color"], "submitted": bool(p["submitted"])}
         for p in players if not p["left_game"]],
        hats_active=active_hats or None,
    )

    if session["status"] == "finished":
        _render_scenario_results(session, scenario, players, is_team)
        return

    if ge.round_expired(session):
        ge.maybe_finish_session(session_id)
        st.rerun()

    st.write("")
    if my_hat:
        comp.hat_role_card(my_hat)
        already = bool(my_row["submitted"])
        answer = st.text_area("Your response from this hat's point of view", max_chars=300, disabled=already,
                               key=f"answer_{session_id}", placeholder="Up to 300 characters…")
        if not already:
            if st.button("✅ Submit answer", type="primary", use_container_width=True):
                secs_left = ge.seconds_left(session)
                is_first = ge.is_first_submitter(session_id)
                on_topic, creativity, correction = evaluator.evaluate_scenario_answer(my_hat, answer, scenario)
                bonus = xp_engine.scenario_individual_bonus(secs_left, creativity, is_first)
                db.submit_answer(session_id, user["display_name"], answer, on_topic, correction,
                                  creativity, base_xp=0, speed_xp=bonus, first_submit=is_first)
                db.add_user_xp(user["display_name"], bonus, individual=not is_team)
                ge.maybe_finish_session(session_id)
                st.rerun()
        else:
            st.success("Answer submitted — waiting for the rest of the team to finish…")
    else:
        st.warning("No hat assigned to you for this round (more players than active hats, or you joined late).")

    if st.button("🚪 Leave round", use_container_width=True):
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

    st.markdown("### 🧠 Debrief — every hat, side by side")
    st.markdown("<div class='sh-soft'>This is the real value of Six Hats: compare how each lens saw the same "
                "situation.</div>", unsafe_allow_html=True)
    for hat in hats_module.HAT_ORDER:
        meta = hats_module.HATS[hat]
        p = next((pp for pp in players if pp["hat_color"] == hat), None)
        with st.container():
            st.markdown(f"<div class='sh-card'><b>{meta['icon']} {meta['name']} — {p['display_name'] if p else 'unassigned'}</b>",
                        unsafe_allow_html=True)
            if p and p["answer"]:
                verdict = "✅ On-topic" if p["is_correct"] else "🟡 Off-topic / partial"
                st.markdown(f"<div class='sh-soft'>{verdict} · creativity {p['creativity_score']}/10 "
                            f"· +{p['speed_xp']} xp</div>", unsafe_allow_html=True)
                st.write(f"**Their answer:** {p['answer']}")
            elif p:
                st.write("_No answer submitted this round._")
            st.markdown(f"<div class='sh-soft'>**Reference {meta['name']} take:** "
                        f"{scenario['reference_answers'].get(hat, '')}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if is_team and c1.button("🔁 Play again with same team", type="primary", use_container_width=True):
        team_key = session["team_key"]
        sid = ge.start_team_lobby(team_key, st.session_state.user["display_name"], "scenario", session["level"],
                                   round_seconds=SCENARIO_ROUND_SECONDS)
        _goto("lobby", session_id=sid)
    if c2.button("🏠 Back to home", use_container_width=True):
        _goto("home")


# ============================================================= PUZZLE =====
def render_puzzle():
    user = st.session_state.user
    level = st.session_state.get("level", "easy")
    scope = st.session_state.get("scope", "individual")

    if "puzzle" not in st.session_state:
        st.session_state.puzzle = {
            "idx": 0, "score": 0, "log": [],
            "q": hats_module.random_puzzle_question(level),
            "q_start": time.time(),
            "exclude": set(),
        }
    pz = st.session_state.puzzle

    st.markdown(f"<div class='sh-title'>🧩 Puzzle Mode — {level.title()}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sh-soft'>Question {pz['idx'] + 1} of {PUZZLE_QUESTIONS_PER_ROUND} "
                f"&nbsp;·&nbsp; scope: {scope}</div>", unsafe_allow_html=True)

    elapsed = time.time() - pz["q_start"]
    left = max(0, PUZZLE_SECONDS_PER_QUESTION - elapsed)
    comp.render_timer(left)

    q = pz["q"]
    st.markdown(f"<div class='sh-card'>“{q['text']}”</div>", unsafe_allow_html=True)

    answered_key = f"answered_{pz['idx']}"
    if not st.session_state.get(answered_key):
        chosen = comp.render_hat_answer_buttons(f"pz_{pz['idx']}")
        if chosen:
            is_correct, _ = evaluator.evaluate_puzzle_answer(chosen, q["hat"])
            xp = xp_engine.puzzle_xp(level, is_correct, left)
            if scope == "team" and st.session_state.get("team_key"):
                db.add_team_xp(st.session_state.team_key, xp)
                for m in db.get_team_members(st.session_state.team_key):
                    db.add_user_xp(m["display_name"], xp, individual=False)
            else:
                db.add_user_xp(user["display_name"], xp, individual=True)
            pz["score"] += xp
            pz["log"].append({"question": q, "chosen": chosen, "correct": is_correct, "xp": xp})
            pz["exclude"].add(q["id"])
            st.session_state[answered_key] = True
            st.rerun()
    else:
        last = pz["log"][-1]
        if last["correct"]:
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
    st.markdown(f"<div class='sh-card'>Total this round: <b>{pz['score']} xp</b></div>", unsafe_allow_html=True)
    for i, item in enumerate(pz["log"]):
        q = item["question"]
        icon = "✅" if item["correct"] else "❌"
        st.markdown(
            f"<div class='sh-card'>{icon} <i>“{q['text']}”</i><br>"
            f"Correct hat: <b>{hats_module.HATS[q['hat']]['name']}</b> "
            f"({'your answer was right' if item['correct'] else 'you answered ' + hats_module.HATS[item['chosen']]['name']})"
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
            st.markdown(f"<div class='sh-card'>{medal} <b>{r['display_name']}</b> "
                        f"<span class='sh-pill'>ID {r['team_id']}</span> — {r['xp']} xp</div>", unsafe_allow_html=True)

    if st.button("🏠 Back to home", use_container_width=True):
        _goto("home")
