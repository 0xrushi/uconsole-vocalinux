"""Tests for LLM config loading."""

import os
import tempfile
import unittest


from vocalinux.llm.llm_config import load_llm_config


class TestLlmConfig(unittest.TestCase):
    def test_load_from_env_var(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    """llm:
  provider: gemini
  model: gemini-3-flash-preview
  api_key_env: GEMINI_API_KEY
  timeout_seconds: 12
  temperature: 0.3
"""
                )

            os.environ["GEMINI_API_KEY"] = "test-key"
            cfg = load_llm_config(path)
            self.assertEqual(cfg.provider, "gemini")
            self.assertEqual(cfg.model, "gemini-3-flash-preview")
            self.assertEqual(cfg.api_key, "test-key")
            self.assertEqual(cfg.timeout_seconds, 12.0)
            self.assertEqual(cfg.temperature, 0.3)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "missing.yaml")
            with self.assertRaises(RuntimeError):
                load_llm_config(path)

    def test_missing_api_key(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    """llm:
  provider: gemini
  model: gemini-3-flash-preview
  api_key_env: GEMINI_API_KEY
"""
                )

            os.environ.pop("GEMINI_API_KEY", None)
            with self.assertRaises(RuntimeError):
                load_llm_config(path)
