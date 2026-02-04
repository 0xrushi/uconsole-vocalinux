# User Guide

This guide explains how to use Vocalinux effectively.

## Getting Started

After installing Vocalinux (see the [Installation Guide](INSTALL.md)), you can start the application from the terminal or add it to your startup applications.

## Basic Usage

### Starting and Stopping Voice Typing

1. **Launch the application**: Run `vocalinux` in a terminal or launch it from your application menu
2. **Find the tray icon**: Look for the microphone icon in your system tray
3. **Start voice typing**: Click the tray icon and select "Start Voice Typing" from the menu, or use the double-tap Ctrl keyboard shortcut
4. **Speak clearly**: As you speak, your words will be transcribed into the currently focused application
5. **Stop voice typing**: Click the tray icon and select "Stop Voice Typing" when you're done, or use the double-tap Ctrl keyboard shortcut again

### Popup After Record (Optional)

You can run Vocalinux in a mode where it does not type while recording. Instead, it shows a popup when recording completes so you can edit/correct the transcript first.

```bash
vocalinux --popup-after-record
```

To use a terminal-style popup with a modern TUI interface (recommended for floating window managers like Openbox/i3wm):

```bash
vocalinux --popup-after-record --popup-ui textual
```

To use the GTK popup:

```bash
vocalinux --popup-after-record --popup-ui gtk
```

In this mode:

- Vocalinux does **not** type while recording.
- When you stop recording, a popup opens with the transcript in an editable field.
- Press `Esc` to enable hotkeys:
  - `a`: Correct for email
  - `b`: Correct for post/message
  - `c`: Correct bash command
- Press `Enter` to copy the text to the clipboard and close the popup.
- After the popup closes, you have 20 seconds to press `ppp` to paste into the focused window.

Openbox floating hint (Textual popup): set a rule to float windows with WM_CLASS `vocalinux-popup`.

LLM settings are read from `~/.config/vocalinux/config.yaml`.

Example:

```yaml
llm:
  provider: gemini
  model: gemini-1.5-flash
  api_key_env: GEMINI_API_KEY
  timeout_seconds: 20
  temperature: 0.2
```

### Understanding the Status Icons

- **Microphone off** (gray): Voice typing is inactive
- **Microphone on** (blue): Voice typing is active and listening
- **Microphone processing** (orange): Voice typing is processing your speech

## Voice Commands

Vocalinux supports several commands that you can speak to control formatting:

| Command | Action |
|---------|--------|
| "new line" or "new paragraph" | Inserts a line break |
| "period" or "full stop" | Types a period (.) |
| "comma" | Types a comma (,) |
| "question mark" | Types a question mark (?) |
| "exclamation point" or "exclamation mark" | Types an exclamation point (!) |
| "semicolon" | Types a semicolon (;) |
| "colon" | Types a colon (:) |
| "delete that" or "scratch that" | Deletes the last sentence |
| "capitalize" or "uppercase" | Capitalizes the next word |
| "all caps" | Makes the next word ALL CAPS |

## Tips for Better Recognition

1. **Use a good microphone**: A quality microphone significantly improves recognition accuracy
2. **Speak clearly**: Enunciate your words clearly but naturally
3. **Moderate pace**: Don't speak too quickly or too slowly
4. **Quiet environment**: Minimize background noise when possible
5. **Learn commands**: Familiarize yourself with voice commands for punctuation and formatting
6. **Use larger models**: For better accuracy, use `vocalinux --model medium` or `--model large`

## Customization

### Keyboard Shortcut

Vocalinux uses a double-tap Ctrl keyboard shortcut for starting and stopping voice typing:

- **Double-tap Ctrl**: Quickly press the Ctrl key twice to toggle voice typing on or off
- The time between taps should be less than 0.3 seconds to be recognized as a double-tap

When using `--popup-after-record`, `ppp` is enabled only after closing the popup with `Enter` and expires after 20 seconds.

### Model Settings

You can change the speech recognition model for better accuracy or faster performance:

1. Open settings from the tray icon menu
2. Go to the "Recognition" tab
3. Select your preferred model size (tiny is the default, use larger models for better accuracy)
4. Choose between Whisper (default, more accurate) and VOSK (lighter weight, faster)

## Troubleshooting

If you encounter issues, check the [Installation Guide](INSTALL.md) troubleshooting section or run the application with debug logging:

```bash
vocalinux --debug
```

Check the logs for error messages and possible solutions.
