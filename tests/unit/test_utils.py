"""Tests for core.utils module."""

import pytest

from core.utils import coerce_bool, normalize_whitespace


class TestCoerceBool:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (True, True),
            (False, False),
            ("1", True),
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("Yes", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("off", False),
            ("", False),
            ("random", False),
            (1, True),
            (0, False),
            (None, False),
        ],
    )
    def test_coerce_bool(self, value, expected):
        assert coerce_bool(value) == expected


class TestNormalizeWhitespace:
    def test_collapses_multiple_spaces(self):
        assert normalize_whitespace("a  b   c") == "a b c"

    def test_collapses_tabs_and_newlines(self):
        assert normalize_whitespace("a\tb\nc") == "a b c"

    def test_strips_leading_trailing(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_lowercase_when_requested(self):
        assert normalize_whitespace("Hello World", lower=True) == "hello world"

    def test_preserves_case_by_default(self):
        assert normalize_whitespace("Hello World") == "Hello World"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""

    def test_only_whitespace(self):
        assert normalize_whitespace("   \t\n  ") == ""
