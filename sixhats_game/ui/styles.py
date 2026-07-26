"""
ui/styles.py
------------
One CSS injector, two palettes, matching the same cute/vibrant/bouncy visual
language as the "Six Thinking Hats" tutorial widget (Baloo 2 for headings,
Quicksand for body text, flat "pop" card shadows, bouncy buttons, playful
hover wiggles).

The golden rule that fixes the "white on white / black on black" bug still
holds: EVERY text color is pulled from a CSS variable that flips with the
theme, and we set that variable on `html` so nothing can silently inherit
the browser/OS default instead of ours.
"""

import streamlit as st

LIGHT = {
    "--bg": "#EAF6FF",                     # same sky-blue as the tutorial
    "--bg-card": "#FFFFFF",
    "--text": "#22314B",                   # "ink"
    "--text-soft": "#4A5A78",              # "ink-soft"
    "--accent": "#4EA8FF",                 # blue hat
    "--accent-2": "#FFC93C",               # yellow hat
    "--accent-pop": "#FF5C5C",             # red hat, used for playful pops/hearts
    "--border": "rgba(34,49,75,0.10)",
    "--shadow": "0 6px 0 rgba(0,0,0,0.08)",       # flat "pop" shadow, not blurred glass
    "--shadow-soft": "0 10px 22px rgba(34,49,75,0.10)",
}

DARK = {
    "--bg": "#161E30",                     # deep playful navy, not harsh black
    "--bg-card": "#212B44",
    "--text": "#F3F6FF",
    "--text-soft": "#B9C4DE",
    "--accent": "#6FBBFF",
    "--accent-2": "#FFD75E",
    "--accent-pop": "#FF7A7A",
    "--border": "rgba(255,255,255,0.10)",
    "--shadow": "0 6px 0 rgba(0,0,0,0.35)",
    "--shadow-soft": "0 10px 26px rgba(0,0,0,0.45)",
}


def inject(theme: str):
    palette = DARK if theme == "dark" else LIGHT
    vars_css = "\n".join(f"{k}: {v};" for k, v in palette.items())

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700;800&family=Quicksand:wght@500;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
            {vars_css}
            background: var(--bg) !important;
            color: var(--text) !important;
            font-family: 'Quicksand', sans-serif !important;
        }}

        /* Force every generic text-bearing element to the theme text color,
           this is what prevents "white text on white background" bugs */
        p, span, div, label, li,
        [data-testid="stMarkdownContainer"], [data-testid="stMetricValue"],
        [data-testid="stMetricLabel"], .stRadio label, .stCheckbox label,
        .stTextInput label, .stSelectbox label, .stTextArea label {{
            color: var(--text) !important;
            font-family: 'Quicksand', sans-serif;
        }}

        /* Headings get the same bouncy display font as the tutorial page */
        h1, h2, h3, h4, h5, h6, .sh-title, .sh-display {{
            font-family: 'Baloo 2', sans-serif !important;
            color: var(--text) !important;
        }}

        [data-testid="stSidebar"] {{
            background: var(--bg-card) !important;
            border-right: 1px solid var(--border);
        }}

        /* ---------- cute "pop" cards, with a gentle bounce-in on render ---------- */
        @keyframes sh-pop-in {{
            from {{ transform: scale(0.94) translateY(8px); opacity: 0; }}
            to   {{ transform: scale(1) translateY(0); opacity: 1; }}
        }}

        .sh-card {{
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: 20px;
            padding: 1.1rem 1.3rem;
            box-shadow: var(--shadow);
            margin-bottom: 0.9rem;
            animation: sh-pop-in 0.4s cubic-bezier(.34,1.56,.64,1) both;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .sh-card:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-soft);
        }}

        .sh-title {{
            font-weight: 800;
            font-size: 1.5rem;
            background: linear-gradient(90deg, var(--accent), var(--accent-pop));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent !important;
            margin-bottom: 0.2rem;
        }}

        .sh-soft {{ color: var(--text-soft) !important; font-size: 0.92rem; }}

        .sh-pill {{
            display: inline-block;
            padding: 0.25rem 0.9rem;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--accent), var(--accent-2));
            color: white !important;
            font-weight: 700;
            font-size: 0.8rem;
            box-shadow: var(--shadow);
        }}

        .sh-timer {{
            font-size: 2.3rem;
            font-family: 'Baloo 2', sans-serif;
            font-weight: 800;
            text-align: center;
            color: var(--accent-pop) !important;
            font-variant-numeric: tabular-nums;
            animation: sh-tick 1s ease-in-out infinite;
        }}
        @keyframes sh-tick {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}

        /* ---------- face avatars: playful hover wiggle ---------- */
        .sh-face-wrap {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.35rem;
            padding: 0.4rem;
        }}

        .sh-face {{
            width: 68px;
            height: 68px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            box-shadow: var(--shadow);
            border: 3px solid rgba(0,0,0,0.12);
            transition: transform 0.2s cubic-bezier(.34,1.56,.64,1), box-shadow 0.2s ease;
            animation: sh-pop-in 0.5s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .sh-face:hover {{ transform: translateY(-4px) rotate(-6deg) scale(1.06); }}

        .sh-face-name {{
            font-size: 0.78rem;
            font-weight: 700;
            color: var(--text) !important;
            max-width: 78px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: center;
        }}

        /* ---------- bouncy, poppy buttons (same feel as the tutorial's CTA) ---------- */
        .stButton>button {{
            border-radius: 16px !important;
            font-weight: 700 !important;
            font-family: 'Quicksand', sans-serif !important;
            border: none !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
        }}
        .stButton>button:hover {{ transform: translateY(-3px); }}
        .stButton>button:active {{ transform: translateY(1px); }}

        button[kind="primary"], [data-testid="stBaseButton-primary"] {{
            background: var(--accent) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 5px 0 rgba(0,0,0,0.30) !important;
            box-shadow: 0 5px 0 color-mix(in srgb, var(--accent) 55%, black) !important;
        }}
        button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
            filter: brightness(1.05);
        }}
        button[kind="primary"]:active, [data-testid="stBaseButton-primary"]:active {{
            box-shadow: 0 2px 0 rgba(0,0,0,0.30) !important;
            box-shadow: 0 2px 0 color-mix(in srgb, var(--accent) 55%, black) !important;
        }}

        button[kind="secondary"], [data-testid="stBaseButton-secondary"] {{
            background: var(--bg-card) !important;
            color: var(--text) !important;
            border: 2px solid var(--accent) !important;
            box-shadow: 0 4px 0 var(--border) !important;
        }}
        button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {{
            background: var(--accent) !important;
            color: #ffffff !important;
        }}
        button[kind="secondary"]:active, [data-testid="stBaseButton-secondary"]:active {{
            box-shadow: 0 1px 0 var(--border) !important;
        }}

        /* Start/Create actions -> green. Leave actions -> red. */
        .st-key-start_solo_btn button, .st-key-create_team_btn button,
        .st-key-start_round_btn button, .st-key-ready_to_play_btn button {{
            background: #3FBE78 !important;
            border: none !important;
            color: #ffffff !important;
            box-shadow: 0 5px 0 #2C8F59 !important;
        }}
        .st-key-start_solo_btn button:active, .st-key-create_team_btn button:active,
        .st-key-start_round_btn button:active {{
            box-shadow: 0 2px 0 #2C8F59 !important;
        }}

        .st-key-leave_team_btn button, .st-key-leave_round_btn button,
        .st-key-leave_lobby_btn button {{
            background: #FF5C5C !important;
            border: none !important;
            color: #ffffff !important;
            box-shadow: 0 5px 0 #B23A3A !important;
        }}
        .st-key-leave_team_btn button:active, .st-key-leave_round_btn button:active,
        .st-key-leave_lobby_btn button:active {{
            box-shadow: 0 2px 0 #B23A3A !important;
        }}

        .sh-section {{
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: 18px;
            padding: 0.9rem 1.1rem 0.6rem;
            margin-bottom: 1rem;
        }}
        .sh-section-label {{
            font-family: 'Baloo 2', sans-serif;
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--text-soft) !important;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}

        /* hat-color answer buttons get a little extra wobble on hover, like
           the hats in the tutorial rack */
        .sh-hatbtn button {{
            font-size: 1.6rem !important;
            padding: 0.7rem 0 !important;
        }}
        .sh-hatbtn:hover {{ transform: translateY(-2px) rotate(-2deg); }}
        .sh-hatbtn {{ transition: transform 0.15s cubic-bezier(.34,1.56,.64,1); }}

        [data-testid="stProgress"] > div > div {{
            background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
        }}

        /* a small bouncing emoji helper, e.g. the 🎩 on the login/home hero */
        .sh-bounce {{
            display: inline-block;
            animation: sh-bounce 1.6s ease-in-out infinite;
        }}
        @keyframes sh-bounce {{
            0%, 100% {{ transform: translateY(0) rotate(0deg); }}
            50% {{ transform: translateY(-6px) rotate(-8deg); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
