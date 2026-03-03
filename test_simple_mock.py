#!/usr/bin/env python3
"""Simple test that patches the LLM before importing."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Patch BEFORE importing the module
import vocalinux.ui.textual_popup as popup_module

# Replace the _correct_text function with a simple mock
original_correct = popup_module._correct_text

def mock_correct_text(mode: str, text: str) -> str:
    """Simple mock that just adds a prefix."""
    print(f"[MOCK] Called with mode={mode}, text length={len(text)}")
    return f"[{mode.upper()} MODE]\n\n{text}"

# Monkey patch
popup_module._correct_text = mock_correct_text

# Now import and run
from vocalinux.ui.textual_popup import TextualPopupApp
import tempfile

def main():
    td = tempfile.mkdtemp(prefix="vocalinux-test-")
    out_path = f"{td}/output.txt"

    test_text = "Test text. Press Esc then A to test email correction."

    print("="*60)
    print("SIMPLE MOCK TEST")
    print("="*60)
    print("LLM is mocked - should return instantly")
    print("Try: Esc -> A (should add [EMAIL MODE] prefix)")
    print("="*60)

    app = TextualPopupApp(initial_text=test_text, output_path=out_path)
    return app.run()

if __name__ == "__main__":
    sys.exit(main())
