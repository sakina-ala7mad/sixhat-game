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

from core import database as db
from ui import styles, screens

st.set_page_config(page_title="Six Hats Arena", page_icon="🎩", layout="centered")

db.init_db()

# ------------------------------------------------------------- session ----
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "screen" not in st.session_state:
    st.session_state.screen = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "team_key" not in st.session_state:
    st.session_state.team_key = None

styles.inject(st.session_state.theme)

# --------------------------------------------------------------- topbar ----
top_l, top_r = st.columns([4, 1])
with top_r:
    dark = st.toggle("🌙 Dark", value=(st.session_state.theme == "dark"), key="theme_toggle")
    st.session_state.theme = "dark" if dark else "light"

# Live screens get a fast heartbeat so teammates see each other instantly
# without anyone hitting refresh. Static screens don't need it.
LIVE_SCREENS = {"lobby"}
if st.session_state.screen in LIVE_SCREENS:
    st_autorefresh(interval=1500, key="heartbeat")

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
if st.session_state.user:
    with st.sidebar:
        st.markdown(f"**{st.session_state.user['display_name']}**")
        if st.button("❓ How to play"):
            st.session_state["_return_screen"] = st.session_state.screen
            st.session_state.screen = "tutorial_reopen"
            st.rerun()
        if st.button("🚪 Log out"):
            st.session_state.user = None
            st.session_state.screen = "login"
            st.rerun()
