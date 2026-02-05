# Command Logging (for Bash Correction History)

Vocalinux’s “correct bash command” mode can optionally reuse your **real shell command history** to fix common dictation mistakes (example: “git stat” → `git status`) before calling the LLM.

This requires a lightweight command logger in your shell that writes TSV lines to:

- `~/.bash_command_log.tsv` (bash)
- `~/.zsh_command_log.tsv` (zsh)

## TSV format

Vocalinux reads tab-separated lines with **at least 6 columns**:

1. timestamp (ISO-8601 recommended)
2. `user@host`
3. working directory (`PWD`)
4. `true`/`false` (whether the command succeeded)
5. exit code (number)
6. command (the command line)

Example:

```tsv
2026-02-04T12:00:00-05:00	doraemon@doraemon-arch	/home/doraemon/Documents/vocalinux	true	0	git status
```

## Bash: add to `~/.bashrc`

Append something like this (interactive shells only):

```bash
# --- Vocalinux command outcome logger (bash) ---
[[ $- != *i* ]] && return

export CMDLOG_FILE="${CMDLOG_FILE:-$HOME/.bash_command_log.tsv}"

__vocalinux_log_last_command() {
  local exit_code=$?
  local ts host cwd last_cmd ok

  ts="$(date -Is)"
  host="${HOSTNAME:-$(hostname 2>/dev/null || echo unknown)}"
  cwd="$PWD"

  # Most recent command (strip leading history number)
  last_cmd="$(history 1 | sed 's/^[[:space:]]*[0-9]\\+[[:space:]]*//')"
  [[ -z "${last_cmd//[[:space:]]/}" ]] && return

  ok=false
  (( exit_code == 0 )) && ok=true

  # time, user@host, cwd, ok, exit_code, command
  printf '%s\t%s@%s\t%s\t%s\t%s\t%s\n' \
    "$ts" "$USER" "$host" "$cwd" "$ok" "$exit_code" "$last_cmd" >> "$CMDLOG_FILE"
}

# Chain into PROMPT_COMMAND without clobbering existing hooks
if [[ -n "$PROMPT_COMMAND" ]]; then
  PROMPT_COMMAND="__vocalinux_log_last_command; $PROMPT_COMMAND"
else
  PROMPT_COMMAND="__vocalinux_log_last_command"
fi

chmod 600 "$CMDLOG_FILE" 2>/dev/null || true
# --- end Vocalinux logger ---
```

Restart your shell (or `source ~/.bashrc`).

## Zsh: add to `~/.zshrc`

Append something like this (interactive shells only):

```zsh
# --- Vocalinux command outcome logger (zsh) ---
[[ -o interactive ]] || return

export CMDLOG_FILE="${CMDLOG_FILE:-$HOME/.zsh_command_log.tsv}"

__vocalinux_log_last_command() {
  local exit_code=$?
  local ts host cwd last_cmd ok

  ts="$(date -Is)"
  host="${HOSTNAME:-$(uname -n 2>/dev/null || echo unknown)}"
  cwd="$PWD"

  # Most recent command
  last_cmd="$(fc -ln -1)"
  [[ -z "${last_cmd//[[:space:]]/}" ]] && return

  ok=false
  (( exit_code == 0 )) && ok=true

  # time, user@host, cwd, ok, exit_code, command
  printf '%s\t%s@%s\t%s\t%s\t%s\t%s\n' \
    "$ts" "$USER" "$host" "$cwd" "$ok" "$exit_code" "$last_cmd" >> "$CMDLOG_FILE"
}

autoload -Uz add-zsh-hook
add-zsh-hook precmd __vocalinux_log_last_command

chmod 600 "$CMDLOG_FILE" 2>/dev/null || true
# --- end Vocalinux logger ---
```

Restart your shell (or `source ~/.zshrc`).

## Verify it’s working

Run a couple commands, then:

```bash
tail -n 3 ~/.bash_command_log.tsv
tail -n 3 ~/.zsh_command_log.tsv
```

You should see new TSV lines with your current `PWD` and the command.

## Privacy / safety notes

- These log files contain **everything you type**, which may include secrets (tokens, passwords, private URLs).
- If you don’t want to log certain commands, add filtering inside the logger (for example, skip lines matching `*token*`).
- Keep permissions tight: `chmod 600 ~/.bash_command_log.tsv ~/.zsh_command_log.tsv`.

