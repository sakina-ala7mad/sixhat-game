# Six Hats Arena — Fix Changelog

Everything from the QA report is fixed except account/password recovery (explicitly out of scope for v1, per your call). Each item below was verified either with an automated logic test (sqlite smoke tests) or by driving the actual app through Streamlit's `AppTest` harness — not just read-through.

## Crashes / correctness

- **Negative-XP Home-screen crash** — `xp_engine.level_progress()` now clamps the displayed percentage to 0–100 before it reaches `st.progress()`, which previously hard-crashed on any negative value (trivially triggered by a first puzzle question answered wrong). *Verified: `level_progress(-5)` now returns `pct=0` instead of crashing.*
- **Sidebar "Home" bypassing the puzzle leave-penalty + leaving a zombie round** — extracted `leave_puzzle_round_and_clear()` in `ui/screens.py`, now called from `app.py`'s sidebar Home/How-to-play/Log-out handlers. It applies the same leave penalty as the in-round Pause button and always clears the round from `session_state`. *Verified: leaving mid-round via the sidebar now deducts the penalty AND the next round starts fresh at question 1, not resumed mid-timeout.*
- **Team-mode puzzle XP inflating every teammate's personal total** — per-question team-scope XP now goes only to the team's pool (`db.add_team_xp`), not looped over every member's individual `total_xp`. Matches the README's own stated design ("XP is credited to the whole team").
- **Duplicate-tab race in scenario submission** — `db.submit_answer()` is now a conditional `UPDATE ... WHERE submitted=0` returning whether it actually recorded; callers only award XP when it does, so a second racing tab can no longer double-credit XP or overwrite an already-submitted answer. *Verified with a direct two-call race test.*
- **Team/account-creation race** — `create_team` and `create_or_login_user` are now wrapped in the module lock and catch `sqlite3.IntegrityError`, so two people registering/creating the identical name at the same instant get the normal friendly error instead of a raw traceback. *Verified with a duplicate-team-name test.*

## Trust / security

- **Cross-account session leakage on shared devices** — logging out now clears every game-related `session_state` key (team, session, puzzle progress, pending actions, etc.), not just the user object, so the next login on the same browser/tab starts completely clean.
- **URL-based session hijack** — added a per-login random `session_token` (stored on the user row, put in the URL alongside the username). Restoring a session from a URL now requires the token to match; logging out invalidates it. A bookmarked/shared/history URL can no longer silently log someone in as another user. *Verified via the token mint/verify/invalidate cycle.*
- **Team password permanently lost after creation** — it's now shown on the Home screen to current team members, plus a "generate a new password" button if it's ever truly lost.

## Fairness / consistency

- **Ambiguous "Leave" button** — the team scenario lobby's Leave button (which also removed you from the whole team) is now labeled "Leave team" and asks for confirmation, matching the puzzle mode's existing leave-confirmation pattern. The in-round Leave button is unchanged (lighter-weight, as intended).
- **Team-only players invisible on the leaderboard** — the Teams leaderboard now lists each team's active members inline, so a team-only player is visible somewhere by name.

## Accessibility / accommodation

- **No relaxed-timing option** — added a "Give me 50% more time on round timers" toggle on the Home screen (persisted per account), applied to both puzzle question timers and scenario round timers via a new `game_engine.effective_seconds()` helper. *Verified: a relaxed-timing user gets 1.5x the base seconds.*
- **Tiny hat-identity label (0.78rem)** — bumped to 0.92rem; this label is the accessible fallback for colorblind users, so it needed to be legible at a glance.
- **No keyboard/ARIA support in the tutorial and mode-intro carousel** — added `role="button"`/`aria-label`/keyboard (Enter/Space, arrow keys) handling to the hat rack, flip-cards, and carousel rail, which were previously mouse/touch-only.

## Pacing / onboarding

- **Puzzle timer left at a stale "test value" (90s) vs the README's stated 15s** — set to 20s and the stale comment removed.
- **Mode-intro carousel replaying on every single round** — now shown once per mode per account (`seen_puzzle_intro` / `seen_scenario_intro` flags), then skipped automatically on later rounds.
- **No show/hide password toggle, no confirm-password on new accounts** — added both to the login screen; a first-time name now requires the password to be typed twice before an account is created, so a typo can't permanently lock someone out of that display name.

## Reliability on flaky connections / mobile

- **6-second staleness window ejecting players over a normal phone interruption** — raised the default `mark_stale_players_left` window from 6s to 20–25s.
- **No way back in once marked "left"** — added `db.rejoin_session()` plus a "Rejoin round" button shown when a player's own row comes back and finds itself marked `left_game` while the round is still active; also fixed the pre-round "Play with them" join button, which previously couldn't undo a stale `left_game` flag due to `INSERT OR IGNORE` no-op-ing on an existing row.

## Not changed (explicitly out of scope)

- **Account/password recovery** — left as-is per your instruction.

## Heads-up (not a bug I introduced, just noticed while testing)

Streamlit logs a deprecation warning that `st.components.v1.html` (used for the tutorial and mode-intro carousels) will be removed after 2026-06-01 in favor of `st.iframe`. Not urgent, but worth migrating before that date.

---

All of the above were exercised through either direct sqlite-level tests or Streamlit's `AppTest` harness driving the real app (login → account creation → tutorial → puzzle round → wrong/right answers → sidebar leave → fresh round), not just read-through — see the fix descriptions above for what was specifically verified.
