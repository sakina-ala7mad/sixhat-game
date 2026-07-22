"""
core/xp_engine.py
------------------
All XP math lives here so the rules are defined exactly once.

Levels (by total XP):
  easy   :   0 -  500
  medium :  500 - 1500
  hard   : 1500 - 3000+

Puzzle mode (per question, scored individually always):
  correct answer base xp : easy=10, medium=20, hard=30
  wrong answer penalty   : -5 xp
  speed bonus            : +2 xp per second left on the clock, only if correct

Scenario mode:
  baseline round xp (whole team, awarded to every active/left member equally):
      easy=100, medium=150, hard=200
  speed bonus   : +2 xp per second left when they submitted (individual)
  creativity xp : the evaluator's 0-10 creativity_score, added as-is (individual)
  first-submit bonus : +15 xp flat to whichever player in the round submits first (individual)
"""

LEVEL_THRESHOLDS = {
    "easy": (0, 500),
    "medium": (500, 1500),
    "hard": (1500, 3000),
}

PUZZLE_BASE_XP = {"easy": 10, "medium": 20, "hard": 30}
PUZZLE_WRONG_PENALTY = -5

SCENARIO_BASELINE_XP = {"easy": 100, "medium": 150, "hard": 200}
FIRST_SUBMIT_BONUS = 15
SPEED_XP_PER_SECOND = 2


def level_for_xp(total_xp: int) -> str:
    if total_xp >= LEVEL_THRESHOLDS["hard"][0]:
        return "hard"
    if total_xp >= LEVEL_THRESHOLDS["medium"][0]:
        return "medium"
    return "easy"


def level_progress(total_xp: int) -> dict:
    """Returns {level, floor, ceiling, into_level, span, pct} for a progress bar."""
    level = level_for_xp(total_xp)
    floor, ceiling = LEVEL_THRESHOLDS[level]
    if level == "hard":
        ceiling = max(ceiling, total_xp)  # hard has no hard cap in the UI bar
    span = max(1, ceiling - floor)
    into_level = min(span, total_xp - floor)
    pct = round(100 * into_level / span)
    return {"level": level, "floor": floor, "ceiling": ceiling, "into_level": into_level, "span": span, "pct": pct}


def puzzle_xp(level: str, is_correct: bool, seconds_left: float) -> int:
    if not is_correct:
        return PUZZLE_WRONG_PENALTY
    base = PUZZLE_BASE_XP[level]
    speed_bonus = int(max(0, seconds_left) * SPEED_XP_PER_SECOND)
    return base + speed_bonus


def scenario_round_baseline(level: str) -> int:
    return SCENARIO_BASELINE_XP[level]


def scenario_individual_bonus(seconds_left: float, creativity_score: int, is_first: bool) -> int:
    speed_bonus = int(max(0, seconds_left) * SPEED_XP_PER_SECOND)
    bonus = speed_bonus + creativity_score
    if is_first:
        bonus += FIRST_SUBMIT_BONUS
    return bonus
