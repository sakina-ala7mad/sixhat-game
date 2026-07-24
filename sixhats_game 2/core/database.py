"""
core/database.py
-----------------
Single source of truth for all persisted game state.

Why SQLite:
- Zero extra infra to run locally or on Streamlit Community Cloud.
- Every "screen" in the app just re-reads this DB on every rerun/autorefresh,
  which is what makes the game feel "live" across multiple browser tabs
  without a real websocket server.

IMPORTANT (read the README "Persistence" section):
Streamlit Community Cloud's filesystem is ephemeral on redeploy/restart.
For a real production rollout, point DB_PATH at a mounted volume or swap
this module for a hosted Postgres/Supabase connection -- the function
signatures below are the only thing the rest of the app depends on, so
that swap does not touch any UI code.
"""

import sqlite3
import time
import uuid
import random
import string
import threading
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "game.db"
_lock = threading.Lock()  # SQLite + Streamlit's multi-session threads -> serialize writes


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                name_key        TEXT PRIMARY KEY,      -- lowercased, for case-insensitive uniqueness
                display_name    TEXT NOT NULL,
                password        TEXT NOT NULL,
                total_xp        INTEGER NOT NULL DEFAULT 0,   -- all-time, all modes
                individual_xp   INTEGER NOT NULL DEFAULT 0,   -- all-time, individual-mode only
                weekly_xp       INTEGER NOT NULL DEFAULT 0,   -- resets weekly for the leaderboard
                level           TEXT NOT NULL DEFAULT 'easy',
                seen_tutorial   INTEGER NOT NULL DEFAULT 0,
                current_team    TEXT,                   -- team_key or NULL
                last_seen       REAL NOT NULL DEFAULT 0,
                created_at      REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teams (
                team_key        TEXT PRIMARY KEY,   -- lowercased
                team_id         TEXT UNIQUE NOT NULL,  -- short shareable join code
                display_name    TEXT NOT NULL,
                password        TEXT NOT NULL,
                total_xp        INTEGER NOT NULL DEFAULT 0,
                weekly_xp       INTEGER NOT NULL DEFAULT 0,
                created_at      REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS team_members (
                team_key   TEXT NOT NULL,
                name_key   TEXT NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1,
                joined_at  REAL NOT NULL,
                PRIMARY KEY (team_key, name_key)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                mode            TEXT NOT NULL,     -- 'puzzle' | 'scenario'
                scope           TEXT NOT NULL,     -- 'individual' | 'team'
                team_key        TEXT,
                level           TEXT NOT NULL,     -- easy|medium|hard
                status          TEXT NOT NULL,     -- lobby|active|finished
                scenario_id     TEXT,
                active_hats     TEXT,              -- json list, team scenario mode only
                host_name       TEXT,
                round_seconds   INTEGER NOT NULL DEFAULT 120,
                round_started_at REAL,
                paid            INTEGER NOT NULL DEFAULT 0,
                created_at      REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_players (
                session_id      TEXT NOT NULL,
                name_key        TEXT NOT NULL,
                display_name    TEXT NOT NULL,
                hat_color       TEXT,
                submitted       INTEGER NOT NULL DEFAULT 0,
                answer          TEXT,
                is_correct      INTEGER,
                correctness_note TEXT,
                creativity_score INTEGER DEFAULT 0,
                speed_xp        INTEGER DEFAULT 0,
                base_xp         INTEGER DEFAULT 0,
                first_submit    INTEGER DEFAULT 0,
                submitted_at    REAL,
                left_game       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (session_id, name_key)
            );
            """
        )


# ---------------------------------------------------------------- users ----
def name_key(name: str) -> str:
    return name.strip().lower()


def get_user(name: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE name_key = ?", (name_key(name),)
        ).fetchone()


def create_or_login_user(name: str, password: str):
    """Returns (user_row, error_message). If the name exists, verifies password
    (same name = same account, case-insensitive). If it doesn't exist, creates it."""
    key = name_key(name)
    if not key:
        return None, "Please enter a name."
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM users WHERE name_key=?", (key,)).fetchone()
        if existing:
            if existing["password"] != password:
                return None, "This name already exists. Wrong password — use another name or the correct password."
            conn.execute("UPDATE users SET last_seen=? WHERE name_key=?", (time.time(), key))
            return conn.execute("SELECT * FROM users WHERE name_key=?", (key,)).fetchone(), None
        conn.execute(
            "INSERT INTO users (name_key, display_name, password, created_at, last_seen) VALUES (?,?,?,?,?)",
            (key, name.strip(), password, time.time(), time.time()),
        )
        return conn.execute("SELECT * FROM users WHERE name_key=?", (key,)).fetchone(), None


def mark_tutorial_seen(name: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET seen_tutorial=1 WHERE name_key=?", (name_key(name),))


def touch_user(name: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_seen=? WHERE name_key=?", (time.time(), name_key(name)))


def set_user_team(name: str, team_key: str | None):
    with get_conn() as conn:
        conn.execute("UPDATE users SET current_team=? WHERE name_key=?", (team_key, name_key(name)))


# ---------------------------------------------------------------- teams ----
def _gen_team_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_team(team_name: str, password: str, host_name: str):
    key = name_key(team_name)
    if not key:
        return None, "Please enter a team name."
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM teams WHERE team_key=?", (key,)).fetchone()
        if existing:
            return None, "This team name already exists, use another name."
        user = conn.execute("SELECT current_team FROM users WHERE name_key=?", (name_key(host_name),)).fetchone()
        if user and user["current_team"]:
            return None, "You are already in a team. Leave it before creating a new one."
        team_id = _gen_team_id()
        while conn.execute("SELECT 1 FROM teams WHERE team_id=?", (team_id,)).fetchone():
            team_id = _gen_team_id()
        conn.execute(
            "INSERT INTO teams (team_key, team_id, display_name, password, created_at) VALUES (?,?,?,?,?)",
            (key, team_id, team_name.strip(), password, time.time()),
        )
        conn.execute(
            "INSERT INTO team_members (team_key, name_key, active, joined_at) VALUES (?,?,1,?)",
            (key, name_key(host_name), time.time()),
        )
        conn.execute("UPDATE users SET current_team=? WHERE name_key=?", (key, name_key(host_name)))
        return conn.execute("SELECT * FROM teams WHERE team_key=?", (key,)).fetchone(), None


def list_teams():
    with get_conn() as conn:
        teams = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()
        out = []
        for t in teams:
            members = conn.execute(
                "SELECT name_key FROM team_members WHERE team_key=? AND active=1", (t["team_key"],)
            ).fetchall()
            out.append({**dict(t), "member_count": len(members)})
        return out


def get_team(team_key: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM teams WHERE team_key=?", (team_key,)).fetchone()


def get_team_by_id(team_id: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM teams WHERE team_id=?", (team_id,)).fetchone()


def get_team_members(team_key: str, active_only=True):
    with get_conn() as conn:
        q = "SELECT tm.*, u.display_name, u.total_xp FROM team_members tm JOIN users u ON u.name_key=tm.name_key WHERE tm.team_key=?"
        if active_only:
            q += " AND tm.active=1"
        return conn.execute(q, (team_key,)).fetchall()


def join_team(team_key: str, password: str, user_name: str):
    with get_conn() as conn:
        team = conn.execute("SELECT * FROM teams WHERE team_key=?", (team_key,)).fetchone()
        if not team:
            return False, "Team not found."
        if team["password"] != password:
            return False, "Incorrect team password."
        user = conn.execute("SELECT current_team FROM users WHERE name_key=?", (name_key(user_name),)).fetchone()
        if user and user["current_team"] and user["current_team"] != team_key:
            return False, "You are already in another team. Leave it first."
        members = conn.execute(
            "SELECT name_key FROM team_members WHERE team_key=? AND active=1", (team_key,)
        ).fetchall()
        if len(members) >= 6 and user_name.strip().lower() not in [m["name_key"] for m in members]:
            return False, "This team is full. Please join another team or create one."
        conn.execute(
            """INSERT INTO team_members (team_key, name_key, active, joined_at) VALUES (?,?,1,?)
               ON CONFLICT(team_key, name_key) DO UPDATE SET active=1""",
            (team_key, name_key(user_name), time.time()),
        )
        conn.execute("UPDATE users SET current_team=? WHERE name_key=?", (team_key, name_key(user_name)))
        return True, None


def leave_team(team_key: str, user_name: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE team_members SET active=0 WHERE team_key=? AND name_key=?",
            (team_key, name_key(user_name)),
        )
        conn.execute("UPDATE users SET current_team=NULL WHERE name_key=?", (name_key(user_name),))


def active_member_count(team_key: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM team_members WHERE team_key=? AND active=1", (team_key,)
        ).fetchone()
        return row["c"]


def add_team_xp(team_key: str, amount: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE teams SET total_xp = total_xp + ?, weekly_xp = weekly_xp + ? WHERE team_key=?",
            (amount, amount, team_key),
        )


def add_user_xp(user_name: str, amount: int, individual: bool):
    with get_conn() as conn:
        if individual:
            conn.execute(
                "UPDATE users SET total_xp = total_xp + ?, individual_xp = individual_xp + ?, weekly_xp = weekly_xp + ? WHERE name_key=?",
                (amount, amount, amount, name_key(user_name)),
            )
        else:
            conn.execute(
                "UPDATE users SET total_xp = total_xp + ?, weekly_xp = weekly_xp + ? WHERE name_key=?",
                (amount, amount, name_key(user_name)),
            )


# ------------------------------------------------------------ leaderboard --
def leaderboard_individual(limit=20):
    """Ranks players by XP earned specifically in Individual mode."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT display_name, individual_xp AS xp, level FROM users "
            "WHERE individual_xp > 0 ORDER BY individual_xp DESC LIMIT ?",
            (limit,),
        ).fetchall()


def leaderboard_teams(limit=20):
    with get_conn() as conn:
        return conn.execute(
            "SELECT display_name, total_xp AS xp, weekly_xp, team_id FROM teams "
            "WHERE total_xp > 0 ORDER BY total_xp DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ------------------------------------------------------------- sessions ----
def create_session(mode, scope, level, team_key=None, host_name=None, round_seconds=120):
    sid = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions (session_id, mode, scope, team_key, level, status,
               host_name, round_seconds, created_at)
               VALUES (?,?,?,?,?, 'lobby', ?, ?, ?)""",
            (sid, mode, scope, team_key, level, host_name, round_seconds, time.time()),
        )
    return sid


def get_session(session_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()


def get_lobby_session_for_team(team_key):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE team_key=? AND status IN ('lobby','active') ORDER BY created_at DESC LIMIT 1",
            (team_key,),
        ).fetchone()


def add_player_to_session(session_id, user_name, display_name, hat_color=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO session_players (session_id, name_key, display_name, hat_color)
               VALUES (?,?,?,?)""",
            (session_id, name_key(user_name), display_name, hat_color),
        )


def get_session_players(session_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM session_players WHERE session_id=? ORDER BY hat_color", (session_id,)
        ).fetchall()


def set_session_hats(session_id, hats_map: dict):
    """hats_map: {name_key: hat_color}"""
    with get_conn() as conn:
        for nk, hat in hats_map.items():
            conn.execute(
                "UPDATE session_players SET hat_color=? WHERE session_id=? AND name_key=?",
                (hat, session_id, nk),
            )


def start_session(session_id, scenario_id, active_hats_json):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status='active', scenario_id=?, active_hats=?, round_started_at=? WHERE session_id=?",
            (scenario_id, active_hats_json, time.time(), session_id),
        )


def reassign_host(session_id, new_host_name):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET host_name=? WHERE session_id=?", (new_host_name, session_id))


def player_leave_session(session_id, user_name):
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_players SET left_game=1 WHERE session_id=? AND name_key=?",
            (session_id, name_key(user_name)),
        )


def submit_answer(session_id, user_name, answer, is_correct, correctness_note, creativity_score, base_xp, speed_xp, first_submit):
    with get_conn() as conn:
        conn.execute(
            """UPDATE session_players SET submitted=1, answer=?, is_correct=?, correctness_note=?,
               creativity_score=?, base_xp=?, speed_xp=?, first_submit=?, submitted_at=?
               WHERE session_id=? AND name_key=?""",
            (answer, int(is_correct) if is_correct is not None else None, correctness_note,
             creativity_score, base_xp, speed_xp, int(first_submit), time.time(),
             session_id, name_key(user_name)),
        )


def finish_session(session_id):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET status='finished' WHERE session_id=?", (session_id,))


def try_mark_session_paid(session_id) -> bool:
    """Atomically flips paid 0->1 and returns True only for the caller that
    won the race. Every browser tab/session polls this same DB, so payout
    logic must be guarded here (not in per-client st.session_state) or a
    team round would get paid once per open tab instead of once total."""
    with _lock:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE sessions SET paid=1 WHERE session_id=? AND paid=0", (session_id,)
            )
            return cur.rowcount == 1


def all_submitted_or_left(session_id) -> bool:
    players = get_session_players(session_id)
    if not players:
        return False
    return all(p["submitted"] or p["left_game"] for p in players)


def any_active_players(session_id) -> bool:
    players = get_session_players(session_id)
    return any(not p["left_game"] for p in players)
