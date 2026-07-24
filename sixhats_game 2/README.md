# 🎩 Six Hats Arena

A mobile-friendly Streamlit game that teaches Edward de Bono's **Six Thinking Hats**
through two game modes (quick-fire **Puzzle** and discussion-style **Scenario**),
playable **solo** or as a **team**, with XP, levels, and a live leaderboard.
Content is currently a hardcoded dataset themed around HR-services + general
corporate life — designed to be swapped for your ML-generated scenario engine later.

---

## 1. Project structure

```
sixhats_game/
├── app.py                     # Entry point: theme, autorefresh heartbeat, routing
├── requirements.txt
├── .streamlit/config.toml     # Base Streamlit theme (our own CSS overrides on top)
├── data/
│   └── scenarios.json         # Hardcoded dataset: hats, puzzle bank, scenario bank
├── core/                      # Backend: pure Python, no Streamlit imports
│   ├── database.py            # SQLite persistence (users, teams, sessions, XP)
│   ├── hats.py                # Loads dataset + random hat-assignment algorithm
│   ├── xp_engine.py           # XP/leveling formulas (single source of truth)
│   ├── evaluator.py           # Answer scoring (placeholder for your future ML model)
│   └── game_engine.py         # Round lifecycle: start, submit, host migration, end
└── ui/                        # Frontend: Streamlit rendering only
    ├── styles.py               # Dark/light CSS (guaranteed text contrast)
    ├── components.py           # Avatar faces, colored hat buttons, timer, XP bar
    └── screens.py               # One render_xxx() per screen
```

**Why this split:** `core/` is the "backend" — deterministic Python you could unit-test
or later expose over an API with zero UI dependency. `ui/` is the "frontend" — it only
reads from `core/` and never touches the database directly. Since the whole thing runs
on Streamlit, everything is Python (that's Streamlit's whole model) — but the
separation still keeps game rules, persistence, and rendering independently editable.

---

## 2. Run it locally

```bash
cd sixhats_game
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

---

## 3. Publish a public link (Streamlit Community Cloud — free)

1. Push this folder to a **GitHub repo** (public or private).
2. Go to **share.streamlit.io** → "New app" → pick the repo/branch → set
   **Main file path** to `app.py` → Deploy.
3. Streamlit gives you a public URL like `https://your-app.streamlit.app` —
   that's the link to send your employees.

### ⚠️ Persistence caveat (important)
Streamlit Community Cloud's filesystem is **ephemeral**: it resets on redeploys and
can reset on app restarts/sleep. That means the local `data/game.db` SQLite file
(scores, teams, accounts) **can be wiped** in that environment even though it works
perfectly for local testing or a self-hosted server with a persistent disk.

For a corporate rollout where scores must survive indefinitely, do one of:
- **Self-host** (a small VM/container with a real disk) — SQLite works as-is.
- **Swap the storage backend** — `core/database.py` is the only file that talks to
  the DB. Point it at Postgres/Supabase/Turso instead of SQLite and nothing in
  `ui/` or `core/game_engine.py` needs to change, since they only call functions
  like `db.get_user()`, `db.add_user_xp()`, etc.
- Mount a persistent volume in your hosting provider and set `DB_PATH` to it.

---

## 4. How the game works (mapped to your spec)

**Login** — case-insensitive name + password. Same name = same account regardless
of case; a taken name shows "this name already exists, use another name" if the
password doesn't match. Tutorial auto-shows once on first login (skippable), and a
"❓ How to play" button in the sidebar reopens it anytime.

**Team creation/joining** — creating a team auto-joins you as host and generates a
shareable 6-character Team ID. Max 6 members; a full team shows the exact popup text
you specified. A player can only be in one team at a time.

**Puzzle mode** — 5 questions/round, 15s timer each, colored hat **icon buttons**
(no dropdown). After each answer, the correct hat + a short explanation is shown
immediately; a full recap screen appears at the end of the round.

**Scenario mode** — host creates the game and can start anytime without a full team.
Hats are assigned **randomly** (never by the host, never a duplicate) and stay hidden
until the round starts. The waiting-room screen and the active-round screen are the
same view, so nothing jarring happens at kickoff. A shared 2-minute timer counts down
for everyone. The round only ends when every still-present player has submitted (or
left) — it never pauses for a dropout, and a leaving host is instantly replaced by
another active player. After the round: a **debrief screen** groups the situation +
all 6 hats' answers side-by-side (the actual learning artifact), each with a
model/reference answer and an on-topic/creativity verdict. A "Play again with the
same team" button generates a fresh scenario immediately.

**XP & leveling** — implemented exactly to your numbers in `core/xp_engine.py`:
- Levels: easy 0–500, medium 500–1500, hard 1500–3000 XP.
- Puzzle: +10/20/30 XP correct (easy/med/hard) + 2 XP per second left, **−5 XP** wrong.
- Scenario: baseline round XP (100/150/200) goes to the **whole team**; speed bonus
  (2 XP/sec left), creativity XP, and the first-submitter's +15 XP bonus all go to
  **that player individually** — matching "baseline is shared, speed/creativity is not."

**Dashboard** — two separate ranked lists in one screen: Individual-mode players and
Teams, exactly as requested, with a weekly XP column.

**Dark/light mode** — `ui/styles.py` injects one CSS block whose colors come entirely
from theme variables, forcing every text element to the correct color for that theme
so nothing renders white-on-white or black-on-black in either mode.

---

## 5. "Live" multiplayer without a websocket server

Streamlit has no native push/websocket model, so this app uses **shared-state
polling**: every game action writes to the SQLite DB, and the lobby/round screen uses
`streamlit-autorefresh` to re-read that DB roughly every 1.5s. That's what makes a
teammate joining, submitting, or leaving show up on the host's screen without anyone
manually refreshing. For a small internal team-building tool this is more than fast
enough; a true production version at large scale would swap this for websockets or
Server-Sent Events.

---

## 6. The ML swap-in point

`core/evaluator.py` currently scores scenario answers with a simple **keyword-match
placeholder** (on-topic check + a 0–10 creativity score from length/keyword hits), and
`data/scenarios.json` is a **hardcoded** dataset. Both are intentionally isolated so
your Six-Hats multi-agent decision system (the one in your Kaggle/GitHub capstone) can
plug in later:

- Replace `evaluate_scenario_answer(hat, answer_text, scenario)` in `evaluator.py`
  with a call to your model — keep the same `(is_on_topic, creativity_score,
  correction_note)` return shape and nothing else in the app needs to change.
- Replace the static `data/scenarios.json` scenario_bank with model-generated
  scenarios at the same schema (`situation`, `keywords` per hat, `reference_answers`
  per hat) to go from hardcoded to dynamically generated content.

---

## 7. Known simplifications (by design, for this MVP)

- **Puzzle-mode team play**: each teammate plays their own quick-fire round
  independently (not synced turn-by-turn); their XP is credited to the whole team.
  A fully synchronized team puzzle mode is a natural next step.
- **"Teammate is typing…"** indicator was intentionally left out of this pass to keep
  polling load low — the live face/submitted-count already gives a strong "the round
  is active" signal.
- **First-submit bonus** is resolved on a best-effort basis against the shared DB;
  under true simultaneous submissions (sub-second race) there's no server-side
  distributed lock, which is a non-issue at normal human typing speed but worth
  knowing about before scaling to hundreds of concurrent teams.
- **Host-selected hat subsets** for 2–5 player teams are currently fully random
  (as you specified) rather than host-toggleable; the toggle described in your
  design notes can be added as checkboxes on the lobby screen for the host.

---

## 8. Dataset snapshot

`data/scenarios.json` currently ships:
- 6 hats with name/description/example/icon/color.
- 36 puzzle sentences (12 per difficulty level), each with the correct hat + a
  one-line "why."
- 9 full scenarios (3 per difficulty level) themed around HR-services/general
  corporate situations — coffee machines and dress codes at the easy end, AI hiring
  bias and layoff leaks at the hard end — each with keyword sets and reference
  answers for all six hats.

Add more by appending entries to `puzzle_bank` / `scenario_bank` in that same JSON
shape — no code changes required.
