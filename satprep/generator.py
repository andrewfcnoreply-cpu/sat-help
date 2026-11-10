"""
Talks to Claude to write new SAT-style questions.

How it works, step by step:
  1. The test builder makes a list of "slots". Each slot says what kind of
     question is needed, like ("Transitions", "hard", "mcq").
  2. We split the slots into small batches and send several batches to
     Claude at the same time (this makes it much faster).
  3. Claude must answer in an exact JSON format (a "schema"), so we can read
     the questions reliably.
  4. We check every question (four choices, a valid answer, and so on).
     Any that fail are asked for again once.
  5. Multiple-choice options are shuffled so the right answer is not always
     in the same spot.

Your API key is read from the ANTHROPIC_API_KEY environment variable by the
official SDK. It is never written into this code or saved anywhere by the app.
"""

from __future__ import annotations

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import anthropic

from . import config
from .models import LETTERS, Question, _to_number
from .skills import domain_of


class GenerationError(Exception):
    """A problem we can explain to the user in plain words."""


@dataclass(frozen=True)
class Slot:
    section: str
    skill: str
    difficulty: str
    qtype: str  # "mcq" or "spr"


# ---------------------------------------------------------------------------
# Instructions for Claude
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You write original practice questions for the digital SAT. \
Students use them to prepare for the real test, so each question must match \
the real test's style, length, and difficulty, and must have exactly one \
defensibly correct answer. Write new content; never reproduce real College \
Board questions or copyrighted passages.

Formatting rules for every text field:
- Plain text. The only markup allowed is <sup>, <sub>, <i>, <b>, <u>, and <br>.
- Use <sup> for exponents (x<sup>2</sup>) and <i> for variable names if you like.
- Use the Unicode characters √, π, ≤, ≥, ≠, °, and − where they read naturally.
- Do not put letters like "A)" in front of choices; the app adds them.
- Explanations must never refer to choices by letter, because the app shuffles \
the choices. Refer to the choice's content instead (for example: "The choice \
'however' is wrong because...").

Difficulty levels:
- easy: one clear step or a common word or rule; distractors are clearly wrong \
to a prepared student.
- medium: two or three steps or a subtler distinction; at least one tempting \
distractor.
- hard: multi-step reasoning, less common vocabulary or structures, or a \
twist; distractors reflect real student mistakes.

Before writing each answer key, solve the question yourself from scratch and \
confirm that exactly one choice is correct."""

RW_GUIDE = """Reading and Writing rules (each question has its own passage):
- "passage": 25 to 150 words. Use varied topics: literature, history, social \
studies, the humanities, and science.
- For literature, start the passage with a line like "The following text is \
adapted from [invented author]'s [year] novel [title]." You may also write in \
the style of public-domain classics.
- Cross-Text Connections: two short texts labeled "Text 1" and "Text 2" with a \
<br><br> between them.
- Boundaries and Form, Structure, and Sense: the passage contains one blank \
written as ______ and the question is "Which choice completes the text so that \
it conforms to the conventions of Standard English?"
- Words in Context: the passage contains ______ and the question is "Which \
choice completes the text with the most logical and precise word or phrase?"
- Transitions: the passage contains ______ and the question is "Which choice \
completes the text with the most logical transition?"
- Rhetorical Synthesis: the passage starts "While researching a topic, a \
student has taken the following notes:" followed by 4 to 6 bullet notes, each \
on its own line starting with "• ". The question names the student's goal and \
asks "Which choice most effectively uses relevant information from the notes \
to accomplish this goal?"
- Text Structure and Purpose, Central Ideas, Inferences, and Command of \
Evidence: use the matching official SAT question wording, such as "Which \
choice best states the main purpose of the text?" or "Which choice most \
logically completes the text?"
- Always exactly four choices."""

MATH_GUIDE = """Math rules:
- "passage" must be an empty string. Put the whole problem in "question".
- No figures, graphs, or tables. Describe geometry in words (for example, \
"In right triangle ABC, angle C is 90°...").
- Mix pure math and real-world contexts, like the real SAT.
- Multiple choice ("mcq"): exactly four choices, "correct_choice" is the \
letter of the right one, and "accepted_answers" is an empty list.
- Student-produced response ("spr"): "choices" is an empty list, \
"correct_choice" is "none", and the answer must be a single number. List \
every acceptable entry in "accepted_answers", following SAT rules: an exact \
fraction like 7/3, and a decimal that fills the answer box (up to 5 characters \
for a positive answer, 6 for a negative one, counting the decimal point and \
minus sign), both rounded and truncated if they differ. Example for 2/3: \
["2/3", ".6666", ".6667", "0.666", "0.667"]."""

# The exact shape Claude must answer in.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_number": {"type": "integer"},
                    "passage": {"type": "string"},
                    "question": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "correct_choice": {"type": "string", "enum": ["A", "B", "C", "D", "none"]},
                    "accepted_answers": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": ["item_number", "passage", "question", "choices",
                             "correct_choice", "accepted_answers", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def _build_request(slots: list[Slot]) -> str:
    section = slots[0].section
    lines = [RW_GUIDE if section == "rw" else MATH_GUIDE, "",
             f"Write {len(slots)} questions, one for each item below, in this order:"]
    for n, s in enumerate(slots, start=1):
        kind = "multiple choice" if s.qtype == "mcq" else "student-produced response"
        lines.append(f"{n}. Skill: {s.skill} | Difficulty: {s.difficulty} | Type: {kind}")
    lines.append("")
    lines.append("Use a different topic or context for each item. Set item_number to "
                 "the item's number from this list.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Calling the API
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # With no arguments, the SDK finds your key in ANTHROPIC_API_KEY.
        _client = anthropic.Anthropic(max_retries=3)
    return _client


def _ask_claude(slots: list[Slot]) -> list[dict]:
    """Send one batch to Claude and return the raw question dictionaries."""
    client = _get_client()
    try:
        # Streaming keeps long answers from timing out. get_final_message()
        # waits for the whole reply and hands it back in one piece.
        with client.beta.messages.stream(
            model=config.MODEL,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_request(slots)}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": config.EFFORT,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            # If the model ever declines a request, the API retries it on a
            # fallback model automatically instead of failing.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise GenerationError(
            "Claude rejected the API key. Check that ANTHROPIC_API_KEY is set "
            "correctly (see the README section 'Add your API key in Xcode')."
        )
    except anthropic.PermissionDeniedError:
        raise GenerationError("Your API key does not have permission to use this model.")
    except anthropic.RateLimitError:
        raise GenerationError("Too many requests right now. Wait a minute and try again.")
    except anthropic.APIConnectionError:
        raise GenerationError("Could not reach Claude. Check your internet connection.")
    except anthropic.APIStatusError as e:
        raise GenerationError(f"Claude returned an error ({e.status_code}): {e.message}")

    if message.stop_reason == "refusal":
        raise GenerationError("Claude declined to write this batch.")
    if message.stop_reason == "max_tokens":
        raise GenerationError("Claude's answer was cut off. Try a smaller BATCH_SIZE in config.py.")

    # If a fallback happened, only the text after the last fallback marker
    # belongs to the final answer.
    blocks = list(message.content)
    for i in range(len(blocks) - 1, -1, -1):
        if blocks[i].type == "fallback":
            blocks = blocks[i + 1:]
            break
    text = "".join(b.text for b in blocks if b.type == "text")
    try:
        return json.loads(text)["questions"]
    except (json.JSONDecodeError, KeyError) as e:
        raise GenerationError(f"Could not read Claude's answer: {e}")


# ---------------------------------------------------------------------------
# Checking and cleaning each question
# ---------------------------------------------------------------------------

_LEADING_LETTER = re.compile(r"^\s*\(?[A-Da-d][\).:]\s+")


def _to_question(raw: dict, slot: Slot) -> Question | None:
    """Turn Claude's raw output into a Question, or None if it is not usable."""
    prompt = (raw.get("question") or "").strip()
    passage = (raw.get("passage") or "").strip()
    explanation = (raw.get("explanation") or "").strip()
    if not prompt or not explanation:
        return None
    if slot.section == "rw" and not passage:
        return None

    if slot.qtype == "mcq":
        choices = [_LEADING_LETTER.sub("", c).strip() for c in raw.get("choices") or []]
        letter = raw.get("correct_choice")
        if len(choices) != 4 or any(not c for c in choices) or len(set(choices)) != 4:
            return None
        if letter not in LETTERS:
            return None
        # Shuffle so the correct answer lands in a random position.
        correct_text = choices[LETTERS.index(letter)]
        random.shuffle(choices)
        answer = LETTERS[choices.index(correct_text)]
        accepted: list[str] = []
    else:
        accepted = [a.strip() for a in raw.get("accepted_answers") or [] if a.strip()]
        if not accepted or _to_number(accepted[0]) is None:
            return None
        choices = []
        answer = accepted[0]

    return Question(
        section=slot.section, skill=slot.skill, domain=domain_of(slot.section, slot.skill),
        difficulty=slot.difficulty, qtype=slot.qtype, passage=passage, prompt=prompt,
        choices=choices, answer=answer, accepted=accepted, explanation=explanation,
    )


def _run_batch(slots: list[Slot]) -> tuple[list[Question], list[Slot]]:
    """Generate one batch. Returns (good questions, slots that still need one)."""
    raw_items = _ask_claude(slots)
    by_number = {item.get("item_number"): item for item in raw_items}
    good, missing = [], []
    for n, slot in enumerate(slots, start=1):
        # Match by item number; fall back to list position.
        raw = by_number.get(n) or (raw_items[n - 1] if n - 1 < len(raw_items) else None)
        q = _to_question(raw, slot) if raw else None
        (good.append(q) if q else missing.append(slot))
    return good, missing


def generate(slots: list[Slot], on_progress: Callable[[int, int], None] | None = None) -> list[Question]:
    """
    Generate one question for every slot (all slots must be the same section).
    on_progress(done, total) is called as batches finish, for the loading bar.
    Returns the questions in the same order as the slots.
    """
    if not slots:
        return []
    total = len(slots)
    done = 0
    results: dict[Slot, list[Question]] = {}
    pending = list(slots)

    for _attempt in range(2):  # first try, plus one retry for any bad items
        batches = [pending[i:i + config.BATCH_SIZE]
                   for i in range(0, len(pending), config.BATCH_SIZE)]
        pending = []
        with ThreadPoolExecutor(max_workers=config.PARALLEL_REQUESTS) as pool:
            futures = {pool.submit(_run_batch, b): b for b in batches}
            for fut in as_completed(futures):
                good, missing = fut.result()  # GenerationError passes through
                for q in good:
                    results.setdefault(Slot(q.section, q.skill, q.difficulty, q.qtype), []).append(q)
                done += len(good)
                pending.extend(missing)
                if on_progress:
                    on_progress(done, total)
        if not pending:
            break

    if pending:
        raise GenerationError(
            f"{len(pending)} question(s) came back unusable twice. Please try again."
        )

    # Put questions back in slot order (slots can repeat, so pop one at a time).
    return [results[s].pop() for s in slots]
