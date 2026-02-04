#!/usr/bin/env python3
"""Test script for textual popup hotkeys.

Usage:
    python test_textual_hotkeys.py
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vocalinux.ui.textual_popup import TextualPopupApp

def main():
    # Create temp directory for output
    td = tempfile.mkdtemp(prefix="vocalinux-test-")
    out_path = f"{td}/output.txt"

    test_text = """This is a test transcript.
You can edit this text in EDIT mode.
Press Esc to toggle to HOTKEY mode.
Then press A, B, C, or Enter to test the hotkeys."""

    print("Starting textual popup test...")
    print(f"Output will be written to: {out_path}")
    print("\nInstructions:")
    print("1. The app starts in EDIT mode - you can type normally")
    print("2. Press Esc to switch to HOTKEY mode")
    print("3. In HOTKEY mode, press:")
    print("   - A to test email correction")
    print("   - B to test post correction")
    print("   - C to test bash correction")
    print("   - Enter to copy and close")
    print("   - Esc to return to EDIT mode")
    print("\n" + "="*60 + "\n")

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
