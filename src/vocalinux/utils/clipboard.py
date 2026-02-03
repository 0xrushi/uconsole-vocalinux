"""Clipboard helpers."""

from __future__ import annotations

import shutil
import subprocess


_HAS_GTK = False
try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gtk

    _HAS_GTK = True
except Exception:
    _HAS_GTK = False


def set_clipboard_text(text: str) -> bool:
    """Set clipboard text.

    Prefer GTK clipboard when available (works in our tray process). Fall back
    to wl-copy/xclip/xsel.
    """
    t = text or ""

    # Try GTK clipboard (preferred)
    if _HAS_GTK:
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(t, -1)
            clipboard.store()
            return True
        except Exception:
            pass

    # wl-copy
    if shutil.which("wl-copy"):
        try:
            subprocess.run(["wl-copy"], input=t, text=True, check=True)
            return True
        except Exception:
            pass

    # xclip
    if shutil.which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"], input=t, text=True, check=True
            )
            return True
        except Exception:
            pass

    # xsel
    if shutil.which("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"], input=t, text=True, check=True
            )
            return True
        except Exception:
            pass

    return False
