"""Tests for popup-after-record flow (non-GUI logic)."""

import unittest
from unittest.mock import MagicMock, patch


from vocalinux.common_types import RecognitionState


class _FakeSpeechEngine:
    def __init__(self):
        self._state_cbs = []
        self._text_cbs = []

    def register_state_callback(self, cb):
        self._state_cbs.append(cb)

    def register_text_callback(self, cb):
        self._text_cbs.append(cb)

    def emit_state(self, state):
        for cb in list(self._state_cbs):
            cb(state)

    def emit_text(self, text):
        for cb in list(self._text_cbs):
            cb(text)


class _FakeShortcutMgr:
    def __init__(self):
        self.paste_cb = None
        self.armed_for = None
        self.armed = False

    def register_paste_callback(self, cb):
        self.paste_cb = cb

    def arm_paste(self, seconds):
        self.armed_for = seconds
        self.armed = True


class TestPopupAfterRecordFlow(unittest.TestCase):
    def test_buffers_text_and_arms_on_complete(self):
        from vocalinux.ui import popup_after_record as mod

        speech = _FakeSpeechEngine()
        ti = MagicMock()
        ti.get_active_window_id.return_value = "123"

        shortcuts = _FakeShortcutMgr()

        # Make GLib.idle_add synchronous
        class _FakeGLib:
            @staticmethod
            def idle_add(fn, *args, **kwargs):
                return fn(*args)

        # Fake popup that immediately completes
        class _FakePopup:
            def __init__(self, initial_text, on_complete, title=None):
                self.initial_text = initial_text
                on_complete(mod.PopupResult(text=initial_text))

            def set_keep_above(self, *_):
                pass

            def show_all(self):
                pass

            def present(self):
                pass

        with patch.object(mod, "GLib", _FakeGLib), patch.object(
            mod, "PostRecordPopup", _FakePopup
        ):
            flow = mod.PopupAfterRecordFlow(
                speech_engine=speech,
                text_injector=ti,
                shortcut_manager=shortcuts,
                arm_seconds=20.0,
                ui="gtk",
            )

            speech.emit_state(RecognitionState.LISTENING)
            speech.emit_text("hello")
            speech.emit_text("world")
            speech.emit_state(RecognitionState.IDLE)

            self.assertTrue(shortcuts.armed)
            self.assertEqual(shortcuts.armed_for, 20.0)

            # Ensure target window captured
            ti.get_active_window_id.assert_called()
            self.assertEqual(flow._armed_window_id, "123")

    def test_ppp_pastes_and_clears_ppp_chars(self):
        from vocalinux.ui.popup_after_record import PopupAfterRecordFlow

        speech = _FakeSpeechEngine()
        ti = MagicMock()
        shortcuts = _FakeShortcutMgr()

        flow = PopupAfterRecordFlow(
            speech_engine=speech,
            text_injector=ti,
            shortcut_manager=shortcuts,
            arm_seconds=20.0,
            ui="gtk",
        )

        flow._armed_window_id = "123"
        with patch("vocalinux.ui.popup_after_record.time.sleep"):
            flow._on_ppp()

        ti.activate_window.assert_called_with("123")
        ti.inject_text.assert_called_with("\b\b\b")
        ti._inject_keyboard_shortcut.assert_called_with("ctrl+v")

    def test_terminal_popup_arms_after_close(self):
        import tempfile

        from vocalinux.ui import popup_after_record as mod

        speech = _FakeSpeechEngine()
        ti = MagicMock()
        ti.get_active_window_id.return_value = "123"
        shortcuts = _FakeShortcutMgr()

        # Make GLib.idle_add synchronous
        class _FakeGLib:
            @staticmethod
            def idle_add(fn, *args, **kwargs):
                return fn(*args)

        # Make thread run inline
        class _InlineThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None):
                self._target = target
                self._args = args
                self._kwargs = kwargs or {}

            def start(self):
                if self._target:
                    self._target(*self._args, **self._kwargs)

        # Fake terminal spec
        class _Spec:
            def __init__(self, argv):
                self.argv = argv

        def fake_build_terminal_launch(*, python_argv, **_):
            return _Spec(["fake-term", *python_argv])

        def fake_popen(argv, *args, **kwargs):
            # argv is what terminal would run; find '--output' from embedded python_argv
            out_path = None
            if "--output" in argv:
                i = argv.index("--output")
                if i + 1 < len(argv):
                    out_path = argv[i + 1]

            class _Proc:
                def wait(self_inner):
                    if out_path:
                        with open(out_path, "w", encoding="utf-8") as f:
                            f.write("final text\n")
                    return 0

            return _Proc()

        with tempfile.TemporaryDirectory() as td:
            with patch.object(mod, "GLib", _FakeGLib), patch(
                "vocalinux.ui.popup_after_record.tempfile.mkdtemp", return_value=td
            ), patch(
                "vocalinux.ui.popup_after_record.build_terminal_launch",
                side_effect=fake_build_terminal_launch,
            ), patch(
                "vocalinux.ui.popup_after_record.threading.Thread",
                _InlineThread,
            ), patch(
                "subprocess.Popen",
                side_effect=fake_popen,
            ), patch(
                "vocalinux.ui.popup_after_record.set_clipboard_text",
                return_value=True,
            ) as mock_set_clip:
                flow = mod.PopupAfterRecordFlow(
                    speech_engine=speech,
                    text_injector=ti,
                    shortcut_manager=shortcuts,
                    arm_seconds=20.0,
                    ui="terminal",
                )

                speech.emit_state(RecognitionState.LISTENING)
                speech.emit_text("hello")
                speech.emit_state(RecognitionState.IDLE)

                mock_set_clip.assert_called()
                self.assertTrue(shortcuts.armed)
                self.assertEqual(shortcuts.armed_for, 20.0)
                self.assertEqual(flow._armed_window_id, "123")
