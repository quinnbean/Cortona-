#!/usr/bin/env python3 -u
"""
Cortona Desktop Client - Controls apps on your computer
Connects to: https://cortona.onrender.com
"""

import os
import sys
import time
import subprocess
import platform

# Force unbuffered output for logging
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
os.environ['PYTHONUNBUFFERED'] = '1'

# Install dependencies if missing
def ensure_deps():
    deps = ['pyautogui', 'pyperclip', 'python-socketio[client]', 'requests']
    for dep in deps:
        pkg_name = dep.split('[')[0].replace('-', '_')
        try:
            __import__(pkg_name)
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', dep])

ensure_deps()

import pyautogui
import pyperclip
import socketio
import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

VERSION = "1.5.0"
SERVER_URL = "https://cortona.onrender.com"
PLATFORM = platform.system()

# Disable PyAutoGUI fail-safe for smoother operation
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# ============================================================================
# APP CONTROL
# ============================================================================

APPS = {
    'cursor': {'Darwin': 'Cursor', 'Windows': 'Cursor.exe', 'Linux': 'cursor'},
    'chrome': {'Darwin': 'Google Chrome', 'Windows': 'chrome.exe', 'Linux': 'google-chrome'},
    'claude': {'Darwin': 'Google Chrome', 'Windows': 'chrome.exe', 'Linux': 'google-chrome', 'url': 'https://claude.ai'},
    'chatgpt': {'Darwin': 'Google Chrome', 'Windows': 'chrome.exe', 'Linux': 'google-chrome', 'url': 'https://chat.openai.com'},
    'terminal': {'Darwin': 'Terminal', 'Windows': 'cmd.exe', 'Linux': 'gnome-terminal'},
    'vscode': {'Darwin': 'Visual Studio Code', 'Windows': 'Code.exe', 'Linux': 'code'},
    'slack': {'Darwin': 'Slack', 'Windows': 'slack.exe', 'Linux': 'slack'},
    'discord': {'Darwin': 'Discord', 'Windows': 'Discord.exe', 'Linux': 'discord'},
    'notes': {'Darwin': 'Notes', 'Windows': 'notepad.exe', 'Linux': 'gedit'},
    'finder': {'Darwin': 'Finder', 'Windows': 'explorer.exe', 'Linux': 'nautilus'}
}

def focus_app(app_name):
    """Bring an app to the foreground"""
    app_name = app_name.lower().strip()
    app_info = APPS.get(app_name, {})
    app_id = app_info.get(PLATFORM, app_name)
    
    try:
        if PLATFORM == 'Darwin':
            script = f'tell application "{app_id}" to activate'
            subprocess.run(['osascript', '-e', script], capture_output=True)
            print(f"✅ Focused: {app_id}")
            
            if 'url' in app_info:
                time.sleep(0.5)
                subprocess.run(['open', app_info['url']], capture_output=True)
                
        elif PLATFORM == 'Windows':
            if 'url' in app_info:
                subprocess.run(['start', app_info['url']], shell=True, capture_output=True)
            else:
                subprocess.run(['powershell', '-Command', 
                    f'(New-Object -ComObject WScript.Shell).AppActivate("{app_id}")'], 
                    capture_output=True)
            print(f"✅ Focused: {app_id}")
            
        elif PLATFORM == 'Linux':
            if 'url' in app_info:
                subprocess.run(['xdg-open', app_info['url']], capture_output=True)
            else:
                subprocess.run(['wmctrl', '-a', app_id], capture_output=True)
            print(f"✅ Focused: {app_id}")
            
        time.sleep(0.3)
        return True
        
    except Exception as e:
        print(f"⚠️ Could not focus {app_name}: {e}")
        return False

def type_text(text):
    """Type text using clipboard + paste for reliability"""
    try:
        pyperclip.copy(text)
        time.sleep(0.1)
        
        if PLATFORM == 'Darwin':
            pyautogui.hotkey('command', 'v')
        else:
            pyautogui.hotkey('ctrl', 'v')
            
        print(f"✅ Typed: {text[:50]}...")
        return True
    except Exception as e:
        print(f"⚠️ Could not type: {e}")
        return False

def press_enter():
    """Press Enter key"""
    pyautogui.press('enter')

def open_url(url):
    """Open a URL"""
    try:
        if PLATFORM == 'Darwin':
            subprocess.run(['open', url], check=True)
        elif PLATFORM == 'Windows':
            os.startfile(url)
        else:
            subprocess.run(['xdg-open', url], check=True)
        print(f"✅ Opened: {url}")
        return True
    except Exception as e:
        print(f"⚠️ Could not open URL: {e}")
        return False

def search_google(query):
    """Search Google"""
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return open_url(url)

# ============================================================================
# SOCKET.IO CLIENT
# ============================================================================

class CortonaClient:
    def __init__(self):
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=5)
        self.device_id = self._get_device_id()
        self.device_name = platform.node() or 'Desktop Client'
        self._setup_handlers()
        
    def _get_device_id(self):
        """Generate a unique device ID"""
        import hashlib
        unique_str = f"{platform.node()}-{platform.system()}-desktop"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def _setup_handlers(self):
        @self.sio.event
        def connect():
            print(f"✅ Connected to {SERVER_URL}")
            self.sio.emit('register_device', {
                'device': {
                    'id': self.device_id,
                    'name': self.device_name,
                    'icon': 'desktop',
                    'wakeWord': self.device_name.lower().split('.')[0],
                    'type': 'desktop_client',
                    'platform': PLATFORM
                }
            })
        
        @self.sio.event
        def disconnect():
            print("❌ Disconnected from server")
        
        @self.sio.event
        def connect_error(data):
            print(f"⚠️ Connection error: {data}")
        
        @self.sio.on('command_received')
        def on_command(data):
            print(f"\n📥 Received command: {data}")
            self._execute_command(data)
        
        # Also listen for the old event name for compatibility
        @self.sio.on('execute_command')
        def on_command_legacy(data):
            print(f"\n📥 Received command (legacy): {data}")
            self._execute_command(data)
    
    def _execute_command(self, data):
        """Execute a received command"""
        command = data.get('command', '')
        action = data.get('action', 'type')
        target_app = data.get('targetApp', None)
        
        if not command:
            print("⚠️ Empty command received")
            return
        
        print(f"🎯 Action: {action}, App: {target_app}, Command: {command[:50]}...")
        
        # Focus the app if specified
        if target_app:
            focus_app(target_app)
            time.sleep(0.3)
        
        # Execute based on action
        if action == 'type':
            type_text(command)
        elif action == 'type_and_send':
            type_text(command)
            time.sleep(0.1)
            press_enter()
        elif action == 'run':
            type_text(command)
            time.sleep(0.1)
            press_enter()
        elif action == 'open_url':
            open_url(command)
        elif action == 'search':
            search_google(command)
        elif action == 'open':
            focus_app(command)
        else:
            # Default to typing
            type_text(command)
    
    def connect(self):
        """Connect to the server"""
        try:
            print(f"🔌 Connecting to {SERVER_URL}...")
            self.sio.connect(SERVER_URL, transports=['websocket', 'polling'])
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
    
    def run(self):
        """Run the client"""
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      🎛️ Cortona Desktop Client v{VERSION}                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Server: {SERVER_URL:<60} ║
║  Device: {self.device_name:<60} ║
║  ID:     {self.device_id:<60} ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
        
        while True:
            try:
                self.connect()
                self.sio.wait()
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"⚠️ Error: {e}")
                print("🔄 Reconnecting in 5 seconds...")
                time.sleep(5)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Check for accessibility permissions on macOS
    if PLATFORM == 'Darwin':
        try:
            # Test if we can control the keyboard
            pyautogui.press('shift')
        except Exception:
            print("""
⚠️ ACCESSIBILITY PERMISSION REQUIRED

To control other apps, you need to grant accessibility access:

1. Open System Preferences → Privacy & Security → Privacy → Accessibility
2. Click the lock 🔒 to make changes
3. Add Terminal (or the app running this script)
4. Make sure the checkbox is ✅ enabled

Then restart this script.
""")
    
    client = CortonaClient()
    client.run()

