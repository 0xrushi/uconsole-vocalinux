"""Terminal-based popup (floating terminal window + curses UI).

This is used for popup-after-record when the user prefers a terminal UI. The
main daemon/tray process launches a terminal emulator that runs this module.
The terminal UI writes the final text to an output file, which the main process
copies to clipboard and uses to arm the global paste trigger.
"""

from __future__ import annotations

import argparse
import curses
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

from ..llm.gemini_client import GeminiClient, GeminiRequest
from ..llm.llm_config import load_llm_config
from ..llm.prompts import prompt_correct_bash, prompt_correct_email, prompt_correct_post


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_text(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _normalize_lines(text: str) -> List[str]:
    lines = (text or "").splitlines()
    return lines if lines else [""]


def _join_lines(lines: List[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class _EditorState:
    lines: List[str]
    cy: int = 0
    cx: int = 0
    scroll: int = 0
    command_mode: bool = False
    status: str = ""


def _clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def _ensure_cursor_in_bounds(st: _EditorState) -> None:
    st.cy = _clamp(st.cy, 0, max(0, len(st.lines) - 1))
    line = st.lines[st.cy]
    st.cx = _clamp(st.cx, 0, len(line))


def _insert_char(st: _EditorState, ch: str) -> None:
    line = st.lines[st.cy]
    st.lines[st.cy] = line[: st.cx] + ch + line[st.cx :]
    st.cx += len(ch)


def _backspace(st: _EditorState) -> None:
    if st.cx > 0:
        line = st.lines[st.cy]
        st.lines[st.cy] = line[: st.cx - 1] + line[st.cx :]
        st.cx -= 1
        return

    if st.cy > 0:
        prev = st.lines[st.cy - 1]
        cur = st.lines[st.cy]
        st.cx = len(prev)
        st.lines[st.cy - 1] = prev + cur
        del st.lines[st.cy]
        st.cy -= 1


def _delete(st: _EditorState) -> None:
    line = st.lines[st.cy]
    if st.cx < len(line):
        st.lines[st.cy] = line[: st.cx] + line[st.cx + 1 :]
        return
    if st.cy < len(st.lines) - 1:
        st.lines[st.cy] = line + st.lines[st.cy + 1]
        del st.lines[st.cy + 1]


def _newline(st: _EditorState) -> None:
    line = st.lines[st.cy]
    left = line[: st.cx]
    right = line[st.cx :]
    st.lines[st.cy] = left
    st.lines.insert(st.cy + 1, right)
    st.cy += 1
    st.cx = 0


def _move_left(st: _EditorState) -> None:
    if st.cx > 0:
        st.cx -= 1
    elif st.cy > 0:
        st.cy -= 1
        st.cx = len(st.lines[st.cy])


def _move_right(st: _EditorState) -> None:
    if st.cx < len(st.lines[st.cy]):
        st.cx += 1
    elif st.cy < len(st.lines) - 1:
        st.cy += 1
        st.cx = 0


def _move_up(st: _EditorState) -> None:
    if st.cy > 0:
        st.cy -= 1
        st.cx = _clamp(st.cx, 0, len(st.lines[st.cy]))


def _move_down(st: _EditorState) -> None:
    if st.cy < len(st.lines) - 1:
        st.cy += 1
        st.cx = _clamp(st.cx, 0, len(st.lines[st.cy]))


def _visible_geometry(max_y: int, max_x: int) -> Tuple[int, int, int, int]:
    # header (2), footer (2)
    top = 2
    bottom = 2
    height = max(3, max_y - top - bottom)
    width = max(10, max_x - 2)
    y0 = top
    x0 = 1
    return y0, x0, height, width


def _apply_scroll(st: _EditorState, view_h: int) -> None:
    if st.cy < st.scroll:
        st.scroll = st.cy
    elif st.cy >= st.scroll + view_h:
        st.scroll = st.cy - view_h + 1
    st.scroll = _clamp(st.scroll, 0, max(0, len(st.lines) - 1))


def _correct_text(mode: str, text: str) -> str:
    cfg = load_llm_config()
    if cfg.provider != "gemini":
        raise RuntimeError(f"Unsupported LLM provider: {cfg.provider}")

    if mode == "email":
        prompt = prompt_correct_email(text)
    elif mode == "post":
        prompt = prompt_correct_post(text)
    elif mode == "bash":
        prompt = prompt_correct_bash(text)
    else:
        raise RuntimeError(f"Unknown correction mode: {mode}")

    client = GeminiClient()
    out = client.generate_text(
        GeminiRequest(
            model=cfg.model,
            api_key=cfg.api_key,
            prompt=prompt,
            temperature=cfg.temperature,
            timeout_seconds=cfg.timeout_seconds,
        )
    )
    return out


def run_curses_editor(initial_text: str, output_path: str) -> int:
    st = _EditorState(lines=_normalize_lines(initial_text))

    def draw(stdscr):
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        title = "Vocalinux (popup-after-record)"
        stdscr.attron(curses.A_BOLD)
        stdscr.addnstr(0, 1, title, max_x - 2)
        stdscr.attroff(curses.A_BOLD)

        if st.command_mode:
            help_line = "Hotkeys: a=email  b=post  c=bash  Enter=copy&close  Esc=edit"
        else:
            help_line = "Edit mode: type to edit  Esc=hotkeys"
        stdscr.addnstr(1, 1, help_line, max_x - 2)

        y0, x0, h, w = _visible_geometry(max_y, max_x)
        _apply_scroll(st, h)

        for i in range(h):
            li = st.scroll + i
            if li >= len(st.lines):
                break
            stdscr.addnstr(y0 + i, x0, st.lines[li], w)

        status = st.status or ""
        stdscr.addnstr(max_y - 2, 1, status, max_x - 2)

        mode = "HOTKEYS" if st.command_mode else "EDIT"
        pos = f"{st.cy + 1}:{st.cx + 1}"
        footer = f"[{mode}]  {pos}"
        stdscr.addnstr(max_y - 1, 1, footer, max_x - 2)

        # Place cursor
        cy = y0 + (st.cy - st.scroll)
        cx = x0 + st.cx
        if 0 <= cy < max_y - 2:
            stdscr.move(cy, min(cx, max_x - 1))

        stdscr.refresh()

    def mainloop(stdscr):
        curses.curs_set(1)
        stdscr.keypad(True)
        try:
            curses.use_default_colors()
        except Exception:
            pass

        while True:
            _ensure_cursor_in_bounds(st)
            draw(stdscr)
            ch = stdscr.get_wch()

            # toggle mode
            if ch == "\x1b":  # ESC
                st.command_mode = not st.command_mode
                st.status = ""
                continue

            if st.command_mode:
                if ch in ("a", "A"):
                    st.status = "Calling LLM (email)…"
                    draw(stdscr)
                    try:
                        out = _correct_text("email", _join_lines(st.lines))
                        st.lines = _normalize_lines(out)
                        st.cy, st.cx, st.scroll = 0, 0, 0
                        st.status = "Updated."
                    except Exception as e:
                        st.status = f"Error: {e}"
                    continue
                if ch in ("b", "B"):
                    st.status = "Calling LLM (post)…"
                    draw(stdscr)
                    try:
                        out = _correct_text("post", _join_lines(st.lines))
                        st.lines = _normalize_lines(out)
                        st.cy, st.cx, st.scroll = 0, 0, 0
                        st.status = "Updated."
                    except Exception as e:
                        st.status = f"Error: {e}"
                    continue
                if ch in ("c", "C"):
                    st.status = "Calling LLM (bash)…"
                    draw(stdscr)
                    try:
                        out = _correct_text("bash", _join_lines(st.lines))
                        st.lines = _normalize_lines(out)
                        st.cy, st.cx, st.scroll = 0, 0, 0
                        st.status = "Updated."
                    except Exception as e:
                        st.status = f"Error: {e}"
                    continue

                if ch in ("\n", "\r"):
                    final = _join_lines(st.lines).strip() + "\n"
                    _write_text(output_path, final)
                    return 0

                continue

            # edit mode
            if ch in ("\n", "\r"):
                _newline(st)
                continue

            if ch in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                _backspace(st)
                continue

            if ch == curses.KEY_DC:
                _delete(st)
                continue

            if ch == curses.KEY_LEFT:
                _move_left(st)
                continue
            if ch == curses.KEY_RIGHT:
                _move_right(st)
                continue
            if ch == curses.KEY_UP:
                _move_up(st)
                continue
            if ch == curses.KEY_DOWN:
                _move_down(st)
                continue

            # printable
            if isinstance(ch, str) and ch.isprintable():
                _insert_char(st, ch)

    return curses.wrapper(mainloop)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vocalinux terminal popup")
    parser.add_argument("--input", required=True, help="Path to input text file")
    parser.add_argument("--output", required=True, help="Path to output text file")
    args = parser.parse_args(argv)

    text = _read_text(args.input)
    return run_curses_editor(text, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
