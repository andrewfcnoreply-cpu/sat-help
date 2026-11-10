"""
Colors and styles for light and dark mode.

All colors live in two dictionaries (LIGHT and DARK). The style sheet below
is like CSS for Qt widgets: it refers to colors by name, so switching themes
just means filling in the other dictionary.

Widgets get a style by name with setObjectName("...") or by a "class"
property, which the style sheet matches as #name or [class="..."].
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

LIGHT = {
    "bg": "#ffffff",
    "surface": "#f4f6fa",       # header, footer, side panels
    "surface2": "#e9edf5",
    "text": "#1a1a1a",
    "muted": "#5b6170",
    "border": "#1a1a1a",        # answer-choice outline (Bluebook uses dark outlines)
    "line": "#d4d9e3",          # thin dividers
    "accent": "#3248c4",        # main blue
    "accent_text": "#ffffff",
    "accent_soft": "#e6eaff",
    "mark": "#c8283c",          # mark-for-review red
    "good": "#1e7d4f",
    "bad": "#c8283c",
    "strike": "#8a8f9c",
}

DARK = {
    "bg": "#16181d",
    "surface": "#1f2229",
    "surface2": "#2a2e37",
    "text": "#eceef2",
    "muted": "#a3a9b7",
    "border": "#c9ceda",
    "line": "#343844",
    "accent": "#8193ff",
    "accent_text": "#0d1020",
    "accent_soft": "#262c4d",
    "mark": "#ff6b7d",
    "good": "#5fd39a",
    "bad": "#ff6b7d",
    "strike": "#7d8394",
}

READING_FONT = "Georgia"   # serif font for passages and questions


def _style_sheet(c: dict) -> str:
    return f"""
    QWidget {{ background: {c['bg']}; color: {c['text']}; font-size: 14px; }}
    QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 1px solid {c['line']}; }}

    #Header, #Footer {{ background: {c['surface']}; }}
    #Header QLabel, #Footer QLabel {{ background: transparent; }}
    #HeaderRule {{ background: {c['line']}; max-height: 2px; min-height: 2px; }}
    #Timer {{ font-size: 20px; font-weight: 600; }}
    #SectionTitle {{ font-size: 16px; font-weight: 600; }}
    #PageTitle {{ font-size: 28px; font-weight: 700; }}
    #Subtle {{ color: {c['muted']}; }}

    QPushButton {{
        background: transparent; color: {c['text']}; border: 1px solid {c['line']};
        border-radius: 12px; padding: 6px 16px;
    }}
    QPushButton:hover {{ background: {c['surface2']}; }}
    QPushButton:disabled {{ color: {c['muted']}; }}
    QPushButton[class="primary"] {{
        background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600;
    }}
    QPushButton[class="primary"]:hover {{ background: {c['accent']}; }}
    QPushButton[class="primary"]:disabled {{ background: {c['line']}; color: {c['muted']}; }}
    QPushButton[class="tool"] {{ border: none; border-radius: 6px; padding: 6px 10px; }}
    QPushButton[class="tool"]:checked {{ background: {c['accent_soft']}; color: {c['accent']}; }}
    QPushButton[class="chip"] {{ border-radius: 8px; padding: 10px 14px; text-align: left; }}
    QPushButton[class="chip"]:checked {{
        border: 2px solid {c['accent']}; background: {c['accent_soft']};
    }}

    #QuestionBar {{ background: {c['surface']}; border-bottom: 2px dashed {c['line']}; }}
    #QuestionBar QLabel {{ background: transparent; }}
    #QuestionBar #QNumber {{
        background: {c['text']}; color: {c['bg']}; font-weight: 700;
        min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
        qproperty-alignment: AlignCenter;
    }}

    #Passage, #Prompt {{ font-family: "{READING_FONT}"; font-size: 17px; }}
    #Passage {{ background: {c['bg']}; }}

    QSplitter::handle {{ background: {c['line']}; width: 4px; }}
    QScrollArea {{ border: none; }}
    QLineEdit {{
        border: 1px solid {c['border']}; border-radius: 6px; padding: 8px;
        font-size: 18px; background: {c['bg']};
    }}
    QComboBox, QSpinBox {{
        border: 1px solid {c['line']}; border-radius: 6px; padding: 4px 8px;
    }}
    QProgressBar {{
        border: none; background: {c['surface2']}; border-radius: 5px; height: 10px;
        text-align: center; color: transparent;
    }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}
    QListWidget, QTableWidget, QTextBrowser {{
        border: 1px solid {c['line']}; border-radius: 8px; background: {c['bg']};
    }}
    QHeaderView::section {{
        background: {c['surface']}; border: none; padding: 6px; font-weight: 600;
    }}
    QListWidget::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['line']}; }}
    QMenu::item:selected {{ background: {c['accent_soft']}; }}
    """


class ThemeManager(QObject):
    """Keeps track of light/dark mode and tells widgets when it changes."""

    changed = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.mode = "system"  # "system", "light", or "dark"
        # Follow the Mac's appearance setting while in "system" mode.
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _s: self.apply())

    @property
    def colors(self) -> dict:
        if self.mode == "light":
            return LIGHT
        if self.mode == "dark":
            return DARK
        scheme = QGuiApplication.styleHints().colorScheme()
        return DARK if scheme == Qt.ColorScheme.Dark else LIGHT

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.apply()

    def apply(self) -> None:
        self.app.setStyleSheet(_style_sheet(self.colors))
        self.changed.emit()


_manager: ThemeManager | None = None


def install(app) -> ThemeManager:
    global _manager
    _manager = ThemeManager(app)
    _manager.apply()
    return _manager


def manager() -> ThemeManager:
    assert _manager is not None, "theme.install(app) must run first"
    return _manager


def colors() -> dict:
    return manager().colors
