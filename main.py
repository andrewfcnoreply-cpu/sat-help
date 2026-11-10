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
from satprep.pack import load_pack
from satprep.ui import theme
from satprep.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SAT Practice")

    # On a Mac this is ~/Library/Application Support/SAT Practice/
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    bank = Bank(data_dir / "sat_practice.db")

    # Add any built-in questions (from the questions/ folder) not saved yet.
    try:
        added = bank.add_if_new(load_pack())
        if added:
            print(f"Added {added} built-in questions to your bank.")
    except Exception as e:  # a broken pack file shouldn't stop the app
        print(f"Could not load the built-in questions: {e}")

    theme.install(app)
    window = MainWindow(bank)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
