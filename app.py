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
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, Response, session, g
from flask_socketio import SocketIO, emit, join_room, disconnect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Security imports
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, using system env vars only

# Claude AI for intelligent command parsing
try:
    import anthropic
    CLAUDE_AVAILABLE = bool(os.environ.get('ANTHROPIC_API_KEY'))
    if CLAUDE_AVAILABLE:
        claude_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        print("🧠 Claude AI enabled for intelligent command parsing")
    else:
        claude_client = None
        print("[WARNING] ANTHROPIC_API_KEY not set - using regex parsing")
except ImportError:
    CLAUDE_AVAILABLE = False
    claude_client = None
    print("⚠️ anthropic package not installed - using regex parsing")

# ============================================================================
# SETUP
# ============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Determine allowed origins for CORS (your Render URL + localhost for dev)
ALLOWED_ORIGINS = [
    "https://cortona.onrender.com",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]
# Add custom origins from environment if needed
if os.environ.get('ALLOWED_ORIGINS'):
    ALLOWED_ORIGINS.extend(os.environ.get('ALLOWED_ORIGINS').split(','))

# Secure cookie configuration
app.config.update(
    # Session cookies
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') != 'development',  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # Prevent CSRF via cross-site requests
    
    # Remember me cookie
    REMEMBER_COOKIE_SECURE=os.environ.get('FLASK_ENV') != 'development',
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax',
    
    # CSRF Protection
    WTF_CSRF_ENABLED=True,
    WTF_CSRF_TIME_LIMIT=3600,  # 1 hour token validity
)

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# Initialize Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],  # Default limits for all routes
    storage_uri="memory://",  # Use memory storage (works on Render)
)

# SocketIO with restricted CORS origins
socketio = SocketIO(
    app, 
    cors_allowed_origins=ALLOWED_ORIGINS,  # Restricted to known origins only
    async_mode='gevent',
    manage_session=False  # Let Flask handle sessions for security
)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.remember_cookie_duration = timedelta(days=30)
login_manager.session_protection = 'strong'  # Regenerate session on login

# Password is loaded from environment variable - NEVER commit passwords to git!
# Set ADMIN_PASSWORD in your .env file or Render dashboard
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

# Users file for persistent storage
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.json')

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    # Default admin user
    return {'admin': {'password_hash': generate_password_hash(ADMIN_PASSWORD), 'name': 'Admin'}}

def save_users():
    """Save users to JSON file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(USERS, f, indent=2)
    except Exception as e:
        print(f"Error saving users: {e}")

USERS = load_users()

# Track failed login attempts for additional protection
failed_login_attempts = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

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

def open_url_native(url):
    """Open a URL using the system's native method - more reliable than webbrowser module"""
    try:
        if PLATFORM == 'Darwin':
            # macOS - use 'open' command
            subprocess.run(['open', url], check=True)
            print(f"✅ Opened URL (macOS): {url}")
        elif PLATFORM == 'Windows':
            # Windows - use os.startfile or start command
            # os.startfile is most reliable on Windows
            os.startfile(url)
            print(f"✅ Opened URL (Windows): {url}")
        else:
            # Linux - use xdg-open
            subprocess.run(['xdg-open', url], check=True)
            print(f"✅ Opened URL (Linux): {url}")
        return True
    except Exception as e:
        print(f"⚠️ Native open failed: {e}, trying webbrowser...")
        # Fallback to webbrowser module
        try:
            import webbrowser
            webbrowser.open(url)
            print(f"✅ Opened URL (webbrowser fallback): {url}")
            return True
        except Exception as e2:
            print(f"❌ Could not open URL: {e2}")
            return False

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
            print("Typed text")
        elif action == 'type_and_send':
            type_text(command)
            time.sleep(0.2)
            press_enter()
            print("Typed and sent!")
        elif action == 'open':
            focus_app(target_app or command)
            print(f"Opened {target_app or command}")
        elif action == 'open_tab':
            # Open a new browser tab
            if command:
                open_url_native(command)
                print(f"Opened new tab: {command}")
            else:
                # Just open a new tab in default browser
                focus_app('chrome')
                time.sleep(0.3)
                pyautogui.hotkey('command' if PLATFORM == 'Darwin' else 'ctrl', 't')
                print("Opened new tab")
        elif action == 'open_url':
            # Open a specific URL
            url = command if command else 'https://google.com'
            # Add https if missing
            if not url.startswith('http'):
                url = 'https://' + url
            open_url_native(url)
            print(f"Opened URL: {url}")
        elif action == 'run':
            run_command(command, target_app or 'terminal')
            print("Command executed")
        elif action == 'search':
            # Search in browser
            search_url = f"https://www.google.com/search?q={command.replace(' ', '+')}"
            open_url_native(search_url)
            print(f"Searching: {command}")
        else:
            # Default: just type
            type_text(command)
            print("Typed")
    
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
            {% if success %}<div class="error" style="background: rgba(0, 245, 212, 0.1); border-color: rgba(0, 245, 212, 0.3); color: var(--accent);">✓ {{ success }}</div>{% endif %}
            <form method="POST">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
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
# SIGNUP PAGE
# ============================================================================

SIGNUP_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub - Create Account</title>
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
        .bg-effects { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
        .orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.4; animation: float 20s ease-in-out infinite; }
        .orb-1 { width: 400px; height: 400px; background: var(--accent-2); top: -100px; right: -100px; }
        .orb-2 { width: 300px; height: 300px; background: var(--accent); bottom: -50px; left: -50px; animation-delay: -10s; }
        @keyframes float { 0%, 100% { transform: translate(0, 0) scale(1); } 50% { transform: translate(30px, -30px) scale(1.1); } }
        .container { position: relative; z-index: 1; width: 100%; max-width: 420px; padding: 20px; }
        .card {
            background: rgba(26, 26, 36, 0.8);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 48px 40px;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
        }
        .logo { text-align: center; margin-bottom: 32px; }
        .logo-icon {
            width: 70px; height: 70px;
            background: linear-gradient(135deg, var(--accent-2), var(--accent));
            border-radius: 18px;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 36px; margin-bottom: 16px;
            box-shadow: 0 10px 40px rgba(123, 44, 191, 0.3);
        }
        h1 { font-size: 28px; font-weight: 700; }
        h1 span { background: linear-gradient(135deg, var(--accent-2), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: var(--text-muted); font-size: 14px; margin-top: 8px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 500; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
        input[type="text"], input[type="password"], input[type="email"] {
            width: 100%;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px 18px;
            font-size: 15px;
            font-family: inherit;
            color: var(--text);
            transition: all 0.3s ease;
        }
        input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px rgba(0, 245, 212, 0.1); }
        .btn {
            width: 100%;
            background: linear-gradient(135deg, var(--accent-2), var(--accent));
            color: white;
            border: none;
            border-radius: 12px;
            padding: 16px;
            font-size: 16px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 8px;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(123, 44, 191, 0.3); }
        .error {
            background: rgba(247, 37, 133, 0.1);
            border: 1px solid rgba(247, 37, 133, 0.3);
            color: var(--accent-3);
            padding: 12px 16px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .link-row { text-align: center; margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border); }
        .link-row a { color: var(--accent); text-decoration: none; font-weight: 600; }
    </style>
</head>
<body>
    <div class="bg-effects">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
    </div>
    <div class="container">
        <div class="card">
            <div class="logo">
                <div class="logo-icon">✨</div>
                <h1><span>Create Account</span></h1>
                <p class="subtitle">Join Voice Hub today</p>
            </div>
            {% if error %}<div class="error">⚠️ {{ error }}</div>{% endif %}
            <form method="POST">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div class="form-group">
                    <label>Display Name</label>
                    <input type="text" name="name" placeholder="Your name" required autofocus>
                </div>
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="Choose a username" required pattern="[a-zA-Z0-9_]+" title="Letters, numbers, and underscores only">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="Choose a password" required minlength="4">
                </div>
                <div class="form-group">
                    <label>Confirm Password</label>
                    <input type="password" name="password2" placeholder="Confirm your password" required>
                </div>
                <button type="submit" class="btn">Create Account →</button>
            </form>
            <div class="link-row">
                <p style="color: var(--text-muted); font-size: 14px;">
                    Already have an account? <a href="/login">Sign in →</a>
                </p>
            </div>
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
        .chat-message {
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            animation: fadeIn 0.3s ease;
        }
        .chat-message.user {
            background: rgba(0, 245, 212, 0.15);
            border: 1px solid rgba(0, 245, 212, 0.3);
            align-self: flex-end;
            color: var(--text);
        }
        .chat-message.jarvis {
            background: rgba(123, 44, 191, 0.15);
            border: 1px solid rgba(123, 44, 191, 0.3);
            align-self: flex-start;
            color: var(--text);
        }
        .chat-message .sender {
            font-size: 11px;
            font-weight: 600;
            margin-bottom: 4px;
            opacity: 0.7;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
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
    
    <div class="main-layout">
        <!-- Sidebar: Device Manager -->
        <aside class="sidebar">
            <h2>📱 My Devices</h2>
            <div class="device-list" id="device-list">
                <!-- Devices will be rendered here -->
            </div>
            <button class="add-device-btn" onclick="openAddDeviceModal()" style="margin-top: 16px;">
                <span>➕</span> Add Device
            </button>
        </aside>
        
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
                        Ready for Wake Word
                    </span>
                    <span id="badge-continuous" class="mode-badge" style="display: none; background: rgba(123, 44, 191, 0.2); color: #a855f7; padding: 6px 14px; border-radius: 50px; font-size: 12px; font-weight: 500;">
                        🔄 Continuous Mode
                    </span>
                </div>
                <div class="transcript-box" id="chat-box">
                    <h4 id="transcript-header" style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        💬 Chat with Jarvis
                        <span id="transcript-count" style="background: var(--accent); color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px; display: none;">0</span>
                        <span style="font-size: 10px; color: var(--text-muted); margin-left: auto;">Click for history</span>
                    </h4>
                    <div id="chat-messages" style="display: flex; flex-direction: column; gap: 12px; max-height: 200px; overflow-y: auto;">
                        <div class="transcript-text" id="transcript">Say your wake word or click the mic...</div>
                    </div>
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
    
    <!-- Transcript History Modal -->
    <div id="transcript-history-modal" class="modal-overlay" onclick="if(event.target === this) closeTranscriptHistory()">
        <div class="modal" style="max-width: 600px;">
            <div class="modal-header">
                <h2>📜 Session Transcripts</h2>
                <button class="modal-close" onclick="closeTranscriptHistory()">✕</button>
            </div>
            <div class="modal-body" style="padding: 20px; max-height: 60vh; overflow-y: auto;">
                <div id="transcript-history-list" style="display: flex; flex-direction: column; gap: 12px;">
                    <p style="color: var(--text-muted); text-align: center; padding: 40px;">No transcripts yet. Start speaking to record your session.</p>
                </div>
            </div>
            <div class="modal-footer" style="padding: 16px 24px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                <span id="transcript-session-info" style="font-size: 13px; color: var(--text-muted);">Session started just now</span>
                <button class="btn btn-ghost" onclick="clearTranscriptHistory()" style="color: #ef4444;">🗑️ Clear Session</button>
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
        
        // Transcript history
        let transcriptHistory = [];
        const sessionStartTime = new Date();
        
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
        
        // Auto-detect device info based on browser/OS - ALWAYS runs on every load
        function getDeviceInfo() {
            const ua = navigator.userAgent;
            const platform = navigator.platform;
            
            let name, icon, wakeWord;
            
            if (platform.includes('Mac') || ua.includes('Macintosh')) {
                name = 'MacBook';
                icon = '💻';
                wakeWord = 'mac';
            } else if (platform.includes('Win') || ua.includes('Windows')) {
                name = 'Windows PC';
                icon = '🖥️';
                wakeWord = 'windows';
            } else if (ua.includes('iPhone')) {
                name = 'iPhone';
                icon = '📱';
                wakeWord = 'phone';
            } else if (ua.includes('iPad')) {
                name = 'iPad';
                icon = '📱';
                wakeWord = 'ipad';
            } else if (ua.includes('Android')) {
                name = 'Android';
                icon = '📱';
                wakeWord = 'android';
            } else if (platform.includes('Linux')) {
                name = 'Linux PC';
                icon = '🐧';
                wakeWord = 'linux';
            } else {
                name = 'My Device';
                icon = '💻';
                wakeWord = 'computer';
            }
            
            return { name, icon, wakeWord };
        }
        
        // Auto-detect device info on EVERY page load
        const deviceInfo = getDeviceInfo();
        
        // Use device type as stable ID (so Mac is always "macbook", Windows is always "windows_pc")
        const deviceId = deviceInfo.name.toLowerCase().replace(/\s+/g, '_');
        
        // Load ALL saved settings (including name, wakeWord, icon that may have been edited remotely)
        let savedPrefs = {};
        try {
            const saved = localStorage.getItem('voicehub_prefs');
            if (saved) savedPrefs = JSON.parse(saved);
        } catch (e) {}
        
        // Use saved name/wakeWord/icon if they exist, otherwise use auto-detected
        // This allows remote edits to persist
        currentDevice = {
            id: deviceId,
            name: savedPrefs.name || deviceInfo.name,
            wakeWord: savedPrefs.wakeWord || deviceInfo.wakeWord,
            icon: savedPrefs.icon || deviceInfo.icon,
            language: savedPrefs.language || 'en-US',
            wordsTyped: savedPrefs.wordsTyped || 0,
            sessions: savedPrefs.sessions || 0,
            alwaysListen: savedPrefs.alwaysListen || false,
            continuous: savedPrefs.continuous || false,
            autoType: savedPrefs.autoType !== false,
            spellCheck: savedPrefs.spellCheck !== false,
            sensitivity: savedPrefs.sensitivity || 3
        };
        
        // Put in devices list
        devices[deviceId] = currentDevice;
        
        function saveDevices() {
            // Save ALL device settings including name, wakeWord, icon
            localStorage.setItem('voicehub_prefs', JSON.stringify({
                name: currentDevice.name,
                wakeWord: currentDevice.wakeWord,
                icon: currentDevice.icon,
                language: currentDevice.language,
                wordsTyped: currentDevice.wordsTyped,
                sessions: currentDevice.sessions,
                alwaysListen: currentDevice.alwaysListen,
                continuous: currentDevice.continuous,
                autoType: currentDevice.autoType,
                spellCheck: currentDevice.spellCheck,
                sensitivity: currentDevice.sensitivity
            }));
        }
        
        console.log('=== DEVICE INIT ===');
        console.log('Saved prefs from localStorage:', savedPrefs);
        console.log('Auto-detected:', deviceInfo);
        console.log('Final device:', currentDevice.name, '| Wake word:', currentDevice.wakeWord);
        console.log('==================');
        
        // Save immediately to ensure prefs are persisted
        // (This also writes back any existing prefs to ensure they're not lost)
        saveDevices();
        
        alwaysListen = currentDevice.alwaysListen || false;
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
            
            // Fix common speech recognition mishearings
            // "right" at the start of a command is often "write"
            if (/^right\s/i.test(text)) {
                text = text.replace(/^right\s/i, 'write ');
            }
            // Handle "cursor right" → "cursor write" 
            text = text.replace(/\b(cursor|claude|chatgpt|terminal)\s+right\s/gi, '$1 write ');
            
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
                        new RegExp(`^(write|type|put|enter|say)\\s+(in|into|to|for)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
                        // "write cursor something" (without preposition)
                        new RegExp(`^(write|type|put|enter|say)\\s+${escapeRegex(keyword)}[,:]?\\s+(.+)`, 'i'),
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
                'type': /^(type|write|enter|input|say)\s+(.+)/i,
                'paste': /^paste\s+(.+)/i,
                'search': /^(search|google|look up|search for)\s+(.+)/i,
                'run': /^(run|execute|do)\s+(.+)/i,
                'open_tab': /^open\s+(a\s+)?new\s+tab$/i,
                'open_url': /^(open|go to|navigate to|launch)\s+(.+)/i,
            };
            
            // If we have a target app but no action keyword match, default to typing the rest
            // e.g., "cursor hello world" → type "hello world" in cursor
            if (result.targetApp && result.command && !Object.values(actionPatterns).some(p => p.test(result.command))) {
                // No action keyword found - just type the content
                result.action = 'type';
                // result.command is already set to the text after the app name
            }
            
            // Common website shortcuts
            const websiteShortcuts = {
                'google': 'https://google.com',
                'youtube': 'https://youtube.com',
                'github': 'https://github.com',
                'twitter': 'https://twitter.com',
                'x': 'https://twitter.com',
                'facebook': 'https://facebook.com',
                'reddit': 'https://reddit.com',
                'amazon': 'https://amazon.com',
                'netflix': 'https://netflix.com',
                'spotify': 'https://spotify.com',
                'linkedin': 'https://linkedin.com',
                'instagram': 'https://instagram.com',
                'gmail': 'https://gmail.com',
                'google docs': 'https://docs.google.com',
                'google sheets': 'https://sheets.google.com',
                'google drive': 'https://drive.google.com',
                'chatgpt': 'https://chat.openai.com',
                'claude': 'https://claude.ai',
                'stackoverflow': 'https://stackoverflow.com',
                'stack overflow': 'https://stackoverflow.com',
            };
            
            for (const [action, pattern] of Object.entries(actionPatterns)) {
                const match = result.command.match(pattern);
                if (match) {
                    result.action = action;
                    
                    // Handle URL opening specially
                    if (action === 'open_url') {
                        var site = match[2].trim().toLowerCase();
                        // Check if it's a known shortcut
                        if (websiteShortcuts[site]) {
                            result.command = websiteShortcuts[site];
                        } else if (site.includes('.')) {
                            // Looks like a domain
                            result.command = site.startsWith('http') ? site : 'https://' + site;
                        } else {
                            // Treat as a search
                            result.action = 'search';
                            result.command = site;
                        }
                    } else if (action === 'open_tab') {
                        result.command = '';
                    } else {
                        result.command = match[match.length - 1].trim();
                    }
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
            if (!container) return; // Element may not exist
            
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
        
        // Check if the transcript is a "send to [device]" command
        // This handles both device NAME and wake word when prefixed with "send to"
        function checkForCrossDeviceCommand(transcript) {
            const lowerTranscript = transcript.toLowerCase().trim();
            
            // Patterns that indicate cross-device routing
            const sendPatterns = [
                /^send\s+to\s+(.+?)\s+(?:type\s+|write\s+|say\s+)?(.+)$/i,
                /^tell\s+(.+?)\s+to\s+(?:type\s+|write\s+)?(.+)$/i,
                /^on\s+(.+?)\s+(?:type\s+|write\s+)(.+)$/i,
                /^(.+?)\s+type\s+(.+)$/i,  // "Windows PC type hello"
                /^(.+?)\s+write\s+(.+)$/i  // "MacBook write hello"
            ];
            
            // Get all other devices
            var otherDevices = Object.values(devices).filter(function(d) {
                return d.id !== deviceId && d.online !== false;
            });
            
            // First check for explicit "send to" patterns (highest priority)
            for (var p = 0; p < 3; p++) {
                var match = lowerTranscript.match(sendPatterns[p]);
                if (match) {
                    var targetName = match[1].trim();
                    var command = match[2].trim();
                    
                    // Find matching device by name OR wake word
                    for (var i = 0; i < otherDevices.length; i++) {
                        var device = otherDevices[i];
                        var deviceName = (device.name || '').toLowerCase();
                        var deviceWake = (device.wakeWord || '').toLowerCase();
                        
                        if (targetName === deviceName || targetName === deviceWake || 
                            deviceName.includes(targetName) || targetName.includes(deviceName)) {
                            return {
                                device: device,
                                command: command,
                                explicit: true  // Explicit send command
                            };
                        }
                    }
                }
            }
            
            // Then check for "[device name] type/write" patterns
            for (var i = 0; i < otherDevices.length; i++) {
                var device = otherDevices[i];
                var deviceName = (device.name || '').toLowerCase();
                
                // Only match by device NAME (not wake word) for implicit routing
                // This prevents accidentally triggering other devices
                if (deviceName && lowerTranscript.startsWith(deviceName)) {
                    var afterName = transcript.substring(deviceName.length).trim();
                    // Must have "type" or "write" after the device name
                    var typeMatch = afterName.match(/^(?:type|write)\s+(.+)$/i);
                    if (typeMatch) {
                        return {
                            device: device,
                            command: typeMatch[1],
                            explicit: false
                        };
                    }
                }
            }
            
            return null;
        }
        
        // Route a command to another device
        function routeToOtherDevice(targetDevice, command) {
            console.log('Routing to', targetDevice.name, ':', command);
            
            // Send command via socket to the target device
            socket.emit('route_command', {
                fromDeviceId: deviceId,
                toDeviceId: targetDevice.id,
                command: command,
                action: 'type',
                crossDevice: true,
                timestamp: new Date().toISOString()
            });
            
            showLastCommand(targetDevice.icon || '💻', '→ ' + targetDevice.name, command);
            addActivity('📤 Sent to ' + targetDevice.name + ': "' + command.substring(0, 40) + '..."', 'success');
            document.getElementById('transcript').textContent = '📡 → ' + targetDevice.name + ': "' + command + '"';
        }
        
        // Check if the user said "stop" as a command (not as part of a sentence)
        function checkForStopCommand(text) {
            const lower = text.toLowerCase().trim();
            
            // Exact "stop" command
            if (lower === 'stop' || lower === 'stop listening' || lower === 'stop recording') {
                return true;
            }
            
            // Ends with "stop" as a command (like "ok stop" or "please stop")
            if (lower.endsWith(' stop') && lower.split(' ').length <= 3) {
                return true;
            }
            
            // Common stop phrases
            const stopPhrases = ['stop now', 'thats enough', 'enough', 'end recording', 'stop dictation', 'cancel'];
            if (stopPhrases.includes(lower)) {
                return true;
            }
            
            // If Claude is available, we'll use smarter detection online
            // For now, simple check: if it's JUST "stop" or a short stop phrase, treat as command
            // Longer sentences containing "stop" are probably not commands
            // e.g., "don't stop believing" should NOT stop recording
            
            return false;
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
                // Check if we should auto-restart (keep listening in always-listen or continuous mode)
                const shouldRestart = (alwaysListen || continuousMode) && currentDevice;
                
                // Always set isListening to false when recognition ends
                isListening = false;
                
                if (shouldRestart) {
                    // Restart after a brief delay
                    setTimeout(() => {
                        // Only restart if still in always-listen or continuous mode
                        if ((alwaysListen || continuousMode) && !isListening) {
                            try {
                                recognition.start();
                                // isListening will be set to true by onstart
                            } catch (e) {
                                console.log('Restart failed, reinitializing...', e.message);
                                // Reinitialize and try again
                                initSpeechRecognition();
                                setTimeout(() => {
                                    if (alwaysListen || continuousMode) {
                                        try { recognition.start(); } catch (e2) {}
                                    }
                                }, 100);
                            }
                        }
                    }, 300);
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
                
                // PRIVACY: In always-listen mode, NEVER show what user is saying
                // Only show the ready message or wake word detection
                if (alwaysListen && !isActiveDictation && !continuousMode) {
                    if (interimTranscript) {
                        const interimDetection = detectWakeWord(interimTranscript, wakeWord);
                        if (interimDetection.detected) {
                            // Only show that wake word was detected, nothing else
                            transcriptEl.textContent = '🎯 Wake word detected...';
                            transcriptEl.classList.add('active');
                        }
                        // NEVER show what user said if wake word not detected - just keep showing ready message
                    }
                    // Don't show any transcript - keep the ready message
                } else if (interimTranscript && (isActiveDictation || continuousMode || !alwaysListen)) {
                    // Only show live transcript when:
                    // 1. In active dictation (wake word was spoken)
                    // 2. In continuous mode
                    // 3. NOT in always-listen mode (manual mic click)
                    const previewText = spellCheck(interimTranscript);
                    transcriptEl.textContent = previewText;
                    transcriptEl.classList.add('active');
                }
                
                if (finalTranscript) {
                    // Check for STOP command first
                    const lowerTranscript = finalTranscript.toLowerCase().trim();
                    const isStopCommand = checkForStopCommand(lowerTranscript);
                    
                    if (isStopCommand) {
                        // Stop the current dictation session, but keep always-listen mode if enabled
                        addActivity('🛑 Stop command - ending dictation', 'info');
                        addToTranscriptHistory(lowerTranscript, 'stop');
                        
                        // End active dictation
                        isActiveDictation = false;
                        
                        if (alwaysListen) {
                            // Stay in always-listen mode, just go back to waiting for wake word
                            transcriptEl.textContent = `Ready for "${wakeWord}"`;
                            transcriptEl.classList.remove('active');
                            document.getElementById('voice-status').textContent = 'Standby';
                            // Recognition keeps running to listen for wake word
                        } else {
                            // Not in always-listen mode, fully stop
                            stopListening();
                            transcriptEl.textContent = 'Stopped.';
                        }
                        updateUI();
                        return;
                    }
                    
                    // First check if command is for ANOTHER device (cross-device routing)
                    const otherDeviceMatch = checkForCrossDeviceCommand(finalTranscript);
                    
                    if (otherDeviceMatch) {
                        // Command is for another device - route it there!
                        playSound('activate');
                        addActivity('📡 Routing to ' + otherDeviceMatch.device.name + '...', 'info');
                        addToTranscriptHistory('→ ' + otherDeviceMatch.device.name + ': ' + otherDeviceMatch.command, 'routed');
                        
                        // Route the command to the other device
                        routeToOtherDevice(otherDeviceMatch.device, otherDeviceMatch.command);
                        
                        // Reset transcript display
                        if (alwaysListen) {
                            setTimeout(function() {
                                transcriptEl.textContent = 'Ready for "' + wakeWord + '"';
                                transcriptEl.classList.remove('active');
                            }, 2000);
                        }
                        return;
                    }
                    
                    // Check for THIS device's wake word with fuzzy matching
                    const detection = detectWakeWord(finalTranscript, wakeWord);
                    
                    if (detection.detected) {
                        // Wake word detected!
                        const afterWakeWord = finalTranscript.substring(detection.index + detection.length).trim();
                        
                        // Play activation sound
                        playSound('activate');
                        
                        const matchInfo = detection.similarity ? ' (' + Math.round(detection.similarity * 100) + '% match)' : '';
                        addActivity('🎯 Wake word detected' + matchInfo + '!', 'success');
                        addToTranscriptHistory(wakeWord + (afterWakeWord ? ' ' + afterWakeWord : ''), 'wake');
                        currentDevice.sessions++;
                        saveDevices();
                        renderDeviceList();
                        
                        // If there's text after the wake word, type it
                        if (afterWakeWord) {
                            handleTranscript(afterWakeWord);
                            // After processing command with wake word, go back to standby
                            isActiveDictation = false;
                            if (alwaysListen && !continuousMode) {
                                setTimeout(() => {
                                    transcriptEl.textContent = `Ready for "${wakeWord}"`;
                                    transcriptEl.classList.remove('active');
                                    document.getElementById('voice-status').textContent = 'Standby';
                                }, 1500);
                            }
                        } else {
                            // Just activated, waiting for command
                            isActiveDictation = true;
                            document.getElementById('voice-status').textContent = 'Listening...';
                            transcriptEl.textContent = 'Speak your command...';
                            transcriptEl.classList.add('active');
                            document.getElementById('voice-hint').innerHTML = 'Say "stop" when done';
                        }
                    } else if (isActiveDictation || continuousMode || !alwaysListen) {
                        // In active dictation mode, type everything
                        addToTranscriptHistory(finalTranscript, 'command');
                        handleTranscript(finalTranscript);
                        
                        // End the active dictation session
                        isActiveDictation = false;
                        
                        // Reset to standby mode after processing command
                        if (alwaysListen && !continuousMode) {
                            // Go back to waiting for wake word
                            setTimeout(() => {
                                transcriptEl.textContent = `Ready for "${wakeWord}"`;
                                transcriptEl.classList.remove('active');
                                document.getElementById('voice-status').textContent = 'Standby';
                                document.getElementById('voice-hint').innerHTML = `Say "<strong>${wakeWord}</strong>" to activate`;
                            }, 1500);
                            addActivity('💬 Command processed - waiting for wake word', 'info');
                        } else if (!alwaysListen && !continuousMode) {
                            // Manual mode without continuous - stop after command
                            setTimeout(() => {
                                if (!isActiveDictation && !continuousMode) {
                                    stopListening();
                                    transcriptEl.textContent = 'Click mic to start again';
                                    addActivity('🎤 Dictation ended', 'info');
                                }
                            }, 2000);
                        }
                    }
                    // In always-listen mode without wake word, don't update transcript (keep showing waiting message)
                }
            };
            
            recognition.onerror = (event) => {
                // Handle common non-fatal errors - these will trigger onend which handles restart
                if (event.error === 'no-speech' || event.error === 'aborted') {
                    // Don't set isListening = false here - let onend handle it
                    // This prevents race conditions with the restart logic
                    console.log('Recognition ended:', event.error);
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
        
        // Audio context - initialized on first user interaction
        let audioCtx = null;
        
        function initAudioContext() {
            if (!audioCtx) {
                try {
                    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                } catch (e) {
                    console.log('AudioContext not available');
                }
            }
            // Resume if suspended (browsers suspend until user gesture)
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            return audioCtx;
        }
        
        // Initialize audio on first user click
        document.addEventListener('click', () => initAudioContext(), { once: true });
        
        // Text-to-Speech for Jarvis responses
        function speakText(text) {
            if (!text) return;
            
            // Use Web Speech API
            if ('speechSynthesis' in window) {
                // Cancel any ongoing speech
                window.speechSynthesis.cancel();
                
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 1.1; // Slightly faster
                utterance.pitch = 1.0;
                utterance.volume = 0.9;
                
                // Try to find a good voice
                const voices = window.speechSynthesis.getVoices();
                const preferredVoices = voices.filter(v => 
                    v.name.includes('Samantha') || 
                    v.name.includes('Google') || 
                    v.name.includes('Microsoft') ||
                    v.lang.startsWith('en')
                );
                if (preferredVoices.length > 0) {
                    utterance.voice = preferredVoices[0];
                }
                
                window.speechSynthesis.speak(utterance);
                console.log('🔊 Speaking:', text);
            } else {
                console.log('Speech synthesis not available');
            }
        }
        
        // Load voices when available
        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = () => {
                window.speechSynthesis.getVoices(); // Cache voices
            };
        }
        
        // Add a message to the chat
        function addChatMessage(text, sender = 'user') {
            const chatMessages = document.getElementById('chat-messages');
            const transcript = document.getElementById('transcript');
            
            // Clear the initial "waiting" message
            if (transcript.textContent.includes('Say your wake word')) {
                transcript.style.display = 'none';
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${sender}`;
            messageDiv.innerHTML = `
                <div class="sender">${sender === 'jarvis' ? '🤖 Jarvis' : '🎤 You'}</div>
                <div>${text}</div>
            `;
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Keep only last 10 messages
            while (chatMessages.children.length > 11) {
                chatMessages.removeChild(chatMessages.children[1]);
            }
        }
        
        // Clear chat messages
        function clearChat() {
            const chatMessages = document.getElementById('chat-messages');
            const transcript = document.getElementById('transcript');
            chatMessages.innerHTML = '';
            transcript.style.display = 'block';
            transcript.textContent = 'Say your wake word or click the mic...';
            chatMessages.appendChild(transcript);
        }
        
        function playSound(type) {
            const ctx = initAudioContext();
            if (!ctx) return;
            
            try {
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
                // Silently fail - sounds are optional
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
            
            // Fix common speech recognition errors before processing
            // "right" is often misheard as "write"
            if (/^right\s/i.test(text)) {
                text = text.replace(/^right\s/i, 'write ');
                console.log('Corrected "right" to "write":', text);
            }
            // "cursor right something" → "cursor write something"
            text = text.replace(/\b(cursor|claude|chatgpt|terminal)\s+right\s/gi, '$1 write ');
            
            console.log('Voice:', text);
            
            let parsed = null;
            
            // Try Claude first for intelligent parsing
            if (claudeAvailable && text.length > 2) {
                const claudeResult = await parseWithClaude(text);
                
                if (claudeResult) {
                    // Show what user said in chat
                    addChatMessage(text, 'user');
                    
                    // Check if Claude needs clarification
                    if (claudeResult.needsClarification || claudeResult.action === 'clarify') {
                        const clarifyMessage = claudeResult.speak || 'Could you be more specific?';
                        
                        // Show Jarvis response in chat
                        addChatMessage(clarifyMessage, 'jarvis');
                        
                        // Speak the clarification
                        speakText(clarifyMessage);
                        
                        // Keep listening for the user's response
                        isActiveDictation = true;
                        document.getElementById('voice-status').textContent = 'Listening...';
                        addActivity(`🤖 ${claudeResult.response || 'Asking for clarification'}`, 'info');
                        
                        console.log('🧠 Claude needs clarification:', clarifyMessage);
                        return; // Don't execute anything, wait for user response
                    }
                    
                    // Claude has a response to speak (but still executing)
                    if (claudeResult.speak && !claudeResult.needsClarification) {
                        addChatMessage(claudeResult.speak, 'jarvis');
                        speakText(claudeResult.speak);
                    }
                    
                    // Normal execution
                    if (claudeResult.targetApp || claudeResult.action) {
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
                            // Show brief confirmation in chat (but don't speak for normal commands)
                            if (!claudeResult.speak) {
                                addChatMessage(`✓ ${claudeResult.response}`, 'jarvis');
                            }
                        }
                    }
                }
            } else {
                // No Claude result - show user message anyway
                addChatMessage(text, 'user');
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
            
            // Handle browser actions (open_tab, open_url, search) - route to desktop client
            if (!skipRouting && (parsed.action === 'open_tab' || parsed.action === 'open_url' || parsed.action === 'search')) {
                const desktopClient = Object.values(devices).find(d => 
                    d.type === 'desktop_client' && d.id !== deviceId
                );
                
                if (desktopClient) {
                    socket.emit('route_command', {
                        fromDeviceId: deviceId,
                        toDeviceId: desktopClient.id,
                        command: parsed.command,
                        action: parsed.action,
                        targetApp: 'browser',
                        timestamp: new Date().toISOString()
                    });
                    
                    var actionLabel = parsed.action === 'open_tab' ? 'Opening new tab' : 
                                     parsed.action === 'open_url' ? 'Opening ' + parsed.command :
                                     'Searching: ' + parsed.command;
                    
                    showLastCommand('🌐', actionLabel, parsed.command || 'new tab');
                    addActivity('🌐 ' + actionLabel, 'success');
                    document.getElementById('transcript').textContent = '🌐 ' + actionLabel;
                    return;
                } else {
                    addActivity('⚠️ No desktop client connected for browser control', 'warning');
                }
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
            'shouldnt': "shouldn\'t", 'couldnt': "couldn\'t", 'wouldnt': "wouldn\'t",
            'dont': "don\'t", 'wont': "won\'t", 'cant': "can\'t", 'didnt': "didn\'t",
            'isnt': "isn\'t", 'wasnt': "wasn\'t", 'havent': "haven\'t", 'hasnt': "hasn\'t",
            'im': "I\'m", 'ive': "I\'ve", 'youre': "you\'re", 'theyre': "they\'re",
            'weve': "we\'ve", 'its a': "it\'s a", 'lets': "let\'s",
            // Common speech recognition errors
            'gonna': 'going to', 'wanna': 'want to', 'gotta': 'got to',
            'kinda': 'kind of', 'sorta': 'sort of', 'dunno': "don\'t know",
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
            if (!recognition) {
                console.error('No recognition object');
                return;
            }
            if (isListening) {
                console.log('Already listening');
                return;
            }
            recognition.lang = currentDevice?.language || 'en-US';
            try {
                recognition.start();
                console.log('Recognition started');
            } catch (e) {
                console.log('Recognition start error:', e.name, e.message);
                if (e.name !== 'InvalidStateError') {
                    addActivity('⚠️ ' + e.message, 'warning');
                }
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
                // Just try to start - the recognition.onerror will handle permission issues
                try {
                    recognition.lang = currentDevice?.language || 'en-US';
                    recognition.start();
                    addActivity('🎤 Starting microphone...', 'info');
                } catch (e) {
                    // Handle "already started" or stale recognition object
                    if (e.name === 'InvalidStateError') {
                        console.log('Recognition in invalid state, reinitializing...');
                        // Reinitialize recognition object and try again
                        initSpeechRecognition();
                        setTimeout(() => {
                            try {
                                recognition.lang = currentDevice?.language || 'en-US';
                                recognition.start();
                                addActivity('🎤 Starting microphone...', 'info');
                            } catch (e2) {
                                addActivity('⚠️ Could not start microphone: ' + e2.message, 'warning');
                            }
                        }, 100);
                    } else {
                        addActivity('⚠️ Could not start microphone: ' + e.message, 'warning');
                    }
                }
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
                    // In always-listen mode, waiting for wake word
                    micButton.innerHTML = 'ON';
                    voiceStatus.textContent = 'Standby';
                    voiceHint.innerHTML = `Say "<strong>${currentDevice?.wakeWord || 'hey computer'}</strong>" to activate`;
                } else if (isActiveDictation) {
                    // Active dictation after wake word
                    micButton.innerHTML = 'REC';
                    voiceStatus.textContent = 'Listening...';
                    voiceHint.innerHTML = 'Speak your command. Say "<strong>stop</strong>" when done.';
                } else {
                    // Manual recording mode
                    micButton.innerHTML = 'REC';
                    voiceStatus.textContent = 'Recording';
                    voiceHint.innerHTML = continuousMode ? 'Continuous mode active' : 'Speak now. Say "stop" or click to end.';
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
        
        let editingDeviceId = null;
        
        // Format relative time (e.g., "just now", "2 min ago")
        function formatLastSeen(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);
            
            if (seconds < 10) return 'just now';
            if (seconds < 60) return seconds + 's ago';
            
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return minutes + ' min ago';
            
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return hours + 'h ago';
            
            const days = Math.floor(hours / 24);
            return days + 'd ago';
        }
        
        function renderDeviceList() {
            const listEl = document.getElementById('device-list');
            if (!listEl) return;
            
            // Get all devices, prioritize current device first
            const allDevices = Object.values(devices);
            const thisDevice = allDevices.find(d => d.id === deviceId);
            const otherDevices = allDevices.filter(d => d.id !== deviceId && d.type !== 'desktop_client');
            
            let html = '';
            
            // This device first (highlighted)
            if (thisDevice) {
                html += `
                    <div class="device-item" onclick="openDeviceEditor('${thisDevice.id}')" style="cursor: pointer; padding: 12px; background: rgba(0,245,212,0.15); border-radius: 10px; border: 2px solid var(--accent); margin-bottom: 8px; transition: transform 0.1s;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 20px;">${thisDevice.icon || '💻'}</span>
                                <strong>${thisDevice.name || 'This Device'}</strong>
                            </div>
                            <span style="font-size: 9px; background: var(--success); color: white; padding: 2px 8px; border-radius: 10px;">THIS DEVICE</span>
                        </div>
                        <div style="font-size: 12px; color: var(--accent); margin-top: 6px; font-family: monospace;">
                            Wake: "${thisDevice.wakeWord || 'computer'}"
                        </div>
                        <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">Click to edit</div>
                    </div>
                `;
            }
            
            // Other connected devices
            otherDevices.forEach(d => {
                const isOnline = d.online !== false;
                const lastSeenText = d.lastSeen ? formatLastSeen(d.lastSeen) : '';
                const statusText = isOnline ? (lastSeenText ? 'Active ' + lastSeenText : 'ONLINE') : 'OFFLINE';
                
                html += `
                    <div class="device-item" onclick="openDeviceEditor('${d.id}')" style="cursor: pointer; padding: 10px; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 6px; opacity: ${isOnline ? 1 : 0.5}; transition: transform 0.1s;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 18px;">${d.icon || '💻'}</span>
                                <span>${d.name || 'Unknown'}</span>
                            </div>
                            <span style="font-size: 8px; background: ${isOnline ? 'var(--success)' : 'var(--text-muted)'}; color: white; padding: 2px 6px; border-radius: 8px;">
                                ${statusText}
                            </span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px; font-family: monospace;">
                            Wake: "${d.wakeWord || 'unknown'}"
                        </div>
                    </div>
                `;
            });
            
            // If no other devices
            if (otherDevices.length === 0 && thisDevice) {
                html += `<div style="color: var(--text-muted); font-size: 12px; padding: 8px; text-align: center;">No other devices connected</div>`;
            }
            
            listEl.innerHTML = html;
        }
        
        // Update lastSeen display every 30 seconds
        setInterval(renderDeviceList, 30000);
        
        function openDeviceEditor(id) {
            // Close any existing modal first
            closeDeviceEditor();
            
            editingDeviceId = id;
            const device = devices[id];
            if (!device) return;
            
            const isThisDevice = id === deviceId;
            
            const modal = document.createElement('div');
            modal.id = 'device-editor-modal';
            modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 10000;';
            
            let modalHTML = '<div id="device-editor-content" style="background: var(--bg-secondary); border-radius: 16px; padding: 24px; width: 90%; max-width: 400px; border: 1px solid var(--border);">';
            modalHTML += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">';
            modalHTML += '<h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">';
            modalHTML += '<span id="editor-header-icon" style="font-size: 24px;">' + (device.icon || '💻') + '</span> Edit Device</h3>';
            modalHTML += '<button id="close-editor-btn" style="background: none; border: none; color: var(--text-muted); font-size: 24px; cursor: pointer; padding: 4px 8px;">&times;</button></div>';
            
            // Clear status indicator
            if (isThisDevice) {
                modalHTML += '<div style="background: rgba(0,245,212,0.15); border: 1px solid var(--accent); border-radius: 8px; padding: 10px; margin-bottom: 16px; font-size: 13px; color: var(--accent); display: flex; align-items: center; gap: 8px;">';
                modalHTML += '<span style="font-size: 16px;">✓</span> <strong>This is YOUR current device</strong></div>';
            } else {
                modalHTML += '<div style="background: rgba(255,165,0,0.15); border: 1px solid orange; border-radius: 8px; padding: 10px; margin-bottom: 16px; font-size: 13px; color: orange; display: flex; align-items: center; gap: 8px;">';
                modalHTML += '<span style="font-size: 16px;">📡</span> <strong>Editing REMOTE device:</strong> ' + (device.name || 'Unknown') + '</div>';
            }
            
            modalHTML += '<div style="margin-bottom: 16px;">';
            modalHTML += '<label style="display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-muted);">Device Name <span style="color: var(--text-muted); font-size: 11px;">(used for cross-device commands)</span></label>';
            modalHTML += '<input type="text" id="edit-device-name" value="' + (device.name || '').replace(/"/g, '&quot;') + '" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-primary); color: var(--text-primary); font-size: 15px; box-sizing: border-box;" autocomplete="off" spellcheck="false">';
            modalHTML += '</div>';
            
            modalHTML += '<div style="margin-bottom: 16px;">';
            modalHTML += '<label style="display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-muted);">Wake Word <span style="color: var(--text-muted); font-size: 11px;">(activates this device only)</span></label>';
            modalHTML += '<input type="text" id="edit-device-wake" value="' + (device.wakeWord || '').replace(/"/g, '&quot;') + '" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-primary); color: var(--text-primary); font-size: 15px; box-sizing: border-box;" autocomplete="off" spellcheck="false">';
            modalHTML += '<div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Say this word to activate listening on this device</div>';
            modalHTML += '</div>';
            
            modalHTML += '<div style="margin-bottom: 20px;">';
            modalHTML += '<label style="display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-muted);">Icon</label>';
            modalHTML += '<div style="display: flex; gap: 8px; flex-wrap: wrap;">';
            var icons = ['💻', '🖥️', '📱', '⌨️', '🎧', '🎤', '🖱️', '📺'];
            for (var i = 0; i < icons.length; i++) {
                var icon = icons[i];
                var isSelected = device.icon === icon;
                var btnStyle = 'padding: 8px 12px; border-radius: 8px; border: 2px solid ' + (isSelected ? 'var(--accent)' : 'var(--border)') + '; background: ' + (isSelected ? 'rgba(0,245,212,0.1)' : 'var(--bg-primary)') + '; cursor: pointer; font-size: 18px;';
                modalHTML += '<button data-icon="' + icon + '" style="' + btnStyle + '">' + icon + '</button>';
            }
            modalHTML += '</div></div>';
            
            modalHTML += '<div style="display: flex; gap: 12px;">';
            modalHTML += '<button onclick="saveDeviceEdit()" style="flex: 1; padding: 12px; border-radius: 8px; border: none; background: var(--accent); color: var(--bg-primary); font-weight: 600; cursor: pointer;">Save Changes</button>';
            modalHTML += '<button onclick="closeDeviceEditor()" style="padding: 12px 20px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text-primary); cursor: pointer;">Cancel</button>';
            modalHTML += '</div></div>';
            
            modal.innerHTML = modalHTML;
            document.body.appendChild(modal);
            
            // Set up event listeners after modal is in DOM
            var closeBtn = document.getElementById('close-editor-btn');
            if (closeBtn) {
                closeBtn.onclick = function(e) {
                    e.stopPropagation();
                    closeDeviceEditor();
                };
            }
            
            // Prevent clicks inside the modal content from closing it
            var content = document.getElementById('device-editor-content');
            if (content) {
                content.onclick = function(e) {
                    e.stopPropagation();
                    // Handle icon button clicks
                    if (e.target.dataset && e.target.dataset.icon) {
                        selectDeviceIcon(e.target.dataset.icon);
                    }
                };
            }
            
            // Close only when clicking the backdrop
            modal.onclick = function(e) {
                if (e.target === modal) {
                    closeDeviceEditor();
                }
            };
            
            // Focus the name input
            setTimeout(function() {
                var nameInput = document.getElementById('edit-device-name');
                if (nameInput) nameInput.focus();
            }, 100);
        }
        
        function selectDeviceIcon(icon) {
            if (editingDeviceId && devices[editingDeviceId]) {
                // Update the icon in memory
                devices[editingDeviceId].icon = icon;
                
                // Update just the icon buttons visually (no re-render)
                var buttons = document.querySelectorAll('#device-editor-modal button[data-icon]');
                buttons.forEach(function(btn) {
                    var btnIcon = btn.dataset.icon;
                    var isSelected = btnIcon === icon;
                    btn.style.borderColor = isSelected ? 'var(--accent)' : 'var(--border)';
                    btn.style.background = isSelected ? 'rgba(0,245,212,0.1)' : 'var(--bg-primary)';
                });
                
                // Update the icon in the header
                var headerIcon = document.getElementById('editor-header-icon');
                if (headerIcon) headerIcon.textContent = icon;
            }
        }
        
        function saveDeviceEdit() {
            if (!editingDeviceId) return;
            
            const name = document.getElementById('edit-device-name').value.trim();
            const wakeWord = document.getElementById('edit-device-wake').value.trim().toLowerCase();
            
            if (!name || !wakeWord) {
                alert('Please fill in all fields');
                return;
            }
            
            const device = devices[editingDeviceId];
            device.name = name;
            device.wakeWord = wakeWord;
            
            // If editing current device, update currentDevice too
            if (editingDeviceId === deviceId) {
                currentDevice.name = name;
                currentDevice.wakeWord = wakeWord;
                currentDevice.icon = device.icon;
                saveDevices(); // Save to localStorage
            }
            
            // Sync to server so other devices see the change
            socket.emit('device_update', {
                deviceId: editingDeviceId,
                settings: {
                    name: device.name,
                    wakeWord: device.wakeWord,
                    icon: device.icon
                }
            });
            
            closeDeviceEditor();
            renderDeviceList();
            addActivity('Device updated: ' + name, 'success');
        }
        
        function closeDeviceEditor() {
            const modal = document.getElementById('device-editor-modal');
            if (modal) modal.remove();
            editingDeviceId = null;
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
        // TRANSCRIPT HISTORY
        // ============================================================
        
        function addToTranscriptHistory(text, type = 'command') {
            const entry = {
                id: Date.now(),
                text: text,
                type: type, // 'command', 'wake', 'routed'
                time: new Date(),
                device: currentDevice?.name || 'Unknown'
            };
            transcriptHistory.push(entry);
            updateTranscriptCount();
        }
        
        function updateTranscriptCount() {
            const countEl = document.getElementById('transcript-count');
            if (transcriptHistory.length > 0) {
                countEl.textContent = transcriptHistory.length;
                countEl.style.display = 'inline';
            } else {
                countEl.style.display = 'none';
            }
        }
        
        function openTranscriptHistory() {
            renderTranscriptHistory();
            document.getElementById('transcript-history-modal').classList.add('active');
        }
        
        function closeTranscriptHistory() {
            document.getElementById('transcript-history-modal').classList.remove('active');
        }
        
        function renderTranscriptHistory() {
            const listEl = document.getElementById('transcript-history-list');
            const infoEl = document.getElementById('transcript-session-info');
            
            // Update session info
            const elapsed = Math.floor((new Date() - sessionStartTime) / 1000 / 60);
            if (elapsed < 1) {
                infoEl.textContent = 'Session started just now';
            } else if (elapsed < 60) {
                infoEl.textContent = 'Session: ' + elapsed + ' min • ' + transcriptHistory.length + ' transcripts';
            } else {
                const hours = Math.floor(elapsed / 60);
                const mins = elapsed % 60;
                infoEl.textContent = 'Session: ' + hours + 'h ' + mins + 'm • ' + transcriptHistory.length + ' transcripts';
            }
            
            if (transcriptHistory.length === 0) {
                listEl.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 40px;">No transcripts yet. Start speaking to record your session.</p>';
                return;
            }
            
            // Render in reverse chronological order (newest first)
            const typeIcons = {
                command: '💬',
                wake: '🎯',
                routed: '📤',
                stop: '🛑'
            };
            
            const typeLabels = {
                command: 'Command',
                wake: 'Wake Word',
                routed: 'Routed',
                stop: 'Stopped'
            };
            
            listEl.innerHTML = transcriptHistory.slice().reverse().map(function(entry) {
                const timeStr = entry.time.toLocaleTimeString();
                var icon = typeIcons[entry.type] || '💬';
                var label = typeLabels[entry.type] || 'Transcript';
                
                return '<div style="background: var(--bg-secondary); border-radius: 12px; padding: 14px 16px; border-left: 3px solid ' + (entry.type === 'wake' ? 'var(--accent)' : entry.type === 'routed' ? '#a855f7' : 'var(--border)') + ';">' +
                    '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">' +
                        '<span style="font-size: 12px; color: var(--text-muted);">' + icon + ' ' + label + '</span>' +
                        '<span style="font-size: 11px; color: var(--text-muted);">' + timeStr + '</span>' +
                    '</div>' +
                    '<p style="font-size: 15px; line-height: 1.5; margin: 0; word-break: break-word;">' + escapeHtml(entry.text) + '</p>' +
                '</div>';
            }).join('');
        }
        
        function clearTranscriptHistory() {
            transcriptHistory = [];
            updateTranscriptCount();
            renderTranscriptHistory();
            addActivity('Session transcripts cleared', 'info');
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Add click listener for transcript header
        document.getElementById('transcript-header').addEventListener('click', openTranscriptHistory);
        
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
                addActivity('Wake word listening enabled', 'success');
                startListening();
            } else {
                addActivity('Wake word listening disabled', 'info');
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
            // Send full device info when joining
            socket.emit('dashboard_join', { 
                deviceId: deviceId,
                device: {
                    id: deviceId,
                    name: currentDevice.name,
                    wakeWord: currentDevice.wakeWord,
                    icon: currentDevice.icon,
                    type: 'browser'
                }
            });
            
            // Send heartbeat every 30 seconds to keep lastSeen updated
            setInterval(function() {
                socket.emit('heartbeat', { deviceId: deviceId });
            }, 30000);
        });
        
        socket.on('devices_update', (data) => {
            if (data.devices) {
                for (const [id, device] of Object.entries(data.devices)) {
                    // Update or add the device
                    devices[id] = { ...devices[id], ...device };
                    
                    // If this is OUR device and settings were changed remotely, update currentDevice and save
                    if (id === deviceId) {
                        var wasChanged = false;
                        if (device.name && device.name !== currentDevice.name) {
                            currentDevice.name = device.name;
                            wasChanged = true;
                        }
                        if (device.wakeWord && device.wakeWord !== currentDevice.wakeWord) {
                            currentDevice.wakeWord = device.wakeWord;
                            wasChanged = true;
                        }
                        if (device.icon && device.icon !== currentDevice.icon) {
                            currentDevice.icon = device.icon;
                            wasChanged = true;
                        }
                        if (wasChanged) {
                            console.log('Device settings updated remotely:', currentDevice.name, currentDevice.wakeWord);
                            saveDevices();
                            updateUI();
                        }
                    }
                }
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
            const id = data.deviceId;
            if (data.device) {
                // New or updated device info
                devices[id] = { ...devices[id], ...data.device, online: true };
            } else if (devices[id]) {
                devices[id].online = true;
            }
            renderDeviceList();
            renderAvailableDevices();
            console.log('Device online:', data.device?.name || id);
        });
        
        socket.on('device_offline', (data) => {
            if (devices[data.deviceId]) {
                devices[data.deviceId].online = false;
                devices[data.deviceId].lastSeen = new Date().toISOString();
                renderDeviceList();
                renderAvailableDevices();
            }
        });
        
        socket.on('device_heartbeat', (data) => {
            if (devices[data.deviceId]) {
                devices[data.deviceId].lastSeen = data.lastSeen;
                devices[data.deviceId].online = true;
                renderDeviceList();
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
# SECURITY MIDDLEWARE & HELPERS
# ============================================================================

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Enable XSS filter in browsers
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Referrer policy - don't leak URLs to external sites
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions policy - disable unnecessary browser features
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), payment=()'
    
    # Content Security Policy - allow inline scripts/styles for our embedded templates
    # but restrict external sources
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' wss: ws: https://cdnjs.cloudflare.com; "
        "frame-ancestors 'self';"
    )
    response.headers['Content-Security-Policy'] = csp
    
    # HSTS - enforce HTTPS (only in production)
    if os.environ.get('FLASK_ENV') != 'development':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

def is_account_locked(username):
    """Check if account is locked due to failed attempts"""
    if username not in failed_login_attempts:
        return False
    
    attempts, lockout_time = failed_login_attempts[username]
    if attempts >= MAX_FAILED_ATTEMPTS:
        if datetime.now() < lockout_time:
            return True
        else:
            # Lockout expired, reset
            del failed_login_attempts[username]
            return False
    return False

def record_failed_login(username):
    """Record a failed login attempt"""
    if username not in failed_login_attempts:
        failed_login_attempts[username] = (1, datetime.now() + LOCKOUT_DURATION)
    else:
        attempts, _ = failed_login_attempts[username]
        failed_login_attempts[username] = (attempts + 1, datetime.now() + LOCKOUT_DURATION)

def clear_failed_logins(username):
    """Clear failed login attempts after successful login"""
    if username in failed_login_attempts:
        del failed_login_attempts[username]

def sanitize_input(text, max_length=10000):
    """Sanitize user input to prevent XSS and injection attacks"""
    if not text:
        return text
    # Limit length
    text = str(text)[:max_length]
    # Remove null bytes
    text = text.replace('\x00', '')
    return text

# CSRF exemptions are now applied as decorators directly on the routes
# This ensures they work correctly (the old approach called csrf.exempt before routes were defined)

# Rate limit decorators for specific routes
login_limit = limiter.limit("5 per minute", error_message="Too many login attempts. Please try again later.")
api_limit = limiter.limit("30 per minute")

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_PAGE, user=current_user)

@app.route('/login', methods=['GET', 'POST'])
@login_limit
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        u = request.form.get('username', '').strip().lower()
        u = sanitize_input(u, max_length=100)  # Sanitize username
        p = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        # Check if account is locked
        if is_account_locked(u):
            return render_template_string(LOGIN_PAGE, error='Account temporarily locked. Try again in 15 minutes.', success=None)
        
        if u in USERS and check_password_hash(USERS[u]['password_hash'], p):
            clear_failed_logins(u)  # Reset on successful login
            login_user(User(u), remember=remember)
            session.permanent = True  # Use permanent session with secure settings
            print(f"User logged in: {u} (remember={remember})")
            return redirect(url_for('dashboard'))
        
        # Record failed attempt
        record_failed_login(u)
        remaining = MAX_FAILED_ATTEMPTS - failed_login_attempts.get(u, (0, None))[0]
        if remaining <= 2:
            return render_template_string(LOGIN_PAGE, error=f'Invalid credentials. {remaining} attempts remaining.', success=None)
        return render_template_string(LOGIN_PAGE, error='Invalid username or password', success=None)
    
    success = request.args.get('success')
    return render_template_string(LOGIN_PAGE, error=None, success=success)

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("10 per hour")  # Rate limit signup to prevent spam
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', '').strip(), max_length=100)
        username = sanitize_input(request.form.get('username', '').strip().lower(), max_length=50)
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        
        # Validation
        if not name or not username or not password:
            return render_template_string(SIGNUP_PAGE, error='All fields are required')
        
        if len(username) < 3:
            return render_template_string(SIGNUP_PAGE, error='Username must be at least 3 characters')
        
        if not username.replace('_', '').isalnum():
            return render_template_string(SIGNUP_PAGE, error='Username can only contain letters, numbers, and underscores')
        
        if len(password) < 4:
            return render_template_string(SIGNUP_PAGE, error='Password must be at least 4 characters')
        
        if password != password2:
            return render_template_string(SIGNUP_PAGE, error='Passwords do not match')
        
        if username in USERS:
            return render_template_string(SIGNUP_PAGE, error='Username already taken')
        
        # Create the user
        USERS[username] = {
            'password_hash': generate_password_hash(password),
            'name': name
        }
        save_users()
        print(f"New user created: {username} ({name})")
        
        return redirect(url_for('login', success='Account created! Please sign in.'))
    
    return render_template_string(SIGNUP_PAGE, error=None)

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

@app.route('/favicon.ico')
def favicon():
    """Return a simple SVG favicon"""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" rx="20" fill="#0a0a0f"/>
        <circle cx="50" cy="45" r="25" fill="#00f5d4"/>
        <rect x="45" y="65" width="10" height="20" rx="2" fill="#00f5d4"/>
    </svg>'''
    return Response(svg, mimetype='image/svg+xml')

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
CLIENT_VERSION = "1.4.0"

# ============================================================================
# CLAUDE AI COMMAND PARSING
# ============================================================================

COMMAND_PARSE_PROMPT = """You are Jarvis, an intelligent voice assistant. Your job is to understand INTENT and help the user.

CORE PRINCIPLE: Understand what the user MEANS. If you're confident, execute silently. If unsure, ASK.

Return JSON:
{
  "targetApp": "cursor" | "vscode" | "claude" | "chatgpt" | "copilot" | "gemini" | "terminal" | "browser" | "notes" | "slack" | "discord" | "finder" | null,
  "action": "type" | "type_and_send" | "open" | "open_url" | "search" | "run" | "stop" | "clarify" | null,
  "content": "the actual content to type/send/search",
  "response": "Brief confirmation (3-5 words) - shown in activity log",
  "speak": "What Jarvis says out loud to the user (only if action is 'clarify' or there's an error)",
  "needsClarification": true | false
}

WHEN TO USE "clarify" ACTION:
- Command is ambiguous: "open it" (open what?)
- Missing critical info: "send this" (send to whom? what content?)
- Multiple interpretations: "type that" (type what exactly?)
- User seems confused or command makes no sense

WHEN TO JUST EXECUTE (no speak):
- Clear command: "open youtube" → just do it
- Obvious intent: "cursor write hello world" → just type it
- Standard patterns: "search for pizza" → just search

WHEN TO SPEAK (explain something):
- Error situation: "I can't find an app called 'blurp'"
- Helpful context: "Opening YouTube in your browser"
- Clarification needed: "Did you mean Cursor or Chrome?"

SMART DEFAULTS BY APP TYPE:

AI ASSISTANTS (cursor, claude, chatgpt, copilot, gemini):
- These are CONVERSATIONAL - default to "type_and_send" (type + press Enter)
- "ask cursor how do I fix this" → type_and_send "how do I fix this" to cursor
- "cursor what is python" → type_and_send "what is python" to cursor
- "tell claude to explain recursion" → type_and_send "explain recursion" to claude
- ANY mention of these apps with a question/request = type_and_send

CODE EDITORS (cursor, vscode) when writing code:
- "cursor write a function" → type "a function" (no enter, they're coding)
- "in cursor type hello world" → type "hello world"
- Distinguish: questions go to AI chat, code goes to editor

TERMINAL:
- Default to "run" (type + enter)
- "terminal npm install" → run "npm install"

BROWSER:
- Websites → "open_url" with full URL
- Questions → "search" 
- "open youtube" → open_url "https://youtube.com"
- "search for recipes" → search "recipes"

INTENT RECOGNITION (be smart about this):

"ask [app] [question]" = type_and_send the question to that app
"tell [app] [message]" = type_and_send the message
"[app] [question/request]" = type_and_send (for AI apps)
"in [app] type [text]" = type the text
"[app] write [code]" = type (for code editors)
"open [website]" = open_url
"go to [website]" = open_url
"search [query]" = search
"google [query]" = search
"run [command]" = run in terminal

APP RECOGNITION (be flexible with names):
- cursor/curser/coursor/cursur = "cursor" (AI-powered code editor)
- claude/cloud/claud = "claude" 
- chatgpt/chat gpt/GPT/gpt/chat = "chatgpt"
- vscode/vs code/visual studio = "vscode"
- copilot/co-pilot = "copilot"
- gemini/bard = "gemini"
- terminal/command/shell/cmd = "terminal"
- chrome/safari/firefox/browser = "browser"

WEBSITE SHORTCUTS:
youtube/google/github/twitter/x/facebook/reddit/amazon/netflix/spotify/linkedin/instagram/gmail → use https://[site].com

STOP DETECTION:
- Pure stop commands: "stop", "stop listening", "cancel", "that's enough" → {"action":"stop","response":"Stopping"}
- NOT stop: "don't stop", "stop sign", "bus stop" → parse normally

EXAMPLES OF SMART PARSING:

"ask cursor how do I center a div" 
→ {"targetApp":"cursor","action":"type_and_send","content":"how do I center a div","response":"Asking Cursor"}

"cursor what is recursion"
→ {"targetApp":"cursor","action":"type_and_send","content":"what is recursion","response":"Asking Cursor"}

"tell cursor to help me fix this bug"
→ {"targetApp":"cursor","action":"type_and_send","content":"help me fix this bug","response":"Asking Cursor"}

"in cursor write function add numbers"
→ {"targetApp":"cursor","action":"type","content":"function add numbers","response":"Typing in Cursor"}

"claude explain python decorators"
→ {"targetApp":"claude","action":"type_and_send","content":"explain python decorators","response":"Asking Claude"}

"open youtube"
→ {"targetApp":"browser","action":"open_url","content":"https://youtube.com","response":"Opening YouTube"}

"search best pizza near me"
→ {"targetApp":"browser","action":"search","content":"best pizza near me","response":"Searching"}

"terminal npm install express"
→ {"targetApp":"terminal","action":"run","content":"npm install express","response":"Running"}

"this is working"
→ {"action":"type","content":"this is working","response":"Typing"}

CLARIFICATION EXAMPLES:

"open it"
→ {"action":"clarify","needsClarification":true,"speak":"Open what? Say the app or website name.","response":"Need more info"}

"send this"
→ {"action":"clarify","needsClarification":true,"speak":"Send what, and where? Try saying 'send hello to Claude' for example.","response":"Need more info"}

"do the thing"
→ {"action":"clarify","needsClarification":true,"speak":"I'm not sure what you want me to do. Can you be more specific?","response":"Need clarification"}

"blurp help me"
→ {"action":"clarify","needsClarification":true,"speak":"I don't recognize 'blurp'. Did you mean Cursor, Claude, or Chrome?","response":"Unknown app"}

ERROR EXAMPLES:

"open netflix" (but Netflix requires login)
→ {"action":"open_url","content":"https://netflix.com","response":"Opening Netflix"}
(No speak needed - just execute, user knows they need to log in)

SILENT EXECUTION (no speak field):

"cursor write a hello world function"
→ {"targetApp":"cursor","action":"type","content":"a hello world function","response":"Typing in Cursor"}

"open github"  
→ {"targetApp":"browser","action":"open_url","content":"https://github.com","response":"Opening GitHub"}

Return ONLY valid JSON."""

@app.route('/api/parse-command', methods=['POST'])
@csrf.exempt
@login_required
@api_limit
def api_parse_command():
    """Use Claude to intelligently parse a voice command"""
    if not CLAUDE_AVAILABLE or not claude_client:
        return jsonify({'error': 'Claude not available', 'fallback': True}), 200
    
    # Try to get JSON data, handle errors gracefully
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    
    text = sanitize_input(data.get('text', ''), max_length=1000)  # Sanitize and limit
    
    if not text or len(text.strip()) == 0:
        # Return fallback instead of 400 - let regex handle it
        return jsonify({'error': 'No text provided', 'fallback': True}), 200
    
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
@csrf.exempt
@login_required
@api_limit
def get_devices():
    return jsonify(devices)

@app.route('/api/devices/<device_id>', methods=['PUT', 'DELETE'])
@csrf.exempt
@login_required
@api_limit
def manage_device(device_id):
    # Sanitize device_id to prevent injection
    device_id = sanitize_input(device_id, max_length=100)
    
    if request.method == 'DELETE':
        if device_id in devices:
            del devices[device_id]
        return jsonify({'status': 'ok'})
    elif request.method == 'PUT':
        data = request.json
        if device_id in devices:
            # Sanitize incoming data
            sanitized_data = {}
            for key, value in data.items():
                if isinstance(value, str):
                    sanitized_data[key] = sanitize_input(value, max_length=500)
                else:
                    sanitized_data[key] = value
            devices[device_id].update(sanitized_data)
        return jsonify(devices.get(device_id, {}))

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

# Store authenticated socket sessions
authenticated_sockets = {}

def require_socket_auth(f):
    """Decorator to require authentication for WebSocket events.
    Allows browser sessions (logged in users) and registered desktop clients."""
    @wraps(f)
    def decorated(*args, **kwargs):
        sid = request.sid
        
        # Check if this socket is from an authenticated browser session
        if current_user.is_authenticated:
            authenticated_sockets[sid] = {'type': 'browser', 'user': current_user.id}
            return f(*args, **kwargs)
        
        # Check if this socket was previously authenticated
        if sid in authenticated_sockets:
            return f(*args, **kwargs)
        
        # Check if this is a desktop client (they identify via device_update)
        # Desktop clients are allowed but tracked
        data = args[0] if args else {}
        device_id = data.get('deviceId') if isinstance(data, dict) else None
        if device_id:
            authenticated_sockets[sid] = {'type': 'desktop', 'device': device_id}
            return f(*args, **kwargs)
        
        # Log unauthenticated access attempt (but don't block to avoid breaking things)
        print(f"⚠️ Unauthenticated WebSocket event from {sid}")
        return f(*args, **kwargs)
    
    return decorated

@socketio.on('connect')
def on_connect():
    """Handle new WebSocket connections"""
    sid = request.sid
    # Check if user is authenticated via browser session
    if current_user.is_authenticated:
        authenticated_sockets[sid] = {'type': 'browser', 'user': current_user.id}
        print(f"🔐 Authenticated browser connected: {current_user.id} (sid: {sid})")
    else:
        # Could be a desktop client - will be validated on first event
        print(f"🔌 New WebSocket connection: {sid} (awaiting authentication)")

@socketio.on('dashboard_join')
@require_socket_auth
def on_dashboard_join(data):
    device_id = data.get('deviceId')
    device_info = data.get('device', {})
    print(f"\n[DEVICE JOIN] {device_info.get('name', device_id)}")
    print(f"   ID: {device_id}")
    print(f"   Wake Word: {device_info.get('wakeWord', 'unknown')}")
    print(f"   Type: {device_info.get('type', 'browser')}")
    
    join_room('dashboard')
    join_room(device_id)  # Join own room to receive routed commands
    
    # Store full device info
    if device_id:
        if device_id not in devices:
            devices[device_id] = {'id': device_id}
        
        # Update with provided info
        devices[device_id].update({
            'id': device_id,
            'name': device_info.get('name', 'Unknown Device'),
            'wakeWord': device_info.get('wakeWord', 'computer'),
            'icon': device_info.get('icon', '💻'),
            'type': device_info.get('type', 'browser'),
            'sid': request.sid,
            'online': True,
            'lastSeen': datetime.now().isoformat()
        })
        
        # Notify others this device is online
        socketio.emit('device_online', {'deviceId': device_id, 'device': devices[device_id]}, room='dashboard')
    
    # Send full device list to the joining client
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
        devices[device_id]['lastSeen'] = datetime.now().isoformat()
        
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

@socketio.on('heartbeat')
def on_heartbeat(data):
    """Update lastSeen timestamp for a device"""
    device_id = data.get('deviceId')
    if device_id and device_id in devices:
        devices[device_id]['lastSeen'] = datetime.now().isoformat()
        devices[device_id]['online'] = True
        # Broadcast updated lastSeen to all dashboards
        socketio.emit('device_heartbeat', {
            'deviceId': device_id,
            'lastSeen': devices[device_id]['lastSeen']
        }, room='dashboard')

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    
    # Clean up authenticated socket tracking
    if sid in authenticated_sockets:
        auth_info = authenticated_sockets.pop(sid)
        print(f"🔌 Socket disconnected: {auth_info.get('user') or auth_info.get('device', 'unknown')}")
    
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
