"""Textual-based popup (floating terminal window + TUI).

This is used for popup-after-record with a modern Textual TUI interface.
The main daemon/tray process launches a terminal emulator that runs this module.
The terminal UI writes the final text to an output file, which the main process
copies to clipboard and uses to arm the global paste trigger.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Label,
    TextArea,
)
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message

from ..llm.gemini_client import GeminiClient, GeminiRequest
from ..llm.llm_config import load_llm_config
from ..llm.prompts import prompt_correct_bash, prompt_correct_email, prompt_correct_post
from ..llm.bash_history_retriever import CommandMatch, suggest_or_fix

logger = logging.getLogger(__name__)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_text(path: str, text: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


@dataclass(frozen=True)
class LlmResult:
    """LLM output with optional token usage."""

    text: str
    total_tokens: int | None


def _correct_text(mode: str, text: str) -> LlmResult | CommandMatch:
    cfg = load_llm_config()
    if cfg.provider != "gemini":
        raise RuntimeError(f"Unsupported LLM provider: {cfg.provider}")

    if mode == "email":
        prompt = prompt_correct_email(text)
        client = GeminiClient()
        logger.info("Gemini prompt (email):\n%s", prompt)
        result = client.generate_text_with_usage(
            GeminiRequest(
                model=cfg.model,
                api_key=cfg.api_key,
                prompt=prompt,
                temperature=cfg.temperature,
                timeout_seconds=cfg.timeout_seconds,
            )
        )
        return LlmResult(text=result.text, total_tokens=result.usage.total_tokens if result.usage else None)
    elif mode == "post":
        prompt = prompt_correct_post(text)
        client = GeminiClient()
        logger.info("Gemini prompt (post):\n%s", prompt)
        result = client.generate_text_with_usage(
            GeminiRequest(
                model=cfg.model,
                api_key=cfg.api_key,
                prompt=prompt,
                temperature=cfg.temperature,
                timeout_seconds=cfg.timeout_seconds,
            )
        )
        return LlmResult(text=result.text, total_tokens=result.usage.total_tokens if result.usage else None)
    elif mode == "bash":
        client = GeminiClient()

        def llm_fallback(query: str, current_dir: str | None) -> tuple[str, int | None]:
            prompt = prompt_correct_bash(query, current_dir)
            logger.info("Gemini prompt (bash):\n%s", prompt)
            result = client.generate_text_with_usage(
                GeminiRequest(
                    model=cfg.model,
                    api_key=cfg.api_key,
                    prompt=prompt,
                    temperature=cfg.temperature,
                    timeout_seconds=cfg.timeout_seconds,
                )
            )
            return result.text, result.usage.total_tokens if result.usage else None

        match = suggest_or_fix(
            query=text,
            llm_fallback=llm_fallback,
            current_dir=os.getcwd(),
            k=1,
            thr=0.70,
        )
        return match
    else:
        raise RuntimeError(f"Unknown correction mode: {mode}")


class ModeChanged(Message):
    """Emitted when the mode changes."""

    def __init__(self, command_mode: bool) -> None:
        self.command_mode = command_mode
        super().__init__()


class TranscriptArea(TextArea):
    """Text area that forwards Escape to the app."""

    def key_escape(self) -> None:
        app = self.app
        if isinstance(app, TextualPopupApp):
            app.action_toggle_mode()


class TextualPopupApp(App[None]):
    """Textual TUI for reviewing and correcting transcripts."""

    BINDINGS = [
        Binding("escape", "toggle_mode", "Toggle Mode", priority=True),
        Binding("q", "quit", "Quit", show=False),
    ]

    # Declare reactive variables at class level
    command_mode = reactive(False)
    is_busy = reactive(False)

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }

    #header-text {
        text-align: center;
        text-style: bold;
        padding: 1 2;
    }

    #help-text {
        text-style: italic;
        color: $text-muted;
        padding: 0 2;
    }

    TextArea {
        height: 1fr;
        margin: 1 2;
        background: $panel;
        border: tall $primary;
    }

    TextArea:focus {
        border: tall $accent;
    }

    TextArea.hotkey-mode {
        border: tall $surface-lighten-1;
    }

    #status-bar {
        padding: 1 2;
        background: $panel;
        border: round $primary;
    }

    #status-text {
        text-style: bold;
    }

    #error-text {
        color: $error;
        text-style: bold;
    }

    #mode-indicator {
        padding: 1 2;
        background: $primary;
        color: $text-primary;
    }

    #mode-text {
        text-style: bold;
    }

    #button-container {
        height: 3;
        dock: bottom;
        background: $panel;
        border: round $primary;
    }

    #button-container Label {
        margin: 0 1;
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $text;
        padding: 1;
    }
    """

    def __init__(self, initial_text: str = "", output_path: str = "") -> None:
        super().__init__()
        self.initial_text = initial_text
        self.output_path = output_path

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Container(
            Vertical(
                Label("Vocalinux - Review Transcript", id="header-text"),
                Label(
                    "Edit the transcript. Press [bold]Esc[/bold] to toggle between Edit and Hotkey mode.",
                    id="help-text",
                ),
                TranscriptArea(id="text-editor"),
                Label("", id="status-bar"),
                Label("EDIT Mode", id="mode-indicator"),
                id="main-container",
            ),
            Horizontal(
                Label("[A] Correct for email", id="label-email"),
                Label("[B] Correct for post", id="label-post"),
                Label("[C] Correct bash", id="label-bash"),
                Label("[Enter] Copy & Close", id="label-copy"),
                id="button-container",
            ),
        )

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        text_area = self.query_one("#text-editor", TextArea)
        text_area.load_text(self.initial_text or "")
        text_area.focus()
        self.query_one("#status-bar", Label).display = False
        self._update_help_text()

    def watch_command_mode(self, old_value: bool, new_value: bool) -> None:
        """React to command_mode changes."""
        self._update_mode_ui()
        self._update_help_text()

    def watch_is_busy(self, old_value: bool, new_value: bool) -> None:
        """React to is_busy changes."""
        self._update_mode_ui()
        self._update_help_text()

    def action_toggle_mode(self) -> None:
        """Toggle between edit and command mode."""
        # If busy, allow Esc to cancel and return to edit mode
        if self.is_busy:
            self.is_busy = False
            self._set_status("Cancelled.", is_error=False)
            self.command_mode = False
        else:
            self.command_mode = not self.command_mode

        # Manage focus based on mode
        text_area = self.query_one("#text-editor", TextArea)
        if self.command_mode:
            # Blur the text area so it doesn't consume key events
            text_area.can_focus = False
            self.set_focus(None)
        else:
            # Return focus to text area for editing
            text_area.can_focus = True
            text_area.focus()

    def _update_mode_ui(self) -> None:
        """Update the UI based on current mode."""
        mode_label = self.query_one("#mode-indicator", Label)
        text_area = self.query_one("#text-editor", TextArea)

        if self.command_mode:
            mode_text = "[bold green]HOTKEY Mode[/bold green]\nPress: A=Email | B=Post | C=Bash | Enter=Copy | Esc=Edit"
            # Dim the text area border when not in edit mode
            text_area.add_class("hotkey-mode")
        else:
            mode_text = "[bold cyan]EDIT Mode[/bold cyan]\nPress Esc to switch to Hotkey mode"
            # Highlight the text area border in edit mode
            text_area.remove_class("hotkey-mode")

        mode_label.update(mode_text)

    def _update_help_text(self) -> None:
        """Update the help text based on current mode."""
        help_label = self.query_one("#help-text", Label)

        if self.is_busy:
            help_text = (
                "⏳ [bold]PROCESSING...[/bold] Press [bold]Esc[/bold] to cancel and return to edit mode."
            )
        elif self.command_mode:
            help_text = (
                "🔥 [bold]HOTKEY MODE:[/bold] Press A (email), B (post), C (bash), Enter (copy & close), or Esc (back to edit)"
            )
        else:
            help_text = (
                "✏️  [bold]EDIT MODE:[/bold] Type to edit. Use arrow keys to navigate. Press [bold]Esc[/bold] to switch to hotkey mode."
            )

        help_label.update(help_text)

    def _set_status(self, text: str, is_error: bool = False) -> None:
        """Set the status bar text."""
        status_label = self.query_one("#status-bar", Label)

        if not text:
            status_label.update("")
            status_label.display = False
            return
        status_label.display = True
        if is_error:
            status_label.update(f"[bold #ff0000]Error: {text}[/]")
        else:
            status_label.update(f"[italic #00ff00]{text}[/]")
        status_label.refresh()

    def _get_text(self) -> str:
        """Get the text from the editor."""
        text_area = self.query_one("#text-editor", TextArea)
        return text_area.text.strip()

    def _set_text(self, text: str) -> None:
        """Set the text in the editor."""
        text_area = self.query_one("#text-editor", TextArea)
        text_area.load_text(text)
        text_area.refresh()

    def _trigger_correct(self, mode: str) -> None:
        """Trigger LLM correction for the given mode."""
        if self.is_busy:
            return

        current_text = self._get_text()
        if not current_text:
            self._set_status("Nothing to correct.", is_error=True)
            return

        self.is_busy = True
        self._set_status(f"Calling LLM ({mode})...")

        # Run correction in a worker thread
        import threading

        threading.Thread(
            target=self._correct_in_thread, args=(mode, current_text), daemon=True
        ).start()

    def _correct_in_thread(self, mode: str, text: str) -> None:
        """Run LLM correction in a thread with timeout."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

        def do_correction():
            """Inner function that does the actual work."""
            return _correct_text(mode, text)

        try:
            # Use ThreadPoolExecutor with timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(do_correction)
                try:
                    result = future.result(timeout=30.0)  # 30 second timeout
                except FutureTimeoutError:
                    raise TimeoutError("LLM call timed out after 30 seconds")

            if isinstance(result, CommandMatch):
                out = result.command
                if not out or not out.strip():
                    raise RuntimeError("LLM returned empty output")

                def update_ui():
                    self._set_text(out)
                    if result.from_history:
                        extra = " ⭐ same dir" if result.from_same_directory else ""
                        self._set_status(
                            f"History match ({result.similarity:.0%}){extra}", is_error=False
                        )
                    else:
                        tokens = (
                            f" tokens={result.total_tokens}"
                            if result.total_tokens is not None
                            else ""
                        )
                        self._set_status(f"LLM corrected.{tokens}", is_error=False)
                    self.is_busy = False

                self.call_from_thread(update_ui)
            elif isinstance(result, LlmResult):
                out = result.text
                if not out or not out.strip():
                    raise RuntimeError("LLM returned empty output")

                def update_ui():
                    self._set_text(out)
                    tokens = (
                        f" tokens={result.total_tokens}"
                        if result.total_tokens is not None
                        else ""
                    )
                    self._set_status(f"Updated.{tokens}", is_error=False)
                    self.is_busy = False

                self.call_from_thread(update_ui)
            else:
                out = result
                if not out or not out.strip():
                    raise RuntimeError("LLM returned empty output")

                def update_ui():
                    self._set_text(out)
                    self._set_status("Updated.", is_error=False)
                    self.is_busy = False

                self.call_from_thread(update_ui)

        except Exception as e:
            error_msg = str(e)

            # Add more context for common errors
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                error_msg = "LLM timeout (30s). Check your internet or API."
            elif "api_key" in error_msg.lower() or "401" in error_msg:
                error_msg = "Invalid API key. Check LLM config."
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                error_msg = "Connection failed. Check internet."
            elif "No module named" in error_msg or "ModuleNotFoundError" in error_msg:
                error_msg = "Missing dependencies. Check installation."

            def update_error():
                self._set_status(error_msg, is_error=True)
                self.is_busy = False

            self.call_from_thread(update_error)

    def _copy_and_close(self) -> None:
        """Copy text to clipboard and close the app."""
        if self.is_busy:
            return

        text = self._get_text()
        if not text:
            self._set_status("Nothing to copy.", is_error=True)
            return

        # Write to output file
        _write_text(self.output_path, text + "\n")

        self._set_status("Copied to clipboard. Closing...")
        self.exit(return_code=0)

    def on_key(self, event) -> None:
        """Handle keyboard input."""
        # Only handle hotkeys when in command mode
        if self.command_mode:
            key = event.key

            if key in ("a", "A"):
                self._trigger_correct("email")
                event.prevent_default()
                event.stop()
            elif key in ("b", "B"):
                self._trigger_correct("post")
                event.prevent_default()
                event.stop()
            elif key in ("c", "C"):
                self._trigger_correct("bash")
                event.prevent_default()
                event.stop()
            elif key == "enter":
                self._copy_and_close()
                event.prevent_default()
                event.stop()
        # In edit mode, let TextArea handle all keys naturally


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the Textual popup."""
    parser = argparse.ArgumentParser(description="Vocalinux Textual popup")
    parser.add_argument("--input", required=True, help="Path to input text file")
    parser.add_argument("--output", required=True, help="Path to output text file")
    args = parser.parse_args(argv)

    text = _read_text(args.input)
    app = TextualPopupApp(initial_text=text, output_path=args.output)

    try:
        return app.run()
    except Exception as e:
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
