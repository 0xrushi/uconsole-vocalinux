#!/usr/bin/env python3
"""Debug test - simulates key presses to see what happens."""

import sys
from pathlib import Path
import asyncio

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Patch BEFORE importing
import vocalinux.ui.textual_popup as popup_module

call_count = 0

def mock_correct_text(mode: str, text: str) -> str:
    """Mock that tracks calls."""
    global call_count
    call_count += 1
    print(f"[MOCK] _correct_text called (call #{call_count}): mode={mode}")
    import time
    time.sleep(0.5)  # Simulate brief processing
    result = f"[{mode.upper()}]\n{text}"
    print(f"[MOCK] _correct_text returning {len(result)} chars")
    return result

popup_module._correct_text = mock_correct_text

from vocalinux.ui.textual_popup import TextualPopupApp
from textual import events
import tempfile

class TestApp(TextualPopupApp):
    """Test app that auto-presses keys."""

    def on_mount(self) -> None:
        """After mounting, simulate key presses."""
        super().on_mount()
        print("\n[TEST] App mounted, scheduling test...")
        self.set_timer(1.0, self.test_sequence)

    async def test_sequence(self):
        """Run test sequence."""
        print("[TEST] Step 1: Pressing Esc to toggle to hotkey mode...")
        self.action_toggle_mode()
        await asyncio.sleep(0.5)

        print(f"[TEST] command_mode={self.command_mode}, is_busy={self.is_busy}")

        print("[TEST] Step 2: Triggering email correction...")
        self._trigger_correct("email")

        print("[TEST] Waiting for completion...")
        await asyncio.sleep(3.0)

        print(f"[TEST] After 3s: is_busy={self.is_busy}")
        print(f"[TEST] Text length: {len(self._get_text())}")

        print("[TEST] Test complete, exiting...")
        self.exit()

def main():
    td = tempfile.mkdtemp(prefix="vocalinux-test-")
    out_path = f"{td}/output.txt"
    test_text = "Original test text"

    print("="*60)
    print("AUTOMATED DEBUG TEST")
    print("="*60)
    print("This will automatically:")
    print("1. Toggle to hotkey mode")
    print("2. Trigger email correction")
    print("3. Wait and check result")
    print("="*60)

    app = TestApp(initial_text=test_text, output_path=out_path)
    return app.run()

if __name__ == "__main__":
    sys.exit(main())
