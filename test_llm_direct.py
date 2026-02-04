#!/usr/bin/env python3
"""Test the LLM function directly without GUI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test 1: Can we import?
print("Test 1: Importing modules...")
try:
    from vocalinux.ui.textual_popup import _correct_text
    print("✓ Import successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Mock and call
print("\nTest 2: Mocking _correct_text...")
import vocalinux.ui.textual_popup as popup_module

def mock_correct(mode: str, text: str) -> str:
    print(f"  Mock called with mode={mode}, text='{text[:30]}...'")
    return f"[{mode.upper()}] {text}"

popup_module._correct_text = mock_correct
print("✓ Mock installed")

# Test 3: Call the mocked function
print("\nTest 3: Calling mocked function directly...")
try:
    result = popup_module._correct_text("email", "test text")
    print(f"✓ Result: '{result}'")
except Exception as e:
    print(f"✗ Call failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Try with threading
print("\nTest 4: Testing with threading...")
import threading
import time

result_holder = []
error_holder = []

def threaded_call():
    try:
        result = popup_module._correct_text("bash", "echo hello")
        result_holder.append(result)
        print("  Thread completed successfully")
    except Exception as e:
        error_holder.append(str(e))
        print(f"  Thread failed: {e}")

thread = threading.Thread(target=threaded_call, daemon=True)
thread.start()
thread.join(timeout=5.0)

if thread.is_alive():
    print("✗ Thread still running after 5s (stuck)")
elif error_holder:
    print(f"✗ Thread error: {error_holder[0]}")
elif result_holder:
    print(f"✓ Thread result: '{result_holder[0]}'")
else:
    print("✗ Thread completed but no result")

# Test 5: Try with ThreadPoolExecutor
print("\nTest 5: Testing with ThreadPoolExecutor...")
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

try:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(popup_module._correct_text, "post", "my post")
        result = future.result(timeout=5.0)
        print(f"✓ Executor result: '{result}'")
except FutureTimeoutError:
    print("✗ Executor timed out")
except Exception as e:
    print(f"✗ Executor error: {e}")

print("\n" + "="*60)
print("All tests completed!")
print("="*60)
