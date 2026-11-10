"""
The screens around the test: home (settings), loading, results, answer
review, and stats.
"""

from __future__ import annotations

import datetime as dt
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QSplitter, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget, QComboBox,
)

from .. import config
from ..models import LETTERS, ModuleState
from ..textfmt import to_display_html
from . import theme
from .widgets import make_button


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("PageTitle")
    return label


def _subtle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Subtle")
    label.setWordWrap(True)
    return label


def _chip_group(parent_layout, heading: str, options: list[tuple[str, str]], default: str):
    """A row of selectable 'chips'. Returns a function that reads the chosen key."""
    parent_layout.addWidget(QLabel(f"<b>{heading}</b>"))
    row = QHBoxLayout()
    group = QButtonGroup(parent_layout.parentWidget())
    group.setExclusive(True)
    keys = {}
    for key, label in options:
        b = make_button(label, "chip", checkable=True)
        b.setChecked(key == default)
        group.addButton(b)
        keys[b] = key
        row.addWidget(b)
    row.addStretch()
    parent_layout.addLayout(row)
    return lambda: keys[group.checkedButton()]


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

class HomePage(QWidget):
    start = Signal(dict)       # chosen settings
    show_stats = Signal()
    reset_bank = Signal()

    def __init__(self):
        super().__init__()
        outer = QHBoxLayout(self)
        column = QWidget()
        column.setMaximumWidth(760)
        lay = QVBoxLayout(column)
        lay.setSpacing(14)
        outer.addWidget(column)

        lay.addWidget(_title("SAT Practice"))
        lay.addWidget(_subtle("Adaptive practice tests with original questions written by "
                              "Claude. Not affiliated with or endorsed by College Board."))

        self.warning = QLabel()
        self.warning.setWordWrap(True)
        lay.addWidget(self.warning)

        lay.addSpacing(8)
        self.get_section = _chip_group(lay, "Section", [
            ("rw", "Reading and Writing"), ("math", "Math"), ("both", "Full test (both)"),
        ], "rw")
        self.get_level = _chip_group(lay, "Difficulty", [
            ("mixed", "Adaptive (like the real test)"), ("easy", "Easy"),
            ("medium", "Medium"), ("hard", "Hard"),
        ], "mixed")
        self.get_length = _chip_group(lay, "Length", [
            ("short", "Short (6-8 questions per module)"), ("full", "Full length"),
        ], "short")

        lay.addSpacing(10)
        go = make_button("Start practice test", "primary")
        go.setMinimumHeight(44)
        go.clicked.connect(lambda: self.start.emit({
            "section": self.get_section(), "level": self.get_level(),
            "short": self.get_length() == "short",
        }))
        lay.addWidget(go)

        lay.addSpacing(10)
        self.bank_label = _subtle("")
        lay.addWidget(self.bank_label)
        row = QHBoxLayout()
        stats = make_button("Stats and past tests")
        stats.clicked.connect(self.show_stats.emit)
        reuse = make_button("Make seen questions available again")
        reuse.setToolTip("Lets the app reuse questions you've already answered")
        reuse.clicked.connect(self.reset_bank.emit)
        appearance = QComboBox()
        appearance.addItems(["Appearance: Match Mac", "Appearance: Light", "Appearance: Dark"])
        modes = ["system", "light", "dark"]
        appearance.currentIndexChanged.connect(lambda i: theme.manager().set_mode(modes[i]))

        def sync_menu():  # keep the menu right if the theme changes from the test screen
            appearance.blockSignals(True)
            appearance.setCurrentIndex(modes.index(theme.manager().mode))
            appearance.blockSignals(False)
        theme.manager().changed.connect(sync_menu)
        row.addWidget(stats)
        row.addWidget(reuse)
        row.addStretch()
        row.addWidget(appearance)
        lay.addLayout(row)
        lay.addStretch()

    def refresh(self, total: int, unused: int) -> None:
        self.bank_label.setText(
            f"Question bank: {total} saved, {unused} not seen yet. Unseen questions are "
            f"used first, so Claude only writes what's missing.")
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.warning.setText("")
            self.warning.hide()
        else:
            self.warning.setText(
                f"<b>No API key set.</b> You can practice with the saved questions. "
                f"To have Claude write new ones, set ANTHROPIC_API_KEY (in Xcode: "
                f"Product > Scheme > Edit Scheme > Run > Arguments).")
            self.warning.show()


# ---------------------------------------------------------------------------
# Loading (while Claude writes questions)
# ---------------------------------------------------------------------------

class LoadingPage(QWidget):
    retry = Signal()
    home = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addStretch()
        self.heading = _title("")
        self.heading.setAlignment(Qt.AlignCenter)
        self.detail = _subtle("")
        self.detail.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setFixedWidth(420)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setAlignment(Qt.AlignCenter)
        self.error.setMaximumWidth(560)
        buttons = QHBoxLayout()
        self.retry_btn = make_button("Try again", "primary")
        self.retry_btn.clicked.connect(self.retry.emit)
        self.home_btn = make_button("Home")
        self.home_btn.clicked.connect(self.home.emit)
        buttons.addStretch()
        buttons.addWidget(self.retry_btn)
        buttons.addWidget(self.home_btn)
        buttons.addStretch()
        lay.addWidget(self.heading)
        lay.addWidget(self.detail)
        lay.addWidget(self.bar, 0, Qt.AlignCenter)
        lay.addWidget(self.error, 0, Qt.AlignCenter)
        lay.addLayout(buttons)
        lay.addStretch()

    def begin(self, heading: str, total: int) -> None:
        self.heading.setText(heading)
        self.detail.setText("Getting questions ready. New ones take about a minute.")
        self.bar.setRange(0, total)
        self.bar.setValue(0)
        self.bar.show()
        self.error.setText("")
        self.retry_btn.hide()
        self.home_btn.hide()

    def progress(self, done: int, total: int) -> None:
        self.bar.setValue(done)
        self.detail.setText(f"{done} of {total} questions ready")

    def failed(self, message: str) -> None:
        c = theme.colors()
        self.bar.hide()
        self.detail.setText("")
        self.error.setText(f"<span style='color:{c['bad']}'>{message}</span>")
        self.retry_btn.show()
        self.home_btn.show()


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class ResultsPage(QWidget):
    review = Signal()
    show_stats = Signal()
    home = Signal()

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(60, 40, 60, 40)

    def show_results(self, summary: dict) -> None:
        c = theme.colors()
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                QWidget().setLayout(item.layout())

        self.lay.addWidget(_title("Your practice results"))
        cards = QHBoxLayout()
        for sec in summary["sections"]:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {c['surface']}; border-radius: 12px; }}"
                               "QLabel { background: transparent; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(24, 20, 24, 20)
            cl.addWidget(QLabel(f"<b>{sec['name']}</b>"))
            score = QLabel(f"<span style='font-size:44px; font-weight:700;"
                           f" color:{c['accent']}'>{sec['score']}</span>")
            cl.addWidget(score)
            cl.addWidget(_subtle(
                f"Module 1: {sec['m1_correct']} of {sec['m1_total']} correct<br>"
                f"Module 2 ({sec['m2_level']}): {sec['m2_correct']} of {sec['m2_total']} correct"))
            cards.addWidget(card)
        if len(summary["sections"]) == 2:
            total = sum(s["score"] for s in summary["sections"])
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {c['accent_soft']}; border-radius: 12px; }}"
                               "QLabel { background: transparent; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(24, 20, 24, 20)
            cl.addWidget(QLabel("<b>Total</b>"))
            cl.addWidget(QLabel(f"<span style='font-size:44px; font-weight:700'>{total}</span>"))
            cl.addWidget(_subtle("out of 1600"))
            cards.addWidget(card)
        self.lay.addLayout(cards)
        note = _subtle("Scores are rough estimates on the 200-800 scale. The real SAT uses "
                       "a scoring model that is not public, and short tests are less precise.")
        self.lay.addWidget(note)

        buttons = QHBoxLayout()
        for text, signal, kind in [("Review answers and explanations", self.review, "primary"),
                                   ("Stats by skill", self.show_stats, None),
                                   ("Home", self.home, None)]:
            b = make_button(text, kind)
            b.clicked.connect(signal.emit)
            buttons.addWidget(b)
        buttons.addStretch()
        self.lay.addLayout(buttons)
        self.lay.addStretch()


# ---------------------------------------------------------------------------
# Review answers and explanations
# ---------------------------------------------------------------------------

class ReviewPage(QWidget):
    back = Signal()

    def __init__(self):
        super().__init__()
        self.modules: list[ModuleState] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 20, 30, 20)
        top = QHBoxLayout()
        top.addWidget(_title("Review"))
        top.addStretch()
        self.filter = QComboBox()
        self.filter.addItems(["All questions", "Incorrect or skipped", "Marked for review"])
        self.filter.currentIndexChanged.connect(self._fill)
        back = make_button("Back to results")
        back.clicked.connect(self.back.emit)
        top.addWidget(self.filter)
        top.addWidget(back)
        lay.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show)
        self.view = QTextBrowser()
        split.addWidget(self.list)
        split.addWidget(self.view)
        split.setSizes([380, 800])
        lay.addWidget(split, 1)

    def load(self, modules: list[ModuleState]) -> None:
        self.modules = modules
        self._fill()

    def _fill(self) -> None:
        self.list.clear()
        mode = self.filter.currentIndex()
        for mi, m in enumerate(self.modules):
            name = config.SECTIONS[m.section]["name"]
            for qi, q in enumerate(m.questions):
                right = q.is_correct(m.answers.get(qi))
                if mode == 1 and right:
                    continue
                if mode == 2 and qi not in m.marked:
                    continue
                mark = "✓" if right else "✗"
                item = QListWidgetItem(f"{mark}  {name} M{m.number} Q{qi + 1}: {q.skill}")
                item.setData(Qt.UserRole, (mi, qi))
                self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.view.setHtml("<p>Nothing to show for this filter.</p>")

    def _show(self, item) -> None:
        if item is None:
            return
        c = theme.colors()
        mi, qi = item.data(Qt.UserRole)
        m = self.modules[mi]
        q = m.questions[qi]
        given = m.answers.get(qi)
        right = q.is_correct(given)
        parts = [f"<p style='color:{c['muted']}'>{q.domain} &middot; {q.skill} &middot; "
                 f"{q.difficulty.title()} &middot; {m.seconds_on.get(qi, 0):.0f} seconds</p>"]
        if q.passage:
            parts.append(f"<div style='font-family:Georgia; font-size:16px'>"
                         f"{to_display_html(q.passage)}</div><hr>")
        parts.append(f"<p style='font-family:Georgia; font-size:16px'>"
                     f"{to_display_html(q.prompt)}</p>")
        if q.qtype == "mcq":
            for letter, text in zip(LETTERS, q.choices):
                style = ""
                tag = ""
                if letter == q.answer:
                    style = f"color:{c['good']}; font-weight:600"
                    tag = " ← correct answer"
                if letter == given and not right:
                    style = f"color:{c['bad']}"
                    tag = " ← your answer"
                parts.append(f"<p style='{style}'>{letter}. {to_display_html(text)}{tag}</p>")
        else:
            accepted = ", ".join(dict.fromkeys([q.answer, *q.accepted]))
            parts.append(f"<p style='color:{c['good']}'><b>Accepted answers:</b> {accepted}</p>")
        verdict = ("Correct" if right else ("Skipped" if not given else f"Your answer: {given}"))
        parts.append(f"<p><b style='color:{c['good'] if right else c['bad']}'>{verdict}</b></p>")
        parts.append(f"<h3>Explanation</h3><p>{to_display_html(q.explanation)}</p>")
        self.view.setHtml("".join(parts))


# ---------------------------------------------------------------------------
# Stats by skill and past tests
# ---------------------------------------------------------------------------

class StatsPage(QWidget):
    back = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 20, 30, 20)
        top = QHBoxLayout()
        top.addWidget(_title("Stats"))
        top.addStretch()
        back = make_button("Back")
        back.clicked.connect(self.back.emit)
        top.addWidget(back)
        lay.addLayout(top)

        lay.addWidget(QLabel("<b>Accuracy by skill</b> (weakest first)"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Section", "Skill", "Answered", "Accuracy", "Avg time"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 2)

        lay.addWidget(QLabel("<b>Past tests</b>"))
        self.history = QListWidget()
        lay.addWidget(self.history, 1)

    def load(self, skill_rows: list[dict], tests: list[dict]) -> None:
        rows = sorted(skill_rows, key=lambda r: (r["right"] or 0) / r["total"])
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            pct = round(100 * (r["right"] or 0) / r["total"])
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setFormat(f"{pct}%")
            bar.setTextVisible(True)
            bar.setStyleSheet(f"QProgressBar {{ color: {theme.colors()['text']}; }}")
            self.table.setItem(i, 0, QTableWidgetItem(config.SECTIONS[r["section"]]["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["skill"]))
            self.table.setItem(i, 2, QTableWidgetItem(str(r["total"])))
            self.table.setCellWidget(i, 3, bar)
            self.table.setItem(i, 4, QTableWidgetItem(f"{r['avg_seconds']:.0f} s"))
        self.table.resizeColumnToContents(0)

        self.history.clear()
        for t in tests:
            when = dt.datetime.fromtimestamp(t["finished_at"]).strftime("%b %d, %Y %I:%M %p")
            scores = ", ".join(f"{s['name']} {s['score']}" for s in t["sections"])
            length = "short" if t.get("short") else "full length"
            self.history.addItem(f"{when}  —  {scores}  ({length})")
        if not tests:
            self.history.addItem("No finished tests yet.")
