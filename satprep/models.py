"""
Plain data objects used everywhere in the app.

A "dataclass" is just a Python class that mostly holds data. Writing
@dataclass above it makes Python create the __init__ method for us.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

LETTERS = ["A", "B", "C", "D"]


@dataclass
class Question:
    section: str             # "rw" or "math"
    skill: str               # e.g. "Transitions" or "Circles"
    domain: str              # e.g. "Expression of Ideas"
    difficulty: str          # "easy", "medium", or "hard"
    qtype: str               # "mcq" (choose A-D) or "spr" (type the answer)
    passage: str             # reading passage; empty for most math questions
    prompt: str              # the question itself
    choices: list[str]       # four choices for mcq, empty list for spr
    answer: str              # "A"-"D" for mcq; the main correct answer for spr
    accepted: list[str]      # spr only: every answer form that counts as right
    explanation: str         # why the answer is right (shown in review)
    id: int | None = None    # database id, filled in once saved

    def is_correct(self, response: str | None) -> bool:
        """Check a student's response against the answer key."""
        if not response:
            return False
        if self.qtype == "mcq":
            return response == self.answer
        return spr_matches(response, [self.answer, *self.accepted])


def _to_number(text: str) -> Fraction | None:
    """Turn '3/4', '.75', '-2', '1.5' into an exact number, or None."""
    text = text.strip().replace(" ", "").replace("−", "-")
    if not text:
        return None
    try:
        if "/" in text:
            top, bottom = text.split("/", 1)
            return Fraction(Fraction(top), Fraction(bottom))
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def spr_matches(response: str, accepted: list[str]) -> bool:
    """
    True if a typed (student-produced) answer matches any accepted answer.

    The SAT accepts equivalent forms, so 3/4, .75 and 0.75 are all fine.
    We compare as exact numbers when possible, otherwise as plain text.
    """
    given = _to_number(response)
    for option in accepted:
        if response.strip().lower() == option.strip().lower():
            return True
        expected = _to_number(option)
        if given is None or expected is None:
            continue
        if given == expected:
            return True
        if _close_decimal(response, given, expected):
            return True
    return False


def _close_decimal(text: str, given: Fraction, expected: Fraction) -> bool:
    """
    The SAT accepts a decimal that fills the answer box, rounded or cut off.
    For 2/3 that means .6666, .6667, 0.666, and 0.667 all count. We accept a
    decimal with at least 3 digits after the point that is within one unit
    of its last digit. So 0.67 is still marked wrong for 2/3, as on the SAT.
    """
    text = text.strip()
    if "." not in text or "/" in text:
        return False
    places = len(text.split(".", 1)[1])
    if places < 3:
        return False
    return abs(given - expected) < Fraction(1, 10 ** places)


@dataclass
class ModuleState:
    """Everything about one module while you are taking it."""
    section: str
    number: int                       # 1 or 2
    level: str                        # "mixed", "harder", "easier", or a fixed difficulty
    questions: list[Question]
    minutes: int
    answers: dict[int, str] = field(default_factory=dict)        # question index -> response
    marked: set[int] = field(default_factory=set)                # flagged for review
    eliminated: dict[int, set[str]] = field(default_factory=dict)  # index -> crossed-out letters
    seconds_on: dict[int, float] = field(default_factory=dict)   # time spent per question

    def num_correct(self) -> int:
        return sum(
            1 for i, q in enumerate(self.questions) if q.is_correct(self.answers.get(i))
        )
