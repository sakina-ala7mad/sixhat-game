"""
core/hats.py
------------
Loads the hardcoded dataset (data/scenarios.json) and provides the
random hat-assignment algorithm.

Hat assignment rules (per spec):
- Assignment is always random -- the host never hand-picks who gets which hat.
- No player ever gets more than one hat in the same round.
- With exactly 6 active players: all 6 hats are used, one each.
- With 2-5 active players: a random subset of hats (same size as the
  player count) is activated for that round; the rest simply don't appear.
  (The host may optionally pre-select which hats to make eligible for that
  subset -- see `pick_random_hats(eligible=...)` -- but if they don't,
  all 6 are eligible and the subset is fully random.)
"""

import json
import random
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"

with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _DATA = json.load(f)

HATS = _DATA["hats"]  # dict: color -> {name, focus, description, example, color_hex, icon}
HAT_ORDER = ["white", "red", "black", "yellow", "green", "blue"]
PUZZLE_BANK = _DATA["puzzle_bank"]
SCENARIO_BANK = _DATA["scenario_bank"]


def pick_random_hats(n: int, eligible: list[str] | None = None) -> list[str]:
    """Return `n` distinct random hat colors out of the eligible pool."""
    pool = eligible if eligible else HAT_ORDER
    n = max(1, min(n, len(pool)))
    return random.sample(pool, n)


def assign_hats_to_players(player_keys: list[str], eligible: list[str] | None = None) -> dict:
    """Randomly assigns one distinct hat to each player. Returns {name_key: hat_color}."""
    hats = pick_random_hats(len(player_keys), eligible=eligible)
    shuffled_players = player_keys[:]
    random.shuffle(shuffled_players)
    return {p: h for p, h in zip(shuffled_players, hats)}


def random_puzzle_question(level: str, exclude_ids: set | None = None) -> dict:
    exclude_ids = exclude_ids or set()
    pool = [q for q in PUZZLE_BANK[level] if q["id"] not in exclude_ids]
    if not pool:
        pool = PUZZLE_BANK[level]
    return random.choice(pool)


def random_scenario(level: str) -> dict:
    return random.choice(SCENARIO_BANK[level])


def get_scenario_by_id(level: str, scenario_id: str) -> dict:
    for s in SCENARIO_BANK[level]:
        if s["id"] == scenario_id:
            return s
    return SCENARIO_BANK[level][0]
