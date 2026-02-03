"""Tests for clipboard helper."""

import sys
import unittest
from unittest.mock import MagicMock, patch


from vocalinux.utils.clipboard import set_clipboard_text


class TestClipboard(unittest.TestCase):
    def test_falls_back_to_wl_copy(self):
        # Force GTK path to fail without patching __import__
        with patch.dict(sys.modules, {"gi": None}):
            with patch(
                "vocalinux.utils.clipboard.shutil.which",
                side_effect=lambda c: "/usr/bin/wl-copy" if c == "wl-copy" else None,
            ):
                mock_run = MagicMock()
                with patch("vocalinux.utils.clipboard.subprocess.run", mock_run):
                    ok = set_clipboard_text("hello")

        self.assertTrue(ok)
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.kwargs["input"], "hello")

    def test_falls_back_to_xclip(self):
        def which(cmd):
            return "/usr/bin/xclip" if cmd == "xclip" else None

        with patch.dict(sys.modules, {"gi": None}):
            with patch("vocalinux.utils.clipboard.shutil.which", side_effect=which):
                mock_run = MagicMock()
                with patch("vocalinux.utils.clipboard.subprocess.run", mock_run):
                    ok = set_clipboard_text("hello")

        self.assertTrue(ok)
        args = mock_run.call_args.args[0]
        self.assertEqual(args[:2], ["xclip", "-selection"])
