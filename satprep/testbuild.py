"""
Builds practice modules and estimates scores. No AI or screens here, just
the rules, which makes this file easy to read and to test.

Adaptive testing in one paragraph: Module 1 has a mix of easy, medium, and
hard questions. If you do well on it, Module 2 is the "harder" version; if
not, it is the "easier" version. Only the harder path can reach the top
scores, which is why the real SAT feels hard when you are doing well.
"""

from __future__ import annotations

import os
import random

from . import config
from .bank import Bank
from .generator import GenerationError, Slot, generate
from .models import ModuleState, Question
from .skills import CATALOG, RW_ORDER, domain_of

# What share of easy / medium / hard questions each kind of module gets.
DIFFICULTY_MIX = {
    "mixed": {"easy": 0.34, "medium": 0.33, "hard": 0.33},   # adaptive module 1
    "harder": {"easy": 0.15, "medium": 0.35, "hard": 0.50},  # adaptive module 2, high path
    "easier": {"easy": 0.50, "medium": 0.35, "hard": 0.15},  # adaptive module 2, low path
    "easy": {"easy": 1.0},
    "medium": {"medium": 1.0},
    "hard": {"hard": 1.0},
}

_DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def _spread(total: int, shares: dict[str, float]) -> list[str]:
    """
    Split `total` items between keys by their shares, so the counts add up
    exactly. Example: _spread(10, {"a": .5, "b": .5}) -> 5 a's and 5 b's.
    """
    exact = {k: total * v for k, v in shares.items()}
    counts = {k: int(x) for k, x in exact.items()}
    # Hand out the leftover items to whoever was rounded down the most.
    leftovers = sorted(exact, key=lambda k: exact[k] - counts[k], reverse=True)
    for k in leftovers[: total - sum(counts.values())]:
        counts[k] += 1
    return [k for k, n in counts.items() for _ in range(n)]


def module_size(section: str, short: bool) -> tuple[int, int]:
    """(number of questions, minutes) for one module."""
    info = config.SECTIONS[section]
    if not short:
        return info["questions_per_module"], info["minutes_per_module"]
    n = config.SHORT_TEST_QUESTIONS[section]
    minutes = max(1, round(info["minutes_per_module"] * n / info["questions_per_module"]))
    return n, minutes


def plan_slots(section: str, count: int, level: str) -> list[Slot]:
    """Decide what kind of question goes in each position of a module."""
    domains = CATALOG[section]
    domain_names = _spread(count, {name: weight for name, weight, _ in domains})
    difficulties = _spread(count, DIFFICULTY_MIX[level])
    random.shuffle(difficulties)

    skills_by_domain = {name: skills for name, _w, skills in domains}
    slots = []
    for domain, difficulty in zip(domain_names, difficulties):
        skill = random.choice(skills_by_domain[domain])
        qtype = "mcq"
        if section == "math" and random.random() < config.MATH_SPR_FRACTION:
            qtype = "spr"
        slots.append(Slot(section, skill, difficulty, qtype))
    return slots


def order_questions(section: str, questions: list[Question]) -> list[Question]:
    """
    Put questions in test order. Reading and Writing groups questions by
    type (like the real test); Math goes roughly from easier to harder.
    """
    if section == "rw":
        key = lambda q: (RW_ORDER.index(q.skill) if q.skill in RW_ORDER else 99,
                         _DIFFICULTY_RANK[q.difficulty])
    else:
        key = lambda q: (_DIFFICULTY_RANK[q.difficulty], random.random())
    return sorted(questions, key=key)


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _from_bank(bank: Bank, slot: Slot, flexible: bool) -> Question | None:
    """
    Find a saved question for a slot, trying the closest match first:
      1. the exact skill, difficulty, and type
      2. another skill from the same domain (same difficulty and type)
    With flexible=True (no API key, so we can't write new questions), also:
      3. any skill in the section at the same difficulty
      4. the same skill at any difficulty, then anything left in the section
    """
    domain = domain_of(slot.section, slot.skill)
    domain_skills = next(s for d, _w, s in CATALOG[slot.section] if d == domain)
    tries = [
        dict(skills=[slot.skill], difficulty=slot.difficulty, qtype=slot.qtype),
        dict(skills=domain_skills, difficulty=slot.difficulty, qtype=slot.qtype),
    ]
    if flexible:
        tries += [
            dict(difficulty=slot.difficulty),
            dict(skills=[slot.skill]),
            dict(),
        ]
    for filters in tries:
        q = bank.take_unused(slot.section, **filters)
        if q:
            return q
    return None


def build_module(bank: Bank, section: str, number: int, level: str, short: bool,
                 on_progress=None) -> ModuleState:
    """
    Make a ready-to-take module. Uses saved, unseen questions from the bank
    first and asks Claude only for what is missing. New questions are saved
    to the bank right away. Without an API key, it uses only saved questions.
    """
    count, minutes = module_size(section, short)
    slots = plan_slots(section, count, level)
    can_generate = has_api_key()

    from_bank: list[Question] = []
    needed: list[Slot] = []
    for slot in slots:
        q = _from_bank(bank, slot, flexible=not can_generate)
        (from_bank.append(q) if q else needed.append(slot))

    if needed and not can_generate:
        bank.mark_served([q.id for q in from_bank], undo=True)
        raise GenerationError(
            f"There aren't enough unseen saved questions for this module "
            f"({len(needed)} more needed), and no API key is set to write new ones. "
            f"On the home screen, choose 'Make seen questions available again', "
            f"pick a shorter test, or add an API key.")

    if on_progress:
        on_progress(len(from_bank), count)

    def progress(done, _total):
        if on_progress:
            on_progress(len(from_bank) + done, count)

    try:
        fresh = generate(needed, progress)
    except Exception:
        # Put the saved questions back so they are not wasted.
        bank.mark_served([q.id for q in from_bank], undo=True)
        raise
    bank.save_questions(fresh)
    bank.mark_served([q.id for q in fresh if q.id is not None])

    questions = order_questions(section, from_bank + fresh)
    return ModuleState(section=section, number=number, level=level,
                       questions=questions, minutes=minutes)


def next_level(module1: ModuleState) -> str:
    """After module 1, pick the harder or easier module 2."""
    if module1.level not in ("mixed",):
        return module1.level  # fixed-difficulty practice keeps the same level
    share = module1.num_correct() / max(1, len(module1.questions))
    return "harder" if share >= config.ADAPTIVE_THRESHOLD else "easier"


# Rough top score for each kind of module 2. These are estimates; the real
# SAT uses a statistical model (item response theory) that is not public.
_CEILING = {"harder": 800, "easier": 650, "easy": 600, "medium": 700, "hard": 800}
_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}


def estimate_score(module1: ModuleState, module2: ModuleState) -> int:
    """
    Estimate a 200-800 section score. Harder questions count for more, and
    the easier module-2 path has a lower ceiling, like the real test.
    """
    earned = possible = 0.0
    for m in (module1, module2):
        for i, q in enumerate(m.questions):
            w = _WEIGHT[q.difficulty]
            possible += w
            if q.is_correct(m.answers.get(i)):
                earned += w
    ceiling = _CEILING.get(module2.level, 800)
    score = 200 + (ceiling - 200) * (earned / possible if possible else 0)
    return int(round(score / 10) * 10)
