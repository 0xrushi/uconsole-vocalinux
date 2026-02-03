"""Terminal emulator launcher for floating popup UI."""

from __future__ import annotations

import shlex
import shutil
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
