"""
ui/mode_intro_content.py
-------------------------
Self-contained HTML/CSS/JS for the "how this round works" pop-out carousel
shown right after the player clicks Start/Create Game, before the round
actually begins. Rendered via st.components.v1.html() from
ui/screens.py's render_mode_intro().

Same visual language as the rest of the app + the main tutorial (Baloo 2 /
Quicksand fonts, pop-shadow cards, hat-color accents), but built as a
left/right scrollable (swipe or arrow-button) step-by-step carousel, each
step paired with a tiny mocked-up preview of the real in-game screen
element it's explaining (the timer, the hat buttons, the answer box, etc.)
so a first-time player knows exactly what they're about to see.

Two variants are exported, pre-built at import time:
    PUZZLE_INTRO_HTML
    SCENARIO_INTRO_HTML
"""


def _carousel_html(accent: str, accent_dark: str, steps: list[dict]) -> str:
    slides = ""
    for i, s in enumerate(steps, start=1):
        slides += f"""
        <div class="slide">
          <div class="step-badge">Step {i} of {len(steps)}</div>
          <div class="mockup">{s['mockup']}</div>
          <div class="slide-title">{s['icon']} {s['title']}</div>
          <p class="slide-desc">{s['desc']}</p>
        </div>"""

    dots = "".join(f'<span class="dot"></span>' for _ in steps)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Quicksand:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{ --accent:{accent}; --accent-dark:{accent_dark}; }}
  *{{ box-sizing:border-box; }}
  body{{ margin:0; font-family:'Quicksand',sans-serif; background:transparent; }}
  .wrap{{ padding:8px 2px 2px; }}
  .rail-wrap{{ position:relative; }}

  .rail{{
     display:flex; gap:16px; overflow-x:auto; scroll-snap-type:x mandatory;
     padding:8px 38px 18px; -webkit-overflow-scrolling:touch; scrollbar-width:thin;
  }}
  .rail::-webkit-scrollbar{{ height:6px; }}
  .rail::-webkit-scrollbar-thumb{{ background:var(--accent); border-radius:10px; }}

  .slide{{
     flex:0 0 80%; max-width:290px; scroll-snap-align:center;
     background:#ffffff; border-radius:22px; padding:18px 18px 20px;
     box-shadow:0 6px 0 rgba(0,0,0,0.08); border:2px solid rgba(0,0,0,0.06);
     display:flex; flex-direction:column; align-items:center; text-align:center;
     animation: sh-pop .4s cubic-bezier(.34,1.56,.64,1) both;
  }}
  @keyframes sh-pop{{
     from{{ opacity:0; transform:scale(.92) translateY(10px); }}
     to{{ opacity:1; transform:scale(1) translateY(0); }}
  }}

  .step-badge{{
     font-family:'Baloo 2',sans-serif; font-weight:700; font-size:12px;
     color:#fff; background:var(--accent); padding:4px 13px; border-radius:999px; margin-bottom:12px;
  }}
  .mockup{{ width:100%; min-height:54px; display:flex; align-items:center; justify-content:center; margin-bottom:14px; }}
  .slide-title{{ font-family:'Baloo 2',sans-serif; font-weight:700; font-size:18px; color:#22314B; margin-bottom:6px; }}
  .slide-desc{{ font-size:13.5px; font-weight:600; color:#5B6478; line-height:1.5; margin:0; }}

  .nav-btn{{
     position:absolute; top:42%; transform:translateY(-50%);
     width:36px; height:36px; border-radius:50%; border:none;
     background:var(--accent); color:#fff; font-size:16px; font-weight:800;
     cursor:pointer; box-shadow:0 4px 0 var(--accent-dark); z-index:2;
  }}
  .nav-btn:active{{ box-shadow:0 1px 0 var(--accent-dark); transform:translateY(-46%); }}
  .nav-left{{ left:-6px; }}
  .nav-right{{ right:-6px; }}

  .dots{{ display:flex; justify-content:center; gap:6px; margin-top:2px; }}
  .dot{{ width:7px; height:7px; border-radius:50%; background:rgba(34,49,75,0.18); transition:all .2s ease; }}
  .dot.active{{ background:var(--accent); width:18px; border-radius:5px; }}

  /* ---- tiny reusable mockup building blocks ---- */
  .m-card{{ background:#F6F8FC; border:1.5px dashed rgba(34,49,75,0.20); border-radius:14px;
            padding:10px 12px; font-size:12px; font-weight:700; color:#4A5A78; width:100%; }}
  .m-timer{{ font-family:'Baloo 2',sans-serif; font-weight:800; font-size:24px; color:var(--accent); }}
  .m-hats{{ display:flex; justify-content:center; gap:7px; }}
  .m-hat{{ width:22px; height:22px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 0 1.5px rgba(0,0,0,0.14); }}
  .m-bar-track{{ background:#E7EAF2; border-radius:999px; height:11px; overflow:hidden; width:100%; }}
  .m-bar-fill{{ height:100%; border-radius:999px; background:linear-gradient(90deg,#4EA8FF,#FFC93C); }}

  @media (max-width:420px){{ .slide{{ flex-basis:86%; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="rail-wrap">
    <button class="nav-btn nav-left" onclick="document.getElementById('rail').scrollBy({{left:-300,behavior:'smooth'}})">‹</button>
    <button class="nav-btn nav-right" onclick="document.getElementById('rail').scrollBy({{left:300,behavior:'smooth'}})">›</button>
    <div class="rail" id="rail">
      {slides}
    </div>
  </div>
  <div class="dots" id="dots">{dots}</div>
</div>
<script>
  const rail = document.getElementById('rail');
  const dots = Array.from(document.querySelectorAll('.dot'));
  function updateDots(){{
    const slides = Array.from(document.querySelectorAll('.slide'));
    const railBox = rail.getBoundingClientRect();
    let closest = 0, min = Infinity;
    slides.forEach((s,i)=>{{
      const d = Math.abs(s.getBoundingClientRect().left - railBox.left - 20);
      if(d < min){{ min = d; closest = i; }}
    }});
    dots.forEach((d,i)=> d.classList.toggle('active', i===closest));
  }}
  rail.addEventListener('scroll', ()=> requestAnimationFrame(updateDots));
  updateDots();
</script>
</body>
</html>
"""


_PUZZLE_STEPS = [
    {
        "icon": "🧩", "title": "Read the sentence",
        "desc": "Each round shows a short workplace sentence. Your job: figure out "
                "which of the six hats is \u201ctalking.\u201d",
        "mockup": '<div class="m-card">\u201cI have a bad feeling about this reorg\u2026\u201d</div>',
    },
    {
        "icon": "⏱️", "title": "Watch the clock",
        "desc": "Every question has a countdown. The faster you answer correctly, "
                "the bigger your speed bonus.",
        "mockup": '<div class="m-timer">⏱ 02:47</div>',
    },
    {
        "icon": "🎨", "title": "Tap the matching hat",
        "desc": "Six colored buttons, one tap. No dropdowns \u2014 just pick the hat "
                "color you think fits.",
        "mockup": ('<div class="m-hats">'
                   '<div class="m-hat" style="background:#F4F1EA"></div>'
                   '<div class="m-hat" style="background:#FF5C5C"></div>'
                   '<div class="m-hat" style="background:#3A3A42"></div>'
                   '<div class="m-hat" style="background:#FFC93C"></div>'
                   '<div class="m-hat" style="background:#4CD787"></div>'
                   '<div class="m-hat" style="background:#4EA8FF"></div>'
                   '</div>'),
    },
    {
        "icon": "✅", "title": "Instant feedback",
        "desc": "Right after you answer you'll see the correct hat and a one-line "
                "reason why \u2014 nothing left unresolved.",
        "mockup": '<div class="m-card">✅ Correct! It was the Red Hat.</div>',
    },
    {
        "icon": "⭐", "title": "Level up",
        "desc": "Every correct answer adds XP to your bar. Five questions per round, "
                "then a full recap of what you got right.",
        "mockup": '<div class="m-bar-track"><div class="m-bar-fill" style="width:64%;"></div></div>',
    },
]

_SCENARIO_STEPS = [
    {
        "icon": "🗂️", "title": "Everyone sees the same situation",
        "desc": "A real workplace scenario appears for the whole team \u2014 everyone "
                "reads the exact same setup.",
        "mockup": '<div class="m-card">\u201cHR just installed a coffee machine that needs a PIN nobody has\u2026\u201d</div>',
    },
    {
        "icon": "🎩", "title": "You get ONE random hat",
        "desc": "Hats are assigned randomly and stay hidden until the round starts \u2014 "
                "no two teammates get the same hat.",
        "mockup": '<div class="m-card" style="background:#FBE0DF; border-style:solid; border-color:#FF5C5C; color:#7A2320;">🔴 Red Hat \u2014 Emotional</div>',
    },
    {
        "icon": "⏱️", "title": "One shared timer",
        "desc": "The whole team races the same clock \u2014 everyone's countdown is "
                "in sync, down to the second.",
        "mockup": '<div class="m-timer">⏱ 01:52</div>',
    },
    {
        "icon": "✍️", "title": "Write your answer",
        "desc": "Respond from your hat's point of view in up to 300 characters \u2014 "
                "short, focused, to the point.",
        "mockup": '<div class="m-card">142 / 300 characters</div>',
    },
    {
        "icon": "🔍", "title": "Compare in the debrief",
        "desc": "Once everyone's submitted, all six hats' answers are shown side-by-side "
                "with the model take \u2014 that's where the real learning happens.",
        "mockup": ('<div class="m-hats">'
                   '<div class="m-hat" style="background:#FF5C5C"></div>'
                   '<div class="m-hat" style="background:#4EA8FF"></div>'
                   '<div class="m-hat" style="background:#FFC93C"></div>'
                   '<div class="m-hat" style="background:#4CD787"></div>'
                   '</div>'),
    },
]

PUZZLE_INTRO_HTML = _carousel_html("#4EA8FF", "#1A5FA6", _PUZZLE_STEPS)
SCENARIO_INTRO_HTML = _carousel_html("#FF5C5C", "#B23A3A", _SCENARIO_STEPS)
