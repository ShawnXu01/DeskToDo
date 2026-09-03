"""使用系统默认应用打开课程的 Syllabus 或课程网页。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


def open_course_resource(target: str) -> tuple[bool, str]:
    value = target.strip()
    if not value:
        return False, ""

    url = QUrl(value)
    scheme = url.scheme().lower()
    if scheme in {"http", "https"}:
        if not url.isValid() or not url.host():
            return False, "课程资料网址无效，请在课程设置中检查。"
    elif scheme == "file":
        path = Path(url.toLocalFile())
        if not path.is_file():
            return False, f"找不到课程资料文件：\n{path}"
        url = QUrl.fromLocalFile(str(path))
    else:
        path = Path(value).expanduser()
        if not path.is_file():
            return False, f"找不到课程资料文件：\n{path}"
        url = QUrl.fromLocalFile(str(path.resolve()))

    if not QDesktopServices.openUrl(url):
        return False, "系统无法打开该课程资料，请检查默认浏览器或 PDF 阅读器设置。"
    return True, ""
