"""Tests for terminal popup helpers (non-curses)."""

import os
import tempfile
import unittest


from vocalinux.ui import terminal_popup as tp


class TestTerminalPopupHelpers(unittest.TestCase):
    def test_read_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "missing.txt")
            self.assertEqual(tp._read_text(path), "")

    def test_write_and_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sub", "out.txt")
            tp._write_text(path, "abc")
            self.assertEqual(tp._read_text(path), "abc")

    def test_normalize_and_join(self):
        self.assertEqual(tp._normalize_lines(""), [""])
        self.assertEqual(tp._normalize_lines("a\n"), ["a"])
        self.assertEqual(tp._join_lines(["a", "b"]), "a\nb\n")

    def test_basic_editing_ops(self):
        st = tp._EditorState(lines=["hi"], cy=0, cx=2)
        tp._insert_char(st, "!")
        self.assertEqual(st.lines[0], "hi!")
        tp._backspace(st)
        self.assertEqual(st.lines[0], "hi")
        tp._newline(st)
        self.assertEqual(st.lines, ["hi", ""])
