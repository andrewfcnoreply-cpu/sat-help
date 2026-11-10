"""
The test-taking screen, laid out like the Bluebook app:

  +-----------------------------------------------------------------+
  | Section 1, Module 1     31:59  [Hide]      Calculator  Ref  More |  <- header
  |-----------------------------------------------------------------|
  |  passage (left)          |  [1] Mark for Review          [ABC]  |
  |                          |  question                            |
  |                          |  (A) ...   (B) ...                   |
  |-----------------------------------------------------------------|
  |  Practice Test        [Question 1 of 27 ^]          Back  Next  |  <- footer
  +-----------------------------------------------------------------+
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QScrollArea,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget, QGridLayout, QPushButton,
)

from .. import config
from ..models import LETTERS, ModuleState
from ..textfmt import to_display_html
from . import theme
from .widgets import (
    CalculatorDialog, ChoiceRow, NavigatorPopup, ReferenceDialog, make_button,
)

DIRECTIONS = {
    "rw": ("The questions in this section address a number of important reading and "
           "writing skills. Each question includes one or more passages, which may "
           "include a table or graph. Read each passage and question carefully, and "
           "then choose the best answer to the question based on the passage(s). All "
           "questions in this section are multiple-choice with four answer choices. "
           "Each question has a single best answer."),
    "math": ("The questions in this section address a number of important math skills. "
             "Use of a calculator is permitted for all questions. Unless otherwise "
             "indicated, all variables and expressions represent real numbers, figures "
             "are drawn to scale, and the domain of a function is the set of all real "
             "numbers x for which f(x) is a real number.<br><br>"
             "For multiple-choice questions, solve each problem and choose the correct "
             "answer from the choices provided. For student-produced response questions, "
             "enter your answer: if you find more than one correct answer, enter only one; "
             "you can enter up to 5 characters for a positive answer and up to 6 "
             "characters (including the negative sign) for a negative answer; if your "
             "answer is a fraction that doesn't fit, enter the decimal equivalent; "
             "don't enter symbols such as a percent sign, comma, or dollar sign."),
}


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


class TestPage(QWidget):
    finished = Signal(object)   # the ModuleState, once submitted
    quit_requested = Signal()

    def __init__(self, module: ModuleState, section_index: int):
        super().__init__()
        self.m = module
        self.index = 0
        self.eliminator_on = False
        self.remaining = module.minutes * 60
        self.shown_at = time.monotonic()
        self.section_name = config.SECTIONS[module.section]["name"]
        self.title = f"Section {section_index}, Module {module.number}: {self.section_name}"
        self.calculator: CalculatorDialog | None = None
        self.reference: ReferenceDialog | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        rule = QFrame()
        rule.setObjectName("HeaderRule")
        root.addWidget(rule)

        self.body = QStackedWidget()
        self.body.addWidget(self._build_question_view())
        self.check_page = QWidget()
        self.body.addWidget(self.check_page)
        root.addWidget(self.body, 1)
        root.addWidget(self._build_footer())

        self.clock = QTimer(self)
        self.clock.timeout.connect(self._tick)
        self.clock.start(1000)
        self._update_timer_label()

        theme.manager().changed.connect(self.show_question)
        self.show_question()

    # ----- building the layout ------------------------------------------------

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Header")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 10, 20, 10)

        left = QVBoxLayout()
        title = QLabel(self.title)
        title.setObjectName("SectionTitle")
        directions = make_button("Directions ▾", "tool")
        directions.clicked.connect(self._show_directions)
        left.addWidget(title)
        left.addWidget(directions, 0, Qt.AlignLeft)

        center = QVBoxLayout()
        self.timer_label = QLabel()
        self.timer_label.setObjectName("Timer")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.hide_btn = make_button("Hide", "tool")
        self.hide_btn.clicked.connect(self._toggle_timer)
        center.addWidget(self.timer_label)
        center.addWidget(self.hide_btn, 0, Qt.AlignCenter)

        right = QHBoxLayout()
        if self.m.section == "math":
            calc_btn = make_button("\U0001F5A9  Calculator", "tool")
            calc_btn.clicked.connect(self._open_calculator)
            ref_btn = make_button("π  Reference", "tool")
            ref_btn.clicked.connect(self._open_reference)
            right.addWidget(calc_btn)
            right.addWidget(ref_btn)
        more = make_button("⋮  More", "tool")
        menu = QMenu(more)
        for label, mode in [("Appearance: Match Mac", "system"),
                            ("Appearance: Light", "light"),
                            ("Appearance: Dark", "dark")]:
            menu.addAction(label, lambda m=mode: theme.manager().set_mode(m))
        menu.addSeparator()
        menu.addAction("Exit test (progress is lost)", self._confirm_quit)
        more.setMenu(menu)
        right.addWidget(more)

        lay.addLayout(left, 1)
        lay.addLayout(center, 1)
        lay.addLayout(right, 1)
        right.insertStretch(0)
        return bar

    def _build_question_view(self) -> QWidget:
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left: the passage.
        self.passage = QLabel()
        self.passage.setObjectName("Passage")
        self.passage.setWordWrap(True)
        self.passage.setTextFormat(Qt.RichText)
        self.passage.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.passage.setTextInteractionFlags(Qt.TextSelectableByMouse)
        holder = QWidget()
        pl = QVBoxLayout(holder)
        pl.setContentsMargins(40, 30, 30, 30)
        pl.addWidget(self.passage)
        pl.addStretch()
        self.passage_area = _scroll(holder)

        # Right: question bar, prompt, choices.
        right = QWidget()
        self.right_layout = QVBoxLayout(right)
        self.right_layout.setContentsMargins(30, 30, 40, 30)
        self.right_layout.setSpacing(16)

        qbar = QWidget()
        qbar.setObjectName("QuestionBar")
        ql = QHBoxLayout(qbar)
        ql.setContentsMargins(0, 0, 8, 0)
        self.qnum = QLabel("1")
        self.qnum.setObjectName("QNumber")
        self.mark_btn = make_button("⚐  Mark for Review", "tool", checkable=True)
        self.mark_btn.toggled.connect(self._toggle_mark)
        self.elim_btn = make_button("A̶B̶C̶", "tool", checkable=True)
        self.elim_btn.setToolTip("Answer eliminator: cross out choices")
        self.elim_btn.toggled.connect(self._toggle_eliminator)
        ql.addWidget(self.qnum)
        ql.addWidget(self.mark_btn)
        ql.addStretch()
        ql.addWidget(self.elim_btn)
        self.right_layout.addWidget(qbar)

        self.prompt = QLabel()
        self.prompt.setObjectName("Prompt")
        self.prompt.setWordWrap(True)
        self.prompt.setTextFormat(Qt.RichText)
        self.prompt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.right_layout.addWidget(self.prompt)

        self.choices_box = QVBoxLayout()
        self.choices_box.setSpacing(12)
        self.right_layout.addLayout(self.choices_box)

        # Typed-answer box for student-produced response questions.
        self.spr_input = QLineEdit()
        self.spr_input.setMaxLength(6)
        self.spr_input.setFixedWidth(160)
        self.spr_input.textEdited.connect(self._spr_changed)
        self.spr_preview = QLabel()
        self.spr_preview.setObjectName("Subtle")
        self.right_layout.addWidget(self.spr_input)
        self.right_layout.addWidget(self.spr_preview)
        self.right_layout.addStretch()

        # Math has no passage, so the question sits in a centered column.
        center = QWidget()
        cl = QHBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        right.setMaximumWidth(820)
        cl.addWidget(right)
        self.question_area = _scroll(center)

        self.splitter.addWidget(self.passage_area)
        self.splitter.addWidget(self.question_area)
        self.splitter.setSizes([600, 600])
        return self.splitter

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Footer")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 10, 20, 10)
        name = QLabel("Practice Test")
        name.setObjectName("Subtle")
        self.nav_btn = QPushButton()
        self.nav_btn.setCursor(Qt.PointingHandCursor)
        self.nav_btn.setStyleSheet("font-weight: 600; border-radius: 6px;")
        self.nav_btn.clicked.connect(self._open_navigator)
        self.back_btn = make_button("Back", "primary")
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn = make_button("Next", "primary")
        self.next_btn.clicked.connect(self.go_next)
        lay.addWidget(name, 1)
        lay.addWidget(self.nav_btn, 0, Qt.AlignCenter)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.back_btn)
        buttons.addWidget(self.next_btn)
        lay.addLayout(buttons, 1)
        return bar

    # ----- showing a question -------------------------------------------------

    def _clear_choices(self) -> None:
        while self.choices_box.count():
            item = self.choices_box.takeAt(0)
            if item.widget():
                # Hide and detach right away; otherwise the old choices stay
                # on screen until Qt gets around to deleting them.
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()

    def show_question(self) -> None:
        if self.body.currentIndex() == 1:
            self._show_check_page()
            return
        q = self.m.questions[self.index]
        i = self.index

        self.qnum.setText(str(i + 1))
        self.mark_btn.blockSignals(True)
        self.mark_btn.setChecked(i in self.m.marked)
        self.mark_btn.setText(("⚑" if i in self.m.marked else "⚐") + "  Mark for Review")
        self.mark_btn.blockSignals(False)
        color = theme.colors()["mark"] if i in self.m.marked else theme.colors()["text"]
        self.mark_btn.setStyleSheet(f"color: {color};")

        self.passage_area.setVisible(bool(q.passage))
        self.passage.setText(to_display_html(q.passage))
        self.prompt.setText(to_display_html(q.prompt))

        self._clear_choices()
        is_mcq = q.qtype == "mcq"
        self.elim_btn.setVisible(is_mcq)
        self.spr_input.setVisible(not is_mcq)
        self.spr_preview.setVisible(not is_mcq)
        if is_mcq:
            chosen = self.m.answers.get(i)
            crossed = self.m.eliminated.get(i, set())
            for letter, text in zip(LETTERS, q.choices):
                row = ChoiceRow(letter, text)
                row.set_state(chosen == letter, letter in crossed, self.eliminator_on)
                row.picked.connect(self._pick)
                row.struck.connect(self._strike)
                self.choices_box.addWidget(row)
        else:
            self.spr_input.setText(self.m.answers.get(i, ""))
            self._spr_changed(self.spr_input.text(), save=False)

        total = len(self.m.questions)
        self.nav_btn.setText(f"Question {i + 1} of {total}  ▴")
        self.back_btn.setEnabled(i > 0)
        self.next_btn.setText("Next")

    def _record_time(self) -> None:
        now = time.monotonic()
        if self.body.currentIndex() == 0:
            self.m.seconds_on[self.index] = self.m.seconds_on.get(self.index, 0) + now - self.shown_at
        self.shown_at = now

    def goto(self, index: int) -> None:
        self._record_time()
        self.index = index
        self.body.setCurrentIndex(0)
        self.show_question()

    # ----- user actions -------------------------------------------------------

    def _pick(self, letter: str) -> None:
        i = self.index
        if letter in self.m.eliminated.get(i, set()):
            self.m.eliminated[i].discard(letter)  # picking a crossed-out choice restores it
        if self.m.answers.get(i) == letter:
            del self.m.answers[i]                 # click again to unselect
        else:
            self.m.answers[i] = letter
        self.show_question()

    def _strike(self, letter: str) -> None:
        crossed = self.m.eliminated.setdefault(self.index, set())
        if letter in crossed:
            crossed.discard(letter)
        else:
            crossed.add(letter)
            if self.m.answers.get(self.index) == letter:
                del self.m.answers[self.index]
        self.show_question()

    def _spr_changed(self, text: str, save: bool = True) -> None:
        allowed = "".join(ch for ch in text if ch in "0123456789./-")
        if allowed != text:
            self.spr_input.setText(allowed)
        if save:
            if allowed:
                self.m.answers[self.index] = allowed
            else:
                self.m.answers.pop(self.index, None)
        self.spr_preview.setText(f"Answer Preview: {allowed}" if allowed else "")

    def _toggle_mark(self, on: bool) -> None:
        (self.m.marked.add if on else self.m.marked.discard)(self.index)
        self.show_question()

    def _toggle_eliminator(self, on: bool) -> None:
        self.eliminator_on = on
        self.show_question()

    def go_back(self) -> None:
        if self.body.currentIndex() == 1:
            self.goto(len(self.m.questions) - 1)
        elif self.index > 0:
            self.goto(self.index - 1)

    def go_next(self) -> None:
        if self.body.currentIndex() == 1:
            self._submit()
        elif self.index < len(self.m.questions) - 1:
            self.goto(self.index + 1)
        else:
            self._record_time()
            self.body.setCurrentIndex(1)
            self._show_check_page()

    def _open_navigator(self) -> None:
        answered = set(self.m.answers)
        popup = NavigatorPopup(self, self.title, len(self.m.questions),
                               self.index if self.body.currentIndex() == 0 else -1,
                               answered, self.m.marked)
        popup.jump.connect(self.goto)
        popup.review.connect(lambda: (self._record_time(), self.body.setCurrentIndex(1),
                                      self._show_check_page()))
        popup.adjustSize()
        anchor = self.nav_btn.mapToGlobal(self.nav_btn.rect().topLeft())
        popup.move(anchor.x() + self.nav_btn.width() // 2 - popup.width() // 2,
                   anchor.y() - popup.height() - 8)
        popup.show()

    # ----- "Check Your Work" page ---------------------------------------------

    def _show_check_page(self) -> None:
        c = theme.colors()
        old = self.check_page.layout()
        if old is not None:
            QWidget().setLayout(old)  # standard Qt trick to throw away an old layout
        lay = QVBoxLayout(self.check_page)
        lay.setContentsMargins(40, 30, 40, 30)
        title = QLabel("Check Your Work")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        note = QLabel("On test day, you won't be able to move on to the next module until "
                      "time expires.<br>For practice, you can select <b>Next</b> when "
                      "you're ready to submit this module.")
        note.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(note)

        card = QFrame()
        card.setStyleSheet(f"QFrame {{ border: 1px solid {c['line']}; border-radius: 10px; }}"
                           "QLabel { border: none; }")
        cl = QVBoxLayout(card)
        unanswered = len(self.m.questions) - len(self.m.answers)
        head = QLabel(f"<b>{self.title} Questions</b> &nbsp; "
                      f"<span style='color:{c['muted']}'>{unanswered} unanswered, "
                      f"{len(self.m.marked)} marked for review</span>")
        head.setAlignment(Qt.AlignCenter)
        cl.addWidget(head)
        grid = QGridLayout()
        for i in range(len(self.m.questions)):
            b = QPushButton(str(i + 1) + (" ⚑" if i in self.m.marked else ""))
            b.setFixedSize(52, 44)
            b.setCursor(Qt.PointingHandCursor)
            if i in self.m.answers:
                style = f"background: {c['accent']}; color: {c['accent_text']}; border: none;"
            else:
                style = f"background: transparent; border: 1px dashed {c['muted']};"
            if i in self.m.marked and i not in self.m.answers:
                style += f"color: {c['mark']};"
            b.setStyleSheet(style + "border-radius: 4px; font-weight: 600;")
            b.clicked.connect(lambda _=False, n=i: self.goto(n))
            grid.addWidget(b, i // 10, i % 10)
        cl.addLayout(grid)
        lay.addWidget(card, 0, Qt.AlignHCenter)
        lay.addStretch()

        self.nav_btn.setText(f"Review  ▴")
        self.back_btn.setEnabled(True)
        self.next_btn.setText("Submit")

    # ----- timer --------------------------------------------------------------

    def _tick(self) -> None:
        self.remaining -= 1
        self._update_timer_label()
        if self.remaining == 5 * 60 and self.timer_label.isHidden():
            self._toggle_timer()  # Bluebook shows the timer for the last 5 minutes
        if self.remaining <= 0:
            self.clock.stop()
            QMessageBox.information(self, "Time's up", "Time is up for this module. "
                                    "Your answers have been submitted.")
            self._finish()

    def _update_timer_label(self) -> None:
        mins, secs = divmod(max(0, self.remaining), 60)
        self.timer_label.setText(f"{mins}:{secs:02d}")
        if self.remaining <= 5 * 60:
            self.timer_label.setStyleSheet(f"color: {theme.colors()['mark']};")

    def _toggle_timer(self) -> None:
        hidden = self.timer_label.isVisible()
        self.timer_label.setVisible(not hidden)
        self.hide_btn.setText("Show" if hidden else "Hide")

    # ----- dialogs and finishing ----------------------------------------------

    def _show_directions(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Directions")
        box.setTextFormat(Qt.RichText)
        box.setText(DIRECTIONS[self.m.section])
        box.exec()

    def _open_calculator(self) -> None:
        if self.calculator is None:
            self.calculator = CalculatorDialog(self)
        self.calculator.show()
        self.calculator.raise_()

    def _open_reference(self) -> None:
        if self.reference is None:
            self.reference = ReferenceDialog(self)
        self.reference.show()
        self.reference.raise_()

    def _submit(self) -> None:
        unanswered = len(self.m.questions) - len(self.m.answers)
        if unanswered:
            reply = QMessageBox.question(
                self, "Submit module?",
                f"You have {unanswered} unanswered question(s). Submit anyway?")
            if reply != QMessageBox.Yes:
                return
        self._finish()

    def _finish(self) -> None:
        self.clock.stop()
        self._record_time()
        for dlg in (self.calculator, self.reference):
            if dlg:
                dlg.close()
        self.finished.emit(self.m)

    def _confirm_quit(self) -> None:
        reply = QMessageBox.question(self, "Exit test?",
                                     "Exit this test? Your answers will not be saved.")
        if reply == QMessageBox.Yes:
            self.clock.stop()
            self.quit_requested.emit()
