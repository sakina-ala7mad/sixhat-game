"""
ui/tutorial_content.py
-----------------------
Self-contained HTML/CSS/JS for the "Six Thinking Hats" interactive tutorial
(clickable hat rack + flip cards + how-to-play steps). Rendered inside an
iframe via st.components.v1.html() in ui/screens.py's render_tutorial().

This is intentionally a fully self-styled mini-page (its own fonts, colors,
animations) rather than reusing the app's dark/light theme variables --
components.html() renders in an isolated iframe, so the app's CSS can't
reach inside it anyway, and this tutorial's own bright, colorful look is
meant to be a fun standalone moment regardless of which app theme is active.

The original design included its own "Let's play!" CTA button wired to a JS
alert(); that was removed here because it can't drive the app's actual
Streamlit navigation/session_state. The real "Got it, let's play! / Skip /
Close" buttons are rendered by Streamlit itself, directly below this
component, in render_tutorial().
"""

TUTORIAL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Six Thinking Hats — Let's Play!</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700;800&family=Quicksand:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --sky:#EAF6FF;
    --ink:#22314B;
    --ink-soft:#4A5A78;
    --card:#FFFFFF;

    --white-hat:#F4F1EA; --white-line:#C9C3B4; --white-dark:#8A8574;
    --red-hat:#FF5C5C;   --red-dark:#B32E2E;
    --black-hat:#3A3A42; --black-dark:#1C1C22;
    --yellow-hat:#FFC93C;--yellow-dark:#A6740B;
    --green-hat:#4CD787; --green-dark:#1D8A52;
    --blue-hat:#4EA8FF;  --blue-dark:#1A5FA6;
  }

  *{ box-sizing:border-box; }
  body{
    margin:0;
    background:var(--sky);
    font-family:'Quicksand', sans-serif;
    color:var(--ink);
    overflow-x:hidden;
  }
  h1,h2,h3,.display{ font-family:'Baloo 2', sans-serif; }

  .wrap{ max-width:1000px; margin:0 auto; padding:32px 20px 60px; }

  /* ---------- HERO ---------- */
  .hero{ text-align:center; padding:20px 0 10px; }
  .hero h1{
    font-size:clamp(32px,6vw,52px);
    font-weight:800;
    margin:0 0 6px;
    color:var(--ink);
  }
  .hero h1 span{ color:var(--red-dark); }
  .hero p{
    font-size:clamp(16px,2.6vw,20px);
    font-weight:600;
    color:var(--ink-soft);
    margin:0 0 28px;
  }

  .rack{
    display:flex;
    justify-content:center;
    gap:18px;
    flex-wrap:wrap;
    margin-bottom:10px;
  }

  /* ---------- HAT SHAPE ---------- */
  .hat{
    width:78px;
    cursor:pointer;
    animation:drop 0.7s cubic-bezier(.34,1.56,.64,1) both;
    transition:transform .15s ease;
  }
  .hat:hover{ transform:translateY(-8px) rotate(-4deg); }
  .hat:active{ transform:translateY(-2px) scale(0.96); }

  .hat-top{
    height:44px;
    border-radius:40px 40px 6px 6px;
    position:relative;
    border:3px solid rgba(0,0,0,0.12);
    border-bottom:none;
  }
  .hat-brim{
    height:14px;
    border-radius:14px;
    margin-top:-4px;
    border:3px solid rgba(0,0,0,0.12);
  }
  .face{
    position:absolute; top:16px; left:0; right:0;
    display:flex; justify-content:center; gap:12px;
  }
  .eye{ width:7px; height:7px; border-radius:50%; background:var(--ink); }

  .hat0 .hat-top,.hat0 .hat-brim{ background:var(--white-hat); }
  .hat1 .hat-top,.hat1 .hat-brim{ background:var(--red-hat); }
  .hat2 .hat-top,.hat2 .hat-brim{ background:var(--black-hat); }
  .hat3 .hat-top,.hat3 .hat-brim{ background:var(--yellow-hat); }
  .hat4 .hat-top,.hat4 .hat-brim{ background:var(--green-hat); }
  .hat5 .hat-top,.hat5 .hat-brim{ background:var(--blue-hat); }
  .hat2 .eye{ background:#fff; }

  .hat:nth-child(1){ animation-delay:.05s; }
  .hat:nth-child(2){ animation-delay:.15s; }
  .hat:nth-child(3){ animation-delay:.25s; }
  .hat:nth-child(4){ animation-delay:.35s; }
  .hat:nth-child(5){ animation-delay:.45s; }
  .hat:nth-child(6){ animation-delay:.55s; }

  @keyframes drop{
    from{ transform:translateY(-60px) rotate(-15deg); opacity:0; }
    to{ transform:translateY(0) rotate(0); opacity:1; }
  }

  .hint{
    text-align:center;
    font-weight:600;
    color:var(--ink-soft);
    font-size:14px;
    margin-bottom:40px;
  }

  /* ---------- CARDS GRID ---------- */
  .grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
    gap:18px;
    margin-bottom:40px;
  }

  .flip-outer{ perspective:1200px; height:170px; }
  .flip-inner{
    position:relative; width:100%; height:100%;
    transform-style:preserve-3d;
    transition:transform .55s cubic-bezier(.34,1.56,.64,1);
    cursor:pointer;
  }
  .flip-outer.flipped .flip-inner{ transform:rotateY(180deg); }

  .face-card{
    position:absolute; inset:0;
    border-radius:20px;
    backface-visibility:hidden;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    gap:10px;
    padding:16px;
    text-align:center;
    box-shadow:0 6px 0 rgba(0,0,0,0.08);
  }
  .face-card .name{ font-family:'Baloo 2'; font-weight:700; font-size:20px; }
  .face-card .job{ font-weight:600; font-size:13px; opacity:.85; }

  .back-card{
    transform:rotateY(180deg);
    background:var(--card);
    border:3px solid var(--line);
    justify-content:flex-start;
    padding-top:20px;
  }
  .back-card .q{
    font-family:'Baloo 2';
    font-weight:700;
    font-size:17px;
    margin:0;
  }
  .back-card .a{
    font-weight:600;
    font-size:14px;
    color:var(--ink-soft);
    margin:0;
    line-height:1.4;
  }
  .tap-tag{
    position:absolute; bottom:10px; right:14px;
    font-size:11px; font-weight:700;
    opacity:.55;
  }

  .c0{ background:var(--white-hat); color:var(--white-dark); }
  .c1{ background:var(--red-hat); color:#fff; }
  .c2{ background:var(--black-hat); color:#fff; }
  .c3{ background:var(--yellow-hat); color:var(--yellow-dark); }
  .c4{ background:var(--green-hat); color:#fff; }
  .c5{ background:var(--blue-hat); color:#fff; }

  .b0{ --line:var(--white-line); }
  .b1{ --line:var(--red-hat); }
  .b2{ --line:var(--black-hat); }
  .b3{ --line:var(--yellow-hat); }
  .b4{ --line:var(--green-hat); }
  .b5{ --line:var(--blue-hat); }

  .dot{ width:26px; height:26px; border-radius:50%; }
  .dot0{ background:var(--white-line); }
  .dot1{ background:var(--red-hat); }
  .dot2{ background:var(--black-hat); }
  .dot3{ background:var(--yellow-hat); }
  .dot4{ background:var(--green-hat); }
  .dot5{ background:var(--blue-hat); }

  /* ---------- HOW TO PLAY ---------- */
  .how{ text-align:center; }
  .how h2{ font-size:28px; font-weight:700; margin-bottom:26px; }
  .steps{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:16px;
  }
  .step{
    background:var(--card);
    border-radius:18px;
    padding:22px 14px;
    box-shadow:0 6px 0 rgba(0,0,0,0.06);
  }
  .step .num{
    width:34px; height:34px; margin:0 auto 10px;
    border-radius:50%;
    background:var(--blue-hat);
    color:#fff;
    font-family:'Baloo 2'; font-weight:700;
    display:flex; align-items:center; justify-content:center;
  }
  .step p{ font-weight:700; margin:0; font-size:15px; }

  @media (max-width:480px){
    .hat{ width:56px; }
  }
</style>
</head>
<body>

<div class="wrap">

  <div class="hero">
    <h1>Six Thinking <span>Hats</span> 🎩</h1>
    <p>6 hats. 6 ways to think. Tap a hat to meet it!</p>
    <div class="rack" id="rack"></div>
    <div class="hint">👆 tap a hat above, or flip a card below</div>
  </div>

  <div class="grid" id="grid"></div>

  <div class="how">
    <h2>How to play</h2>
    <div class="steps">
      <div class="step"><div class="num">1</div><p>Pick a hat</p></div>
      <div class="step"><div class="num">2</div><p>Think like that hat</p></div>
      <div class="step"><div class="num">3</div><p>Swap hats and think again!</p></div>
    </div>
  </div>

</div>

<script>
const hats = [
  { name:"White", job:"Facts", q:"What do we know?", a:"White hat looks for facts and numbers only. No feelings, just info!", color:0 },
  { name:"Red", job:"Feelings", q:"How do I feel?", a:"Red hat shares feelings and gut reactions. No need to explain why!", color:1 },
  { name:"Black", job:"Caution", q:"What could go wrong?", a:"Black hat spots problems and risks, so we're extra careful.", color:2 },
  { name:"Yellow", job:"Sunny side", q:"What's good about it?", a:"Yellow hat finds the good stuff and reasons to be hopeful.", color:3 },
  { name:"Green", job:"New ideas", q:"What new idea can we try?", a:"Green hat grows fresh, wild, and fun new ideas.", color:4 },
  { name:"Blue", job:"Big boss", q:"What's our next step?", a:"Blue hat leads the game and decides which hat comes next.", color:5 },
];

const rack = document.getElementById('rack');
const grid = document.getElementById('grid');

hats.forEach((h, i) => {
  const hat = document.createElement('div');
  hat.className = `hat hat${h.color}`;
  hat.innerHTML = `<div class="hat-top"><div class="face"><div class="eye"></div><div class="eye"></div></div></div><div class="hat-brim"></div>`;
  hat.onclick = () => {
    const card = document.getElementById('card' + i);
    card.classList.toggle('flipped');
    card.scrollIntoView({ behavior:'smooth', block:'center' });
  };
  rack.appendChild(hat);

  const outer = document.createElement('div');
  outer.className = 'flip-outer';
  outer.id = 'card' + i;
  outer.innerHTML = `
    <div class="flip-inner">
      <div class="face-card c${h.color}">
        <div class="dot dot${h.color}"></div>
        <div class="name">${h.name} hat</div>
        <div class="job">${h.job}</div>
      </div>
      <div class="face-card back-card b${h.color}">
        <p class="q">${h.q}</p>
        <p class="a">${h.a}</p>
        <span class="tap-tag">tap to flip back</span>
      </div>
    </div>`;
  outer.onclick = () => outer.classList.toggle('flipped');
  grid.appendChild(outer);
});
</script>

</body>
</html>
"""
