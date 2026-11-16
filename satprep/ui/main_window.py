"""
The main window. It owns every screen and decides which one to show next:

  Home -> Loading -> Module 1 -> Loading -> Module 2 -> (next section...) -> Results

Writing questions with Claude takes a while, so it runs on a background
thread. Otherwise the window would freeze until the questions arrived.
The thread sends its results back with Qt "signals", which Qt delivers
safely on the main (screen) thread.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from .. import config
from ..bank import Bank
from ..generator import GenerationError
from ..testbuild import build_module, estimate_score, has_api_key, module_size, next_level
from .pages import HomePage, LoadingPage, ResultsPage, ReviewPage, StatsPage
from .test_view import TestPage


class ModuleBuilder(QObject):
    """Runs build_module() on a background thread and reports back with signals.

    It is a "daemon" thread, so quitting the app never waits for Claude.
    """

    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, bank: Bank, section: str, number: int, level: str, short: bool):
        super().__init__()
        self.args = (bank, section, number, level, short)

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            module = build_module(*self.args, on_progress=self.progress.emit)
        except GenerationError as e:
            self.failed.emit(str(e))
        except Exception as e:  # anything unexpected still gets shown, not swallowed
            self.failed.emit(f"Unexpected error: {e!r}")
        else:
            self.done.emit(module)


class MainWindow(QMainWindow):
    def __init__(self, bank: Bank):
        super().__init__()
        self.bank = bank
        self.setWindowTitle("SAT Practice")
        self.resize(1280, 820)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.home = HomePage()
        self.loading = LoadingPage()
        self.results = ResultsPage()
        self.review = ReviewPage()
        self.stats = StatsPage()
        for page in (self.home, self.loading, self.results, self.review, self.stats):
            self.stack.addWidget(page)
        self.test_page: TestPage | None = None
        self.stats_return_to = self.home

        self.home.start.connect(self.start_test)
        self.home.show_stats.connect(lambda: self.open_stats(self.home))
        self.home.reset_bank.connect(self.reset_bank)
        self.loading.retry.connect(self._build_next)
        self.loading.home.connect(self.go_home)
        self.results.review.connect(lambda: self.stack.setCurrentWidget(self.review))
        self.results.show_stats.connect(lambda: self.open_stats(self.results))
        self.results.home.connect(self.go_home)
        self.review.back.connect(lambda: self.stack.setCurrentWidget(self.results))
        self.stats.back.connect(lambda: self.stack.setCurrentWidget(self.stats_return_to))

        self.builder: ModuleBuilder | None = None
        self.go_home()

    # ----- navigation ---------------------------------------------------------

    def go_home(self) -> None:
        self._drop_test_page()
        self.home.refresh(self.bank.count(), self.bank.count(unused_only=True))
        self.stack.setCurrentWidget(self.home)

    def open_stats(self, came_from) -> None:
        self.stats_return_to = came_from
        self.stats.load(self.bank.skill_stats(), self.bank.past_tests())
        self.stack.setCurrentWidget(self.stats)

    def reset_bank(self) -> None:
        self.bank.reset_served()
        self.go_home()

    def _drop_test_page(self) -> None:
        if self.test_page is not None:
            self.stack.removeWidget(self.test_page)
            self.test_page.deleteLater()
            self.test_page = None

    # ----- running a test -----------------------------------------------------

    def start_test(self, settings: dict) -> None:
        self.settings = settings
        self.sections = ["rw", "math"] if settings["section"] == "both" else [settings["section"]]
        if not self._enough_hard_questions():
            return
        self.finished_modules = []
        # What to build next: (index into self.sections, module number, level)
        self.next_step = (0, 1, settings["level"])
        self._build_next()

    def _enough_hard_questions(self) -> bool:
        """
        For a "Hard only" test without an API key, check up front that every
        section has enough unseen hard questions for both modules, so the test
        can't run out halfway through.
        """
        if self.settings["level"] != "hard" or has_api_key():
            return True
        short_of = []
        for section in self.sections:
            needed = 2 * module_size(section, self.settings["short"])[0]
            have = self.bank.count(unused_only=True, section=section, difficulty="hard")
            if have < needed:
                short_of.append(f"{config.SECTIONS[section]['name']}: {have} unseen hard "
                                f"questions left, {needed} needed")
        if short_of:
            QMessageBox.information(
                self, "Not enough hard questions",
                "There aren't enough unseen hard questions for this test.\n\n"
                + "\n".join(short_of)
                + "\n\nTry a shorter test or one section, choose 'Make seen questions "
                  "available again', switch to Adaptive, or add an API key so Claude can "
                  "write new ones.")
            return False
        return True

    def _build_next(self) -> None:
        sec_i, number, level = self.next_step
        section = self.sections[sec_i]
        name = config.SECTIONS[section]["name"]
        count, _ = module_size(section, self.settings["short"])
        if number == 1:
            heading = f"Preparing {name}, Module 1"
        else:
            heading = f"Module 1 complete. Preparing {name}, Module 2"
        self.loading.begin(heading, count)
        self.stack.setCurrentWidget(self.loading)

        self.builder = ModuleBuilder(self.bank, section, number, level, self.settings["short"])
        self.builder.progress.connect(self.loading.progress)
        self.builder.done.connect(self._module_ready)
        self.builder.failed.connect(self.loading.failed)
        self.builder.start()

    def _module_ready(self, module) -> None:
        self._drop_test_page()
        section_number = self.next_step[0] + 1
        self.test_page = TestPage(module, section_number)
        self.test_page.finished.connect(self._module_finished)
        self.test_page.quit_requested.connect(self.go_home)
        self.stack.addWidget(self.test_page)
        self.stack.setCurrentWidget(self.test_page)

    def _module_finished(self, module) -> None:
        self.finished_modules.append(module)
        sec_i, number, _level = self.next_step
        if number == 1:
            self.next_step = (sec_i, 2, next_level(module))
        elif sec_i + 1 < len(self.sections):
            self.next_step = (sec_i + 1, 1, self.settings["level"])
        else:
            self._show_results()
            return
        self._build_next()

    def _show_results(self) -> None:
        self._drop_test_page()
        sections = []
        mods = self.finished_modules
        for m1, m2 in zip(mods[0::2], mods[1::2]):
            sections.append({
                "section": m1.section,
                "name": config.SECTIONS[m1.section]["name"],
                "score": estimate_score(m1, m2),
                "m1_correct": m1.num_correct(), "m1_total": len(m1.questions),
                "m2_correct": m2.num_correct(), "m2_total": len(m2.questions),
                "m2_level": m2.level,
            })
        summary = {"sections": sections, "level": self.settings["level"],
                   "short": self.settings["short"]}
        try:
            self.bank.save_test(summary, mods)
        except Exception as e:
            QMessageBox.warning(self, "Not saved", f"Your results could not be saved: {e}")
        self.results.show_results(summary)
        self.review.load(mods)
        self.stack.setCurrentWidget(self.results)
