"""
The built-in question pack: ready-made questions that ship with the app, so
you can practice without an API key.

The questions live in JSON files in the `questions/` folder. Each file looks
like this:

    {
      "section": "rw",
      "questions": [
        {
          "skill": "Transitions",
          "diff": "easy",                 # easy, medium, or hard
          "passage": "...",
          "question": "@transition",      # or the full question text
          "choices": ["...", "...", "...", "..."],
          "answer": "B",
          "explain": "..."
        }
      ]
    }

Math questions where you type the answer use "type": "spr", put the answer
in "answer" (like "3/4"), and can list other accepted forms in "accept".

To save typing, a few question wordings that repeat on every SAT have
short codes (see STOCK_QUESTIONS below).

At startup the app adds any pack questions that aren't in your bank yet.
Multiple-choice options are shuffled as they're added.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .models import LETTERS, Question, _to_number
from .skills import all_skills, domain_of

PACK_DIR = Path(__file__).resolve().parent.parent / "questions"

STOCK_QUESTIONS = {
    "@word": "Which choice completes the text with the most logical and precise word or phrase?",
    "@conventions": "Which choice completes the text so that it conforms to the conventions of Standard English?",
    "@transition": "Which choice completes the text with the most logical transition?",
    "@purpose": "Which choice best states the main purpose of the text?",
    "@structure": "Which choice best describes the overall structure of the text?",
    "@main": "Which choice best states the main idea of the text?",
    "@complete": "Which choice most logically completes the text?",
}

NOTES_INTRO = "While researching a topic, a student has taken the following notes:"


def _expand(text: str) -> str:
    text = text.strip()
    if text in STOCK_QUESTIONS:
        return STOCK_QUESTIONS[text]
    if text.startswith("@notes"):
        return NOTES_INTRO + "\n" + text[len("@notes"):].strip()
    return text


def _build(item: dict, section: str, where: str) -> Question:
    """Turn one JSON item into a Question. Raises ValueError if anything is off."""
    skill = item["skill"]
    if skill not in all_skills(section):
        raise ValueError(f"{where}: unknown skill {skill!r}")
    difficulty = item["diff"]
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError(f"{where}: bad difficulty {difficulty!r}")
    qtype = item.get("type", "mcq")
    passage = _expand(item.get("passage", ""))
    prompt = _expand(item["question"])
    explanation = item["explain"].strip()
    if section == "rw" and not passage:
        raise ValueError(f"{where}: Reading and Writing questions need a passage")

    if qtype == "mcq":
        choices = [c.strip() for c in item["choices"]]
        if len(choices) != 4 or len(set(choices)) != 4 or not all(choices):
            raise ValueError(f"{where}: needs four different choices")
        correct = choices[LETTERS.index(item["answer"])]
        random.shuffle(choices)
        answer, accepted = LETTERS[choices.index(correct)], []
    elif qtype == "spr":
        answer = str(item["answer"]).strip()
        accepted = [str(a).strip() for a in item.get("accept", [])]
        if _to_number(answer) is None:
            raise ValueError(f"{where}: typed answers must be numbers")
        choices = []
    else:
        raise ValueError(f"{where}: unknown type {qtype!r}")

    return Question(section=section, skill=skill, domain=domain_of(section, skill),
                    difficulty=difficulty, qtype=qtype, passage=passage, prompt=prompt,
                    choices=choices, answer=answer, accepted=accepted,
                    explanation=explanation)


def load_pack(folder: Path = PACK_DIR) -> list[Question]:
    """Read every question file in the pack folder."""
    questions = []
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        section = data["section"]
        for n, item in enumerate(data["questions"], start=1):
            questions.append(_build(item, section, f"{path.name} item {n}"))
    return questions
