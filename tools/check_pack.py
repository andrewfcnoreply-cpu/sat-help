"""
Check the built-in question pack before publishing new questions.

Run from the project folder:
    python3 tools/check_pack.py

It loads every file in questions/ the same way the app does, so any format
problem (wrong skill name, three choices instead of four, a typed answer
that isn't a number) shows up here with the file name and item number.
It also reports repeated questions and how many questions there are for
each skill and difficulty. This script needs only plain Python (no PySide6).
"""

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from satprep.pack import load_pack  # noqa: E402
from satprep.skills import all_skills  # noqa: E402


def main() -> int:
    try:
        questions = load_pack()
    except (ValueError, KeyError) as e:
        print(f"FORMAT ERROR: {e}")
        return 1

    problems = 0
    seen = {}
    for q in questions:
        key = (q.prompt.strip().lower(), q.passage.strip().lower())
        if key in seen:
            print(f"DUPLICATE: {q.skill}: {q.prompt[:70]}")
            problems += 1
        seen[key] = True

    print(f"{len(questions)} questions loaded.\n")
    for section, name in (("rw", "Reading and Writing"), ("math", "Math")):
        in_section = [q for q in questions if q.section == section]
        counts = collections.Counter((q.skill, q.difficulty) for q in in_section)
        print(f"{name}: {len(in_section)} questions")
        for skill in all_skills(section):
            row = [counts[(skill, d)] for d in ("easy", "medium", "hard")]
            print(f"  {skill[:60]:<60} easy {row[0]:>2}  medium {row[1]:>2}  hard {row[2]:>2}")
        print()

    if problems:
        print(f"{problems} problem(s) found.")
        return 1
    print("No problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
