"""
ui/components.py
-----------------
Small, reusable render helpers used across every screen: the colored
"face" avatars for the lobby/active room, hat-color answer buttons
(instead of a dropdown), the countdown timer, and the XP progress bar.
"""

import streamlit as st
from src.hats import HATS
from src import xp_engine

FACE_ON = "😊"
FACE_SUBMITTED = "😄"
FACE_OFF = "💤"


def _dim(hex_color: str) -> str:
    """Return a darker/greyed version of a hat color for 'not joined yet' faces."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    r, g, b = [int(c * 0.35 + 60 * 0.65) for c in (r, g, b)]
    return f"#{r:02x}{g:02x}{b:02x}"


def render_faces_row(players: list, hats_active: list[str] | None = None):
    """players: list of dicts with keys name, hat_color(optional), submitted(bool), joined(bool)"""
    hats_active = hats_active or list(HATS.keys())
    cols = st.columns(len(hats_active) if hats_active else 6)
    joined_by_hat = {p.get("hat_color"): p for p in players if p.get("hat_color")}

    for i, hat in enumerate(hats_active):
        meta = HATS[hat]
        p = joined_by_hat.get(hat)
        with cols[i]:
            if p is None:
                bg = _dim(meta["color_hex"])
                face = FACE_OFF
                name = "— open —"
            elif p.get("submitted"):
                bg = meta["color_hex"]
                face = FACE_SUBMITTED
                name = p["name"]
            else:
                bg = meta["color_hex"]
                face = FACE_ON
                name = p["name"]
            st.markdown(
                f"""
                <div class="sh-face-wrap">
                    <div class="sh-face" style="background:{bg};">{face}</div>
                    <div class="sh-face-name">{name}</div>
                    <div class="sh-face-name" style="opacity:0.7;">{meta['icon']} {meta['name'].replace(' Hat','')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_lobby_slots(member_names: list[str], max_slots=6):
    """Pre-round waiting room: hats are NOT revealed yet. Empty slots are dark/off,
    joined slots turn on (neutral grey glow) with the player's name above them."""
    cols = st.columns(max_slots)
    for i in range(max_slots):
        with cols[i]:
            if i < len(member_names):
                name = member_names[i]
                bg = "#9AA0B4"
                face = FACE_ON
            else:
                name = "— open —"
                bg = "#40424D"
                face = FACE_OFF
            st.markdown(
                f"""
                <div class="sh-face-wrap">
                    <div class="sh-face" style="background:{bg}; opacity:0.9;">{face}</div>
                    <div class="sh-face-name">{name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_hat_answer_buttons(question_key: str, disabled=False):
    """Renders 6 colored hat buttons instead of a dropdown.
    Returns the hat color that was clicked this run, or None."""
    chosen = None
    cols = st.columns(6)
    for i, hat in enumerate(["white", "red", "black", "yellow", "green", "blue"]):
        meta = HATS[hat]
        with cols[i]:
            st.markdown(f"<div class='sh-hatbtn'>", unsafe_allow_html=True)
            label = f"{meta['icon']}\n{meta['name'].replace(' Hat','')}"
            if st.button(label, key=f"{question_key}_{hat}", disabled=disabled, use_container_width=True):
                chosen = hat
            st.markdown("</div>", unsafe_allow_html=True)
    return chosen


def render_timer(seconds_left: float):
    m, s = divmod(int(max(0, seconds_left)), 60)
    st.markdown(f"<div class='sh-timer'>⏱ {m:02d}:{s:02d}</div>", unsafe_allow_html=True)


def render_xp_bar(total_xp: int, label: str = "Your progress"):
    prog = xp_engine.level_progress(total_xp)
    st.markdown(
        f"<div class='sh-soft'>{label} — Level: <b>{prog['level'].title()}</b> "
        f"({total_xp} XP total)</div>",
        unsafe_allow_html=True,
    )
    st.progress(prog["pct"] / 100)


def hat_role_card(hat_color: str):
    meta = HATS[hat_color]
    st.markdown(
        f"""
        <div class="sh-card">
            <div style="font-size:2.2rem;">{meta['icon']}</div>
            <div class="sh-title">{meta['name']} — {meta['focus']}</div>
            <div class="sh-soft">{meta['description']}</div>
            <div class="sh-soft" style="margin-top:0.4rem;"><i>Example: "{meta['example']}"</i></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
