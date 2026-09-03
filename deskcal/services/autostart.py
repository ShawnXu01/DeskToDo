"""开机自启：静默读写 Windows 注册表 Run 键，失败时不弹错误（静默容错）。"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path
from typing import Optional

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DeskCal"


def _default_command() -> str:
    """打包后 sys.executable 就是程序本身；开发环境下是裸 python.exe，
    必须显式带上 -m deskcal.main 才能真正启动程序，否则只会弹出一个空的 Python 控制台。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" -m deskcal.main --background'


def enable_autostart(target_path: Optional[str] = None) -> None:
    command = target_path or _default_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    except OSError:
        pass


def disable_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass
