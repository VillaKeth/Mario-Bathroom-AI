"""Pure helpers for the scrollable VN chat backlog (client/mario_display.py)."""
from client.chat_backlog import _clamp_chat_scroll, _wrap_text


class TestClampScroll:
    def test_bottom_is_zero(self):
        assert _clamp_chat_scroll(0, 100, 10) == 0

    def test_caps_at_top(self):
        # 100 lines, 10 visible -> max scroll-up is 90
        assert _clamp_chat_scroll(999, 100, 10) == 90

    def test_no_scroll_when_everything_fits(self):
        assert _clamp_chat_scroll(5, 8, 10) == 0

    def test_negative_clamped_to_zero(self):
        assert _clamp_chat_scroll(-3, 100, 10) == 0


class TestWrapText:
    def test_short_line_unchanged(self):
        assert _wrap_text("hello there", 20) == ["hello there"]

    def test_wraps_on_word_boundary(self):
        assert _wrap_text("aaa bbb ccc", 7) == ["aaa bbb", "ccc"]

    def test_hard_splits_overlong_word(self):
        assert _wrap_text("xxxxxxxx", 4) == ["xxxx", "xxxx"]

    def test_empty_is_single_blank(self):
        assert _wrap_text("", 10) == [""]
