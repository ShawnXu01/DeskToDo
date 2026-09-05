from deskcal.utils.monitor import compute_screen_signature, describe_screen


class _Geometry:
    def width(self):
        return 2560

    def height(self):
        return 1440


class _Screen:
    def name(self):
        return "DISPLAY2"

    def geometry(self):
        return _Geometry()

    def devicePixelRatio(self):
        return 1.25


def test_screen_signature_uses_display_name_size_and_scale():
    screen = _Screen()

    assert compute_screen_signature(screen) == "DISPLAY2:2560x1440:1.25"
    assert describe_screen(screen) == "DISPLAY2 · 2560×1440 · 1.25× 缩放"
