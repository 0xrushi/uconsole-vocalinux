#!/bin/bash
# Script to install Vocalinux as a systemd user service

set -e

SERVICE_FILE="vocalinux.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
VENV_BIN="$HOME/.local/share/vocalinux/venv/bin/vocalinux"

# Ensure the service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: $SERVICE_FILE not found in current directory."
    exit 1
fi

# Create systemd user directory
mkdir -p "$SYSTEMD_USER_DIR"

# Copy the service file
cp "$SERVICE_FILE" "$SYSTEMD_USER_DIR/"

# Update ExecStart path if venv location is different from default in service file
# (This handles if the user installed to a custom location)
if [ -f "venv/bin/vocalinux" ]; then
    CURRENT_VENV_BIN="$(realpath venv/bin/vocalinux)"
    sed -i "s|ExecStart=.*|ExecStart=$CURRENT_VENV_BIN|" "$SYSTEMD_USER_DIR/$SERVICE_FILE"
fi

# Reload systemd
systemctl --user daemon-reload

echo "Vocalinux systemd service installed successfully."
echo "To enable autostart on login:"
echo "  systemctl --user enable vocalinux.service"
echo "To start immediately:"
echo "  systemctl --user start vocalinux.service"
echo "To check status:"
echo "  systemctl --user status vocalinux.service"
