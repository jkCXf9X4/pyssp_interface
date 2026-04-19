from __future__ import annotations

from pyssp_interface.app import _select_qt_platform, _xcb_platform_is_available


def test_xcb_platform_is_available_when_library_is_found(monkeypatch):
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: "libxcb-cursor.so.0")

    assert _xcb_platform_is_available() is True


def test_xcb_platform_is_not_available_when_library_is_missing(monkeypatch):
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: None)

    assert _xcb_platform_is_available() is False


def test_select_qt_platform_prefers_xcb_on_wayland_when_x11_is_available(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: "libxcb-cursor.so.0")

    assert _select_qt_platform(
        {
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":0",
        }
    ) == "xcb"


def test_select_qt_platform_respects_existing_qt_platform(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: "libxcb-cursor.so.0")

    assert _select_qt_platform(
        {
            "QT_QPA_PLATFORM": "wayland",
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":0",
        }
    ) is None


def test_select_qt_platform_leaves_pure_wayland_sessions_unchanged(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: "libxcb-cursor.so.0")

    assert _select_qt_platform(
        {
            "WAYLAND_DISPLAY": "wayland-0",
        }
    ) is None


def test_select_qt_platform_leaves_wayland_session_unchanged_without_xcb_support(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("pyssp_interface.app.find_library", lambda name: None)

    assert _select_qt_platform(
        {
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":0",
        }
    ) is None
