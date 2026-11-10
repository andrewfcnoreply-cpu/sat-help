"""
The list of SAT skills the app can generate questions for.

These follow the domains and skills College Board publishes for the digital
SAT. Skills that need a graph, chart, or scatterplot are left out for now,
because version 1 is text only. (Quantitative "Command of Evidence" and
"Two-variable data" are the main ones skipped.)

Each domain has a "weight": roughly what fraction of a real module comes from
that domain. The test builder uses these weights so a practice module has
about the same mix as the real thing.
"""

# section -> list of (domain name, weight, [skills])
CATALOG = {
    "rw": [
        ("Information and Ideas", 0.26, [
            "Central Ideas and Details",
            "Command of Evidence (Textual)",
            "Inferences",
        ]),
        ("Craft and Structure", 0.28, [
            "Words in Context",
            "Text Structure and Purpose",
            "Cross-Text Connections",
        ]),
        ("Expression of Ideas", 0.20, [
            "Rhetorical Synthesis",
            "Transitions",
        ]),
        ("Standard English Conventions", 0.26, [
            "Boundaries",
            "Form, Structure, and Sense",
        ]),
    ],
    "math": [
        ("Algebra", 0.35, [
            "Linear equations in one variable",
            "Linear functions",
            "Linear equations in two variables",
            "Systems of two linear equations in two variables",
            "Linear inequalities in one or two variables",
        ]),
        ("Advanced Math", 0.35, [
            "Nonlinear functions",
            "Nonlinear equations in one variable and systems of equations in two variables",
            "Equivalent expressions",
        ]),
        ("Problem-Solving and Data Analysis", 0.15, [
            "Ratios, rates, proportional relationships, and units",
            "Percentages",
            "One-variable data: distributions and measures of center and spread",
            "Probability and conditional probability",
            "Inference from sample statistics and margin of error",
            "Evaluating statistical claims: observational studies and experiments",
        ]),
        ("Geometry and Trigonometry", 0.15, [
            "Area and volume",
            "Lines, angles, and triangles",
            "Right triangles and trigonometry",
            "Circles",
        ]),
    ],
}

# On the real SAT, Reading and Writing questions appear grouped by type in
# this order. Math questions are mixed. We copy that behavior.
RW_ORDER = [
    "Words in Context",
    "Text Structure and Purpose",
    "Cross-Text Connections",
    "Central Ideas and Details",
    "Command of Evidence (Textual)",
    "Inferences",
    "Boundaries",
    "Form, Structure, and Sense",
    "Transitions",
    "Rhetorical Synthesis",
]


def domain_of(section: str, skill: str) -> str:
    """Return the domain name a skill belongs to."""
    for domain, _weight, skills in CATALOG[section]:
        if skill in skills:
            return domain
    return "Other"


def all_skills(section: str) -> list[str]:
    """Every skill in a section, as one flat list."""
    return [s for _d, _w, skills in CATALOG[section] for s in skills]
