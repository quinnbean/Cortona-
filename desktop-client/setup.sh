#!/bin/bash
# Cortona Desktop Client - One-Time Setup
# This installs the desktop client to run automatically on login

set -e

echo "🎛️ Cortona Desktop Client Setup"
echo "================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLIENT_SCRIPT="$SCRIPT_DIR/cortona-client.py"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
LAUNCH_AGENT_FILE="$LAUNCH_AGENT_DIR/com.cortona.desktop-client.plist"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install it from https://www.python.org/downloads/"
    exit 1
fi
echo "✅ Python 3 found: $(python3 --version)"

# Install required Python packages
echo ""
echo "📦 Installing Python dependencies..."
pip3 install --user pyautogui pyperclip python-socketio[client] requests --quiet
echo "✅ Dependencies installed"

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENT_DIR"

# Create the LaunchAgent plist
echo ""
echo "⚙️  Setting up auto-start..."
cat > "$LAUNCH_AGENT_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cortona.desktop-client</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$CLIENT_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/cortona-client.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cortona-client.log</string>
</dict>
</plist>
EOF

# Load the LaunchAgent
launchctl unload "$LAUNCH_AGENT_FILE" 2>/dev/null || true
launchctl load "$LAUNCH_AGENT_FILE"

echo "✅ Desktop client installed and started!"
echo ""
echo "📍 The client will now:"
echo "   - Run automatically when you log in"
echo "   - Stay running in the background"
echo "   - Restart if it crashes"
echo ""
echo "🔧 To check status:  launchctl list | grep cortona"
echo "🔧 To view logs:     tail -f /tmp/cortona-client.log"
echo "🔧 To stop:          launchctl unload ~/Library/LaunchAgents/com.cortona.desktop-client.plist"
echo ""
echo "✨ Setup complete! You can close this window."

