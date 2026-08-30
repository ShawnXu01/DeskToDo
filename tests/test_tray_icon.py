from PyQt6.QtWidgets import QSystemTrayIcon

from deskcal.tray.tray_icon import TrayIcon


class _FakeWindow:
    def __init__(self):
        self.open_count = 0

    def open_config_panel(self) -> None:
        self.open_count += 1


def test_left_click_opens_config_panel_but_context_click_does_not():
    window = _FakeWindow()
    tray = type("FakeTray", (), {"_window": window})()

    TrayIcon._on_activated(tray, QSystemTrayIcon.ActivationReason.Trigger)
    TrayIcon._on_activated(tray, QSystemTrayIcon.ActivationReason.Context)

    assert window.open_count == 1
