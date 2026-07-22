"""
ui/styles.py
------------
One CSS injector, two palettes. The golden rule that fixes the
"white on white / black on black" bug: EVERY text color is pulled from a
CSS variable that flips with the theme, and we set that variable on `html`
so nothing can silently inherit the browser/OS default instead of ours.
"""

import streamlit as st

LIGHT = {
    "--bg": "#FBF9F6",
    "--bg-card": "rgba(255,255,255,0.75)",
    "--text": "#232323",
    "--text-soft": "#5B5B5B",
    "--accent": "#6C63FF",
    "--accent-2": "#FF8A65",
    "--border": "rgba(0,0,0,0.08)",
    "--shadow": "0 8px 24px rgba(0,0,0,0.08)",
}

DARK = {
    "--bg": "#14151F",
    "--bg-card": "rgba(255,255,255,0.06)",
    "--text": "#F3F3F7",
    "--text-soft": "#B7B8C6",
    "--accent": "#8F87FF",
    "--accent-2": "#FFAB8A",
    "--border": "rgba(255,255,255,0.10)",
    "--shadow": "0 8px 24px rgba(0,0,0,0.35)",
}


def inject(theme: str):
    palette = DARK if theme == "dark" else LIGHT
    vars_css = "\n".join(f"{k}: {v};" for k, v in palette.items())

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
            {vars_css}
            background: var(--bg) !important;
            color: var(--text) !important;
        }}

        /* Force every generic text-bearing element to the theme text color,
           this is what prevents "white text on white background" bugs */
        p, span, div, label, li, h1, h2, h3, h4, h5, h6,
        [data-testid="stMarkdownContainer"], [data-testid="stMetricValue"],
        [data-testid="stMetricLabel"], .stRadio label, .stCheckbox label,
        .stTextInput label, .stSelectbox label, .stTextArea label {{
            color: var(--text) !important;
        }}

        [data-testid="stSidebar"] {{
            background: var(--bg-card) !important;
            border-right: 1px solid var(--border);
        }}

        .sh-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 1.1rem 1.3rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(6px);
            margin-bottom: 0.9rem;
        }}

        .sh-title {{
            font-weight: 800;
            font-size: 1.4rem;
            background: linear-gradient(90deg, var(--accent), var(--accent-2));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent !important;
            margin-bottom: 0.2rem;
        }}

        .sh-soft {{ color: var(--text-soft) !important; font-size: 0.92rem; }}

        .sh-pill {{
            display: inline-block;
            padding: 0.25rem 0.8rem;
            border-radius: 999px;
            background: var(--accent);
            color: white !important;
            font-weight: 700;
            font-size: 0.8rem;
        }}

        .sh-timer {{
            font-size: 2.1rem;
            font-weight: 800;
            text-align: center;
            color: var(--accent-2) !important;
            font-variant-numeric: tabular-nums;
        }}

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
            border: 2px solid var(--border);
            transition: all 0.35s ease;
        }}

        .sh-face-name {{
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text) !important;
            max-width: 78px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: center;
        }}

        .stButton>button {{
            border-radius: 16px !important;
            font-weight: 700 !important;
            border: none !important;
            box-shadow: var(--shadow);
            transition: transform 0.15s ease;
        }}
        .stButton>button:hover {{ transform: translateY(-2px); }}

        .sh-hatbtn button {{
            font-size: 1.6rem !important;
            padding: 0.7rem 0 !important;
        }}

        [data-testid="stProgress"] > div > div {{
            background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
