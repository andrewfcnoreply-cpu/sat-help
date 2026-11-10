"""
Reusable pieces of the test screen: answer choices, the question navigator,
the calculator, and the math reference sheet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget, QCheckBox,
)

from .. import calc
from ..textfmt import to_display_html
from . import theme


def make_button(text: str, kind: str | None = None, checkable: bool = False) -> QPushButton:
    """Shortcut for a styled button. kind: None, "primary", "tool", or "chip"."""
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setCheckable(checkable)
    if kind:
        b.setProperty("class", kind)
    return b


# ---------------------------------------------------------------------------
# One answer choice (A, B, C, or D)
# ---------------------------------------------------------------------------

class ChoiceRow(QWidget):
    """
    A Bluebook-style answer choice: a rounded box with a letter circle and
    the choice text. When the eliminator is on, a small button to the right
    crosses the choice out.
    """

    picked = Signal(str)       # letter
    struck = Signal(str)       # letter

    def __init__(self, letter: str, text: str):
        super().__init__()
        self.letter = letter
        self.text = text
        self.selected = False
        self.crossed = False

        self.box = QFrame()
        self.box.setCursor(Qt.PointingHandCursor)
        self.box.mousePressEvent = lambda _e: self.picked.emit(self.letter)

        self.circle = QLabel(letter)
        self.circle.setFixedSize(28, 28)
        self.circle.setAlignment(Qt.AlignCenter)

        self.label = QLabel()
        self.label.setObjectName("Prompt")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)

        inner = QHBoxLayout(self.box)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(12)
        inner.addWidget(self.circle, 0, Qt.AlignTop)
        inner.addWidget(self.label, 1)

        self.strike_btn = QPushButton(letter)
        self.strike_btn.setFixedSize(30, 30)
        self.strike_btn.setCursor(Qt.PointingHandCursor)
        self.strike_btn.setToolTip(f"Cross out choice {letter}")
        self.strike_btn.clicked.connect(lambda: self.struck.emit(self.letter))

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.box, 1)
        # A fixed-width holder keeps every choice box the same width,
        # whether the button says a letter or "Undo".
        self.strike_holder = QWidget()
        self.strike_holder.setFixedWidth(56)
        hl = QHBoxLayout(self.strike_holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.strike_btn, 0, Qt.AlignCenter)
        self.strike_holder.hide()
        row.addWidget(self.strike_holder, 0, Qt.AlignVCenter)
        self.refresh()

    def set_state(self, selected: bool, crossed: bool, eliminator_on: bool) -> None:
        self.selected, self.crossed = selected, crossed
        self.strike_holder.setVisible(eliminator_on)
        self.strike_btn.setText("Undo" if crossed else self.letter)
        self.strike_btn.setFixedWidth(52 if crossed else 30)
        self.refresh()

    def refresh(self) -> None:
        c = theme.colors()
        border = c["accent"] if self.selected else c["border"]
        width = 3 if self.selected else 1
        self.box.setStyleSheet(
            f"QFrame {{ border: {width}px solid {border}; border-radius: 8px; background: {c['bg']}; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )
        circle_bg = c["accent"] if self.selected else "transparent"
        circle_fg = c["accent_text"] if self.selected else c["text"]
        self.circle.setStyleSheet(
            f"border: 1.5px solid {c['accent'] if self.selected else c['border']};"
            f"border-radius: 14px; background: {circle_bg}; color: {circle_fg}; font-weight: 700;"
        )
        body = to_display_html(self.text)
        if self.crossed:
            body = f"<s style='color:{c['strike']}'>{body}</s>"
        self.label.setText(body)
        self.strike_btn.setStyleSheet(
            f"border: 1px solid {c['border']}; border-radius: 15px; font-size: 12px; padding: 0;"
            + ("text-decoration: none;" if self.crossed else "text-decoration: line-through;")
        )


# ---------------------------------------------------------------------------
# Question navigator popup ("Question 3 of 27" at the bottom)
# ---------------------------------------------------------------------------

class NavigatorPopup(QFrame):
    """Grid of question numbers showing answered, unanswered, and marked."""

    jump = Signal(int)
    review = Signal()

    def __init__(self, parent, title: str, total: int, current: int,
                 answered: set[int], marked: set[int]):
        super().__init__(parent, Qt.Popup)
        c = theme.colors()
        self.setStyleSheet(
            f"NavigatorPopup {{ background: {c['bg']}; border: 1px solid {c['line']};"
            f" border-radius: 10px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)

        head = QLabel(f"<b>{title} Questions</b>")
        head.setAlignment(Qt.AlignCenter)
        lay.addWidget(head)
        legend = QLabel(
            f"<span style='color:{c['accent']}'>&#9679;</span> Current &nbsp;&nbsp;"
            f"<span style='color:{c['muted']}'>&#9634;</span> Unanswered &nbsp;&nbsp;"
            f"<span style='color:{c['mark']}'>&#9873;</span> For Review")
        legend.setAlignment(Qt.AlignCenter)
        lay.addWidget(legend)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i in range(total):
            b = QPushButton(str(i + 1) + (" ⚑" if i in marked else ""))
            b.setFixedSize(46, 40)
            b.setCursor(Qt.PointingHandCursor)
            if i in answered:
                style = f"background: {c['accent']}; color: {c['accent_text']}; border: none;"
            else:
                style = f"background: transparent; border: 1px dashed {c['muted']};"
            if i == current:
                style += f"border: 3px solid {c['text']};"
            if i in marked:
                style += f"color: {c['mark'] if i not in answered else c['accent_text']};"
            b.setStyleSheet(style + "border-radius: 4px; font-weight: 600; padding: 0;")
            b.clicked.connect(lambda _=False, n=i: (self.jump.emit(n), self.close()))
            grid.addWidget(b, i // 10, i % 10)
        lay.addLayout(grid)

        go = make_button("Go to Review Page")
        go.clicked.connect(lambda: (self.review.emit(), self.close()))
        lay.addWidget(go, 0, Qt.AlignCenter)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class CalculatorDialog(QDialog):
    """A floating scientific calculator, plus a link to the Desmos graphing calculator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setWindowFlag(Qt.Tool)
        self.resize(360, 460)

        self.history = QListWidget()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type, e.g. 3^2 + sqrt(16)")
        self.input.returnPressed.connect(self.calculate)
        self.degrees = QCheckBox("Degrees (for sin, cos, tan)")
        self.degrees.setChecked(True)
        self.error = QLabel()
        self.error.setObjectName("Subtle")

        keys = QGridLayout()
        for n, token in enumerate(["sqrt(", "^", "π", "(", ")",
                                   "sin(", "cos(", "tan(", "log(", "ln("]):
            b = make_button(token if token == "(" else token.rstrip("("))
            b.clicked.connect(lambda _=False, t=token: self.insert(t))
            keys.addWidget(b, n // 5, n % 5)

        desmos = make_button("Open Desmos graphing calculator")
        desmos.setToolTip("Opens desmos.com in your web browser")
        desmos.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.desmos.com/calculator")))

        lay = QVBoxLayout(self)
        lay.addWidget(self.history, 1)
        lay.addWidget(self.input)
        lay.addWidget(self.error)
        lay.addLayout(keys)
        lay.addWidget(self.degrees)
        lay.addWidget(desmos)

    def insert(self, token: str) -> None:
        self.input.insert(token)
        self.input.setFocus()

    def calculate(self) -> None:
        expr = self.input.text().strip()
        if not expr:
            return
        try:
            value = calc.evaluate(expr, degrees=self.degrees.isChecked())
        except ValueError as e:
            self.error.setText(str(e))
            return
        self.error.setText("")
        self.history.addItem(f"{expr}  =  {calc.format_number(value)}")
        self.history.scrollToBottom()
        self.input.setText(calc.format_number(value))
        self.input.selectAll()


# ---------------------------------------------------------------------------
# Math reference sheet
# ---------------------------------------------------------------------------

REFERENCE_HTML = """
<h3>Reference</h3>
<table cellpadding="6">
<tr><td><b>Circle</b></td><td>A = πr<sup>2</sup> &nbsp;&nbsp; C = 2πr</td></tr>
<tr><td><b>Rectangle</b></td><td>A = ℓw</td></tr>
<tr><td><b>Triangle</b></td><td>A = ½bh</td></tr>
<tr><td><b>Pythagorean theorem</b></td><td>c<sup>2</sup> = a<sup>2</sup> + b<sup>2</sup></td></tr>
<tr><td><b>30°-60°-90° triangle</b></td><td>sides x, x√3, 2x</td></tr>
<tr><td><b>45°-45°-90° triangle</b></td><td>sides s, s, s√2</td></tr>
<tr><td><b>Rectangular prism</b></td><td>V = ℓwh</td></tr>
<tr><td><b>Cylinder</b></td><td>V = πr<sup>2</sup>h</td></tr>
<tr><td><b>Sphere</b></td><td>V = (4/3)πr<sup>3</sup></td></tr>
<tr><td><b>Cone</b></td><td>V = (1/3)πr<sup>2</sup>h</td></tr>
<tr><td><b>Pyramid</b></td><td>V = (1/3)ℓwh</td></tr>
</table>
<p>The number of degrees of arc in a circle is 360.<br>
The number of radians of arc in a circle is 2π.<br>
The sum of the measures in degrees of the angles of a triangle is 180.</p>
"""


class ReferenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reference Sheet")
        self.setWindowFlag(Qt.Tool)
        self.resize(420, 520)
        view = QTextBrowser()
        view.setHtml(REFERENCE_HTML)
        lay = QVBoxLayout(self)
        lay.addWidget(view)
