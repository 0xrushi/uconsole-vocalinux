"""Tests for terminal launcher selection."""

import unittest
from unittest.mock import patch


from vocalinux.ui.terminal_launcher import build_terminal_launch


class TestTerminalLauncher(unittest.TestCase):
    def test_prefers_kitty(self):
        def which(cmd):
            return "/usr/bin/kitty" if cmd == "kitty" else None

        with patch("vocalinux.ui.terminal_launcher.shutil.which", side_effect=which):
            spec = build_terminal_launch(python_argv=["python", "-c", "print(1)"])

        self.assertEqual(spec.argv[0], "kitty")
        self.assertIn("-e", spec.argv)

    def test_falls_back_to_xterm(self):
        def which(cmd):
            return "/usr/bin/xterm" if cmd == "xterm" else None

        with patch("vocalinux.ui.terminal_launcher.shutil.which", side_effect=which):
            spec = build_terminal_launch(python_argv=["python", "-c", "print(1)"])

        self.assertEqual(spec.argv[0], "xterm")
        self.assertIn("-e", spec.argv)

    def test_raises_when_no_terminal(self):
        with patch("vocalinux.ui.terminal_launcher.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                build_terminal_launch(python_argv=["python", "-c", "print(1)"])
