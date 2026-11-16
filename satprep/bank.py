"""
The question bank and your results, saved in a small SQLite database file.

SQLite is a database that lives in a single file and comes built into
Python, so there is nothing extra to install. The file is stored in your
Mac's Application Support folder (see main.py for the exact location).

Three tables:
  questions  - every question Claude has written, so it can be reused
  tests      - one row per practice test you finish
  responses  - one row per question you answered (used for stats by skill)
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .models import Question

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id           INTEGER PRIMARY KEY,
    section      TEXT NOT NULL,
    skill        TEXT NOT NULL,
    domain       TEXT NOT NULL,
    difficulty   TEXT NOT NULL,
    qtype        TEXT NOT NULL,
    passage      TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    choices      TEXT NOT NULL,   -- JSON list
    answer       TEXT NOT NULL,
    accepted     TEXT NOT NULL,   -- JSON list
    explanation  TEXT NOT NULL,
    created_at   REAL NOT NULL,
    times_served INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tests (
    id          INTEGER PRIMARY KEY,
    finished_at REAL NOT NULL,
    summary     TEXT NOT NULL     -- JSON: sections, scores, settings
);
CREATE TABLE IF NOT EXISTS responses (
    id          INTEGER PRIMARY KEY,
    test_id     INTEGER NOT NULL REFERENCES tests(id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    section     TEXT NOT NULL,
    skill       TEXT NOT NULL,
    domain      TEXT NOT NULL,
    difficulty  TEXT NOT NULL,
    response    TEXT,
    correct     INTEGER NOT NULL,
    seconds     REAL NOT NULL
);
"""


class Bank:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False lets the background generator save
        # questions too. We only ever write from one place at a time.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        # A lock makes sure two threads never use the database at once.
        self.lock = threading.RLock()

    # ----- questions ---------------------------------------------------------

    def save_questions(self, questions: list[Question]) -> None:
        with self.lock:
            with self.db:
                for q in questions:
                    cur = self.db.execute(
                        "INSERT INTO questions (section, skill, domain, difficulty, qtype,"
                        " passage, prompt, choices, answer, accepted, explanation, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (q.section, q.skill, q.domain, q.difficulty, q.qtype, q.passage,
                         q.prompt, json.dumps(q.choices), q.answer, json.dumps(q.accepted),
                         q.explanation, time.time()),
                    )
                    q.id = cur.lastrowid

    def take_unused(self, section: str, skills: list[str] | None = None,
                    difficulty: str | None = None, qtype: str | None = None) -> Question | None:
        """
        Get one saved question you have not seen yet, or None.
        Leave a filter as None to accept any value for it.
        Marks the question as served so you will not get it again.
        """
        sql = "SELECT * FROM questions WHERE section=? AND times_served=0"
        args: list = [section]
        if skills:
            sql += f" AND skill IN ({','.join('?' * len(skills))})"
            args += skills
        if difficulty:
            sql += " AND difficulty=?"
            args.append(difficulty)
        if qtype:
            sql += " AND qtype=?"
            args.append(qtype)
        with self.lock:
            row = self.db.execute(sql + " ORDER BY RANDOM() LIMIT 1", args).fetchone()
            if row is None:
                return None
            self.mark_served([row["id"]])
            return _row_to_question(row)

    def add_if_new(self, questions: list[Question]) -> int:
        """Save questions that are not in the bank yet. Returns how many were added."""
        with self.lock:
            new = [q for q in questions if self.db.execute(
                "SELECT 1 FROM questions WHERE prompt=? AND passage=?",
                (q.prompt, q.passage)).fetchone() is None]
            self.save_questions(new)
            return len(new)

    def mark_served(self, ids: list[int], undo: bool = False) -> None:
        """Count these questions as seen (or, with undo=True, as unseen again)."""
        change = -1 if undo else 1
        with self.lock:
            with self.db:
                self.db.executemany(
                    f"UPDATE questions SET times_served = MAX(0, times_served + {change}) WHERE id=?",
                    [(i,) for i in ids],
                )

    def count(self, unused_only: bool = False, section: str | None = None,
              difficulty: str | None = None) -> int:
        """How many questions are saved, optionally only unseen ones of one kind."""
        sql, args = "SELECT COUNT(*) FROM questions WHERE 1=1", []
        if unused_only:
            sql += " AND times_served=0"
        if section:
            sql += " AND section=?"
            args.append(section)
        if difficulty:
            sql += " AND difficulty=?"
            args.append(difficulty)
        with self.lock:
            return self.db.execute(sql, args).fetchone()[0]

    def reset_served(self) -> None:
        """Make every saved question available again."""
        with self.lock:
            with self.db:
                self.db.execute("UPDATE questions SET times_served=0")

    # ----- results -----------------------------------------------------------

    def save_test(self, summary: dict, modules) -> int:
        """Save a finished test plus every answer in it. Returns the test id."""
        with self.lock:
            with self.db:
                cur = self.db.execute(
                    "INSERT INTO tests (finished_at, summary) VALUES (?, ?)",
                    (time.time(), json.dumps(summary)),
                )
                test_id = cur.lastrowid
                for m in modules:
                    for i, q in enumerate(m.questions):
                        resp = m.answers.get(i)
                        self.db.execute(
                            "INSERT INTO responses (test_id, question_id, section, skill, domain,"
                            " difficulty, response, correct, seconds) VALUES (?,?,?,?,?,?,?,?,?)",
                            (test_id, q.id, q.section, q.skill, q.domain, q.difficulty, resp,
                             int(q.is_correct(resp)), m.seconds_on.get(i, 0.0)),
                        )
            return test_id

    def past_tests(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id, finished_at, summary FROM tests ORDER BY finished_at DESC"
            ).fetchall()
            return [{"id": r["id"], "finished_at": r["finished_at"], **json.loads(r["summary"])}
                    for r in rows]

    def skill_stats(self) -> list[dict]:
        """Accuracy and average time for every skill you have practiced."""
        with self.lock:
            rows = self.db.execute(
                "SELECT section, domain, skill, COUNT(*) AS total, SUM(correct) AS right,"
                " AVG(seconds) AS avg_seconds FROM responses"
                " GROUP BY section, domain, skill ORDER BY section, domain, skill"
            ).fetchall()
            return [dict(r) for r in rows]


def _row_to_question(row: sqlite3.Row) -> Question:
    return Question(
        id=row["id"], section=row["section"], skill=row["skill"], domain=row["domain"],
        difficulty=row["difficulty"], qtype=row["qtype"], passage=row["passage"],
        prompt=row["prompt"], choices=json.loads(row["choices"]), answer=row["answer"],
        accepted=json.loads(row["accepted"]), explanation=row["explanation"],
    )
