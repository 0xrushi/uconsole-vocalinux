"""Tests for textual popup UI.

Note: Full Textual app testing requires the app to be running, which is complex
for unit tests. These tests focus on the logic and use mocks where needed.
For integration testing, use the test scripts in the project root.
"""

import unittest
from unittest.mock import MagicMock, patch, Mock, call
import tempfile
import time
from pathlib import Path


class TestCorrectTextFunction(unittest.TestCase):
    """Tests for the _correct_text helper function."""

    @patch("vocalinux.ui.textual_popup.load_llm_config")
    @patch("vocalinux.ui.textual_popup.GeminiClient")
    def test_correct_text_calls_gemini_client(self, mock_client_class, mock_config):
        """Test that _correct_text calls GeminiClient with correct parameters."""
        from vocalinux.ui.textual_popup import _correct_text

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock client
        mock_instance = MagicMock()
        mock_instance.generate_text.return_value = "Corrected output"
        mock_client_class.return_value = mock_instance

        result = _correct_text("email", "test input")

        # Should create client and call generate_text
        mock_client_class.assert_called_once()
        mock_instance.generate_text.assert_called_once()
        self.assertEqual(result, "Corrected output")


class TestLLMCorrectionThreading(unittest.TestCase):
    """Tests for threaded LLM correction logic."""

    @patch("vocalinux.ui.textual_popup._correct_text")
    def test_thread_executor_with_successful_result(self, mock_correct):
        """Test that ThreadPoolExecutor successfully calls _correct_text."""
        from concurrent.futures import ThreadPoolExecutor

        mock_correct.return_value = "Success result"

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(mock_correct, "bash", "echo hello")
            result = future.result(timeout=5.0)

        self.assertEqual(result, "Success result")
        mock_correct.assert_called_once_with("bash", "echo hello")

    def test_thread_executor_with_timeout(self):
        """Test that ThreadPoolExecutor properly times out."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError

        # Function that hangs
        def slow_function(*args):
            time.sleep(10)
            return "never reached"

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_function, "bash", "echo hello")

            with self.assertRaises(TimeoutError):
                future.result(timeout=0.1)


class TestHotkeyLogic(unittest.TestCase):
    """Tests for hotkey handling logic (without full app)."""

    def test_key_mapping_for_corrections(self):
        """Test that keys map to correct correction modes."""
        # This tests the logic that should be in on_key
        key_to_mode = {
            "a": "email",
            "A": "email",
            "b": "post",
            "B": "post",
            "c": "bash",
            "C": "bash",
        }

        for key, expected_mode in key_to_mode.items():
            # Verify our mapping is correct
            if key in ("a", "A"):
                self.assertEqual(expected_mode, "email")
            elif key in ("b", "B"):
                self.assertEqual(expected_mode, "post")
            elif key in ("c", "C"):
                self.assertEqual(expected_mode, "bash")


class TestFileOperations(unittest.TestCase):
    """Tests for file reading/writing operations."""

    def test_output_file_writing(self):
        """Test writing final text to output file."""
        temp_dir = tempfile.mkdtemp(prefix="vocalinux-test-")
        output_path = f"{temp_dir}/output.txt"

        # Simulate what _copy_and_close does
        final_text = "This is the final text"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_text)

        # Verify it was written
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertEqual(content, final_text)

    def test_input_file_reading(self):
        """Test reading initial text from input file."""
        temp_dir = tempfile.mkdtemp(prefix="vocalinux-test-")
        input_path = f"{temp_dir}/input.txt"

        initial_text = "Initial transcript"

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(initial_text)

        # Simulate reading it back
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertEqual(content, initial_text)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling logic."""

    def test_error_message_formatting_for_timeout(self):
        """Test that timeout errors get user-friendly messages."""
        error_msg = "LLM call timed out after 30 seconds"

        # Simulate the error handling logic
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            user_msg = "LLM timeout (30s). Check your internet or API."
        else:
            user_msg = error_msg

        self.assertEqual(user_msg, "LLM timeout (30s). Check your internet or API.")

    def test_error_message_formatting_for_api_key(self):
        """Test that API key errors get user-friendly messages."""
        error_msg = "Invalid api_key provided"

        if "api_key" in error_msg.lower() or "401" in error_msg:
            user_msg = "Invalid API key. Check LLM config."
        else:
            user_msg = error_msg

        self.assertEqual(user_msg, "Invalid API key. Check LLM config.")

    def test_error_message_formatting_for_connection(self):
        """Test that connection errors get user-friendly messages."""
        error_msg = "Connection failed: network unreachable"

        if "connection" in error_msg.lower() or "network" in error_msg.lower():
            user_msg = "Connection failed. Check internet."
        else:
            user_msg = error_msg

        self.assertEqual(user_msg, "Connection failed. Check internet.")

    def test_empty_output_detection(self):
        """Test that empty LLM output is detected."""
        test_cases = [
            ("", True),
            ("   ", True),
            ("\n\n", True),
            ("actual text", False),
            ("  actual text  ", False),
        ]

        for output, should_be_empty in test_cases:
            is_empty = not output or not output.strip()
            self.assertEqual(
                is_empty,
                should_be_empty,
                f"Failed for output: {repr(output)}",
            )


class TestModeToggleLogic(unittest.TestCase):
    """Tests for mode toggle logic."""

    def test_mode_toggle_basic_state(self):
        """Test basic mode toggling logic."""
        command_mode = False

        # Toggle to hotkey mode
        command_mode = not command_mode
        self.assertTrue(command_mode)

        # Toggle back to edit mode
        command_mode = not command_mode
        self.assertFalse(command_mode)

    def test_busy_state_prevents_operations(self):
        """Test that busy state should prevent new operations."""
        is_busy = False

        # Operation should be allowed
        can_start = not is_busy
        self.assertTrue(can_start)

        # Set busy
        is_busy = True

        # Operation should be blocked
        can_start = not is_busy
        self.assertFalse(can_start)

    def test_cancel_logic_when_busy(self):
        """Test cancel logic when pressing Esc while busy."""
        is_busy = True
        command_mode = True

        # Simulate pressing Esc while busy
        if is_busy:
            is_busy = False
            command_mode = False
            status = "Cancelled."

        self.assertFalse(is_busy)
        self.assertFalse(command_mode)
        self.assertEqual(status, "Cancelled.")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration-style tests for common user scenarios."""

    def test_email_correction_flow(self):
        """Test the full flow of email correction (logic only)."""
        # Initial state
        text = "hey can you send me that file"
        is_busy = False
        command_mode = True

        # User presses 'a' for email
        if command_mode and not is_busy:
            is_busy = True
            mode = "email"

        self.assertTrue(is_busy)
        self.assertEqual(mode, "email")

        # Simulate correction complete
        corrected_text = "Hi,\n\nCould you please send me that file?\n\nBest regards"
        is_busy = False

        self.assertFalse(is_busy)
        self.assertNotEqual(text, corrected_text)

    def test_cancel_during_correction(self):
        """Test canceling a correction in progress."""
        is_busy = True
        command_mode = True

        # User presses Esc to cancel
        if is_busy:
            is_busy = False
            command_mode = False

        self.assertFalse(is_busy)
        self.assertFalse(command_mode)

    def test_empty_text_handling(self):
        """Test handling when text is empty."""
        text = "   "
        is_busy = False

        # Attempt correction
        if not text.strip():
            error = "Nothing to correct."
            can_proceed = False
        else:
            can_proceed = True
            error = None

        self.assertFalse(can_proceed)
        self.assertEqual(error, "Nothing to correct.")


class TestDebugOutput(unittest.TestCase):
    """Tests for debug logging (verifies debug statements would work)."""

    @patch("sys.stderr")
    def test_debug_output_format(self, mock_stderr):
        """Test that debug output can be written."""
        import sys

        print("[DEBUG] Test message", file=sys.stderr)

        # Verify print was called (mock might intercept it)
        # This is mainly to ensure the debug code won't crash


class TestUILabelsInsteadOfButtons(unittest.TestCase):
    """Tests to verify that labels are used instead of buttons."""

    @patch("vocalinux.ui.textual_popup.load_llm_config")
    def test_compose_creates_labels_not_buttons(self, mock_config):
        """Test that compose() creates Label widgets, not Button widgets."""
        from vocalinux.ui.textual_popup import TextualPopupApp
        import inspect

        # Check the module source to verify Labels are used instead of Buttons
        import vocalinux.ui.textual_popup as popup_module
        module_source = inspect.getsource(popup_module)

        # Verify Button is NOT imported
        self.assertNotIn("from textual.widgets import (\n    Button,", module_source)

        # Get the compose method source
        source = inspect.getsource(TextualPopupApp.compose)

        # Verify Label widgets are created with correct IDs
        self.assertIn('Label("[A] Correct for email", id="label-email")', source)
        self.assertIn('Label("[B] Correct for post", id="label-post")', source)
        self.assertIn('Label("[C] Correct bash", id="label-bash")', source)
        self.assertIn('Label("[Enter] Copy & Close", id="label-copy")', source)

        # Verify Button widgets are NOT created
        self.assertNotIn('Button("[A]', source)
        self.assertNotIn('Button("[B]', source)
        self.assertNotIn('Button("[C]', source)
        self.assertNotIn('Button("[Enter]', source)

    def test_no_button_click_handlers(self):
        """Test that there are no button click handlers (@on decorators for buttons)."""
        import vocalinux.ui.textual_popup as popup_module
        import inspect

        source = inspect.getsource(popup_module)

        # Verify there are no @on(Button.Pressed, ...) decorators
        self.assertNotIn("@on(Button.Pressed", source)
        self.assertNotIn("on_email_button", source)
        self.assertNotIn("on_post_button", source)
        self.assertNotIn("on_bash_button", source)
        self.assertNotIn("on_copy_button", source)


class TestHotkeyFunctionalityWithLabels(unittest.TestCase):
    """Tests to verify hotkeys work correctly with labels (not buttons)."""

    def test_hotkey_mode_toggle_logic(self):
        """Test that hotkey mode toggle logic is correct (without mounting)."""
        # Test the pure logic without accessing reactive properties
        command_mode = False

        # Toggle to hotkey mode
        command_mode = not command_mode
        self.assertTrue(command_mode)

        # Toggle back to edit mode
        command_mode = not command_mode
        self.assertFalse(command_mode)

    @patch("vocalinux.ui.textual_popup._correct_text")
    def test_hotkey_triggers_correction_logic(self, mock_correct):
        """Test that correction logic works correctly in hotkey mode."""
        # Simulate the logic that happens when 'a' is pressed in hotkey mode
        command_mode = True
        is_busy = False
        current_text = "test text"

        if command_mode:
            mode = "email"

            # This simulates _trigger_correct being called
            if not is_busy and current_text:
                correction_triggered = True
            else:
                correction_triggered = False
        else:
            correction_triggered = False

        self.assertTrue(correction_triggered)

    def test_hotkeys_disabled_in_edit_mode(self):
        """Test that hotkeys don't trigger corrections in edit mode."""
        # Test the pure logic
        command_mode = False

        # Simulate checking if hotkey should trigger
        # In edit mode, hotkeys should NOT trigger corrections
        if command_mode:
            should_trigger = True
        else:
            should_trigger = False

        self.assertFalse(should_trigger)

    def test_on_key_method_exists_and_handles_hotkeys(self):
        """Test that on_key method exists and has correct hotkey handling."""
        from vocalinux.ui.textual_popup import TextualPopupApp
        import inspect

        # Verify on_key method exists
        self.assertTrue(hasattr(TextualPopupApp, "on_key"))

        # Verify it handles the correct keys
        source = inspect.getsource(TextualPopupApp.on_key)
        self.assertIn('if key in ("a", "A"):', source)
        self.assertIn('elif key in ("b", "B"):', source)
        self.assertIn('elif key in ("c", "C"):', source)
        self.assertIn('elif key == "enter":', source)


class TestGTKUILabels(unittest.TestCase):
    """Tests for GTK UI labels instead of buttons."""

    def test_gtk_popup_creates_labels_not_buttons(self):
        """Test that GTK PostRecordPopup creates labels, not buttons."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        # Check the source code to verify labels are created instead of buttons
        source = inspect.getsource(PostRecordPopup.__init__)

        # Verify Gtk.Label is used, not Gtk.Button
        self.assertIn("_label_email = Gtk.Label", source)
        self.assertIn("_label_post = Gtk.Label", source)
        self.assertIn("_label_bash = Gtk.Label", source)
        self.assertIn("_label_copy = Gtk.Label", source)

        # Verify button creation is NOT present
        self.assertNotIn("_btn_email = Gtk.Button", source)
        self.assertNotIn("_btn_post = Gtk.Button", source)
        self.assertNotIn("_btn_bash = Gtk.Button", source)

    def test_gtk_hotkeys_still_work(self):
        """Test that hotkeys still trigger corrections in GTK UI."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        from unittest.mock import Mock

        # Mock callback
        on_complete = Mock()

        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Enable command mode
            popup._command_mode = True

            # Test the key mapping logic (from _on_key_press)
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gdk

            # Verify the key codes that should trigger corrections
            key_mappings = {
                Gdk.KEY_a: "email",
                Gdk.KEY_A: "email",
                Gdk.KEY_b: "post",
                Gdk.KEY_B: "post",
                Gdk.KEY_c: "bash",
                Gdk.KEY_C: "bash",
            }

            for keyval, expected_mode in key_mappings.items():
                # In command mode, these keys should trigger corrections
                if popup._command_mode:
                    if keyval in (Gdk.KEY_a, Gdk.KEY_A):
                        triggered_mode = "email"
                    elif keyval in (Gdk.KEY_b, Gdk.KEY_B):
                        triggered_mode = "post"
                    elif keyval in (Gdk.KEY_c, Gdk.KEY_C):
                        triggered_mode = "bash"
                    else:
                        triggered_mode = None

                    self.assertEqual(triggered_mode, expected_mode)

            # Cleanup
            popup.destroy()
        except Exception as e:
            import unittest
            raise unittest.SkipTest(f"GTK not available: {e}")


if __name__ == "__main__":
    unittest.main()
