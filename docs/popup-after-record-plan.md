# Popup After Record Plan (vocalinux --popup-after-record)

## Behavior Contract
- [x] When `--popup-after-record` is enabled:
- [x] Do NOT inject/type any recognized text while recording
- [x] Collect transcript internally during recording session
- [x] Show popup after recording completes (on stop / transition to IDLE)
- [x] Close popup with `Enter` (copies to clipboard)
- [x] Only paste after popup closes and global `ppp` is detected
- [x] `ppp` is armed for 20 seconds after popup close

## UI
- [x] GTK popup with editable text field
- [x] `Esc` toggles hotkey mode; in hotkey mode:
- [x] `a`: Correct for email
- [x] `b`: Correct for post/message
- [x] `c`: Correct bash command
- [x] `Enter`: copy to clipboard + close

## LLM Integration
- [x] Read LLM settings from `~/.config/vocalinux/config.yaml`
- [x] Provider: Gemini
- [x] `llm.api_key_env` recommended (env var)
- [x] Prompts for email / post / bash command correction

## Paste Workflow
- [x] After popup closes via `Enter`, arm a global `ppp` trigger for 20s
- [x] When `ppp` is detected while armed:
- [x] Focus the previous window best-effort (X11/XWayland)
- [x] Paste via Ctrl+V injection
