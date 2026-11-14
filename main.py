"""
Start the SAT Practice app.

Run it from Xcode (see README.md) or from Terminal:
    python3 main.py
"""

import os
import sys
from pathlib import Path

import PySide6


def _point_qt_at_its_plugins() -> None:
    """
    Tell Qt exactly where its plugins are before any window is made.

    Without this, Qt sometimes can't find the plugin that draws windows on a
    Mac ("cocoa") and the app quits with "Could not find the Qt platform
    plugin". Leftover Qt settings from other programs (such as Anaconda) are
    a common cause, so we replace them with the right folder.
    """
    plugins = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins"
    if not (plugins / "platforms").is_dir():
        sys.exit(
            "PySide6 looks incomplete: its Qt plugins folder is missing.\n"
            f"Expected: {plugins / 'platforms'}\n"
            "Fix it by reinstalling:  ./.venv/bin/pip install --force-reinstall PySide6==6.12.0"
        )
    if sys.platform == "darwin":
        os.environ.pop("QT_QPA_PLATFORM", None)  # on a Mac, always use the normal "cocoa" display
    os.environ["QT_PLUGIN_PATH"] = str(plugins)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")


_point_qt_at_its_plugins()

from PySide6.QtCore import QStandardPaths  # noqa: E402  (must come after the fix above)
from PySide6.QtWidgets import QApplication  # noqa: E402

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
