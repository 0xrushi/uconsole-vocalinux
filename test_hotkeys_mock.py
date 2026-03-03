#!/usr/bin/env python3
"""Test script for textual popup hotkeys with mock LLM.

This version mocks the LLM calls so you can test hotkeys without API setup.
"""

import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vocalinux.ui.textual_popup import TextualPopupApp, _correct_text

# Mock the _correct_text function
original_correct = _correct_text

def mock_correct_text(mode: str, text: str) -> str:
    """Mock LLM correction that just adds a prefix."""
    # Simulate some processing time
    time.sleep(1)

    if mode == "email":
        return f"[EMAIL CORRECTED]\n\n{text}\n\nBest regards,\nYour Name"
    elif mode == "post":
        return f"[POST CORRECTED]\n\n{text}\n\n#hashtags #cool"
    elif mode == "bash":
        # Extract potential commands and format them
        return f"#!/bin/bash\n# {text}\necho 'Running command...'"
    else:
        return text

# Monkey patch the module
import vocalinux.ui.textual_popup as popup_module
popup_module._correct_text = mock_correct_text

def main():
    # Create temp directory for output
    td = tempfile.mkdtemp(prefix="vocalinux-test-")
    out_path = f"{td}/output.txt"

    test_text = """This is a test transcript.
Press Esc to switch to HOTKEY mode.
Then test the hotkeys:
A = Email correction
B = Post correction
C = Bash correction
Enter = Copy and close"""

    print("Starting textual popup test with MOCK LLM...")
    print(f"Output will be written to: {out_path}")
    print("\nThe LLM calls are mocked - they'll just add prefixes to test the UI.")
    print("="*60 + "\n")

    app = TextualPopupApp(initial_text=test_text, output_path=out_path)
    return_code = app.run()

    # Check output
    try:
        with open(out_path, "r") as f:
            output = f.read()
        print(f"\nOutput file contents:\n{output}")
    except FileNotFoundError:
        print("\nNo output file created (user quit without copying)")

    return return_code

if __name__ == "__main__":
    sys.exit(main())
