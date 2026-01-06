
import gi

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3
    print("AyatanaAppIndicator3 is available")
except (ValueError, ImportError) as e:
    print(f"AyatanaAppIndicator3 is NOT available: {e}")

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
    print("AppIndicator3 is available")
except (ValueError, ImportError) as e:
    print(f"AppIndicator3 is NOT available: {e}")
