"""
app.py
------
Entry point. Keep this file thin: it only wires up the theme, the
autorefresh "heartbeat" that makes multiplayer feel live, session
bootstrapping, and routing to the right screen in ui/screens.py.

Run locally:    streamlit run app.py
Deploy:         see README.md
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src import database as db
from src import game_engine as ge
from ui import styles
from ui import screens

st.set_page_config(page_title="Six Hats Arena", page_icon="🎩", layout="centered")

db.init_db()
//db.reap_abandoned_teams_throttled()

# ------------------------------------------------------------- session ----
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "screen" not in st.session_state:
    st.session_state.screen = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "team_key" not in st.session_state:
    st.session_state.team_key = None

# ------------------------------------------------- restore after refresh --
if st.session_state.user is None and "u" in st.query_params and "t" in st.query_params:
    candidate_name = st.query_params["u"]
    candidate_token = st.query_params["t"]
    # The token must match this user's CURRENT login, not just be non-empty --
    # otherwise anyone who ever saw this URL (browser history, a bookmark, a
    # screenshot, a shared link) could resume this account with no password.
    if db.verify_session_token(candidate_name, candidate_token):
        urow = db.get_user(candidate_name)
        st.session_state.user = {"name_key": urow["name_key"], "display_name": urow["display_name"]}
        st.session_state.session_token = candidate_token
        if urow["current_team"]:
            st.session_state.team_key = urow["current_team"]
        st.session_state.screen = st.query_params.get("screen", "home")
        if "session_id" in st.query_params:
            st.session_state.session_id = st.query_params["session_id"]
    else:
        st.query_params.clear()

styles.inject(st.session_state.theme)

if st.session_state.user:
    db.touch_user(st.session_state.user["display_name"])

# --------------------------------------------------------------- topbar ----
if st.session_state.screen != "login":
    top_l, top_r = st.columns([4, 1])
    with top_r:
        dark = st.toggle("🌙 Dark", value=(st.session_state.theme == "dark"), key="theme_toggle")
        st.session_state.theme = "dark" if dark else "light"

# Live screens get a fast heartbeat so teammates see each other instantly
# without anyone hitting refresh. Static screens don't need it.
LIVE_SCREENS = {"lobby", "puzzle"}
if st.session_state.screen in LIVE_SCREENS:
    st_autorefresh(interval=1000, key="heartbeat")

# ----------------------------------------------------------- guard rails --
if st.session_state.screen != "login" and not st.session_state.user:
    st.session_state.screen = "login"

# ------------------------------------------------------------- routing ----
screen = st.session_state.screen

if screen == "login":
    screens.render_login()
elif screen == "tutorial":
    screens.render_tutorial(first_time=True)
elif screen == "tutorial_reopen":
    screens.render_tutorial(first_time=False)
elif screen == "home":
    screens.render_home()
elif screen == "mode_intro":
    screens.render_mode_intro()
elif screen == "lobby":
    screens.render_lobby()
elif screen == "puzzle":
    screens.render_puzzle()
elif screen == "puzzle_results":
    screens.render_puzzle_results()
elif screen == "dashboard":
    screens.render_dashboard()
else:
    st.session_state.screen = "home"
    st.rerun()

# ------------------------------------------------------------- sidebar ----
def _leave_current_round_if_any():
    """If the player is mid scenario-round OR mid puzzle-round, navigating
    away by any of the sidebar buttons below counts as leaving it -- same
    consequence as the in-round Leave/Pause button. This used to only cover
    scenario mode's 'lobby' screen: a puzzle player who used the sidebar
    instead of the in-round Pause button skipped the leave penalty entirely,
    AND left a stale, already-timed-out round sitting in session_state that
    would silently reappear (already time-expired) the next time they
    started a puzzle round."""
    if st.session_state.screen == "lobby" and st.session_state.get("session_id") and st.session_state.user:
        ge.player_leaves(st.session_state.session_id, st.session_state.user["display_name"])
    if st.session_state.screen == "puzzle" and st.session_state.get("puzzle"):
        screens.leave_puzzle_round_and_clear(apply_penalty=True)
    elif st.session_state.screen == "puzzle_results" and st.session_state.get("puzzle"):
        screens.leave_puzzle_round_and_clear(apply_penalty=False)


# Session-state keys that describe "what game/round am I in right now" --
# these must never survive a logout, or the next person to log in on the
# same browser/device (a shared office laptop, a kiosk) can silently inherit
# the previous user's team, in-progress round, or half-finished puzzle.
_GAME_STATE_KEYS = [
    "team_key", "session_id", "puzzle", "level", "scope", "pending_action",
    "home_scope", "home_mode", "home_level", "home_mode_i", "home_level_i",
    "confirm_leave_puzzle", "confirm_leave_team", "_return_screen", "session_token",
]


def _clear_game_session_state():
    for k in _GAME_STATE_KEYS:
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if k.startswith("answered_") or k.startswith("answer_") or k.startswith("jt_pw_"):
            del st.session_state[k]


if st.session_state.user:
    with st.sidebar:
        st.markdown(f"**{st.session_state.user['display_name']}**")
        if st.button("🏠 Home", key="sidebar_home_btn", use_container_width=True):
            _leave_current_round_if_any()
            st.session_state.screen = "home"
            st.rerun()
        if st.button("❓ How to play"):
            _leave_current_round_if_any()
            st.session_state["_return_screen"] = "home"
            st.session_state.screen = "tutorial_reopen"
            st.rerun()
        if st.button("🚪 Log out"):
            _leave_current_round_if_any()
            db.clear_session_token(st.session_state.user["display_name"])
            st.session_state.user = None
            _clear_game_session_state()
            st.session_state.screen = "login"
            st.query_params.clear()
            st.rerun()

# --------------------------------------------------- keep URL in sync -----
if st.session_state.user:
    st.query_params["u"] = st.session_state.user["name_key"]
    st.query_params["t"] = st.session_state.get("session_token", "")
    st.query_params["screen"] = st.session_state.screen
    if st.session_state.get("session_id") and st.session_state.screen == "lobby":
        st.query_params["session_id"] = st.session_state.session_id
    elif "session_id" in st.query_params:
        del st.query_params["session_id"]
else:
    st.query_params.clear()
