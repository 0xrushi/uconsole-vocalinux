"""
Keyboard shortcut manager for Vocalinux.

This module provides global keyboard shortcut functionality to
start/stop speech recognition with a double-tap of the Ctrl key.
"""

import logging
import threading
import time
from typing import Callable, Optional

# Make keyboard a module-level attribute first, even if it's None
# This will ensure the attribute exists for patching in tests
keyboard = None
KEYBOARD_AVAILABLE = False

# Try to import X11 keyboard libraries
try:
    from pynput import keyboard

    KEYBOARD_AVAILABLE = True
except ImportError:
    # Keep keyboard as None, which we set above
    pass

logger = logging.getLogger(__name__)


class KeyboardShortcutManager:
    """
    Manages global keyboard shortcuts for the application.

    This class allows registering the double-tap Ctrl shortcut to
    toggle voice typing on and off across the desktop environment.
    """

    def __init__(self):
        """Initialize the keyboard shortcut manager."""
        self.listener = None
        self.active = False
        self.last_trigger_time = 0  # Track last trigger time to prevent double triggers

        # Double-tap tracking variables
        self.last_ctrl_press_time = 0
        self.double_tap_callback = None
        self.double_tap_threshold = 0.3  # seconds between taps to count as double-tap

        # Paste arming + triple-key tracking (used by popup-after-record)
        self._paste_callback: Optional[Callable[[], None]] = None
        self._paste_armed_until = 0.0
        self._paste_ppp_times = []  # list[float]
        self._ppp_total_window = 0.6  # seconds for 3 presses
        self._ppp_trigger_cooldown = 0.5
        self._last_ppp_trigger_time = 0.0

        if not KEYBOARD_AVAILABLE:
            logger.error(
                "Keyboard shortcut libraries not available. Shortcuts will not work."
            )
            return

    def start(self):
        """Start listening for keyboard shortcuts."""
        if not KEYBOARD_AVAILABLE:
            return

        if self.active:
            return

        logger.info("Starting keyboard shortcut listener")
        self.active = True

        # Track currently pressed modifier keys
        self.current_keys = set()

        try:
            # Start keyboard listener in a separate thread
            self.listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self.listener.daemon = True
            self.listener.start()

            # Verify the listener started successfully
            if not self.listener.is_alive():
                logger.error("Failed to start keyboard listener")
                self.active = False
            else:
                logger.info("Keyboard shortcut listener started successfully")
        except Exception as e:
            logger.error(f"Error starting keyboard listener: {e}")
            self.active = False

    def stop(self):
        """Stop listening for keyboard shortcuts."""
        if not self.active or not self.listener:
            return

        logger.info("Stopping keyboard shortcut listener")
        self.active = False

        if self.listener:
            try:
                self.listener.stop()
                self.listener.join(timeout=1.0)
            except Exception as e:
                logger.error(f"Error stopping keyboard listener: {e}")
            finally:
                self.listener = None

    def register_toggle_callback(self, callback: Callable):
        """
        Register a callback for the double-tap Ctrl shortcut.

        Args:
            callback: Function to call when the double-tap Ctrl is pressed
        """
        self.double_tap_callback = callback
        logger.info("Registered shortcut: Double-tap Ctrl")

    def register_paste_callback(self, callback: Callable[[], None]):
        """Register a callback for paste-on-ppp (armed-only)."""
        self._paste_callback = callback
        logger.info("Registered shortcut: ppp (armed-only)")

    def arm_paste(self, duration_seconds: float = 20.0):
        """Arm the triple-press 'p' detector for a limited time."""
        if duration_seconds <= 0:
            self.disarm_paste()
            return
        self._paste_armed_until = time.time() + float(duration_seconds)
        self._paste_ppp_times = []
        logger.debug(f"Paste armed for {duration_seconds:.1f}s")

    def disarm_paste(self):
        """Disarm the triple-press 'p' detector."""
        self._paste_armed_until = 0.0
        self._paste_ppp_times = []

    @property
    def paste_armed(self) -> bool:
        return time.time() < self._paste_armed_until

    def _on_press(self, key):
        """
        Handle key press events.

        Args:
            key: The pressed key
        """
        try:
            # Check for double-tap Ctrl
            normalized_key = self._normalize_modifier_key(key)
            if normalized_key == keyboard.Key.ctrl:
                current_time = time.time()
                if current_time - self.last_ctrl_press_time < self.double_tap_threshold:
                    # This is a double-tap Ctrl
                    if (
                        self.double_tap_callback
                        and current_time - self.last_trigger_time > 0.5
                    ):
                        logger.debug("Double-tap Ctrl detected")
                        self.last_trigger_time = current_time
                        # Run callback in a separate thread to avoid blocking
                        threading.Thread(
                            target=self.double_tap_callback, daemon=True
                        ).start()
                self.last_ctrl_press_time = current_time

            # Triple-press 'p' (armed-only)
            if self.paste_armed and self._paste_callback is not None:
                key_char = None
                try:
                    # pynput uses KeyCode for character keys
                    key_char = getattr(key, "char", None)
                except Exception:
                    key_char = None

                if key_char and key_char.lower() == "p":
                    now = time.time()
                    # Expire arm if needed
                    if now >= self._paste_armed_until:
                        self.disarm_paste()
                    else:
                        self._paste_ppp_times.append(now)
                        # Keep only last 3
                        if len(self._paste_ppp_times) > 3:
                            self._paste_ppp_times = self._paste_ppp_times[-3:]

                        if (
                            len(self._paste_ppp_times) == 3
                            and (self._paste_ppp_times[-1] - self._paste_ppp_times[0])
                            <= self._ppp_total_window
                            and (now - self._last_ppp_trigger_time)
                            > self._ppp_trigger_cooldown
                        ):
                            logger.debug("ppp detected (armed)")
                            self._last_ppp_trigger_time = now
                            self.disarm_paste()
                            threading.Thread(
                                target=self._paste_callback, daemon=True
                            ).start()

            # Add to currently pressed modifier keys (only for tracking Ctrl)
            if key in {
                keyboard.Key.ctrl,
                keyboard.Key.ctrl_l,
                keyboard.Key.ctrl_r,
            }:
                # Normalize left/right variants
                normalized_key = self._normalize_modifier_key(key)
                self.current_keys.add(normalized_key)

        except Exception as e:
            logger.error(f"Error in keyboard shortcut handling: {e}")

    def _on_release(self, key):
        """
        Handle key release events.

        Args:
            key: The released key
        """
        try:
            # Normalize the key for left/right variants
            normalized_key = self._normalize_modifier_key(key)
            # Remove from currently pressed keys
            self.current_keys.discard(normalized_key)
        except Exception as e:
            logger.error(f"Error in keyboard release handling: {e}")

    def _normalize_modifier_key(self, key):
        """Normalize left/right variants of modifier keys to their base form."""
        # Map left/right variants to their base key
        key_mapping = {
            keyboard.Key.alt_l: keyboard.Key.alt,
            keyboard.Key.alt_r: keyboard.Key.alt,
            keyboard.Key.shift_l: keyboard.Key.shift,
            keyboard.Key.shift_r: keyboard.Key.shift,
            keyboard.Key.ctrl_l: keyboard.Key.ctrl,
            keyboard.Key.ctrl_r: keyboard.Key.ctrl,
            keyboard.Key.cmd_l: keyboard.Key.cmd,
            keyboard.Key.cmd_r: keyboard.Key.cmd,
        }

        return key_mapping.get(key, key)
