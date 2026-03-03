"""Terminal emulator launcher for floating popup UI."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class TerminalLaunchSpec:
    argv: List[str]


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def build_terminal_launch(
    *,
    python_argv: List[str],
    title: str = "Vocalinux",
    wm_class: str = "vocalinux-popup",
    geometry: str = "100x30",
) -> TerminalLaunchSpec:
    """Build a terminal command to run python_argv.

    Tries common terminals in a fixed order.
    """

    if _which("kitty"):
        return TerminalLaunchSpec(
            argv=["kitty", "--class", wm_class, "--title", title, "-e", *python_argv]
        )

    if _which("alacritty"):
        # alacritty class is "instance,class"
        return TerminalLaunchSpec(
            argv=[
                "alacritty",
                "--class",
                f"{wm_class},{wm_class}",
                "-t",
                title,
                "-e",
                *python_argv,
            ]
        )

    if _which("gnome-terminal"):
        # gnome-terminal doesn't reliably expose WM_CLASS customization.
        return TerminalLaunchSpec(argv=["gnome-terminal", "--", *python_argv])

    if _which("xterm"):
        return TerminalLaunchSpec(
            argv=[
                "xterm",
                "-class",
                wm_class,
                "-title",
                title,
                "-geometry",
                geometry,
                "-e",
                *python_argv,
            ]
        )

    raise RuntimeError(
        "No supported terminal found. Install one of: kitty, alacritty, gnome-terminal, xterm"
    )


def parse_terminal_override(override: str) -> List[str]:
    """Parse a user-provided terminal command string."""
    return shlex.split(override)


def _run_capture(argv: List[str]) -> str:
    try:
        out = subprocess.check_output(argv, stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _get_display_geometry() -> Optional[tuple[int, int]]:
    if _which("xdotool"):
        out = _run_capture(["xdotool", "getdisplaygeometry"]).strip()
        parts = out.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])

    if _which("xrandr"):
        out = _run_capture(["xrandr", "--current"])
        for line in out.splitlines():
            if "current" in line and " x " in line:
                # Example: "Screen 0: minimum 8 x 8, current 1280 x 720, maximum ..."
                try:
                    seg = line.split("current", 1)[1]
                    dims = seg.split(",", 1)[0].strip()
                    w_str, h_str = [p.strip() for p in dims.split("x", 1)]
                    return int(w_str), int(h_str)
                except Exception:
                    continue

    return None


def _find_window_id(title: str, wm_class: str) -> Optional[str]:
    if not _which("wmctrl"):
        return None

    out = _run_capture(["wmctrl", "-lx"])
    for line in out.splitlines():
        # Format: 0x01200003  0 hostname WM_CLASS.WM_CLASS  Title
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        win_id, _, _, klass, win_title = parts
        if wm_class and wm_class in klass:
            return win_id
        if title and title in win_title:
            return win_id

    out = _run_capture(["wmctrl", "-l"])
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        win_id, _, _, win_title = parts
        if title and title in win_title:
            return win_id

    return None


def _get_window_size(window_id: str) -> Optional[tuple[int, int]]:
    out = _run_capture(["wmctrl", "-lG"])
    for line in out.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 6:
            continue
        win_id = parts[0]
        if win_id.lower() != window_id.lower():
            continue
        try:
            w = int(parts[4])
            h = int(parts[5])
            return w, h
        except Exception:
            return None
    return None


def center_window(
    *,
    title: str,
    wm_class: str,
    attempts: int = 12,
    delay_seconds: float = 0.1,
) -> bool:
    """Best-effort window centering using wmctrl/xdotool/xrandr."""
    if not _which("wmctrl"):
        return False

    display = _get_display_geometry()
    if not display:
        return False
    disp_w, disp_h = display

    for _ in range(attempts):
        win_id = _find_window_id(title, wm_class)
        if not win_id:
            time.sleep(delay_seconds)
            continue

        size = _get_window_size(win_id)
        if not size:
            time.sleep(delay_seconds)
            continue

        win_w, win_h = size
        x = max(0, int((disp_w - win_w) / 2))
        y = max(0, int((disp_h - win_h) / 2))

        _run_capture(["wmctrl", "-ir", win_id, "-e", f"0,{x},{y},{win_w},{win_h}"])
        return True

    return False
