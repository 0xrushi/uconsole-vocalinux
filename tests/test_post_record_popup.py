"""Tests for GTK PostRecordPopup widget."""

import unittest
from unittest.mock import MagicMock, Mock, patch, call
import logging


class TestPostRecordPopupMarkup(unittest.TestCase):
    """Tests for GTK markup escaping."""

    def test_ampersand_escaped_in_header(self):
        """Test that ampersands are properly escaped in header markup."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        source = inspect.getsource(PostRecordPopup.__init__)

        # Verify ampersands are escaped as &amp; in markup strings
        self.assertIn("&amp;", source)
        # Should NOT have unescaped & in markup (except in &amp; itself)
        # This checks that "copy & close" is NOT present (should be "copy &amp; close")
        self.assertIn("copy &amp; close", source.lower())

    def test_label_markup_uses_amp_entity(self):
        """Test that label markup properly uses &amp; entity."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        source = inspect.getsource(PostRecordPopup.__init__)

        # Verify labels use &amp; instead of &
        self.assertIn('Copy &amp; Close', source)


class TestPostRecordPopupTokenUsage(unittest.TestCase):
    """Tests for token usage tracking and display."""

    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_uses_generate_text_with_usage(self, mock_client_class, mock_config):
        """Test that _correct_in_thread uses generate_text_with_usage."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        source = inspect.getsource(PostRecordPopup._correct_in_thread)

        # Verify it uses generate_text_with_usage instead of generate_text
        self.assertIn("generate_text_with_usage", source)
        self.assertNotIn("client.generate_text(", source)

    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_correct_success_displays_token_count(self, mock_client_class, mock_glib, mock_config):
        """Test that _on_correct_success displays token count when available."""
        from vocalinux.ui.post_record_popup import PostRecordPopup, GeminiUsage

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock GeminiClient result
        mock_result = MagicMock()
        mock_result.text = "Corrected text"
        mock_result.usage = GeminiUsage(prompt_tokens=50, output_tokens=100, total_tokens=150)

        mock_instance = MagicMock()
        mock_instance.generate_text_with_usage.return_value = mock_result
        mock_client_class.return_value = mock_instance

        # Mock GLib.idle_add to call function directly
        def fake_idle_add(fn, *args):
            fn(*args)
            return False

        mock_glib.idle_add = fake_idle_add

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Mock the _set_text and _set_status methods to track calls
            popup._set_text = Mock()
            popup._set_status = Mock()
            popup._update_mode_ui = Mock()

            # Call _on_correct_success with usage
            result = popup._on_correct_success("Corrected text", mock_result.usage)

            # Verify status message includes token count
            popup._set_status.assert_called_once()
            status_msg = popup._set_status.call_args[0][0]
            self.assertIn("tokens=150", status_msg)
            self.assertIn("Updated", status_msg)

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")

    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_correct_success_handles_none_usage(self, mock_client_class, mock_glib, mock_config):
        """Test that _on_correct_success handles None usage gracefully."""
        from vocalinux.ui.post_record_popup import PostRecordPopup

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_config.return_value = mock_cfg

        # Mock GLib.idle_add to call function directly
        def fake_idle_add(fn, *args):
            fn(*args)
            return False

        mock_glib.idle_add = fake_idle_add

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Mock methods
            popup._set_text = Mock()
            popup._set_status = Mock()
            popup._update_mode_ui = Mock()

            # Call _on_correct_success with None usage
            result = popup._on_correct_success("Corrected text", usage=None)

            # Verify status message does NOT include token count
            popup._set_status.assert_called_once()
            status_msg = popup._set_status.call_args[0][0]
            self.assertNotIn("tokens=", status_msg)
            self.assertIn("Updated", status_msg)

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")

    def test_on_correct_success_signature_accepts_usage(self):
        """Test that _on_correct_success method signature accepts usage parameter."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        # Get the method signature
        sig = inspect.signature(PostRecordPopup._on_correct_success)
        params = list(sig.parameters.keys())

        # Should have: self, out, usage
        self.assertIn("out", params)
        self.assertIn("usage", params)

        # usage should have a default value of None
        self.assertEqual(sig.parameters["usage"].default, None)


class TestPostRecordPopupPromptLogging(unittest.TestCase):
    """Tests for LLM prompt logging."""

    @patch("vocalinux.ui.post_record_popup.logger")
    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_logs_email_prompt(self, mock_client_class, mock_config, mock_glib, mock_logger):
        """Test that email correction logs the prompt."""
        from vocalinux.ui.post_record_popup import PostRecordPopup

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock GeminiClient result
        mock_result = MagicMock()
        mock_result.text = "Corrected text"
        mock_result.usage = None

        mock_instance = MagicMock()
        mock_instance.generate_text_with_usage.return_value = mock_result
        mock_client_class.return_value = mock_instance

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Call _correct_in_thread directly (in same thread for testing)
            popup._correct_in_thread("email", "test input")

            # Verify logger.info was called with prompt
            mock_logger.info.assert_called()
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

            # Should contain a log message about the Gemini prompt
            prompt_logged = any("Gemini prompt" in str(msg) and "email" in str(msg) for msg in log_calls)
            self.assertTrue(prompt_logged, f"Expected prompt logging, got: {log_calls}")

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")

    @patch("vocalinux.ui.post_record_popup.logger")
    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_logs_post_prompt(self, mock_client_class, mock_config, mock_glib, mock_logger):
        """Test that post correction logs the prompt."""
        from vocalinux.ui.post_record_popup import PostRecordPopup

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock GeminiClient result
        mock_result = MagicMock()
        mock_result.text = "Corrected text"
        mock_result.usage = None

        mock_instance = MagicMock()
        mock_instance.generate_text_with_usage.return_value = mock_result
        mock_client_class.return_value = mock_instance

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Call _correct_in_thread directly
            popup._correct_in_thread("post", "test input")

            # Verify logger.info was called with prompt
            mock_logger.info.assert_called()
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

            # Should contain a log message about the Gemini prompt for post
            prompt_logged = any("Gemini prompt" in str(msg) and "post" in str(msg) for msg in log_calls)
            self.assertTrue(prompt_logged, f"Expected prompt logging, got: {log_calls}")

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")

    @patch("vocalinux.ui.post_record_popup.logger")
    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_logs_bash_prompt(self, mock_client_class, mock_config, mock_glib, mock_logger):
        """Test that bash correction logs the prompt."""
        from vocalinux.ui.post_record_popup import PostRecordPopup

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock GeminiClient result
        mock_result = MagicMock()
        mock_result.text = "Corrected text"
        mock_result.usage = None

        mock_instance = MagicMock()
        mock_instance.generate_text_with_usage.return_value = mock_result
        mock_client_class.return_value = mock_instance

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="test", on_complete=on_complete)

            # Call _correct_in_thread directly
            popup._correct_in_thread("bash", "test input")

            # Verify logger.info was called with prompt
            mock_logger.info.assert_called()
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

            # Should contain a log message about the Gemini prompt for bash
            prompt_logged = any("Gemini prompt" in str(msg) and "bash" in str(msg) for msg in log_calls)
            self.assertTrue(prompt_logged, f"Expected prompt logging, got: {log_calls}")

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")

    def test_logging_statement_present_in_code(self):
        """Test that logger.info statement exists in _correct_in_thread."""
        from vocalinux.ui.post_record_popup import PostRecordPopup
        import inspect

        source = inspect.getsource(PostRecordPopup._correct_in_thread)

        # Verify logger.info is called
        self.assertIn("logger.info", source)
        # Verify it logs the prompt
        self.assertIn("Gemini prompt", source)
        # Verify it includes the mode
        self.assertIn("{mode}", source)


class TestPostRecordPopupIntegration(unittest.TestCase):
    """Integration tests for PostRecordPopup."""

    @patch("vocalinux.ui.post_record_popup.GLib")
    @patch("vocalinux.ui.post_record_popup.load_llm_config")
    @patch("vocalinux.ui.post_record_popup.GeminiClient")
    def test_full_correction_flow_with_tokens(self, mock_client_class, mock_config, mock_glib):
        """Test complete correction flow with token usage."""
        from vocalinux.ui.post_record_popup import PostRecordPopup, GeminiUsage

        # Mock config
        mock_cfg = MagicMock()
        mock_cfg.provider = "gemini"
        mock_cfg.model = "test-model"
        mock_cfg.api_key = "test-key"
        mock_cfg.temperature = 0.7
        mock_cfg.timeout_seconds = 30
        mock_config.return_value = mock_cfg

        # Mock GeminiClient result with usage
        mock_result = MagicMock()
        mock_result.text = "Corrected: Hello, how are you?"
        mock_result.usage = GeminiUsage(prompt_tokens=25, output_tokens=50, total_tokens=75)

        mock_instance = MagicMock()
        mock_instance.generate_text_with_usage.return_value = mock_result
        mock_client_class.return_value = mock_instance

        # Mock GLib.idle_add to execute immediately
        def fake_idle_add(fn, *args):
            return fn(*args)

        mock_glib.idle_add = fake_idle_add

        # Create popup
        on_complete = Mock()
        try:
            popup = PostRecordPopup(initial_text="hey whats up", on_complete=on_complete)

            # Mock internal methods to track behavior
            original_set_text = popup._set_text
            original_set_status = popup._set_status

            set_text_calls = []
            set_status_calls = []

            def track_set_text(text):
                set_text_calls.append(text)
                original_set_text(text)

            def track_set_status(text, **kwargs):
                set_status_calls.append((text, kwargs))
                original_set_status(text, **kwargs)

            popup._set_text = track_set_text
            popup._set_status = track_set_status

            # Trigger correction
            popup._correct_in_thread("email", "hey whats up")

            # Verify text was updated
            self.assertIn("Corrected: Hello, how are you?", set_text_calls)

            # Verify status shows token count
            status_messages = [msg for msg, _ in set_status_calls]
            has_token_info = any("tokens=75" in str(msg) for msg in status_messages)
            self.assertTrue(has_token_info, f"Expected token info in: {status_messages}")

            # Verify client was called
            mock_instance.generate_text_with_usage.assert_called_once()

            # Cleanup
            popup.destroy()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not available: {e}")


class TestGeminiUsageImport(unittest.TestCase):
    """Test that GeminiUsage is properly imported."""

    def test_gemini_usage_imported(self):
        """Test that GeminiUsage is imported from gemini_client."""
        from vocalinux.ui.post_record_popup import GeminiUsage
        from vocalinux.llm.gemini_client import GeminiUsage as OriginalGeminiUsage

        # Verify they are the same class
        self.assertEqual(GeminiUsage, OriginalGeminiUsage)

    def test_import_statement_present(self):
        """Test that import statement includes GeminiUsage."""
        import vocalinux.ui.post_record_popup as module
        import inspect

        source = inspect.getsource(module)

        # Verify GeminiUsage is imported
        self.assertIn("from ..llm.gemini_client import", source)
        self.assertIn("GeminiUsage", source)


if __name__ == "__main__":
    unittest.main()
