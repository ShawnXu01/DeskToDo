"""仅供测试用：当本机 PyQt6 因环境问题无法导入时，注册一个最小化的假 PyQt6，
让只用到 QWidget/QTimer 作为基类或类型引用的纯逻辑模块能被正常 import。

不修改任何生产代码；一旦本机 PyQt6 环境修好，这个 stub 会被真实的 PyQt6 自然覆盖
（因为我们先尝试真实 import，只有失败才注册 stub）。
"""
import sys
import types


def ensure_pyqt6_importable() -> None:
    try:
        import PyQt6.QtCore  # noqa: F401
        import PyQt6.QtWidgets  # noqa: F401
        return
    except ImportError:
        pass

    qtcore = types.ModuleType("PyQt6.QtCore")

    class _DummySignal:
        def connect(self, *_a, **_k):
            pass

        def emit(self, *_a, **_k):
            pass

    class _DummyTimer:
        def __init__(self, *_a, **_k):
            self.timeout = _DummySignal()

        def start(self, *_a, **_k):
            pass

    class _DummyThread:
        def __init__(self, *_a, **_k):
            pass

        def isRunning(self):
            return False

        def start(self):
            pass

    class _AlignmentFlag:
        AlignCenter = 0

    class _Qt:
        AlignmentFlag = _AlignmentFlag

    qtcore.QTimer = _DummyTimer
    qtcore.QThread = _DummyThread
    qtcore.pyqtSignal = lambda *_a, **_k: _DummySignal()
    qtcore.Qt = _Qt

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")

    class _DummyWidget:
        def __init__(self, *_a, **_k):
            pass

    for name in ("QWidget", "QLabel", "QVBoxLayout", "QHBoxLayout", "QProgressBar"):
        setattr(qtwidgets, name, _DummyWidget)

    pyqt6_pkg = types.ModuleType("PyQt6")
    sys.modules["PyQt6"] = pyqt6_pkg
    sys.modules["PyQt6.QtCore"] = qtcore
    sys.modules["PyQt6.QtWidgets"] = qtwidgets
