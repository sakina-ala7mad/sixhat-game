"""
core/game_engine.py
--------------------
Thin orchestration layer on top of database.py. Every function here is
safe to call on every Streamlit rerun -- it always re-derives state from
the DB rather than trusting anything cached in session_state, which is
what lets the game "just work" across multiple browsers/tabs when combined
with streamlit-autorefresh polling in app.py.
"""

import json
import time

from src import database as db
from src import hats as hats_module
from src import xp_engine


# ------------------------------------------------------------- creation ---
def start_team_lobby(team_key: str, host_name: str, mode: str, level: str, round_seconds=120):
    """Host creates a new lobby session for their team. Only the host can do this."""
    existing = db.get_lobby_session_for_team(team_key)
    if existing and existing["status"] in ("lobby", "active"):
        return existing["session_id"]
    sid = db.create_session(mode=mode, scope="team", level=level, team_key=team_key,
                             host_name=host_name, round_seconds=round_seconds)
    members = db.get_team_members(team_key)
    for m in members:
        db.add_player_to_session(sid, m["name_key"], m["display_name"])
    return sid


def start_individual_session(user_name: str, display_name: str, mode: str, level: str, round_seconds=120):
    sid = db.create_session(mode=mode, scope="individual", level=level, team_key=None,
                             host_name=user_name, round_seconds=round_seconds)
    db.add_player_to_session(sid, user_name, display_name)
    return sid


def sync_team_session_players(session_id: str, team_key: str):
    """Called every rerun while a team lobby is open, so newly-joined teammates
    show up instantly without the host needing to do anything."""
    members = db.get_team_members(team_key)
    for m in members:
        db.add_player_to_session(session_id, m["name_key"], m["display_name"])


# ------------------------------------------------------------ round start -
def begin_round(session_id: str, mode: str, level: str, eligible_hats=None):
    session = db.get_session(session_id)
    players = [p for p in db.get_session_players(session_id) if not p["left_game"]]
    player_keys = [p["name_key"] for p in players]

    if mode == "scenario":
        scenario = hats_module.random_scenario(level)
        assigned = hats_module.assign_hats_to_players(player_keys, eligible=eligible_hats)
        db.set_session_hats(session_id, assigned)
        db.start_session(session_id, scenario["id"], json.dumps(list(assigned.values())))
    else:  # puzzle mode: no hats assigned, question is chosen per-player on the fly by the UI
        db.start_session(session_id, "", json.dumps([]))


# ------------------------------------------------------------ submission --
def seconds_left(session) -> float:
    if not session["round_started_at"]:
        return session["round_seconds"]
    elapsed = time.time() - session["round_started_at"]
    return max(0.0, session["round_seconds"] - elapsed)


def round_expired(session) -> bool:
    return seconds_left(session) <= 0


def is_first_submitter(session_id: str) -> bool:
    players = db.get_session_players(session_id)
    return not any(p["submitted"] for p in players)

def auto_submit_timeout(session_id: str, scenario: dict, skip_name_key: str | None = None):
    ...


def maybe_finish_session(session_id: str):
    """A round ends when every non-departed player has submitted, or when
    everyone has left. It is never paused for a dropout -- their hat is
    simply skipped/left unanswered and the round continues for the rest."""
    session = db.get_session(session_id)
    if session["status"] != "active":
        return
    players = db.get_session_players(session_id)
    if not players:
        return
    still_playing = [p for p in players if not p["left_game"]]
    if not still_playing:
        db.finish_session(session_id)
        return
    if all(p["submitted"] for p in still_playing):
        db.finish_session(session_id)


def player_leaves(session_id: str, user_name: str):
    session = db.get_session(session_id)
    db.player_leave_session(session_id, user_name)
    # host migration: if the departing player was the host, hand off to
    # the next still-active player so the game is never orphaned.
    if session and session["host_name"] and db.name_key(session["host_name"]) == db.name_key(user_name):
        remaining = [p for p in db.get_session_players(session_id) if not p["left_game"]]
        if remaining:
            db.reassign_host(session_id, remaining[0]["display_name"])
    maybe_finish_session(session_id)


# --------------------------------------------------------------- payouts --
def payout_team_scenario_round(session_id: str, level: str, team_key: str):
    """Baseline round XP goes to every team member who was ever in the round
    (even ones who left mid-round), on top of each player's own speed/creativity
    bonus which was already credited at submit-time."""
    baseline = xp_engine.scenario_round_baseline(level)
    db.add_team_xp(team_key, baseline)
    players = db.get_session_players(session_id)
    for p in players:
        db.add_user_xp(p["display_name"], baseline, individual=False)


def payout_individual_scenario_round(session_id: str, level: str, user_name: str):
    baseline = xp_engine.scenario_round_baseline(level)
    db.add_user_xp(user_name, baseline, individual=True)
