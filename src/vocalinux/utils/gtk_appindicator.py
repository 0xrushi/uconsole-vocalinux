"""
Utilities for loading GTK and AppIndicator bindings with graceful fallbacks.
"""

from __future__ import annotations

import importlib
from typing import Tuple

import gi


def load_gtk_appindicator() -> Tuple[object, object, str]:
    """Return Gtk/AppIndicator classes, using Ayatana fallback if needed."""

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk  # type: ignore

    for namespace in ("AppIndicator3", "AyatanaAppIndicator3"):
        try:
            gi.require_version(namespace, "0.1")
            indicator_module = importlib.import_module(f"gi.repository.{namespace}")
            return Gtk, indicator_module, namespace
        except (AttributeError, ImportError, ValueError):
            continue

    raise ImportError(
        "Neither AppIndicator3 nor AyatanaAppIndicator3 bindings are available. "
        "Install gir1.2-appindicator3-0.1 or gir1.2-ayatanaappindicator3-0.1."
    )
