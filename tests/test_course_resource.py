from pathlib import Path

from PyQt6.QtCore import QUrl

from deskcal.ui.schedule import course_resource


def test_open_course_web_uses_system_handler(monkeypatch):
    opened: list[QUrl] = []
    monkeypatch.setattr(course_resource.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

    success, error = course_resource.open_course_resource("https://example.edu/course")

    assert success
    assert error == ""
    assert opened[0].toString() == "https://example.edu/course"


def test_open_local_syllabus_uses_file_url(tmp_path, monkeypatch):
    syllabus = tmp_path / "syllabus.pdf"
    syllabus.write_bytes(b"%PDF-1.4")
    opened: list[QUrl] = []
    monkeypatch.setattr(course_resource.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

    success, error = course_resource.open_course_resource(str(syllabus))

    assert success
    assert error == ""
    assert opened[0].isLocalFile()
    assert Path(opened[0].toLocalFile()) == syllabus.resolve()


def test_missing_local_syllabus_reports_error(tmp_path):
    success, error = course_resource.open_course_resource(str(tmp_path / "missing.pdf"))

    assert not success
    assert "找不到课程资料文件" in error
