from __future__ import annotations

from ctypes.util import find_library
import os
import sys

from pyssp_interface.main_window import MainWindow


def _xcb_platform_is_available() -> bool:
    return find_library("xcb-cursor") is not None


def _select_qt_platform(env: dict[str, str] | None = None) -> str | None:
    env = env if env is not None else os.environ
    if sys.platform != "linux":
        return None

    if env.get("QT_QPA_PLATFORM"):
        return None

    # Prefer XWayland when both displays are available. Native Qt Wayland has
    # been less stable in some compositor environments used for development.
    if env.get("WAYLAND_DISPLAY") and env.get("DISPLAY") and _xcb_platform_is_available():
        return "xcb"

    return None


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    platform = _select_qt_platform()
    if platform is not None:
        os.environ["QT_QPA_PLATFORM"] = platform
        print(
            f"pyssp-interface: using Qt platform '{platform}' for startup stability",
            file=sys.stderr,
        )

    from PySide6.QtWidgets import QApplication

    app = QApplication(argv)
    window = MainWindow()
    window.show()
    return app.exec()
