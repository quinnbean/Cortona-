"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        🎛️ VOICE HUB - CLOUD SERVER                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Browser-based voice recognition - no terminal needed!                       ║
║  Deploy on Render, login, and start dictating                                ║
║  Login: admin / voicehub123 (or set ADMIN_PASSWORD env variable)             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import secrets
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, Response
from flask_socketio import SocketIO, emit, join_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Claude AI for intelligent command parsing
try:
    import anthropic
    CLAUDE_AVAILABLE = bool(os.environ.get('ANTHROPIC_API_KEY'))
    if CLAUDE_AVAILABLE:
        claude_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        print("🧠 Claude AI enabled for intelligent command parsing")
    else:
        claude_client = None
        print("⚠️ ANTHROPIC_API_KEY not set - using regex parsing")
except ImportError:
    CLAUDE_AVAILABLE = False
    claude_client = None
    print("⚠️ anthropic package not installed - using regex parsing")

# ============================================================================
# SETUP
# ============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.remember_cookie_duration = timedelta(days=30)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '1281Cherry!')
USERS = {'admin': {'password_hash': generate_password_hash(ADMIN_PASSWORD), 'name': 'Admin'}}

# Store devices and their settings
devices = {}
# Store active listening sessions
active_sessions = {}

# ============================================================================
# INSTALL PAGE - SUPER EASY SETUP
# ============================================================================

INSTALL_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub - Install Desktop Client</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --border: rgba(255,255,255,0.08);
            --accent: #00f5d4;
            --accent-2: #7b2cbf;
            --text: #ffffff;
            --text-muted: #6b7280;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            color: var(--text);
            min-height: 100vh;
            padding: 40px 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 48px;
        }
        .logo {
            font-size: 64px;
            margin-bottom: 16px;
        }
        h1 {
            font-size: 36px;
            margin-bottom: 12px;
        }
        h1 span { color: var(--accent); }
        .subtitle {
            color: var(--text-muted);
            font-size: 18px;
        }
        .os-tabs {
            display: flex;
            gap: 12px;
            margin-bottom: 32px;
            justify-content: center;
        }
        .os-tab {
            padding: 14px 28px;
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: 12px;
            cursor: pointer;
            font-family: inherit;
            font-size: 16px;
            font-weight: 500;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.2s;
        }
        .os-tab:hover {
            border-color: var(--accent);
            color: var(--text);
        }
        .os-tab.active {
            border-color: var(--accent);
            background: rgba(0, 245, 212, 0.1);
            color: var(--accent);
        }
        .os-tab .icon { font-size: 24px; }
        .install-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 32px;
            margin-bottom: 32px;
        }
        .step {
            margin-bottom: 32px;
        }
        .step:last-child { margin-bottom: 0; }
        .step-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }
        .step-number {
            width: 36px;
            height: 36px;
            background: var(--accent);
            color: var(--bg-primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }
        .step h3 {
            font-size: 20px;
        }
        .step p {
            color: var(--text-muted);
            margin-bottom: 16px;
            line-height: 1.6;
        }
        .code-box {
            position: relative;
            background: var(--bg-primary);
            border-radius: 12px;
            padding: 20px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            color: var(--accent);
            overflow-x: auto;
            word-break: break-all;
        }
        .code-box code {
            display: block;
        }
        .copy-btn {
            position: absolute;
            top: 12px;
            right: 12px;
            padding: 8px 16px;
            background: var(--accent);
            color: var(--bg-primary);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .copy-btn:hover {
            transform: scale(1.05);
        }
        .copy-btn.copied {
            background: #10b981;
        }
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 24px;
        }
        .feature {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .feature .icon {
            font-size: 24px;
        }
        .feature span {
            font-size: 14px;
        }
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--text-muted);
            text-decoration: none;
            margin-bottom: 32px;
        }
        .back-link:hover {
            color: var(--accent);
        }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to Dashboard</a>
        
        <div class="header">
            <div class="logo">🎛️</div>
            <h1><span>Voice Hub</span> Desktop Client</h1>
            <p class="subtitle">Control any app on your computer with voice commands</p>
        </div>
        
        <!-- Big Download Buttons -->
        <div style="display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin-bottom: 40px;">
            <a href="/download/mac" class="download-btn" style="padding: 20px 32px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: var(--bg-primary); border-radius: 16px; text-decoration: none; font-weight: 600; font-size: 18px; display: flex; align-items: center; gap: 12px; transition: all 0.2s;">
                <span style="font-size: 28px;">🍎</span>
                <div style="text-align: left;">
                    <div>Download for Mac</div>
                    <div style="font-size: 12px; opacity: 0.8;">Double-click to install</div>
                </div>
            </a>
            <a href="/download/windows" class="download-btn" style="padding: 20px 32px; background: linear-gradient(135deg, #0078d4, #00bcf2); color: white; border-radius: 16px; text-decoration: none; font-weight: 600; font-size: 18px; display: flex; align-items: center; gap: 12px; transition: all 0.2s;">
                <span style="font-size: 28px;">🪟</span>
                <div style="text-align: left;">
                    <div>Download for Windows</div>
                    <div style="font-size: 12px; opacity: 0.8;">Double-click to install</div>
                </div>
            </a>
        </div>
        
        <p style="text-align: center; color: var(--text-muted); margin-bottom: 32px;">
            Or use the terminal commands below for advanced setup
        </p>
        
        <div class="os-tabs">
            <button class="os-tab active" onclick="showOS('mac')" id="tab-mac">
                <span class="icon">🍎</span> Mac
            </button>
            <button class="os-tab" onclick="showOS('windows')" id="tab-windows">
                <span class="icon">🪟</span> Windows
            </button>
            <button class="os-tab" onclick="showOS('linux')" id="tab-linux">
                <span class="icon">🐧</span> Linux
            </button>
        </div>
        
        <!-- Mac Instructions -->
        <div id="os-mac" class="install-section">
            <div class="step">
                <div class="step-header">
                    <div class="step-number">1</div>
                    <h3>Download & Open</h3>
                </div>
                <p>Click the <strong>"Download for Mac"</strong> button above. Find <strong>VoiceHub.command</strong> in your Downloads folder.</p>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">2</div>
                    <h3>First Time Only: Allow to Run</h3>
                </div>
                <p>Right-click the file → <strong>Open</strong> → Click <strong>"Open"</strong> in the popup. (Mac blocks unsigned apps by default)</p>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">3</div>
                    <h3>Grant Permissions</h3>
                </div>
                <p>Mac will ask for Accessibility permissions. Go to <strong>System Settings → Privacy & Security → Accessibility</strong> and enable Terminal.</p>
            </div>
            
            <div style="background: var(--bg-primary); border-radius: 12px; padding: 16px; margin-top: 20px;">
                <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 8px;">Alternative: Terminal command</p>
                <div class="code-box" style="margin: 0;">
                    <code id="mac-command">curl -sL {{ server }}/install.sh | bash</code>
                    <button class="copy-btn" onclick="copyCommand('mac-command', this)">📋 Copy</button>
                </div>
            </div>
            
            <div class="features">
                <div class="feature"><span class="icon">✅</span><span>No Terminal knowledge needed</span></div>
                <div class="feature"><span class="icon">✅</span><span>Auto-installs everything</span></div>
                <div class="feature"><span class="icon">✅</span><span>Double-click to run anytime</span></div>
            </div>
        </div>
        
        <!-- Windows Instructions -->
        <div id="os-windows" class="install-section hidden">
            <div class="step">
                <div class="step-header">
                    <div class="step-number">1</div>
                    <h3>Download & Open</h3>
                </div>
                <p>Click the <strong>"Download for Windows"</strong> button above. Find <strong>VoiceHub.bat</strong> in your Downloads folder and double-click it.</p>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">2</div>
                    <h3>Allow to Run</h3>
                </div>
                <p>If Windows shows a security warning, click <strong>"More info"</strong> → <strong>"Run anyway"</strong>.</p>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">3</div>
                    <h3>Install Python (if needed)</h3>
                </div>
                <p>If prompted, download Python from <a href="https://python.org" target="_blank" style="color: var(--accent);">python.org</a>. <strong>Important:</strong> Check "Add Python to PATH" during install!</p>
            </div>
            
            <div style="background: var(--bg-primary); border-radius: 12px; padding: 16px; margin-top: 20px;">
                <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 8px;">Alternative: PowerShell command</p>
                <div class="code-box" style="margin: 0;">
                    <code id="windows-command">irm {{ server }}/install.ps1 | iex</code>
                    <button class="copy-btn" onclick="copyCommand('windows-command', this)">📋 Copy</button>
                </div>
            </div>
            
            <div class="features">
                <div class="feature"><span class="icon">✅</span><span>No command line needed</span></div>
                <div class="feature"><span class="icon">✅</span><span>Auto-installs everything</span></div>
                <div class="feature"><span class="icon">✅</span><span>Double-click to run anytime</span></div>
            </div>
        </div>
        
        <!-- Linux Instructions -->
        <div id="os-linux" class="install-section hidden">
            <div class="step">
                <div class="step-header">
                    <div class="step-number">1</div>
                    <h3>Open Terminal</h3>
                </div>
                <p>Press <strong>Ctrl + Alt + T</strong> or find Terminal in your applications.</p>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">2</div>
                    <h3>Paste This Command</h3>
                </div>
                <p>Copy and paste this single command:</p>
                <div class="code-box">
                    <code id="linux-command">curl -sL {{ server }}/install.sh | bash</code>
                    <button class="copy-btn" onclick="copyCommand('linux-command', this)">📋 Copy</button>
                </div>
            </div>
            
            <div class="step">
                <div class="step-header">
                    <div class="step-number">3</div>
                    <h3>Install Dependencies (if needed)</h3>
                </div>
                <p>For X11/Wayland support: <code style="background: var(--bg-primary); padding: 4px 8px; border-radius: 4px;">sudo apt install python3-tk python3-dev</code></p>
            </div>
            
            <div class="features">
                <div class="feature"><span class="icon">✅</span><span>Works with bash/zsh</span></div>
                <div class="feature"><span class="icon">✅</span><span>X11 and Wayland support</span></div>
                <div class="feature"><span class="icon">✅</span><span>Debian/Ubuntu/Fedora</span></div>
            </div>
        </div>
    </div>
    
    <script>
        function showOS(os) {
            document.querySelectorAll('.os-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.install-section').forEach(s => s.classList.add('hidden'));
            document.getElementById('tab-' + os).classList.add('active');
            document.getElementById('os-' + os).classList.remove('hidden');
        }
        
        function copyCommand(id, btn) {
            const code = document.getElementById(id).textContent;
            navigator.clipboard.writeText(code).then(() => {
                btn.innerHTML = '✅ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.innerHTML = '📋 Copy';
                    btn.classList.remove('copied');
                }, 2000);
            });
        }
        
        // Auto-detect OS
        const ua = navigator.userAgent;
        if (ua.includes('Win')) showOS('windows');
        else if (ua.includes('Linux')) showOS('linux');
        // Default is Mac
    </script>
</body>
</html>
'''

# ============================================================================
# DESKTOP CLIENT - AUTO-CONFIGURED
# ============================================================================

DESKTOP_CLIENT = r'''#!/usr/bin/env python3
"""
Voice Hub Desktop Client - Controls apps on your computer
Auto-configured for: {{SERVER_URL}}
Version: {{VERSION}}
"""

import os
import sys
import time
import subprocess
import platform

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

VERSION = "{{VERSION}}"
SERVER_URL = "{{SERVER_URL}}"
# Ensure HTTPS for Render
if SERVER_URL.startswith('http://') and 'onrender.com' in SERVER_URL:
    SERVER_URL = SERVER_URL.replace('http://', 'https://')
PLATFORM = platform.system()
CLIENT_PATH = os.path.abspath(__file__)

# ============================================================================
# AUTO-UPDATE
# ============================================================================

def check_for_updates():
    """Check if a newer version is available and auto-update if so"""
    try:
        print(f"Checking for updates (current: v{VERSION})...")
        response = requests.get(f"{SERVER_URL}/api/version", timeout=10)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get('version', VERSION)
            
            if compare_versions(latest_version, VERSION) > 0:
                print(f"New version available: v{latest_version}")
                return update_client(data.get('download_url'))
            else:
                print(f"You have the latest version (v{VERSION})")
                return False
    except Exception as e:
        print(f"Could not check for updates: {e}")
    return False

def compare_versions(v1, v2):
    """Compare two version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal"""
    try:
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        
        # Pad shorter version with zeros
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
        
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    except:
        return 0

def update_client(download_url):
    """Download and install the new version"""
    try:
        print("Downloading update...")
        response = requests.get(download_url, timeout=30)
        if response.status_code == 200:
            # Write the new version
            new_content = response.text
            
            # Save to a temp file first
            temp_path = CLIENT_PATH + '.new'
            with open(temp_path, 'w') as f:
                f.write(new_content)
            
            # Replace the old file
            backup_path = CLIENT_PATH + '.backup'
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(CLIENT_PATH, backup_path)
            os.rename(temp_path, CLIENT_PATH)
            
            print("Update installed! Restarting...")
            time.sleep(1)
            
            # Restart the script
            os.execv(sys.executable, [sys.executable, CLIENT_PATH])
            return True
    except Exception as e:
        print(f"Update failed: {e}")
        # Try to restore backup
        if os.path.exists(backup_path):
            try:
                os.rename(backup_path, CLIENT_PATH)
                print("Restored previous version")
            except:
                pass
    return False

# ============================================================================
# APP CONTROL
# ============================================================================

# App identifiers for different platforms
APPS = {
    'cursor': {
        'Darwin': 'Cursor',
        'Windows': 'Cursor.exe',
        'Linux': 'cursor'
    },
    'chrome': {
        'Darwin': 'Google Chrome',
        'Windows': 'chrome.exe',
        'Linux': 'google-chrome'
    },
    'claude': {
        'Darwin': 'Google Chrome',  # Claude runs in browser
        'Windows': 'chrome.exe',
        'Linux': 'google-chrome',
        'url': 'https://claude.ai'
    },
    'chatgpt': {
        'Darwin': 'Google Chrome',
        'Windows': 'chrome.exe', 
        'Linux': 'google-chrome',
        'url': 'https://chat.openai.com'
    },
    'terminal': {
        'Darwin': 'Terminal',
        'Windows': 'cmd.exe',
        'Linux': 'gnome-terminal'
    },
    'vscode': {
        'Darwin': 'Visual Studio Code',
        'Windows': 'Code.exe',
        'Linux': 'code'
    },
    'slack': {
        'Darwin': 'Slack',
        'Windows': 'slack.exe',
        'Linux': 'slack'
    },
    'discord': {
        'Darwin': 'Discord',
        'Windows': 'Discord.exe',
        'Linux': 'discord'
    },
    'notes': {
        'Darwin': 'Notes',
        'Windows': 'notepad.exe',
        'Linux': 'gedit'
    },
    'finder': {
        'Darwin': 'Finder',
        'Windows': 'explorer.exe',
        'Linux': 'nautilus'
    }
}

def focus_app(app_name):
    """Bring an app to the foreground"""
    app_name = app_name.lower().strip()
    app_info = APPS.get(app_name, {})
    app_id = app_info.get(PLATFORM, app_name)
    
    try:
        if PLATFORM == 'Darwin':
            # macOS
            script = f'tell application "{app_id}" to activate'
            subprocess.run(['osascript', '-e', script], capture_output=True)
            print(f"✅ Focused: {app_id}")
            
            # If it's a web app, open the URL
            if 'url' in app_info:
                time.sleep(0.5)
                subprocess.run(['open', app_info['url']], capture_output=True)
                
        elif PLATFORM == 'Windows':
            # Windows - use PowerShell
            if 'url' in app_info:
                subprocess.run(['start', app_info['url']], shell=True, capture_output=True)
            else:
                # Try to focus the window
                subprocess.run(['powershell', '-Command', 
                    f'(New-Object -ComObject WScript.Shell).AppActivate("{app_id}")'], 
                    capture_output=True)
            print(f"✅ Focused: {app_id}")
            
        elif PLATFORM == 'Linux':
            # Linux - use wmctrl or xdotool
            if 'url' in app_info:
                subprocess.run(['xdg-open', app_info['url']], capture_output=True)
            else:
                subprocess.run(['wmctrl', '-a', app_id], capture_output=True)
            print(f"✅ Focused: {app_id}")
            
        time.sleep(0.3)  # Wait for app to focus
        return True
        
    except Exception as e:
        print(f"⚠️ Could not focus {app_name}: {e}")
        return False

def type_text(text):
    """Type text using the keyboard"""
    try:
        # Use clipboard + paste for reliability
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
    """Press the Enter key"""
    pyautogui.press('enter')

def run_command(command, app=None):
    """Run a command in terminal/shell"""
    if app:
        focus_app(app)
        time.sleep(0.3)
    
    type_text(command)
    time.sleep(0.1)
    press_enter()

# ============================================================================
# SOCKET.IO CLIENT
# ============================================================================

class VoiceHubClient:
    def __init__(self):
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=5)
        self.device_id = self._get_device_id()
        self.device_name = platform.node() or 'Desktop Client'
        self._setup_handlers()
        
    def _get_device_id(self):
        """Get or create a persistent device ID"""
        id_file = os.path.expanduser('~/.voicehub/device_id')
        os.makedirs(os.path.dirname(id_file), exist_ok=True)
        
        if os.path.exists(id_file):
            with open(id_file, 'r') as f:
                return f.read().strip()
        else:
            import uuid
            device_id = f"desktop_{uuid.uuid4().hex[:8]}"
            with open(id_file, 'w') as f:
                f.write(device_id)
            return device_id
    
    def _setup_handlers(self):
        """Set up Socket.IO event handlers"""
        
        @self.sio.event
        def connect():
            print("Connected to Voice Hub!")
            self.sio.emit('dashboard_join', {'deviceId': self.device_id})
            self.sio.emit('device_update', {
                'deviceId': self.device_id,
                'settings': {
                    'id': self.device_id,
                    'name': self.device_name,
                    'icon': 'desktop',
                    'wakeWord': self.device_name.lower().split('.')[0],
                    'type': 'desktop_client',
                    'platform': PLATFORM
                }
            })
            print(f"Registered as: {self.device_name} ({self.device_id})")
        
        @self.sio.event
        def disconnect():
            print("Disconnected from Voice Hub")
        
        @self.sio.event
        def connect_error(data):
            print(f"Connection error: {data}")
        
        @self.sio.on('devices_update')
        def on_devices_update(data):
            count = len(data.get('devices', {}))
            print(f"Devices online: {count}")
        
        @self.sio.on('command_received')
        def on_command_received(data):
            print(f"\\n{'='*50}")
            print(f"COMMAND RECEIVED!")
            print(f"{'='*50}")
            self._execute_command(data)
        
        @self.sio.on('update_available')
        def on_update_available(data):
            """Server notified us of a new version - update now!"""
            new_version = data.get('version', 'unknown')
            print(f"\n{'='*60}")
            print(f"New version available: v{new_version} (current: v{VERSION})")
            print(f"{'='*60}")
            if compare_versions(new_version, VERSION) > 0:
                download_url = data.get('download_url')
                # If relative URL, prepend server URL
                if download_url and not download_url.startswith('http'):
                    download_url = SERVER_URL + download_url
                if download_url:
                    print(f"Downloading update from {download_url}...")
                    update_client(download_url)
            else:
                print("Already up to date!")
    
    def _execute_command(self, data):
        """Execute a received command"""
        command = data.get('command', '')
        action = data.get('action', 'type')
        target_app = data.get('targetApp')
        from_device = data.get('fromDeviceId', 'unknown')
        
        print(f"\nCommand from {from_device}:")
        print(f"  Action: {action}")
        print(f"  Target: {target_app or 'current app'}")
        print(f"  Text: {command[:50]}{'...' if len(command) > 50 else ''}")
        
        # Focus target app if specified
        if target_app:
            focus_app(target_app)
            time.sleep(0.5)
        
        # Execute the action
        if action == 'type' or action == 'paste':
            type_text(command)
            print("✅ Typed text")
        elif action == 'type_and_send':
            type_text(command)
            time.sleep(0.2)
            press_enter()
            print("✅ Typed and sent!")
        elif action == 'open':
            focus_app(target_app or command)
            print(f"✅ Opened {target_app or command}")
        elif action == 'run':
            run_command(command, target_app or 'terminal')
            print("✅ Command executed")
        elif action == 'search':
            focus_app('chrome')
            time.sleep(0.5)
            pyautogui.hotkey('command' if PLATFORM == 'Darwin' else 'ctrl', 'l')
            time.sleep(0.2)
            type_text(command)
            press_enter()
            print("✅ Searching...")
        else:
            # Default: just type
            type_text(command)
            print("✅ Typed")
    
    def run(self):
        """Run the client"""
        print(f"""
==============================================================================
                    Voice Hub Desktop Client v{VERSION}
==============================================================================
  Server: {SERVER_URL}
  Device: {self.device_name}
  Platform: {PLATFORM}
------------------------------------------------------------------------------
  This client receives voice commands from your Voice Hub dashboard
  and executes them on this computer (switch apps, type text, etc.)

  Press Ctrl+C to stop
==============================================================================
        """)
        
        # Check for updates on startup
        check_for_updates()
        
        try:
            print(f"Connecting to {SERVER_URL}...")
            self.sio.connect(SERVER_URL, transports=['websocket', 'polling'])
            self.sio.wait()
        except KeyboardInterrupt:
            print("\nGoodbye!")
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            if self.sio.connected:
                self.sio.disconnect()

if __name__ == '__main__':
    client = VoiceHubClient()
    client.run()
'''

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.name = USERS.get(username, {}).get('name', username)

@login_manager.user_loader
def load_user(username):
    return User(username) if username in USERS else None

# ============================================================================
# LOGIN PAGE
# ============================================================================

LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --border: rgba(255,255,255,0.08);
            --accent: #00f5d4;
            --accent-2: #7b2cbf;
            --accent-3: #f72585;
            --text: #ffffff;
            --text-muted: #6b7280;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text);
            overflow: hidden;
        }
        .bg-effects {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
        }
        .orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: float 20s ease-in-out infinite;
        }
        .orb-1 { width: 400px; height: 400px; background: var(--accent); top: -100px; left: -100px; }
        .orb-2 { width: 300px; height: 300px; background: var(--accent-2); bottom: -50px; right: -50px; animation-delay: -10s; }
        .orb-3 { width: 200px; height: 200px; background: var(--accent-3); top: 50%; left: 50%; animation-delay: -5s; }
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(30px, -30px) scale(1.1); }
            66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        .container {
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 420px;
            padding: 20px;
        }
        .card {
            background: rgba(26, 26, 36, 0.8);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 48px 40px;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
        }
        .logo {
            text-align: center;
            margin-bottom: 40px;
        }
        .logo-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0, 245, 212, 0.3);
            animation: pulse-glow 3s ease-in-out infinite;
        }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 10px 40px rgba(0, 245, 212, 0.3); }
            50% { box-shadow: 0 10px 60px rgba(0, 245, 212, 0.5); }
        }
        h1 { font-size: 32px; font-weight: 700; }
        h1 span {
            background: linear-gradient(135deg, var(--accent), var(--accent-3));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { color: var(--text-muted); font-size: 14px; margin-top: 8px; }
        .form-group { margin-bottom: 24px; }
        label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            font-size: 16px;
            font-family: inherit;
            color: var(--text);
            transition: all 0.3s ease;
        }
        input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 4px rgba(0, 245, 212, 0.1);
        }
        .remember-row {
            display: flex;
            align-items: center;
            margin-bottom: 24px;
        }
        .remember-row input[type="checkbox"] {
            width: 20px;
            height: 20px;
            accent-color: var(--accent);
            margin-right: 10px;
            cursor: pointer;
        }
        .remember-row label {
            margin: 0;
            font-size: 14px;
            text-transform: none;
            letter-spacing: 0;
            cursor: pointer;
        }
        .btn {
            width: 100%;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: var(--bg-primary);
            border: none;
            border-radius: 12px;
            padding: 18px;
            font-size: 16px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 245, 212, 0.3);
        }
        .error {
            background: rgba(247, 37, 133, 0.1);
            border: 1px solid rgba(247, 37, 133, 0.3);
            color: var(--accent-3);
            padding: 14px 18px;
            border-radius: 12px;
            margin-bottom: 24px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="bg-effects">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
    </div>
    <div class="container">
        <div class="card">
            <div class="logo">
                <div class="logo-icon">🎛️</div>
                <h1><span>Voice Hub</span></h1>
                <p class="subtitle">Browser-based voice-to-text</p>
            </div>
            {% if error %}<div class="error">⚠️ {{ error }}</div>{% endif %}
            <form method="POST">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="Enter username" required autofocus>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="Enter password" required>
                </div>
                <div class="remember-row">
                    <input type="checkbox" name="remember" id="remember" checked>
                    <label for="remember">Remember me for 30 days</label>
                </div>
                <button type="submit" class="btn">Sign In →</button>
            </form>
        </div>
    </div>
</body>
</html>
'''

# ============================================================================
# MAIN DASHBOARD - BROWSER-BASED VOICE RECOGNITION
# ============================================================================

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --bg-elevated: #22222e;
            --border: rgba(255,255,255,0.08);
            --border-hover: rgba(255,255,255,0.15);
            --accent: #00f5d4;
            --accent-2: #7b2cbf;
            --accent-3: #f72585;
            --success: #10b981;
            --warning: #f59e0b;
            --text: #ffffff;
            --text-secondary: #a1a1aa;
            --text-muted: #6b7280;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            color: var(--text);
            min-height: 100vh;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--bg-elevated); border-radius: 4px; }
        
        /* Header */
        header {
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 16px 32px;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 22px;
            font-weight: 700;
        }
        .logo-icon {
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
        }
        .logo span { color: var(--accent); }
        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .btn {
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            border: none;
            text-decoration: none;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-ghost {
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        .btn-ghost:hover {
            background: var(--bg-card);
            border-color: var(--border-hover);
            color: var(--text);
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: var(--bg-primary);
        }
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(0, 245, 212, 0.3);
        }
        .btn-danger {
            background: var(--accent-3);
            color: white;
        }
        
        /* Main Layout */
        .main-layout {
            display: grid;
            grid-template-columns: 320px 1fr;
            min-height: calc(100vh - 74px);
        }
        
        /* Sidebar - Device Manager */
        .sidebar {
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            padding: 24px;
            overflow-y: auto;
        }
        .sidebar h2 {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .add-device-btn {
            width: 100%;
            padding: 14px;
            background: var(--bg-card);
            border: 2px dashed var(--border);
            border-radius: 12px;
            color: var(--text-muted);
            font-family: inherit;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 16px;
        }
        .add-device-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
            background: rgba(0, 245, 212, 0.05);
        }
        .device-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .device-item {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .device-item:hover {
            border-color: var(--border-hover);
        }
        .device-item.active {
            border-color: var(--accent);
            border-width: 2px;
            background: rgba(0, 245, 212, 0.1);
            box-shadow: 0 0 20px rgba(0, 245, 212, 0.15);
        }
        .device-item.active::before {
            content: '✓ EDITING';
            position: absolute;
            top: -10px;
            right: 12px;
            background: var(--accent);
            color: var(--bg-primary);
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        }
        .device-item {
            position: relative;
        }
        .device-item.listening {
            border-color: var(--success);
            background: rgba(16, 185, 129, 0.08);
        }
        @keyframes listening-pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            50% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        }
        .device-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .device-name {
            font-weight: 600;
            font-size: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .device-status {
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 50px;
            font-weight: 500;
        }
        .device-status.online {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }
        .device-status.offline {
            background: rgba(107, 114, 128, 0.2);
            color: var(--text-muted);
        }
        .device-status.listening {
            background: rgba(16, 185, 129, 0.3);
            color: var(--success);
            font-weight: 600;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .device-wake-word {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--accent);
            background: rgba(0, 245, 212, 0.1);
            padding: 4px 10px;
            border-radius: 6px;
            display: inline-block;
        }
        .device-stats {
            display: flex;
            gap: 16px;
            margin-top: 12px;
            font-size: 12px;
            color: var(--text-muted);
        }
        .device-stats span {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        /* Main Content */
        .main-content {
            padding: 32px;
            overflow-y: auto;
        }
        
        /* Voice Control Card */
        .voice-control {
            background: linear-gradient(135deg, rgba(0, 245, 212, 0.1), rgba(123, 44, 191, 0.1));
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 40px;
            text-align: center;
            margin-bottom: 32px;
        }
        .mic-button {
            width: 60px;
            height: 60px;
            border-radius: 12px;
            background: var(--accent);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
            color: var(--bg-primary);
            margin: 0 auto 24px;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(0, 245, 212, 0.2);
        }
        .mic-button:hover {
            transform: scale(1.02);
            box-shadow: 0 6px 16px rgba(0, 245, 212, 0.3);
        }
        .mic-button.listening {
            background: var(--success);
            box-shadow: 0 4px 16px rgba(16, 185, 129, 0.3);
        }
        .mic-button.disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        @keyframes mic-pulse {
            0%, 100% { transform: scale(1); box-shadow: 0 10px 40px rgba(16, 185, 129, 0.3); }
            50% { transform: scale(1.08); box-shadow: 0 15px 60px rgba(16, 185, 129, 0.5); }
        }
        .voice-status {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .voice-hint {
            color: var(--text-muted);
            font-size: 14px;
        }
        .transcript-box {
            background: var(--bg-primary);
            border-radius: 16px;
            padding: 20px;
            margin-top: 24px;
            min-height: 80px;
            text-align: left;
        }
        .transcript-box h4 {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        .transcript-text {
            font-size: 16px;
            line-height: 1.6;
            color: var(--text-secondary);
            min-height: 24px;
        }
        .transcript-text.active {
            color: var(--text);
        }
        
        /* Browser Support Warning */
        .browser-warning {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--warning);
        }
        
        /* Device Settings */
        .settings-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 28px;
            margin-bottom: 24px;
        }
        .settings-section h3 {
            font-size: 18px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }
        .setting-row:last-child { border: none; }
        .setting-label h4 {
            font-size: 15px;
            margin-bottom: 4px;
        }
        .setting-label p {
            font-size: 13px;
            color: var(--text-muted);
        }
        .setting-input {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 14px;
            font-family: inherit;
            color: var(--text);
            min-width: 200px;
        }
        .setting-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        select.setting-input {
            cursor: pointer;
        }
        .toggle {
            width: 52px;
            height: 28px;
            background: var(--bg-secondary);
            border-radius: 50px;
            position: relative;
            cursor: pointer;
            transition: background 0.3s;
        }
        .toggle.active { background: var(--accent); }
        .toggle::after {
            content: '';
            position: absolute;
            width: 22px;
            height: 22px;
            background: white;
            border-radius: 50%;
            top: 3px;
            left: 3px;
            transition: transform 0.3s;
        }
        .toggle.active::after { transform: translateX(24px); }
        
        /* Activity Log */
        .activity-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 28px;
        }
        .activity-section h3 {
            font-size: 18px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .activity-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .activity-item {
            display: flex;
            gap: 14px;
            padding: 14px 0;
            border-bottom: 1px solid var(--border);
        }
        .activity-item:last-child { border: none; }
        .activity-icon {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
        }
        .activity-icon.success { background: rgba(16, 185, 129, 0.15); }
        .activity-icon.info { background: rgba(0, 245, 212, 0.15); }
        .activity-icon.warning { background: rgba(245, 158, 11, 0.15); }
        .activity-content {
            flex: 1;
        }
        .activity-content p {
            font-size: 14px;
            margin-bottom: 4px;
        }
        .activity-content .time {
            font-size: 12px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Modal */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s;
        }
        .modal-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        .modal {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 24px;
            width: 100%;
            max-width: 480px;
            max-height: 90vh;
            overflow-y: auto;
            transform: translateY(20px);
            transition: transform 0.3s;
        }
        .modal-overlay.active .modal { transform: translateY(0); }
        .modal-header {
            padding: 24px 28px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-header h2 {
            font-size: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .modal-close {
            width: 36px;
            height: 36px;
            background: var(--bg-secondary);
            border: none;
            border-radius: 10px;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 18px;
        }
        .modal-close:hover {
            background: var(--bg-elevated);
            color: var(--text);
        }
        .modal-body { padding: 28px; }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .form-group input, .form-group select {
            width: 100%;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            font-size: 15px;
            font-family: inherit;
            color: var(--text);
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: var(--accent);
        }
        .modal-actions {
            display: flex;
            gap: 12px;
            margin-top: 28px;
        }
        .modal-actions .btn { flex: 1; justify-content: center; padding: 14px; }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 40px;
            color: var(--text-muted);
        }
        .empty-state .icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        .empty-state h3 {
            font-size: 20px;
            color: var(--text);
            margin-bottom: 10px;
        }
        
        /* Responsive */
        @media (max-width: 900px) {
            .main-layout {
                grid-template-columns: 1fr;
            }
            .sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-icon">🎛️</div>
            <span>Voice</span> Hub
        </div>
        <div class="header-actions">
            <a href="/install" class="btn btn-primary">🖥️ Install Desktop Client</a>
            <span style="color: var(--text-muted); font-size: 14px;">👤 {{ user.name }}</span>
            <a href="/logout" class="btn btn-ghost">Logout</a>
        </div>
    </header>
    
    <div class="main-layout" style="grid-template-columns: 1fr;">
        <!-- Main Content -->
        <main class="main-content">
            <div id="browser-warning" class="browser-warning" style="display: none;">
                ⚠️ Your browser doesn't support speech recognition. Please use Chrome, Edge, or Safari.
            </div>
            
            <!-- Voice Control -->
            <div class="voice-control">
                <button class="mic-button" id="mic-button" onclick="toggleListening()">
                    🎤
                </button>
                <div class="voice-status" id="voice-status">Click to Start</div>
                <div class="voice-hint" id="voice-hint">
                    Or say your wake word: <strong id="current-wake-word">"Hey Computer"</strong>
                </div>
                <div class="mode-badges" style="display: flex; gap: 10px; justify-content: center; margin-top: 16px;">
                    <span id="badge-always" class="mode-badge" style="display: none; background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 6px 14px; border-radius: 50px; font-size: 12px; font-weight: 500;">
                        👂 Always Listening
                    </span>
                    <span id="badge-continuous" class="mode-badge" style="display: none; background: rgba(123, 44, 191, 0.2); color: #a855f7; padding: 6px 14px; border-radius: 50px; font-size: 12px; font-weight: 500;">
                        🔄 Continuous Mode
                    </span>
                </div>
                <div class="transcript-box">
                    <h4>📝 Live Transcript</h4>
                    <div class="transcript-text" id="transcript">Waiting for speech...</div>
                </div>
            </div>
            
            <!-- Device Settings -->
            <div class="settings-section" id="device-settings">
                <h3>⚙️ Settings for: <span id="editing-device-name" style="color: var(--accent);">This Device</span></h3>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Device Name</h4>
                        <p>A friendly name for this device</p>
                    </div>
                    <input type="text" class="setting-input" id="device-name-input" 
                           placeholder="Quinn's MacBook Pro" onblur="updateDeviceSetting('name', this.value)">
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Wake Word</h4>
                        <p>Say this to activate voice recognition</p>
                    </div>
                    <input type="text" class="setting-input" id="wake-word-input" 
                           placeholder="jarvis" onblur="updateDeviceSetting('wakeWord', this.value)">
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Language</h4>
                        <p>Speech recognition language</p>
                    </div>
                    <select class="setting-input" id="language-select" onchange="updateDeviceSetting('language', this.value)">
                        <option value="en-US">English (US)</option>
                        <option value="en-GB">English (UK)</option>
                        <option value="es-ES">Spanish</option>
                        <option value="fr-FR">French</option>
                        <option value="de-DE">German</option>
                        <option value="it-IT">Italian</option>
                        <option value="pt-BR">Portuguese</option>
                        <option value="ja-JP">Japanese</option>
                        <option value="ko-KR">Korean</option>
                        <option value="zh-CN">Chinese</option>
                    </select>
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Always Listen for Wake Word</h4>
                        <p>Keep microphone on to detect wake word anytime</p>
                    </div>
                    <div class="toggle" id="toggle-always-listen" onclick="toggleAlwaysListen()"></div>
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Continuous Dictation</h4>
                        <p>Keep dictating after each phrase (no wake word needed)</p>
                    </div>
                    <div class="toggle" id="toggle-continuous" onclick="toggleContinuous()"></div>
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Wake Word Sensitivity</h4>
                        <p>How closely speech must match your wake word</p>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <input type="range" min="1" max="5" value="3" id="sensitivity-slider" 
                               style="width: 120px; accent-color: var(--accent);"
                               onchange="updateSensitivity(this.value)">
                        <span id="sensitivity-label" style="font-size: 13px; color: var(--text-muted); min-width: 60px;">Medium</span>
                    </div>
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Auto-Type</h4>
                        <p>Automatically copy recognized text to clipboard</p>
                    </div>
                    <div class="toggle active" id="toggle-autotype" onclick="toggleAutoType()"></div>
                </div>
                <div class="setting-row">
                    <div class="setting-label">
                        <h4>Spell Check</h4>
                        <p>Auto-correct common misspellings and grammar</p>
                    </div>
                    <div class="toggle active" id="toggle-spellcheck" onclick="toggleSpellCheck()"></div>
                </div>
            </div>
            
            <!-- Command Routing Panel -->
            <div class="settings-section" id="command-routing">
                <h3>🎯 Command Routing</h3>
                <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 20px;">
                    Say a device name or app to route your command. Example: <strong>"Jarvis, type hello world"</strong> or <strong>"Cursor, write a function"</strong>
                </p>
                
                <div class="routing-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <!-- Available Devices -->
                    <div class="routing-section">
                        <h4 style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                            📱 Available Devices
                        </h4>
                        <div id="available-devices" class="routing-list" style="display: flex; flex-direction: column; gap: 8px;">
                            <!-- Devices will be rendered here -->
                        </div>
                    </div>
                    
                    <!-- Target Apps -->
                    <div class="routing-section">
                        <h4 style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                            🤖 AI Apps & Targets
                        </h4>
                        <div class="routing-list" style="display: flex; flex-direction: column; gap: 8px;">
                            <div class="route-item" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 10px; font-size: 14px;">
                                <span style="font-size: 20px;">🖱️</span>
                                <div>
                                    <div style="font-weight: 500;">Cursor</div>
                                    <div style="font-size: 12px; color: var(--text-muted);">"Cursor, write..."</div>
                                </div>
                            </div>
                            <div class="route-item" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 10px; font-size: 14px;">
                                <span style="font-size: 20px;">🧠</span>
                                <div>
                                    <div style="font-weight: 500;">Claude</div>
                                    <div style="font-size: 12px; color: var(--text-muted);">"Claude, explain..."</div>
                                </div>
                            </div>
                            <div class="route-item" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 10px; font-size: 14px;">
                                <span style="font-size: 20px;">💬</span>
                                <div>
                                    <div style="font-weight: 500;">ChatGPT</div>
                                    <div style="font-size: 12px; color: var(--text-muted);">"ChatGPT, help..."</div>
                                </div>
                            </div>
                            <div class="route-item" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 10px; font-size: 14px;">
                                <span style="font-size: 20px;">✨</span>
                                <div>
                                    <div style="font-weight: 500;">Copilot</div>
                                    <div style="font-size: 12px; color: var(--text-muted);">"Copilot, suggest..."</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Test Connection Button -->
                <div style="margin-top: 20px; display: flex; gap: 10px;">
                    <button onclick="testDesktopConnection()" 
                            style="flex: 1; padding: 12px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 10px; color: var(--text-secondary); cursor: pointer; font-size: 14px;">
                        🔌 Test Desktop Connection
                    </button>
                    <button onclick="testTypeToCursor()" 
                            style="flex: 1; padding: 12px; background: var(--accent); border: none; border-radius: 10px; color: var(--bg-primary); cursor: pointer; font-size: 14px; font-weight: 600;">
                        ⌨️ Test Type to Cursor
                    </button>
                </div>
                
                <!-- Last Command -->
                <div id="last-command-box" style="margin-top: 20px; padding: 16px; background: var(--bg-primary); border-radius: 12px; display: none;">
                    <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">Last Routed Command</div>
                    <div id="last-command-content" style="display: flex; align-items: center; gap: 12px;">
                        <span id="last-command-icon" style="font-size: 24px;">🎯</span>
                        <div>
                            <div id="last-command-target" style="font-weight: 600; color: var(--accent);"></div>
                            <div id="last-command-text" style="font-size: 14px; color: var(--text-secondary);"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Activity Log -->
            <div class="activity-section">
                <h3>📊 Activity Log</h3>
                <div class="activity-list" id="activity-list">
                    <div class="empty-state">
                        <div class="icon">📝</div>
                        <h3>No activity yet</h3>
                        <p>Start speaking to see your transcripts here</p>
                    </div>
                </div>
            </div>
        </main>
    </div>
    
    <!-- Add Device Modal -->
    <div class="modal-overlay" id="add-device-modal">
        <div class="modal">
            <div class="modal-header">
                <h2>➕ Add New Device</h2>
                <button class="modal-close" onclick="closeAddDeviceModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Device Name</label>
                    <input type="text" id="new-device-name" placeholder="e.g., Work Laptop, Home PC">
                </div>
                <div class="form-group">
                    <label>Wake Word</label>
                    <input type="text" id="new-device-wake" placeholder="e.g., Hey Jarvis, OK Computer">
                </div>
                <div class="form-group">
                    <label>Icon</label>
                    <select id="new-device-icon">
                        <option value="💻">💻 Laptop</option>
                        <option value="🖥️">🖥️ Desktop</option>
                        <option value="📱">📱 Phone</option>
                        <option value="⌨️">⌨️ Workstation</option>
                        <option value="🎮">🎮 Gaming PC</option>
                        <option value="🏠">🏠 Home</option>
                        <option value="🏢">🏢 Office</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-ghost" onclick="closeAddDeviceModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="addDevice()">Add Device</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // ============================================================
        // INITIALIZATION
        // ============================================================
        
        const socket = io();
        let recognition = null;
        let isListening = false;
        let currentDevice = null;
        let devices = {};
        let activityLog = [];
        let alwaysListen = false;
        let continuousMode = false;
        let autoType = true;
        let spellCheckEnabled = true;
        let sensitivity = 3; // 1-5, higher = more strict matching
        let isActiveDictation = false; // true when wake word triggered dictation
        
        // Sensitivity labels
        const sensitivityLabels = {
            1: 'Very Low',
            2: 'Low', 
            3: 'Medium',
            4: 'High',
            5: 'Exact'
        };
        
        // Check browser support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let micPermission = 'prompt'; // 'granted', 'denied', or 'prompt'
        
        if (!SpeechRecognition) {
            document.getElementById('browser-warning').style.display = 'flex';
            document.getElementById('mic-button').classList.add('disabled');
        } else {
            initSpeechRecognition();
            checkMicPermission();
        }
        
        // Check and track microphone permission status
        async function checkMicPermission() {
            try {
                const result = await navigator.permissions.query({ name: 'microphone' });
                micPermission = result.state;
                updateMicPermissionUI();
                
                // Listen for permission changes
                result.onchange = () => {
                    micPermission = result.state;
                    updateMicPermissionUI();
                    if (result.state === 'granted') {
                        addActivity('🎤 Microphone access granted!', 'success');
                    }
                };
            } catch (e) {
                // Permissions API not supported, we'll find out when we try to use it
                console.log('Permissions API not available');
            }
        }
        
        function updateMicPermissionUI() {
            const micButton = document.getElementById('mic-button');
            const warning = document.getElementById('browser-warning');
            
            if (micPermission === 'denied') {
                warning.innerHTML = '⚠️ Microphone access blocked. <a href="#" onclick="showPermissionHelp()" style="color: var(--accent); text-decoration: underline;">Click here to fix</a>';
                warning.style.display = 'flex';
            } else if (micPermission === 'granted') {
                warning.style.display = 'none';
            }
        }
        
        function showPermissionHelp() {
            alert('To enable microphone access:\\n\\n1. Click the lock icon 🔒 in Chrome\\'s address bar\\n2. Find "Microphone" and set it to "Allow"\\n3. Refresh the page\\n\\nOr go to: chrome://settings/content/microphone');
        }
        
        // Request microphone permission explicitly
        async function requestMicPermission() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                // Permission granted! Stop the stream immediately (we just needed permission)
                stream.getTracks().forEach(track => track.stop());
                micPermission = 'granted';
                updateMicPermissionUI();
                addActivity('🎤 Microphone access granted!', 'success');
                return true;
            } catch (err) {
                if (err.name === 'NotAllowedError') {
                    micPermission = 'denied';
                    updateMicPermissionUI();
                    addActivity('⚠️ Microphone access denied. Click the lock icon in the address bar to allow.', 'warning');
                } else {
                    addActivity('⚠️ Could not access microphone: ' + err.message, 'warning');
                }
                return false;
            }
        }
        
        // Use a consistent device ID based on this browser
        const deviceId = 'browser_' + (localStorage.getItem('voicehub_browser_id') || (() => {
            const id = Math.random().toString(36).substr(2, 9);
            localStorage.setItem('voicehub_browser_id', id);
            return id;
        })());
        
        // Load this device's settings (just this device, not a list)
        const savedSettings = localStorage.getItem('voicehub_my_settings');
        currentDevice = savedSettings ? JSON.parse(savedSettings) : {
            id: deviceId,
            name: navigator.platform.includes('Mac') ? "Quinn's MacBook Pro" : 'My Computer',
            wakeWord: 'jarvis',
            icon: '💻',
            language: 'en-US',
            wordsTyped: 0,
            sessions: 0,
            alwaysListen: false,
            continuous: false,
            autoType: true,
            sensitivity: 3
        };
        currentDevice.id = deviceId; // Ensure ID is current
        devices[deviceId] = currentDevice;
        alwaysListen = currentDevice.alwaysListen || false;
        
        function saveSettings() {
            localStorage.setItem('voicehub_my_settings', JSON.stringify(currentDevice));
        }
        sensitivity = currentDevice.sensitivity || 3;
        
        // ============================================================
        // COMMAND PARSING & ROUTING
        // ============================================================
        
        // Known AI apps and targets
        const knownApps = {
            'cursor': { name: 'Cursor', icon: '🖱️', keywords: ['cursor', 'code editor'] },
            'claude': { name: 'Claude', icon: '🧠', keywords: ['claude', 'anthropic'] },
            'chatgpt': { name: 'ChatGPT', icon: '💬', keywords: ['chatgpt', 'chat gpt', 'openai', 'gpt'] },
            'copilot': { name: 'Copilot', icon: '✨', keywords: ['copilot', 'github copilot'] },
            'gemini': { name: 'Gemini', icon: '🌟', keywords: ['gemini', 'google ai', 'bard'] },
            'terminal': { name: 'Terminal', icon: '⬛', keywords: ['terminal', 'command line', 'shell', 'console'] },
            'browser': { name: 'Browser', icon: '🌐', keywords: ['browser', 'chrome', 'firefox', 'safari', 'edge'] },
            'notes': { name: 'Notes', icon: '📝', keywords: ['notes', 'notepad', 'text editor'] },
            'slack': { name: 'Slack', icon: '💼', keywords: ['slack'] },
            'discord': { name: 'Discord', icon: '🎮', keywords: ['discord'] },
        };
        
        // Parse a command to extract target device/app and the actual command
        function parseCommand(text) {
            // Trim whitespace - speech recognition often adds leading/trailing spaces
            text = text.trim();
            const lowerText = text.toLowerCase();
            const result = {
                originalText: text,
                targetDevice: null,
                targetApp: null,
                command: text,
                action: 'type' // default action
            };
            
            // Check for device targeting first (e.g., "Jarvis, type hello")
            const allDevices = Object.values(devices);
            for (const device of allDevices) {
                const deviceName = (device.name || '').toLowerCase();
                const wakeWord = (device.wakeWord || '').toLowerCase();
                
                // Check various patterns
                const patterns = [
                    new RegExp(`^${escapeRegex(deviceName)}[,:]?\\s+(.+)`, 'i'),
                    new RegExp(`^${escapeRegex(wakeWord)}[,:]?\\s+(.+)`, 'i'),
                    new RegExp(`^hey\\s+${escapeRegex(deviceName)}[,:]?\\s+(.+)`, 'i'),
                    new RegExp(`^ok\\s+${escapeRegex(deviceName)}[,:]?\\s+(.+)`, 'i'),
                ];
                
                for (const pattern of patterns) {
                    const match = text.match(pattern);
                    if (match) {
                        result.targetDevice = device;
                        result.command = match[1].trim();
                        break;
                    }
                }
                if (result.targetDevice) break;
            }
            
            // Check for app targeting (e.g., "Cursor, write a function" or "write in cursor hello")
            for (const [appId, app] of Object.entries(knownApps)) {
                for (const keyword of app.keywords) {
                    const patterns = [
                        // "cursor, write something" or "cursor write something" or even just "cursor type"
                        new RegExp(`^${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "cursor type" or "cursor hello" (single word after app name)
                        new RegExp(`^${escapeRegex(keyword)}[,:]?\\s+(\\S+)`, 'i'),
                        // "in cursor write something"
                        new RegExp(`^(in|to|for|into)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "send to cursor something"
                        new RegExp(`^send\\s+(to\\s+)?${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "paste in cursor something"
                        new RegExp(`^paste\\s+(in|into|to)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "write in cursor something" or "type into cursor something"
                        // Note: "right" is a common mishearing of "write"
                        new RegExp(`^(write|right|type|put|enter|say)\\s+(in|into|to|for)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "write cursor something" (without preposition)
                        new RegExp(`^(write|right|type|put|enter|say)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "tell cursor to write something"
                        new RegExp(`^tell\\s+${escapeRegex(keyword)}\\s+(to\\s+)?(.+)`, 'i'),
                        // "use cursor to write something"  
                        new RegExp(`^use\\s+${escapeRegex(keyword)}\\s+(to\\s+)?(.+)`, 'i'),
                        // "ask cursor something"
                        new RegExp(`^ask\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "ask cursor to do something"
                        new RegExp(`^ask\\s+${escapeRegex(keyword)}\\s+to\\s+(.+)`, 'i'),
                    ];
                    
                    for (const pattern of patterns) {
                        const match = (result.command || text).match(pattern);
                        if (match) {
                            result.targetApp = { id: appId, ...app };
                            // Get the last capture group as the command
                            result.command = match[match.length - 1].trim();
                            break;
                        }
                    }
                    if (result.targetApp) break;
                }
                if (result.targetApp) break;
            }
            
            // Check for action keywords
            const actionPatterns = {
                'type': /^(type|write|right|enter|input|say)\s+(.+)/i,
                'paste': /^paste\s+(.+)/i,
                'search': /^(search|google|look up)\s+(.+)/i,
                'run': /^(run|execute|do)\s+(.+)/i,
            };
            
            for (const [action, pattern] of Object.entries(actionPatterns)) {
                const match = result.command.match(pattern);
                if (match) {
                    result.action = action;
                    result.command = match[match.length - 1].trim();
                    break;
                }
            }
            
            return result;
        }
        
        function escapeRegex(string) {
            // Escape special regex characters
            return string.replace(/[.*+?^${}()|\\[\\]\\\\]/g, '\\\\$&');
        }
        
        // Route a command to a specific device
        function routeCommandToDevice(targetDevice, command, action, targetApp = null) {
            socket.emit('route_command', {
                fromDeviceId: deviceId,
                toDeviceId: targetDevice.id,
                command: command,
                action: action || 'type',
                targetApp: targetApp,
                timestamp: new Date().toISOString()
            });
            
            showLastCommand(targetDevice.icon || '💻', `→ ${targetDevice.name}`, command);
            addActivity(`📤 Sent to ${targetDevice.name}: "${command.substring(0, 40)}..."`, 'success');
        }
        
        // Test desktop client connection
        function testDesktopConnection() {
            console.log('Testing desktop connection...');
            console.log('All devices:', devices);
            
            const desktopClient = Object.values(devices).find(d => d.type === 'desktop_client');
            
            if (desktopClient) {
                addActivity(`✅ Desktop client found: ${desktopClient.name} (${desktopClient.id})`, 'success');
                console.log('Desktop client:', desktopClient);
                
                // Send a test ping
                socket.emit('route_command', {
                    fromDeviceId: deviceId,
                    toDeviceId: desktopClient.id,
                    command: '--- TEST CONNECTION FROM VOICE HUB ---',
                    action: 'type',
                    timestamp: new Date().toISOString()
                });
                addActivity(`📤 Sent test ping to ${desktopClient.name}`, 'info');
            } else {
                addActivity('❌ No desktop client found! Check if terminal is running.', 'warning');
                console.log('No desktop client. Device types:', Object.values(devices).map(d => ({name: d.name, type: d.type})));
            }
        }
        
        // Test typing to Cursor app
        function testTypeToCursor() {
            console.log('Testing type to Cursor...');
            
            const desktopClient = Object.values(devices).find(d => d.type === 'desktop_client');
            
            if (desktopClient) {
                socket.emit('route_command', {
                    fromDeviceId: deviceId,
                    toDeviceId: desktopClient.id,
                    command: 'Hello from Voice Hub! This is a test.',
                    action: 'type',
                    targetApp: 'cursor',
                    timestamp: new Date().toISOString()
                });
                addActivity('📤 Sent test text to Cursor', 'success');
            } else {
                addActivity('❌ No desktop client! Run the client in terminal first.', 'warning');
            }
        }
        
        // Handle an incoming routed command
        function handleRoutedCommand(data) {
            const { command, action, fromDeviceId } = data;
            const fromDevice = devices[fromDeviceId];
            const fromName = fromDevice?.name || 'Unknown Device';
            
            addActivity(`📥 Received from ${fromName}: "${command.substring(0, 40)}..."`, 'info');
            playSound('activate');
            
            // Execute the command
            if (action === 'type' || action === 'paste') {
                handleTranscript(command);
            }
            
            showLastCommand('📥', `← From ${fromName}`, command);
        }
        
        // Show the last command in the UI
        function showLastCommand(icon, target, text) {
            const box = document.getElementById('last-command-box');
            document.getElementById('last-command-icon').textContent = icon;
            document.getElementById('last-command-target').textContent = target;
            document.getElementById('last-command-text').textContent = text.length > 60 ? text.substring(0, 60) + '...' : text;
            box.style.display = 'block';
            
            // Highlight effect
            box.style.borderColor = 'var(--accent)';
            box.style.border = '1px solid var(--accent)';
            setTimeout(() => {
                box.style.border = 'none';
            }, 2000);
        }
        
        // Render available devices for routing
        function renderAvailableDevices() {
            const container = document.getElementById('available-devices');
            const deviceList = Object.values(devices);
            
            if (deviceList.length === 0) {
                container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No devices available</div>';
                return;
            }
            
            container.innerHTML = deviceList.map(d => `
                <div class="route-item" style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 10px; font-size: 14px; ${d.id === deviceId ? 'border: 1px solid var(--accent);' : ''}">
                    <span style="font-size: 20px;">${d.icon || '💻'}</span>
                    <div style="flex: 1;">
                        <div style="font-weight: 500;">${d.name || 'Unnamed'}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">"${d.wakeWord || 'hey computer'}"</div>
                    </div>
                    ${d.id === deviceId ? '<span style="font-size: 10px; background: var(--accent); color: var(--bg-primary); padding: 2px 8px; border-radius: 50px;">THIS DEVICE</span>' : ''}
                </div>
            `).join('');
        }
        
        // ============================================================
        // FUZZY WAKE WORD MATCHING
        // ============================================================
        
        // Calculate similarity between two strings (0-1)
        function similarity(s1, s2) {
            s1 = s1.toLowerCase().trim();
            s2 = s2.toLowerCase().trim();
            
            if (s1 === s2) return 1;
            if (s1.length === 0 || s2.length === 0) return 0;
            
            // Check if one contains the other
            if (s1.includes(s2) || s2.includes(s1)) return 0.9;
            
            // Levenshtein distance
            const matrix = [];
            for (let i = 0; i <= s1.length; i++) {
                matrix[i] = [i];
            }
            for (let j = 0; j <= s2.length; j++) {
                matrix[0][j] = j;
            }
            for (let i = 1; i <= s1.length; i++) {
                for (let j = 1; j <= s2.length; j++) {
                    const cost = s1[i-1] === s2[j-1] ? 0 : 1;
                    matrix[i][j] = Math.min(
                        matrix[i-1][j] + 1,
                        matrix[i][j-1] + 1,
                        matrix[i-1][j-1] + cost
                    );
                }
            }
            const distance = matrix[s1.length][s2.length];
            const maxLen = Math.max(s1.length, s2.length);
            return 1 - (distance / maxLen);
        }
        
        // Check if transcript contains wake word with fuzzy matching
        function detectWakeWord(transcript, wakeWord) {
            const lowerTranscript = transcript.toLowerCase();
            const lowerWake = wakeWord.toLowerCase();
            
            // Exact match - always works
            if (lowerTranscript.includes(lowerWake)) {
                return { detected: true, index: lowerTranscript.indexOf(lowerWake), length: lowerWake.length };
            }
            
            // Fuzzy matching based on sensitivity
            // Sensitivity 5 = exact only (threshold 1.0)
            // Sensitivity 1 = very fuzzy (threshold 0.5)
            const thresholds = { 1: 0.5, 2: 0.6, 3: 0.7, 4: 0.85, 5: 1.0 };
            const threshold = thresholds[sensitivity] || 0.7;
            
            // Split transcript into chunks and check each
            const words = lowerTranscript.split(' ');
            const wakeWords = lowerWake.split(' ');
            
            for (let i = 0; i <= words.length - wakeWords.length; i++) {
                const chunk = words.slice(i, i + wakeWords.length).join(' ');
                const sim = similarity(chunk, lowerWake);
                
                if (sim >= threshold) {
                    const index = lowerTranscript.indexOf(chunk);
                    return { detected: true, index, length: chunk.length, similarity: sim };
                }
            }
            
            // Also check individual words for single-word wake words
            if (wakeWords.length === 1) {
                for (const word of words) {
                    const sim = similarity(word, lowerWake);
                    if (sim >= threshold) {
                        const index = lowerTranscript.indexOf(word);
                        return { detected: true, index, length: word.length, similarity: sim };
                    }
                }
            }
            
            return { detected: false };
        }
        
        // ============================================================
        // SPEECH RECOGNITION
        // ============================================================
        
        function initSpeechRecognition() {
            recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = currentDevice?.language || 'en-US';
            
            recognition.onstart = () => {
                isListening = true;
                updateUI();
                if (!alwaysListen) {
                    addActivity('Started listening', 'info');
                }
                socket.emit('device_status', { deviceId, status: 'listening' });
            };
            
            recognition.onend = () => {
                // Always set isListening to false when recognition ends
                isListening = false;
                
                // Check if we should auto-restart
                const shouldRestart = (alwaysListen || continuousMode) && currentDevice;
                
                if (shouldRestart) {
                    // Restart quickly without changing UI
                    setTimeout(() => {
                        if (alwaysListen || continuousMode) {
                            startListening();
                        }
                    }, 100);
                } else {
                    updateUI();
                }
            };
            
            recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }
                
                const transcriptEl = document.getElementById('transcript');
                const wakeWord = currentDevice?.wakeWord?.toLowerCase() || 'hey computer';
                
                // In always-listen mode, only show transcript when wake word detected or in active dictation
                if (alwaysListen && !isActiveDictation && !continuousMode) {
                    // Check interim transcript for wake word
                    if (interimTranscript) {
                        const interimDetection = detectWakeWord(interimTranscript, wakeWord);
                        if (interimDetection.detected) {
                            // Show that we're detecting the wake word
                            transcriptEl.textContent = '🎯 Wake word detected...';
                            transcriptEl.classList.add('active');
                        } else {
                            // Don't update transcript, show subtle ready message
                            transcriptEl.textContent = `Ready for "${wakeWord}"`;
                            transcriptEl.classList.remove('active');
                        }
                    }
                } else if (interimTranscript) {
                    // In active dictation or continuous mode, show live transcript with spell check preview
                    const previewText = spellCheck(interimTranscript);
                    transcriptEl.textContent = previewText;
                    transcriptEl.classList.add('active');
                }
                
                if (finalTranscript) {
                    // Check for wake word with fuzzy matching
                    const detection = detectWakeWord(finalTranscript, wakeWord);
                    
                    if (detection.detected) {
                        // Wake word detected!
                        const afterWakeWord = finalTranscript.substring(detection.index + detection.length).trim();
                        
                        // Play activation sound
                        playSound('activate');
                        
                        const matchInfo = detection.similarity ? ` (${Math.round(detection.similarity * 100)}% match)` : '';
                        addActivity(`🎯 Wake word detected${matchInfo}!`, 'success');
                        currentDevice.sessions++;
                        saveDevices();
                        renderDeviceList();
                        
                        // If there's text after the wake word, type it
                        if (afterWakeWord) {
                            handleTranscript(afterWakeWord);
                        } else {
                            // Just activated, waiting for command
                            isActiveDictation = true;
                            document.getElementById('voice-status').textContent = 'Activated';
                            transcriptEl.textContent = 'Speak now...';
                            transcriptEl.classList.add('active');
                        }
                    } else if (isActiveDictation || continuousMode || !alwaysListen) {
                        // In active dictation mode, type everything
                        handleTranscript(finalTranscript);
                        isActiveDictation = false;
                        
                        // Reset transcript display after typing
                        if (alwaysListen && !continuousMode) {
                            setTimeout(() => {
                                transcriptEl.textContent = `Ready for "${wakeWord}"`;
                                transcriptEl.classList.remove('active');
                            }, 1500);
                        }
                    }
                    // In always-listen mode without wake word, don't update transcript (keep showing waiting message)
                }
            };
            
            recognition.onerror = (event) => {
                // Ignore common non-errors
                if (event.error === 'no-speech' || event.error === 'aborted') {
                    isListening = false;
                    updateUI();
                    return;
                }
                
                // Log actual errors
                console.warn('Speech recognition error:', event.error);
                
                if (event.error === 'not-allowed') {
                    addActivity('Microphone access denied. Please allow microphone access.', 'warning');
                    alwaysListen = false;
                    document.getElementById('toggle-always-listen').classList.remove('active');
                } else if (event.error === 'audio-capture') {
                    addActivity('No microphone detected. Check your audio settings.', 'warning');
                } else if (event.error === 'network') {
                    addActivity('Network error. Check your internet connection.', 'warning');
                } else {
                    addActivity(`Speech error: ${event.error}`, 'warning');
                }
                isListening = false;
                updateUI();
            };
        }
        
        function playSound(type) {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = ctx.createOscillator();
                const gainNode = ctx.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(ctx.destination);
                
                if (type === 'activate') {
                    oscillator.frequency.setValueAtTime(880, ctx.currentTime);
                    oscillator.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
                } else {
                    oscillator.frequency.setValueAtTime(440, ctx.currentTime);
                }
                
                gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
                
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.2);
            } catch (e) {
                console.log('Sound playback not available');
            }
        }
        
        // Check if Claude is available
        let claudeAvailable = false;
        
        // Check Claude status after page loads
        setTimeout(() => {
            fetch('/api/claude-status')
                .then(r => r.json())
                .then(data => {
                    claudeAvailable = data.available;
                    if (claudeAvailable) {
                        console.log('🧠 Claude AI ready');
                        addActivity('🧠 AI mode enabled', 'success');
                    }
                })
                .catch(() => { claudeAvailable = false; });
        }, 1000);
        
        async function parseWithClaude(text) {
            try {
                const response = await fetch('/api/parse-command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });
                const data = await response.json();
                if (data.error || data.fallback) return null;
                return data;
            } catch (e) {
                return null;
            }
        }
        
        async function handleTranscript(text, skipRouting = false) {
            text = text.trim();
            console.log('Voice:', text);
            
            let parsed = null;
            
            // Try Claude first for intelligent parsing
            if (claudeAvailable && text.length > 2) {
                const claudeResult = await parseWithClaude(text);
                if (claudeResult && (claudeResult.targetApp || claudeResult.action)) {
                    const appId = (claudeResult.targetApp || '').toLowerCase();
                    const knownApp = knownApps[appId];
                    
                    parsed = {
                        originalText: text,
                        targetDevice: null,
                        targetApp: knownApp ? { id: appId, ...knownApp } : (appId ? { id: appId, name: claudeResult.targetApp, icon: '🤖' } : null),
                        command: claudeResult.content || text,
                        action: claudeResult.action || 'type'
                    };
                    
                    console.log('🧠 Claude:', claudeResult.response || `${parsed.action} → ${appId || 'local'}`);
                    if (claudeResult.response) {
                        addActivity(`🧠 ${claudeResult.response}`, 'info');
                    }
                }
            }
            
            // Fallback to regex if Claude didn't parse
            if (!parsed) {
                parsed = parseCommand(text);
                console.log('Regex:', parsed.targetApp?.name || 'local', '→', parsed.command);
            }
            
            // If targeting another device, route the command
            if (!skipRouting && parsed.targetDevice && parsed.targetDevice.id !== deviceId) {
                routeCommandToDevice(parsed.targetDevice, parsed.command, parsed.action);
                copyToClipboard(parsed.command); // Always copy to clipboard
                document.getElementById('transcript').textContent = `📤 Sent to ${parsed.targetDevice.name}: "${parsed.command}"`;
                return;
            }
            
            // If targeting an app (cursor, vscode, etc), route to a desktop client
            if (!skipRouting && parsed.targetApp) {
                const appInfo = parsed.targetApp;
                
                // Debug: Log all devices and their types
                console.log('Looking for desktop client. All devices:', Object.entries(devices).map(([id, d]) => ({id, type: d.type, name: d.name})));
                
                // Find a desktop client to route to
                const desktopClient = Object.values(devices).find(d => 
                    d.type === 'desktop_client' && d.id !== deviceId
                );
                
                console.log('Desktop client found:', desktopClient ? desktopClient.name : 'NONE');
                
                if (desktopClient) {
                    console.log('Routing command to:', desktopClient.id, 'Command:', parsed.command.substring(0, 50));
                    // Route to desktop client with app target info
                    socket.emit('route_command', {
                        fromDeviceId: deviceId,
                        toDeviceId: desktopClient.id,
                        command: parsed.command,
                        action: parsed.action || 'type',
                        targetApp: appInfo.id,
                        timestamp: new Date().toISOString()
                    });
                    
                    // Always copy to clipboard
                    copyToClipboard(parsed.command);
                    
                    showLastCommand(appInfo.icon, `→ ${appInfo.name} on ${desktopClient.name}`, parsed.command);
                    addActivity(`📤 Sent to ${appInfo.name}: "${parsed.command.substring(0, 40)}..." (copied)`, 'success');
                    document.getElementById('transcript').textContent = `📤 → ${appInfo.name}: "${parsed.command}"`;
                    return;
                } else {
                    // No desktop client found, show warning with instructions
                    addActivity(`⚠️ No desktop client connected to control ${appInfo.name}. Run the client on your Mac.`, 'warning');
                    document.getElementById('transcript').textContent = `⚠️ Desktop client not connected`;
                }
                
                text = parsed.command;
            }
            
            // Apply formatting
            text = formatTranscript(text);
            
            document.getElementById('transcript').textContent = text;
            document.getElementById('transcript').classList.add('active');
            
            // Count words
            const wordCount = text.split(/\\s+/).filter(w => w).length;
            currentDevice.wordsTyped += wordCount;
            saveDevices();
            
            // Always copy to clipboard
            copyToClipboard(text);
            
            // Log activity
            if (autoType) {
                const targetInfo = parsed.targetApp ? ` → ${parsed.targetApp.name}` : '';
                addActivity(`Typed${targetInfo}: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}" (copied)`, 'success', wordCount);
            } else {
                addActivity(`Copied: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`, 'info', wordCount);
            }
            
            // Emit to server
            socket.emit('transcript', { 
                deviceId, 
                text, 
                words: wordCount,
                targetApp: parsed.targetApp?.id,
                timestamp: new Date().toISOString()
            });
            
            renderDeviceList();
            renderAvailableDevices();
        }
        
        // Common misspellings and corrections
        const spellCheckDict = {
            'teh': 'the', 'thier': 'their', 'recieve': 'receive', 'wierd': 'weird',
            'occured': 'occurred', 'untill': 'until', 'seperate': 'separate',
            'definately': 'definitely', 'occassion': 'occasion', 'accomodate': 'accommodate',
            'occurence': 'occurrence', 'persistant': 'persistent', 'refered': 'referred',
            'apparant': 'apparent', 'calender': 'calendar', 'collegue': 'colleague',
            'concious': 'conscious', 'enviroment': 'environment', 'existance': 'existence',
            'fourty': 'forty', 'goverment': 'government', 'harrass': 'harass',
            'immediatly': 'immediately', 'independant': 'independent', 'knowlege': 'knowledge',
            'liason': 'liaison', 'millenium': 'millennium', 'neccessary': 'necessary',
            'noticable': 'noticeable', 'parliment': 'parliament', 'posession': 'possession',
            'prefered': 'preferred', 'publically': 'publicly', 'recomend': 'recommend',
            'reffering': 'referring', 'relevent': 'relevant', 'religous': 'religious',
            'repitition': 'repetition', 'resistence': 'resistance', 'responsability': 'responsibility',
            'succesful': 'successful', 'supercede': 'supersede', 'suprise': 'surprise',
            'tommorow': 'tomorrow', 'tounge': 'tongue', 'truely': 'truly',
            'unforseen': 'unforeseen', 'unfortunatly': 'unfortunately', 'wich': 'which',
            'writting': 'writing', 'your welcome': "you're welcome", 'alot': 'a lot',
            'shouldnt': "shouldn't", 'couldnt': "couldn't", 'wouldnt': "wouldn't",
            'dont': "don't", 'wont': "won't", 'cant': "can't", 'didnt': "didn't",
            'isnt': "isn't", 'wasnt': "wasn't", 'havent': "haven't", 'hasnt': "hasn't",
            'im': "I'm", 'ive': "I've", 'youre': "you're", 'theyre': "they're",
            'weve': "we've", 'its a': "it's a", 'lets': "let's",
            // Common speech recognition errors
            'gonna': 'going to', 'wanna': 'want to', 'gotta': 'got to',
            'kinda': 'kind of', 'sorta': 'sort of', 'dunno': "don't know",
            'lemme': 'let me', 'gimme': 'give me', 'coulda': 'could have',
            'shoulda': 'should have', 'woulda': 'would have', 'musta': 'must have',
        };
        
        function spellCheck(text) {
            if (!spellCheckEnabled) return text;
            
            let corrected = text;
            let corrections = [];
            
            for (const [wrong, right] of Object.entries(spellCheckDict)) {
                const regex = new RegExp('\\\\b' + wrong + '\\\\b', 'gi');
                if (regex.test(corrected)) {
                    corrections.push({ from: wrong, to: right });
                    corrected = corrected.replace(regex, right);
                }
            }
            
            if (corrections.length > 0) {
                console.log('Spell corrections:', corrections);
                addActivity(`📝 Auto-corrected: ${corrections.map(c => c.from + ' → ' + c.to).join(', ')}`, 'info');
            }
            
            return corrected;
        }
        
        function formatTranscript(text) {
            // Apply spell check first
            text = spellCheck(text);
            
            // Punctuation replacements
            const replacements = {
                'period': '.', 'comma': ',', 'question mark': '?',
                'exclamation mark': '!', 'exclamation point': '!',
                'colon': ':', 'semicolon': ';',
                'new line': '\\n', 'newline': '\\n', 'new paragraph': '\\n\\n',
                'open quote': '"', 'close quote': '"', 'quote': '"',
                'open paren': '(', 'close paren': ')',
                'hyphen': '-', 'dash': '—'
            };
            
            for (const [word, symbol] of Object.entries(replacements)) {
                const regex = new RegExp('\\\\b' + word + '\\\\b', 'gi');
                text = text.replace(regex, symbol);
            }
            
            // Capitalize first letter
            text = text.charAt(0).toUpperCase() + text.slice(1);
            
            // Capitalize after periods
            text = text.replace(/([.!?]\\s*)(\\w)/g, (m, p1, p2) => p1 + p2.toUpperCase());
            
            return text.trim();
        }
        
        async function copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                // Try to simulate paste (note: this won't work in all contexts due to browser security)
                // The user can manually paste with Ctrl+V / Cmd+V
            } catch (err) {
                console.log('Clipboard write failed:', err);
            }
        }
        
        function startListening() {
            if (!recognition || isListening) return;
            recognition.lang = currentDevice?.language || 'en-US';
            try {
                recognition.start();
            } catch (e) {
                console.log('Recognition already started');
            }
        }
        
        function stopListening() {
            if (!recognition || !isListening) return;
            continuousMode = false;
            document.getElementById('toggle-continuous').classList.remove('active');
            recognition.stop();
            socket.emit('device_status', { deviceId, status: 'idle' });
        }
        
        async function toggleListening() {
            if (!recognition) {
                addActivity('⚠️ Speech recognition not available in this browser', 'warning');
                return;
            }
            
            if (isListening) {
                stopListening();
            } else {
                // Check/request permission before starting
                if (micPermission !== 'granted') {
                    const granted = await requestMicPermission();
                    if (!granted) return;
                }
                startListening();
            }
        }
        
        // ============================================================
        // UI UPDATES
        // ============================================================
        
        function updateUI() {
            // Get elements with null safety
            const micButton = document.getElementById('mic-button');
            const voiceStatus = document.getElementById('voice-status');
            const voiceHint = document.getElementById('voice-hint');
            const wakeWordSpan = document.getElementById('current-wake-word');
            
            // Guard: don't proceed if critical elements missing
            if (!micButton || !voiceStatus || !voiceHint) {
                console.warn('updateUI: Required elements not found');
                return;
            }
            
            if (isListening) {
                micButton.classList.add('listening');
                if (alwaysListen && !isActiveDictation) {
                    micButton.innerHTML = 'ON';
                    voiceStatus.textContent = 'Standby';
                    voiceHint.innerHTML = `Waiting for "${currentDevice?.wakeWord || 'hey computer'}"`;
                } else {
                    micButton.innerHTML = 'REC';
                    voiceStatus.textContent = 'Recording';
                    voiceHint.innerHTML = 'Speak now. Click to stop.';
                }
            } else {
                micButton.classList.remove('listening');
                micButton.innerHTML = 'MIC';
                if (alwaysListen) {
                    voiceStatus.textContent = 'Starting';
                    voiceHint.innerHTML = 'Initializing microphone...';
                } else {
                    voiceStatus.textContent = 'Off';
                    voiceHint.innerHTML = 'Click to start listening';
                }
            }
            
            if (wakeWordSpan) {
                wakeWordSpan.textContent = `"${currentDevice?.wakeWord || 'hey computer'}"`;
            }
            
            // Update settings header to show which device is being edited
            const editingLabel = document.getElementById('editing-device-name');
            if (editingLabel) {
                editingLabel.textContent = currentDevice?.name || 'This Device';
            }
            
            // Update settings inputs (with null safety)
            const nameInput = document.getElementById('device-name-input');
            const wakeWordInput = document.getElementById('wake-word-input');
            const langSelect = document.getElementById('language-select');
            const sensitivitySlider = document.getElementById('sensitivity-slider');
            const sensitivityLabel = document.getElementById('sensitivity-label');
            const alwaysListenToggle = document.getElementById('toggle-always-listen');
            const badgeAlways = document.getElementById('badge-always');
            const badgeContinuous = document.getElementById('badge-continuous');
            
            if (nameInput) nameInput.value = currentDevice?.name || '';
            if (wakeWordInput) wakeWordInput.value = currentDevice?.wakeWord || '';
            if (langSelect) langSelect.value = currentDevice?.language || 'en-US';
            if (sensitivitySlider) sensitivitySlider.value = sensitivity;
            if (sensitivityLabel) sensitivityLabel.textContent = sensitivityLabels[sensitivity];
            if (alwaysListenToggle) alwaysListenToggle.classList.toggle('active', alwaysListen);
            if (badgeAlways) badgeAlways.style.display = alwaysListen ? 'inline-block' : 'none';
            if (badgeContinuous) badgeContinuous.style.display = continuousMode ? 'inline-block' : 'none';
        }
        
        function renderDeviceList() {
            const listEl = document.getElementById('device-list');
            const deviceArray = Object.values(devices);
            
            if (deviceArray.length === 0) {
                listEl.innerHTML = '<div class="empty-state"><p>No devices added yet</p></div>';
                return;
            }
            
            listEl.innerHTML = deviceArray.map(d => `
                <div class="device-item ${d.id === currentDevice?.id ? 'active editing' : ''} ${d.id === deviceId && isListening ? 'listening' : ''}"
                     onclick="selectDevice('${d.id}')"
                     style="cursor: pointer; position: relative;">
                    ${d.id === currentDevice?.id ? '<div style="position: absolute; top: 8px; right: 8px; background: var(--accent); color: var(--bg-primary); padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;">EDITING</div>' : ''}
                    ${d.id !== deviceId ? `<button onclick="event.stopPropagation(); deleteDevice('${d.id}')" style="position: absolute; top: 8px; right: ${d.id === currentDevice?.id ? '70px' : '8px'}; background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 14px; opacity: 0.5;" title="Delete device">✕</button>` : ''}
                    <div class="device-header">
                        <div class="device-name">
                            <span>${d.icon || '💻'}</span>
                            ${d.name || 'Unnamed Device'}
                            ${d.type === 'desktop_client' ? '<span style="font-size: 10px; background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px; margin-left: 6px;">DESKTOP</span>' : ''}
                        </div>
                        <span class="device-status ${d.id === deviceId ? (isListening ? 'listening' : 'online') : (d.online ? 'online' : 'offline')}">
                            ${d.id === deviceId ? (isListening ? '● Listening' : '● This Browser') : (d.online ? '● Online' : '○ Offline')}
                        </span>
                    </div>
                    <div class="device-wake-word">"${d.wakeWord || 'hey computer'}"</div>
                    <div class="device-stats">
                        <span>📝 ${d.wordsTyped || 0} words</span>
                        <span>🎤 ${d.sessions || 0} sessions</span>
                    </div>
                </div>
            `).join('');
        }
        
        function addActivity(message, type = 'info', words = 0) {
            const time = new Date().toLocaleTimeString();
            activityLog.unshift({ message, type, time, words });
            activityLog = activityLog.slice(0, 50); // Keep last 50
            renderActivityLog();
        }
        
        function renderActivityLog() {
            const listEl = document.getElementById('activity-list');
            
            if (activityLog.length === 0) {
                listEl.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📝</div>
                        <h3>No activity yet</h3>
                        <p>Start speaking to see your transcripts here</p>
                    </div>
                `;
                return;
            }
            
            const icons = { success: '✅', info: 'ℹ️', warning: '⚠️' };
            
            listEl.innerHTML = activityLog.map(a => `
                <div class="activity-item">
                    <div class="activity-icon ${a.type}">${icons[a.type] || 'ℹ️'}</div>
                    <div class="activity-content">
                        <p>${a.message}</p>
                        <span class="time">${a.time}${a.words ? ` • ${a.words} words` : ''}</span>
                    </div>
                </div>
            `).join('');
        }
        
        // ============================================================
        // DEVICE MANAGEMENT
        // ============================================================
        
        function deleteDevice(id) {
            if (id === deviceId) {
                addActivity('Cannot delete this browser device', 'warning');
                return;
            }
            
            const device = devices[id];
            const name = device?.name || 'Unknown';
            
            if (confirm(`Delete device "${name}"? This cannot be undone.`)) {
                delete devices[id];
                saveDevices();
                socket.emit('device_delete', { deviceId: id });
                renderDeviceList();
                renderAvailableDevices();
                addActivity(`Deleted device: ${name}`, 'info');
            }
        }
        
        function selectDevice(id) {
            if (devices[id]) {
                currentDevice = devices[id];
                
                // Load this device's settings into the UI
                alwaysListen = currentDevice.alwaysListen || false;
                continuousMode = currentDevice.continuous || false;
                autoType = currentDevice.autoType ?? true;
                spellCheckEnabled = currentDevice.spellCheck ?? true;
                sensitivity = currentDevice.sensitivity || 3;
                
                if (recognition) {
                    recognition.lang = currentDevice.language || 'en-US';
                }
                
                // Update all toggle states
                document.getElementById('toggle-always-listen').classList.toggle('active', alwaysListen);
                document.getElementById('toggle-continuous').classList.toggle('active', continuousMode);
                document.getElementById('toggle-autotype').classList.toggle('active', autoType);
                document.getElementById('toggle-spellcheck').classList.toggle('active', spellCheckEnabled);
                
                updateUI();
                renderDeviceList();
                
                // Show which device is selected
                addActivity(`Selected device: ${currentDevice.name || 'Unnamed'}`, 'info');
            }
        }
        
        function updateDeviceSetting(setting, value) {
            if (!currentDevice) {
                addActivity('No device selected', 'warning');
                return;
            }
            
            if (setting === 'wakeWord') {
                value = value.toLowerCase().trim();
            }
            
            currentDevice[setting] = value;
            devices[currentDevice.id] = currentDevice;
            saveDevices();
            
            if (setting === 'language' && recognition) {
                recognition.lang = value;
            }
            
            updateUI();
            renderDeviceList();
            addActivity(`Updated ${setting} to "${value}"`, 'info');
            
            // Sync to server
            socket.emit('device_update', { deviceId: currentDevice.id, settings: currentDevice });
        }
        
        async function toggleAlwaysListen() {
            // If enabling, check permission first
            if (!alwaysListen && micPermission !== 'granted') {
                const granted = await requestMicPermission();
                if (!granted) return;
            }
            
            alwaysListen = !alwaysListen;
            document.getElementById('toggle-always-listen').classList.toggle('active', alwaysListen);
            currentDevice.alwaysListen = alwaysListen;
            saveDevices();
            
            if (alwaysListen) {
                addActivity('🎧 Always Listen enabled - say your wake word anytime!', 'success');
                startListening();
            } else {
                addActivity('Always Listen disabled', 'info');
                if (isListening && !continuousMode) {
                    stopListening();
                }
            }
            updateUI();
        }
        
        async function toggleContinuous() {
            // If enabling, check permission first
            if (!continuousMode && micPermission !== 'granted') {
                const granted = await requestMicPermission();
                if (!granted) return;
            }
            
            continuousMode = !continuousMode;
            document.getElementById('toggle-continuous').classList.toggle('active', continuousMode);
            currentDevice.continuous = continuousMode;
            saveDevices();
            
            if (continuousMode && !isListening) {
                startListening();
            }
            
            addActivity(continuousMode ? 'Continuous dictation enabled' : 'Continuous dictation disabled', 'info');
        }
        
        function toggleAutoType() {
            autoType = !autoType;
            document.getElementById('toggle-autotype').classList.toggle('active', autoType);
            currentDevice.autoType = autoType;
            saveDevices();
            addActivity(autoType ? 'Auto-type enabled' : 'Auto-type disabled', 'info');
        }
        
        function updateSensitivity(value) {
            sensitivity = parseInt(value);
            currentDevice.sensitivity = sensitivity;
            saveDevices();
            document.getElementById('sensitivity-label').textContent = sensitivityLabels[sensitivity];
            addActivity(`Wake word sensitivity set to: ${sensitivityLabels[sensitivity]}`, 'info');
        }
        
        function toggleSpellCheck() {
            spellCheckEnabled = !spellCheckEnabled;
            document.getElementById('toggle-spellcheck').classList.toggle('active', spellCheckEnabled);
            currentDevice.spellCheck = spellCheckEnabled;
            saveDevices();
            addActivity(spellCheckEnabled ? '✓ Spell check enabled' : 'Spell check disabled', 'info');
        }
        
        function saveDevices() {
            // Save current device settings
            saveSettings();
        }
        
        // ============================================================
        // MODAL HANDLERS
        // ============================================================
        
        function openAddDeviceModal() {
            document.getElementById('add-device-modal').classList.add('active');
            document.getElementById('new-device-name').focus();
        }
        
        function closeAddDeviceModal() {
            document.getElementById('add-device-modal').classList.remove('active');
            document.getElementById('new-device-name').value = '';
            document.getElementById('new-device-wake').value = '';
        }
        
        function addDevice() {
            const name = document.getElementById('new-device-name').value.trim();
            const wakeWord = document.getElementById('new-device-wake').value.trim().toLowerCase();
            const icon = document.getElementById('new-device-icon').value;
            
            if (!name) {
                alert('Please enter a device name');
                return;
            }
            
            const newId = 'device_' + Math.random().toString(36).substr(2, 9);
            devices[newId] = {
                id: newId,
                name,
                wakeWord: wakeWord || 'hey computer',
                icon,
                language: 'en-US',
                wordsTyped: 0,
                sessions: 0,
                continuous: false,
                autoType: true
            };
            
            saveDevices();
            renderDeviceList();
            closeAddDeviceModal();
            addActivity(`Added new device: ${name}`, 'success');
            
            socket.emit('device_add', devices[newId]);
        }
        
        // ============================================================
        // SOCKET EVENTS
        // ============================================================
        
        socket.on('connect', () => {
            console.log('Connected to server');
            socket.emit('dashboard_join', { deviceId });
        });
        
        socket.on('devices_update', (data) => {
            // Merge server devices with local - UPDATE existing devices too
            if (data.devices) {
                for (const [id, device] of Object.entries(data.devices)) {
                    if (!devices[id]) {
                        // New device from server
                        devices[id] = device;
                    } else {
                        // Update existing device with server data (type, online status, etc.)
                        devices[id] = { ...devices[id], ...device };
                    }
                }
                saveDevices();
                renderDeviceList();
                renderAvailableDevices();
                
                // Debug: log connected desktop clients
                const desktopClients = Object.values(devices).filter(d => d.type === 'desktop_client');
                if (desktopClients.length > 0) {
                    console.log('Desktop clients available:', desktopClients.map(d => d.name));
                }
            }
        });
        
        // Handle incoming routed commands from other devices
        socket.on('command_received', (data) => {
            console.log('Received routed command:', data);
            handleRoutedCommand(data);
        });
        
        // Handle device online/offline updates
        socket.on('device_online', (data) => {
            if (devices[data.deviceId]) {
                devices[data.deviceId].online = true;
                renderDeviceList();
                renderAvailableDevices();
            }
        });
        
        socket.on('device_offline', (data) => {
            if (devices[data.deviceId]) {
                devices[data.deviceId].online = false;
                renderDeviceList();
                renderAvailableDevices();
            }
        });
        
        // ============================================================
        // INITIALIZATION
        // ============================================================
        
        // Initial render
        updateUI();
        renderDeviceList();
        renderActivityLog();
        renderAvailableDevices();
        
        // Restore settings
        alwaysListen = currentDevice?.alwaysListen || false;
        continuousMode = currentDevice?.continuous || false;
        autoType = currentDevice?.autoType ?? true;
        spellCheckEnabled = currentDevice?.spellCheck ?? true;
        sensitivity = currentDevice?.sensitivity || 3;
        
        document.getElementById('toggle-always-listen').classList.toggle('active', alwaysListen);
        document.getElementById('toggle-continuous').classList.toggle('active', continuousMode);
        document.getElementById('toggle-autotype').classList.toggle('active', autoType);
        document.getElementById('toggle-spellcheck').classList.toggle('active', spellCheckEnabled);
        document.getElementById('sensitivity-slider').value = sensitivity;
        document.getElementById('sensitivity-label').textContent = sensitivityLabels[sensitivity];
        
        // Close modal on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeAddDeviceModal();
        });
        
        // Close modal on overlay click
        document.getElementById('add-device-modal').addEventListener('click', (e) => {
            if (e.target.id === 'add-device-modal') closeAddDeviceModal();
        });
        
        // Auto-start listening if always-listen or continuous mode is enabled
        if (alwaysListen || continuousMode) {
            setTimeout(() => {
                addActivity('🚀 Auto-starting voice recognition...', 'info');
                startListening();
            }, 1000);
        }
    </script>
</body>
</html>
'''

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_PAGE, user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username', '').strip(), request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        if u in USERS and check_password_hash(USERS[u]['password_hash'], p):
            login_user(User(u), remember=remember)
            return redirect(url_for('dashboard'))
        return render_template_string(LOGIN_PAGE, error='Invalid credentials')
    return render_template_string(LOGIN_PAGE, error=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'devices': len(devices)})

@app.route('/ping')
def ping():
    """Simple test endpoint"""
    return 'pong', 200, {'Content-Type': 'text/plain'}

@app.route('/download/mac')
def download_mac_app():
    """Download a double-clickable .command file for Mac"""
    server_url = request.host_url.rstrip('/').replace('http://', 'https://')
    
    script = '''#!/bin/bash
# Voice Hub Desktop Client
# Just double-click this file to install and run!

SERVER_URL="''' + server_url + '''"

clear
echo ""
echo "Voice Hub Desktop Client Installer"
echo "========================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required."
    echo ""
    echo "Opening Python download page..."
    open "https://www.python.org/downloads/"
    echo ""
    echo "After installing Python, double-click this file again."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Create directory
mkdir -p ~/.voicehub
cd ~/.voicehub

# Download the client
echo "Downloading Voice Hub client..."
curl -sL "$SERVER_URL/setup.py" -o voice_hub_client.py

if [ ! -f voice_hub_client.py ]; then
    echo "Download failed. Check your internet connection."
    read -p "Press Enter to close..."
    exit 1
fi

# Install dependencies
echo "Installing dependencies (this may take a minute)..."
pip3 install --quiet --user pyautogui pyperclip websocket-client requests 2>/dev/null

echo ""
echo "Installation complete!"
echo ""
echo "Starting Voice Hub client..."
echo "Keep this window open while using voice commands."
echo "Press Ctrl+C to stop."
echo ""

python3 voice_hub_client.py

echo ""
read -p "Press Enter to close..."
'''
    
    response = Response(script, mimetype='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename=VoiceHub.command'
    return response

@app.route('/download/windows')
def download_windows_app():
    """Download a double-clickable .bat file for Windows"""
    server_url = request.host_url.rstrip('/').replace('http://', 'https://')
    
    script = '''@echo off
title Voice Hub Desktop Client
color 0A

set SERVER_URL=''' + server_url + '''

echo.
echo  Voice Hub Desktop Client Installer
echo  ========================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python 3 is required.
    echo.
    echo  Opening Python download page...
    start https://www.python.org/downloads/
    echo.
    echo  After installing Python, double-click this file again.
    echo  IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo  Python found
echo.

:: Create directory
if not exist "%USERPROFILE%\\.voicehub" mkdir "%USERPROFILE%\\.voicehub"
cd /d "%USERPROFILE%\\.voicehub"

:: Download the client
echo  Downloading Voice Hub client...
powershell -Command "Invoke-WebRequest -Uri '%SERVER_URL%/setup.py' -OutFile 'voice_hub_client.py'"

if not exist voice_hub_client.py (
    echo  Download failed. Check your internet connection.
    pause
    exit /b 1
)

:: Install dependencies
echo  Installing dependencies (this may take a minute)...
pip install --quiet pyautogui pyperclip websocket-client requests 2>nul

echo.
echo  Installation complete!
echo.
echo  Starting Voice Hub client...
echo  Keep this window open while using voice commands.
echo  Press Ctrl+C to stop.
echo.

python voice_hub_client.py

echo.
pause
'''
    
    response = Response(script, mimetype='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename=VoiceHub.bat'
    return response

@app.route('/download/linux')
def download_linux_app():
    """Download a shell script for Linux"""
    server_url = request.host_url.rstrip('/').replace('http://', 'https://')
    
    shell_script = '''#!/bin/bash
# Voice Hub Desktop Client for Linux

SERVER_URL="''' + server_url + '''"

cd ~/.voicehub 2>/dev/null || mkdir -p ~/.voicehub && cd ~/.voicehub

if [ ! -f voice_hub_client.py ]; then
    echo "Downloading Voice Hub client..."
    curl -sL "$SERVER_URL/setup.py" -o voice_hub_client.py
    pip3 install --user pyautogui pyperclip websocket-client requests
fi

python3 voice_hub_client.py
'''
    
    response = Response(shell_script, mimetype='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename=voicehub.sh'
    return response

@app.route('/install')
def install_page():
    """Show easy install instructions"""
    server_url = request.host_url.rstrip('/')
    return render_template_string(INSTALL_PAGE, server=server_url)

# Desktop client version - increment this when you update the client
CLIENT_VERSION = "1.3.0"

# ============================================================================
# CLAUDE AI COMMAND PARSING
# ============================================================================

COMMAND_PARSE_PROMPT = """You are Jarvis, a voice command parser for a computer control system.

Parse voice commands and return JSON:
{
  "targetApp": "cursor" | "claude" | "chatgpt" | "terminal" | "browser" | "notes" | "slack" | "discord" | null,
  "action": "type" | "type_and_send" | "open" | "search" | "run" | null,
  "content": "the text to type or action to take",
  "response": "Brief friendly confirmation (5 words max)"
}

ACTIONS:
- "type" = just type the text
- "type_and_send" = type the text AND press Enter to send it
- "open" = open the app
- "search" = search in browser
- "run" = run a command

APPS:
- cursor/curser = Code editor (Cursor IDE)
- claude/cloud = Claude AI chat
- chatgpt/GPT = ChatGPT
- terminal/command = Terminal/shell
- browser/chrome/safari = Web browser

COMMON MISHEARINGS (fix these):
- "right" → "write"
- "curser" → "cursor"  
- "cloud" → "claude"
- "and send" / "and enter" / "and submit" → use action "type_and_send"

EXAMPLES:
"cursor write hello" → {"targetApp":"cursor","action":"type","content":"hello","response":"Typing in Cursor"}
"ask claude about python and send" → {"targetApp":"claude","action":"type_and_send","content":"about python","response":"Sending to Claude"}
"tell chatgpt explain react and enter" → {"targetApp":"chatgpt","action":"type_and_send","content":"explain react","response":"Sending to ChatGPT"}
"claude what is python send it" → {"targetApp":"claude","action":"type_and_send","content":"what is python","response":"Sending to Claude"}
"type hello and submit" → {"targetApp":null,"action":"type_and_send","content":"hello","response":"Typing and sending"}
"open terminal" → {"targetApp":"terminal","action":"open","content":null,"response":"Opening Terminal"}
"search how to code" → {"targetApp":"browser","action":"search","content":"how to code","response":"Searching"}

Return ONLY valid JSON, nothing else."""

@app.route('/api/parse-command', methods=['POST'])
@login_required
def parse_command_with_claude():
    """Use Claude to intelligently parse a voice command"""
    if not CLAUDE_AVAILABLE or not claude_client:
        return jsonify({'error': 'Claude not available', 'fallback': True}), 200
    
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        message = claude_client.messages.create(
            model="claude-3-haiku-20240307",  # Fast and cheap
            max_tokens=200,
            messages=[
                {"role": "user", "content": f"Parse this voice command: \"{text}\""}
            ],
            system=COMMAND_PARSE_PROMPT
        )
        
        # Parse the response
        response_text = message.content[0].text.strip()
        
        # Try to parse as JSON
        try:
            parsed = json.loads(response_text)
            parsed['claude'] = True
            return jsonify(parsed)
        except json.JSONDecodeError:
            # If Claude didn't return valid JSON, return the raw response
            return jsonify({
                'error': 'Invalid JSON from Claude',
                'raw': response_text,
                'fallback': True
            })
            
    except Exception as e:
        print(f"Claude API error: {e}")
        return jsonify({'error': str(e), 'fallback': True}), 200

@app.route('/api/claude-status')
def claude_status():
    """Check if Claude is available"""
    return jsonify({
        'available': CLAUDE_AVAILABLE,
        'model': 'claude-3-haiku-20240307' if CLAUDE_AVAILABLE else None
    })

@app.route('/api/version')
def get_version():
    """Return the current client version"""
    return jsonify({
        'version': CLIENT_VERSION,
        'download_url': request.host_url.rstrip('/') + '/setup.py'
    })

@app.route('/setup.py')
def download_setup():
    """Download the auto-setup script"""
    server_url = request.host_url.rstrip('/')
    script = DESKTOP_CLIENT.replace('{{SERVER_URL}}', server_url).replace('{{VERSION}}', CLIENT_VERSION)
    return Response(script, mimetype='text/plain', 
                   headers={'Content-Disposition': 'attachment; filename=voice_hub_client.py'})

@app.route('/install.sh')
@app.route('/install/mac')
@app.route('/install/linux')
def download_install_sh():
    """One-liner install script for Mac/Linux - no login required"""
    server_url = request.host_url.rstrip('/').replace('http://', 'https://')
    script = '''#!/bin/bash
# Voice Hub Desktop Client - One-Click Installer

SERVER_URL="''' + server_url + '''"

echo "Voice Hub Desktop Client Installer"
echo "========================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install Python first."
    echo "   Mac: brew install python3"
    echo "   Linux: sudo apt install python3 python3-pip"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Create directory
mkdir -p ~/.voicehub
cd ~/.voicehub

# Download the client
echo "Downloading Voice Hub client..."
curl -sL "$SERVER_URL/setup.py" -o voice_hub_client.py

# Install dependencies
echo "Installing dependencies..."
pip3 install --quiet pyautogui pyperclip websocket-client requests 2>/dev/null || pip install --quiet pyautogui pyperclip websocket-client requests

echo ""
echo "Installation complete!"
echo ""
echo "Starting Voice Hub client..."
echo "(Press Ctrl+C to stop)"
echo ""

python3 voice_hub_client.py
'''
    return Response(script, mimetype='text/plain')

@app.route('/install.ps1')
@app.route('/install/windows')
def download_install_ps1():
    """One-liner install script for Windows - no login required"""
    server_url = request.host_url.rstrip('/').replace('http://', 'https://')
    script = '''# Voice Hub Desktop Client - Windows Installer

$SERVER_URL = "''' + server_url + '''"

Write-Host "Voice Hub Desktop Client Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for Python
$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3 is required. Please install Python first." -ForegroundColor Red
    Write-Host "   Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host "Python found: $pythonCheck" -ForegroundColor Green

# Create directory
$installDir = "$env:USERPROFILE\\.voicehub"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Set-Location $installDir

# Download the client
Write-Host "Downloading Voice Hub client..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$SERVER_URL/setup.py" -OutFile "voice_hub_client.py"

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --quiet pyautogui pyperclip websocket-client requests 2>$null

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Starting Voice Hub client..." -ForegroundColor Cyan
Write-Host "(Press Ctrl+C to stop)" -ForegroundColor Gray
Write-Host ""

python voice_hub_client.py
'''
    return Response(script, mimetype='text/plain')

@app.route('/api/devices', methods=['GET'])
@login_required
def get_devices():
    return jsonify(devices)

@app.route('/api/devices/<device_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_device(device_id):
    if request.method == 'DELETE':
        if device_id in devices:
            del devices[device_id]
        return jsonify({'status': 'ok'})
    elif request.method == 'PUT':
        data = request.json
        if device_id in devices:
            devices[device_id].update(data)
        return jsonify(devices.get(device_id, {}))

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('dashboard_join')
def on_dashboard_join(data):
    device_id = data.get('deviceId')
    print(f"\n🔌 dashboard_join from: {device_id}")
    print(f"   Socket ID: {request.sid}")
    
    join_room('dashboard')
    join_room(device_id)  # Join own room to receive routed commands
    print(f"   Joined rooms: 'dashboard' and '{device_id}'")
    
    # Track this device's socket session (even if not in devices dict yet)
    if device_id:
        if device_id not in devices:
            devices[device_id] = {'id': device_id}
            print(f"   Created placeholder device entry")
        devices[device_id]['sid'] = request.sid
        devices[device_id]['online'] = True
        # Notify others this device is online
        socketio.emit('device_online', {'deviceId': device_id}, room='dashboard')
    
    emit('devices_update', {'devices': devices})

@socketio.on('device_status')
def on_device_status(data):
    device_id = data.get('deviceId')
    status = data.get('status')
    if device_id:
        active_sessions[device_id] = status
        socketio.emit('device_status_update', data, room='dashboard')

@socketio.on('device_update')
def on_device_update(data):
    device_id = data.get('deviceId')
    settings = data.get('settings', {})
    if device_id:
        if device_id in devices:
            devices[device_id].update(settings)
        else:
            # Add new device (like desktop clients)
            devices[device_id] = settings
            print(f"📱 New device registered: {settings.get('name', device_id)}")
        
        # Mark as online and track socket session
        devices[device_id]['online'] = True
        devices[device_id]['sid'] = request.sid
        
        # Notify all dashboards
        socketio.emit('device_online', {'deviceId': device_id}, room='dashboard')
    
    socketio.emit('devices_update', {'devices': devices}, room='dashboard')

@socketio.on('device_delete')
def on_device_delete(data):
    device_id = data.get('deviceId')
    if device_id and device_id in devices:
        name = devices[device_id].get('name', device_id)
        del devices[device_id]
        print(f"🗑️ Device deleted: {name}")
        socketio.emit('devices_update', {'devices': devices}, room='dashboard')

@socketio.on('device_add')
def on_device_add(data):
    device_id = data.get('id')
    if device_id:
        devices[device_id] = data
    socketio.emit('devices_update', {'devices': devices}, room='dashboard')

@socketio.on('transcript')
def on_transcript(data):
    device_id = data.get('deviceId')
    text = data.get('text')
    words = data.get('words', 0)
    
    if device_id and device_id in devices:
        devices[device_id]['wordsTyped'] = devices[device_id].get('wordsTyped', 0) + words
    
    socketio.emit('transcript_received', data, room='dashboard')

@socketio.on('route_command')
def on_route_command(data):
    """Route a command from one device to another"""
    from_device_id = data.get('fromDeviceId')
    to_device_id = data.get('toDeviceId')
    command = data.get('command')
    action = data.get('action', 'type')
    target_app = data.get('targetApp')
    
    print(f"\n{'='*60}")
    print(f"📤 ROUTE_COMMAND received!")
    print(f"   From: {from_device_id}")
    print(f"   To: {to_device_id}")
    print(f"   Command: {command[:50] if command else 'NONE'}...")
    print(f"   Target app: {target_app or 'None'}")
    print(f"   Known devices: {list(devices.keys())}")
    print(f"{'='*60}")
    
    # Send the command to the target device
    print(f"   Emitting command_received to room: '{to_device_id}'")
    
    # Check if target device exists and has a socket session
    target_device = devices.get(to_device_id, {})
    print(f"   Target device info: {target_device.get('name', 'unknown')}, sid: {target_device.get('sid', 'NONE')}")
    
    socketio.emit('command_received', {
        'fromDeviceId': from_device_id,
        'command': command,
        'action': action,
        'targetApp': target_app,
        'timestamp': data.get('timestamp')
    }, room=to_device_id)
    
    print(f"   ✅ command_received emitted!")
    
    # Also notify the dashboard
    socketio.emit('command_routed', data, room='dashboard')

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    # Notify other devices this one went offline
    for device_id, device in devices.items():
        if device.get('sid') == sid:
            device['online'] = False
            socketio.emit('device_offline', {'deviceId': device_id}, room='dashboard')

# ============================================================================
# START SERVER
# ============================================================================

def notify_clients_of_update():
    """Notify all connected desktop clients of the new version after server restart"""
    import time
    time.sleep(10)  # Wait for clients to reconnect after server restart
    print(f"Broadcasting update notification (v{CLIENT_VERSION}) to all clients...")
    # Use the Render URL or localhost for download
    base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
    socketio.emit('update_available', {
        'version': CLIENT_VERSION,
        'download_url': f"{base_url}/setup.py"
    }, room='dashboard')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       🎛️  VOICE HUB SERVER v3.0  🎛️                          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  URL: http://localhost:{port:<52} ║
║  Login: admin / {ADMIN_PASSWORD:<51} ║
║  Client Version: {CLIENT_VERSION:<50} ║
║                                                                               ║
║  ✨ NEW: Browser-based voice recognition - no terminal needed!               ║
║  • Click the mic button or say your wake word                                 ║
║  • Add multiple devices with custom wake words                                ║
║  • Edit device settings directly in the web app                               ║
║  • Desktop clients auto-update when you push changes!                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Start background thread to notify clients after startup
    import threading
    update_thread = threading.Thread(target=notify_clients_of_update, daemon=True)
    update_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=port)
