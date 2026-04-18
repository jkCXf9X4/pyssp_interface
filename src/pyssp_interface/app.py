from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pyssp_interface.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    app = QApplication(argv)
    window = MainWindow()
    window.show()
    return app.exec()

