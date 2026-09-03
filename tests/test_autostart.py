from deskcal.services import autostart


def test_frozen_autostart_command_uses_background_mode(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\Program Files\DeskToDo\DeskToDo.exe")

    assert autostart._default_command() == (
        r'"C:\Program Files\DeskToDo\DeskToDo.exe" --background'
    )
