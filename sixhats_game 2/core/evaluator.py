"""
core/evaluator.py
------------------
Answer evaluation. This is intentionally a simple, deterministic keyword-based
placeholder -- the user has an ML model (a Six-Hats multi-agent decision
system, see the referenced Kaggle/GitHub capstone) that will later replace
this module's `evaluate_scenario_answer()` function with a real LLM judgement.

Swap-in contract for the future ML model:
    evaluate_scenario_answer(hat, answer_text, scenario) -> (is_on_topic: bool,
                                                              creativity_score: int 0-10,
                                                              correction_note: str)
Keep that exact signature and the rest of the app (xp_engine, UI) needs no changes.
"""

import re


def evaluate_puzzle_answer(chosen_hat: str, correct_hat: str) -> tuple[bool, str]:
    """Puzzle mode: simple exact match against the hardcoded correct hat."""
    is_correct = chosen_hat == correct_hat
    return is_correct, ""


def _keyword_hits(text: str, keywords: list[str]) -> int:
    text_l = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_l)


def evaluate_scenario_answer(hat: str, answer_text: str, scenario: dict) -> tuple[bool, int, str]:
    """
    Placeholder scoring for free-text scenario-mode answers.

    - is_on_topic: did the answer hit at least one expected keyword for this hat?
    - creativity_score (0-10): rewards length/uniqueness within reason, capped.
    - correction_note: what the reference perspective for this hat actually looks like,
      shown in the debrief/results screen regardless of the player's score.
    """
    answer_text = (answer_text or "").strip()
    keywords = scenario.get("keywords", {}).get(hat, [])
    reference = scenario.get("reference_answers", {}).get(hat, "")

    if not answer_text:
        return False, 0, reference

    hits = _keyword_hits(answer_text, keywords)
    is_on_topic = hits > 0

    word_count = len(re.findall(r"\w+", answer_text))
    length_score = min(5, word_count // 6)          # up to 5 pts for a fuller answer
    keyword_score = min(5, hits * 2)                 # up to 5 pts for hitting relevant angles
    creativity_score = min(10, length_score + keyword_score)

    return is_on_topic, creativity_score, reference
