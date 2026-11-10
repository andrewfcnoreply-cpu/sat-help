"""
Settings for the whole app, kept in one place so they are easy to change.

Beginner tip: if you want to tweak how the app behaves (which Claude model
it uses, how long the timer is, how many questions per module), this is the
file to edit. Nothing else needs to change.
"""

# ---------------------------------------------------------------------------
# AI settings
# ---------------------------------------------------------------------------

# Which Claude model writes the questions. Opus is the most careful at
# writing correct math and well-formed reading passages.
MODEL = "claude-opus-5-5"

# How hard Claude "thinks" before answering: "low", "medium", "high".
# Higher = better questions but slower and a bit more expensive.
EFFORT = "high"

# How many questions to ask Claude for in one request. Smaller batches come
# back faster; several batches run at the same time.
BATCH_SIZE = 5

# How many requests may run at the same time.
PARALLEL_REQUESTS = 4

# ---------------------------------------------------------------------------
# Test layout (matches the digital SAT)
# ---------------------------------------------------------------------------
# Each section has two modules. Module 2 is harder or easier depending on
# how you did on module 1 (that is what "adaptive" means).

SECTIONS = {
    "rw": {
        "name": "Reading and Writing",
        "questions_per_module": 27,
        "minutes_per_module": 32,
    },
    "math": {
        "name": "Math",
        "questions_per_module": 22,
        "minutes_per_module": 35,
    },
}

# "Short" practice tests use fewer questions so you can practice (and test
# the app) without spending an hour or many API calls. The timer is scaled
# down to keep the same time per question.
SHORT_TEST_QUESTIONS = {"rw": 8, "math": 6}

# If you get at least this fraction of module 1 right, module 2 is the
# harder version. The real SAT uses a secret formula; this is a stand-in.
ADAPTIVE_THRESHOLD = 0.6

# About 1 in 4 real SAT math questions is "student-produced response"
# (you type the answer instead of choosing A-D).
MATH_SPR_FRACTION = 0.25
