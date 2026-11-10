"""
Start the SAT Practice app.

Run it from Xcode (see README.md) or from Terminal:
    python3 main.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from satprep.bank import Bank
from satprep.ui import theme
from satprep.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SAT Practice")

    # On a Mac this is ~/Library/Application Support/SAT Practice/
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    bank = Bank(data_dir / "sat_practice.db")

    theme.install(app)
    window = MainWindow(bank)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
