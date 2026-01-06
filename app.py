"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        🎛️ VOICE HUB - CLOUD SERVER                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Upload these files to GitHub, then deploy on Railway                        ║
║  Login: admin / voicehub123 (or set ADMIN_PASSWORD env variable)             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import secrets
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, Response
from flask_socketio import SocketIO, emit, join_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================================
# SETUP
# ============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

login_manager = LoginManager(app)
login_manager.login_view = 'login'

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'voicehub123')
USERS = {'admin': {'password_hash': generate_password_hash(ADMIN_PASSWORD), 'name': 'Admin'}}

connected_clients = {}

# Default settings (can be customized per session)
default_settings = {
    'theme': 'dark',
    'accent_color': '#00f5d4',
    'continuous_mode': False,
    'sound_feedback': True,
    'auto_punctuation': True,
    'language': 'en-US'
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.name = USERS.get(username, {}).get('name', username)

@login_manager.user_loader
def load_user(username):
    return User(username) if username in USERS else None

# ============================================================================
# LOGIN PAGE - REDESIGNED
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
        h1 {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        h1 span {
            background: linear-gradient(135deg, var(--accent), var(--accent-3));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 8px;
        }
        .form-group {
            margin-bottom: 24px;
        }
        label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        input {
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
        input::placeholder {
            color: var(--text-muted);
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
            margin-top: 8px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 245, 212, 0.3);
        }
        .btn:active {
            transform: translateY(0);
        }
        .error {
            background: rgba(247, 37, 133, 0.1);
            border: 1px solid rgba(247, 37, 133, 0.3);
            color: var(--accent-3);
            padding: 14px 18px;
            border-radius: 12px;
            margin-bottom: 24px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
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
                <p class="subtitle">Voice-to-text for your devices</p>
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
                <button type="submit" class="btn">Sign In →</button>
            </form>
        </div>
    </div>
</body>
</html>
'''

# ============================================================================
# DASHBOARD PAGE - COMPLETELY REDESIGNED
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
            overflow-x: hidden;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--bg-elevated); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        
        /* Header */
        header {
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 16px 32px;
            background: rgba(10, 10, 15, 0.8);
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
            gap: 16px;
        }
        .user-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 16px;
            background: var(--bg-card);
            border-radius: 50px;
            font-size: 14px;
            color: var(--text-secondary);
        }
        .user-badge .avatar {
            width: 28px;
            height: 28px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
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
        
        /* Main Layout */
        main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 32px;
        }
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: all 0.3s ease;
        }
        .stat-card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
        }
        .stat-icon {
            width: 56px;
            height: 56px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
        }
        .stat-icon.blue { background: rgba(0, 245, 212, 0.15); }
        .stat-icon.green { background: rgba(16, 185, 129, 0.15); }
        .stat-icon.purple { background: rgba(123, 44, 191, 0.15); }
        .stat-icon.pink { background: rgba(247, 37, 133, 0.15); }
        .stat-content .value {
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
        }
        .stat-content .value.accent { color: var(--accent); }
        .stat-content .value.success { color: var(--success); }
        .stat-content .label {
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Section Header */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        .section-title {
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Quick Setup */
        .setup-card {
            background: linear-gradient(135deg, rgba(0, 245, 212, 0.08), rgba(123, 44, 191, 0.08));
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 32px;
            margin-bottom: 32px;
            position: relative;
            overflow: hidden;
        }
        .setup-card::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(0, 245, 212, 0.1), transparent 70%);
            pointer-events: none;
        }
        .setup-card h3 {
            font-size: 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .setup-steps {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .step {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 14px;
            padding: 20px;
        }
        .step-number {
            width: 28px;
            height: 28px;
            background: var(--accent);
            color: var(--bg-primary);
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 12px;
        }
        .step h4 {
            font-size: 15px;
            margin-bottom: 8px;
        }
        .step p {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }
        .step code {
            display: block;
            background: var(--bg-primary);
            padding: 12px 16px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--accent);
            word-break: break-all;
            overflow-x: auto;
        }
        .step a {
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }
        .step a:hover {
            text-decoration: underline;
        }
        
        /* Clients Grid */
        .clients-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 24px;
        }
        .client-card {
            background: var(--bg-card);
            border: 2px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .client-card:hover {
            border-color: var(--border-hover);
        }
        .client-card.online {
            border-color: var(--success);
        }
        .client-header {
            padding: 20px 24px;
            background: var(--bg-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .client-card.online .client-header {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), transparent);
        }
        .client-identity {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .client-avatar {
            width: 52px;
            height: 52px;
            background: var(--bg-elevated);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
        }
        .client-info h3 {
            font-size: 17px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .wake-word {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--accent);
            background: rgba(0, 245, 212, 0.1);
            padding: 4px 10px;
            border-radius: 6px;
        }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 50px;
            font-size: 13px;
            font-weight: 500;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-muted);
        }
        .status-dot.online {
            background: var(--success);
            box-shadow: 0 0 12px var(--success);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
        }
        .client-body {
            padding: 24px;
        }
        .client-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        .mini-stat {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
        }
        .mini-stat .value {
            font-size: 22px;
            font-weight: 700;
            color: var(--accent);
            margin-bottom: 2px;
        }
        .mini-stat .label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .activity-log {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 16px;
            max-height: 140px;
            overflow-y: auto;
        }
        .activity-log h4 {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        .log-entry {
            display: flex;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }
        .log-entry:last-child { border: none; }
        .log-time {
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-muted);
            font-size: 11px;
            flex-shrink: 0;
        }
        .log-message { color: var(--text-secondary); }
        .log-message.success { color: var(--success); }
        .log-message.error { color: var(--accent-3); }
        .log-message.wake_word { color: var(--accent); }
        
        /* Empty State */
        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 80px 40px;
            background: var(--bg-card);
            border: 2px dashed var(--border);
            border-radius: 20px;
        }
        .empty-state .icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        .empty-state h3 {
            font-size: 22px;
            margin-bottom: 10px;
        }
        .empty-state p {
            color: var(--text-muted);
            max-width: 400px;
            margin: 0 auto;
        }
        
        /* Settings Modal */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
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
            max-width: 520px;
            max-height: 90vh;
            overflow-y: auto;
            transform: translateY(20px);
            transition: transform 0.3s ease;
        }
        .modal-overlay.active .modal {
            transform: translateY(0);
        }
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
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        .modal-close:hover {
            background: var(--bg-elevated);
            color: var(--text);
        }
        .modal-body {
            padding: 28px;
        }
        .setting-group {
            margin-bottom: 28px;
        }
        .setting-group:last-child { margin-bottom: 0; }
        .setting-group h3 {
            font-size: 14px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
        }
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }
        .setting-item:last-child { border: none; }
        .setting-label h4 {
            font-size: 15px;
            margin-bottom: 4px;
        }
        .setting-label p {
            font-size: 13px;
            color: var(--text-muted);
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
        .toggle.active {
            background: var(--accent);
        }
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
        .toggle.active::after {
            transform: translateX(24px);
        }
        select {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 14px;
            font-family: inherit;
            color: var(--text);
            cursor: pointer;
            min-width: 140px;
        }
        select:focus {
            outline: none;
            border-color: var(--accent);
        }
        .color-options {
            display: flex;
            gap: 10px;
        }
        .color-option {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            border: 3px solid transparent;
            transition: all 0.2s;
        }
        .color-option:hover {
            transform: scale(1.1);
        }
        .color-option.active {
            border-color: white;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 768px) {
            header { padding: 12px 16px; }
            main { padding: 20px 16px; }
            .stats-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
            .stat-card { padding: 16px; }
            .stat-icon { width: 44px; height: 44px; font-size: 20px; }
            .stat-content .value { font-size: 24px; }
            .clients-grid { grid-template-columns: 1fr; }
            .setup-steps { grid-template-columns: 1fr; }
        }
        @media (max-width: 480px) {
            .stats-grid { grid-template-columns: 1fr; }
            .header-actions .user-badge { display: none; }
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
            <div class="user-badge">
                <div class="avatar">👤</div>
                <span>{{ user.name }}</span>
            </div>
            <button class="btn btn-ghost" onclick="openSettings()">⚙️ Settings</button>
            <a href="/logout" class="btn btn-ghost">Logout</a>
        </div>
    </header>
    
    <main>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon blue">🖥️</div>
                <div class="stat-content">
                    <div class="value accent" id="total">0</div>
                    <div class="label">Total Devices</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon green">✅</div>
                <div class="stat-content">
                    <div class="value success" id="online">0</div>
                    <div class="label">Online Now</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon purple">📝</div>
                <div class="stat-content">
                    <div class="value" id="words">0</div>
                    <div class="label">Words Typed</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon pink">🎤</div>
                <div class="stat-content">
                    <div class="value" id="sessions">0</div>
                    <div class="label">Voice Sessions</div>
                </div>
            </div>
        </div>
        
        <div class="setup-card">
            <h3>🚀 Quick Setup</h3>
            <div class="setup-steps">
                <div class="step">
                    <div class="step-number">1</div>
                    <h4>Download Client</h4>
                    <p>Get the voice client for your computer</p>
                    <a href="/download" class="btn btn-primary" style="width:100%;justify-content:center;">📥 Download voice_client.py</a>
                </div>
                <div class="step">
                    <div class="step-number">2</div>
                    <h4>Install Dependencies</h4>
                    <p>Run this in your terminal:</p>
                    <code>pip install SpeechRecognition pyaudio pynput pyautogui pyperclip python-socketio</code>
                </div>
                <div class="step">
                    <div class="step-number">3</div>
                    <h4>Start Voice Client</h4>
                    <p>Run with your wake word:</p>
                    <code>python voice_client.py -w cortana -s {{ server }}</code>
                </div>
            </div>
        </div>
        
        <div class="section-header">
            <h2 class="section-title">🖥️ Connected Devices</h2>
        </div>
        
        <div class="clients-grid" id="clients-grid">
            <div class="empty-state">
                <div class="icon">📡</div>
                <h3>No devices connected</h3>
                <p>Follow the setup steps above to connect your first device</p>
            </div>
        </div>
    </main>
    
    <!-- Settings Modal -->
    <div class="modal-overlay" id="settings-modal">
        <div class="modal">
            <div class="modal-header">
                <h2>⚙️ Settings</h2>
                <button class="modal-close" onclick="closeSettings()">✕</button>
            </div>
            <div class="modal-body">
                <div class="setting-group">
                    <h3>Voice Recognition</h3>
                    <div class="setting-item">
                        <div class="setting-label">
                            <h4>Continuous Mode</h4>
                            <p>Keep listening after each dictation</p>
                        </div>
                        <div class="toggle" id="toggle-continuous" onclick="toggleSetting(this)"></div>
                    </div>
                    <div class="setting-item">
                        <div class="setting-label">
                            <h4>Sound Feedback</h4>
                            <p>Play sounds when listening starts/stops</p>
                        </div>
                        <div class="toggle active" id="toggle-sound" onclick="toggleSetting(this)"></div>
                    </div>
                    <div class="setting-item">
                        <div class="setting-label">
                            <h4>Auto Punctuation</h4>
                            <p>Automatically add periods and commas</p>
                        </div>
                        <div class="toggle active" id="toggle-punctuation" onclick="toggleSetting(this)"></div>
                    </div>
                </div>
                <div class="setting-group">
                    <h3>Language</h3>
                    <div class="setting-item">
                        <div class="setting-label">
                            <h4>Recognition Language</h4>
                            <p>Primary language for speech recognition</p>
                        </div>
                        <select id="language-select" onchange="updateLanguage(this.value)">
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
                </div>
                <div class="setting-group">
                    <h3>Appearance</h3>
                    <div class="setting-item">
                        <div class="setting-label">
                            <h4>Accent Color</h4>
                            <p>Choose your preferred accent color</p>
                        </div>
                        <div class="color-options">
                            <div class="color-option active" style="background: #00f5d4;" onclick="setAccent('#00f5d4', this)"></div>
                            <div class="color-option" style="background: #7b2cbf;" onclick="setAccent('#7b2cbf', this)"></div>
                            <div class="color-option" style="background: #f72585;" onclick="setAccent('#f72585', this)"></div>
                            <div class="color-option" style="background: #3b82f6;" onclick="setAccent('#3b82f6', this)"></div>
                            <div class="color-option" style="background: #10b981;" onclick="setAccent('#10b981', this)"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const socket = io();
        let clients = {};
        let settings = {
            continuous: false,
            sound: true,
            punctuation: true,
            language: 'en-US',
            accent: '#00f5d4'
        };
        
        // Socket events
        socket.on('connect', () => socket.emit('dashboard_join'));
        socket.on('clients_update', data => {
            clients = data.clients || {};
            renderClients();
            updateStats();
        });
        socket.on('client_activity', data => {
            if (clients[data.client_id]) {
                const c = clients[data.client_id];
                c.logs = c.logs || [];
                c.logs.unshift({
                    time: new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', second: '2-digit'}),
                    message: data.message,
                    type: data.type
                });
                c.logs = c.logs.slice(0, 15);
                if (data.words) c.words_typed = (c.words_typed || 0) + data.words;
                if (data.type === 'wake_word') c.sessions = (c.sessions || 0) + 1;
                renderClients();
                updateStats();
            }
        });
        
        function getIcon(wakeWord) {
            const icons = {
                cortana: '🤖', jarvis: '🦾', alexa: '🔵', 
                siri: '🍎', computer: '💻', hey: '👋'
            };
            return icons[(wakeWord || '').toLowerCase()] || '🎤';
        }
        
        function renderClients() {
            const grid = document.getElementById('clients-grid');
            const list = Object.values(clients);
            
            if (!list.length) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📡</div>
                        <h3>No devices connected</h3>
                        <p>Follow the setup steps above to connect your first device</p>
                    </div>
                `;
                return;
            }
            
            grid.innerHTML = list.map(c => `
                <div class="client-card ${c.online ? 'online' : ''}">
                    <div class="client-header">
                        <div class="client-identity">
                            <div class="client-avatar">${getIcon(c.wake_word)}</div>
                            <div class="client-info">
                                <h3>${c.name || c.wake_word}</h3>
                                <span class="wake-word">"${c.wake_word}"</span>
                            </div>
                        </div>
                        <div class="status-badge">
                            <span class="status-dot ${c.online ? 'online' : ''}"></span>
                            ${c.online ? 'Online' : 'Offline'}
                        </div>
                    </div>
                    <div class="client-body">
                        <div class="client-stats">
                            <div class="mini-stat">
                                <div class="value">${c.words_typed || 0}</div>
                                <div class="label">Words</div>
                            </div>
                            <div class="mini-stat">
                                <div class="value">${c.sessions || 0}</div>
                                <div class="label">Sessions</div>
                            </div>
                            <div class="mini-stat">
                                <div class="value">${(c.language || 'en').slice(0, 2).toUpperCase()}</div>
                                <div class="label">Lang</div>
                            </div>
                        </div>
                        <div class="activity-log">
                            <h4>Recent Activity</h4>
                            ${(c.logs || []).map(l => `
                                <div class="log-entry">
                                    <span class="log-time">${l.time}</span>
                                    <span class="log-message ${l.type}">${l.message}</span>
                                </div>
                            `).join('') || '<div class="log-entry"><span class="log-message">Waiting for activity...</span></div>'}
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        function updateStats() {
            const list = Object.values(clients);
            document.getElementById('total').textContent = list.length;
            document.getElementById('online').textContent = list.filter(c => c.online).length;
            document.getElementById('words').textContent = list.reduce((s, c) => s + (c.words_typed || 0), 0);
            document.getElementById('sessions').textContent = list.reduce((s, c) => s + (c.sessions || 0), 0);
        }
        
        // Settings
        function openSettings() {
            document.getElementById('settings-modal').classList.add('active');
        }
        
        function closeSettings() {
            document.getElementById('settings-modal').classList.remove('active');
        }
        
        function toggleSetting(el) {
            el.classList.toggle('active');
            const id = el.id.replace('toggle-', '');
            settings[id] = el.classList.contains('active');
            socket.emit('update_settings', settings);
        }
        
        function updateLanguage(lang) {
            settings.language = lang;
            socket.emit('update_settings', settings);
        }
        
        function setAccent(color, el) {
            document.querySelectorAll('.color-option').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.documentElement.style.setProperty('--accent', color);
            settings.accent = color;
        }
        
        // Close modal on overlay click
        document.getElementById('settings-modal').addEventListener('click', e => {
            if (e.target.id === 'settings-modal') closeSettings();
        });
        
        // Close modal on Escape
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') closeSettings();
        });
    </script>
</body>
</html>
'''

# ============================================================================
# IMPROVED VOICE CLIENT SCRIPT
# ============================================================================

VOICE_CLIENT = r'''#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       🎤 VOICE HUB - CLIENT v2.0                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Features:                                                                    ║
║  • Wake word activation OR continuous mode                                    ║
║  • Hotkey support (Ctrl+Shift+V to toggle)                                   ║
║  • Auto-punctuation                                                           ║
║  • Multi-language support                                                     ║
║  • Audio feedback                                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
  python voice_client.py --wake-word cortana --server https://your-app.railway.app
  python voice_client.py --continuous --server https://your-app.railway.app
  python voice_client.py --hotkey --server https://your-app.railway.app
"""

import argparse
import sys
import time
import threading
import re

try:
    import speech_recognition as sr
    from pynput import keyboard
    from pynput.keyboard import Controller as KeyboardController, Key
    import pyautogui
    import pyperclip
    import socketio
except ImportError as e:
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ Missing Dependencies                                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Run this command to install:                                                 ║
║  pip install SpeechRecognition pyaudio pynput pyautogui pyperclip            ║
║             python-socketio                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    sys.exit(1)

PLATFORM = __import__('platform').system()

# Punctuation patterns for auto-formatting
PUNCTUATION_MAP = {
    r'\bperiod\b': '.', r'\bcomma\b': ',', r'\bquestion mark\b': '?',
    r'\bexclamation mark\b': '!', r'\bexclamation point\b': '!',
    r'\bcolon\b': ':', r'\bsemicolon\b': ';', r'\bhyphen\b': '-',
    r'\bdash\b': '—', r'\bquote\b': '"', r'\bopen quote\b': '"',
    r'\bclose quote\b': '"', r'\bapostrophe\b': "'", r'\bat sign\b': '@',
    r'\bhashtag\b': '#', r'\bdollar sign\b': '$', r'\bpercent\b': '%',
    r'\bampersand\b': '&', r'\basterisk\b': '*', r'\bplus sign\b': '+',
    r'\bequals\b': '=', r'\bslash\b': '/', r'\bbackslash\b': '\\',
    r'\bnew line\b': '\n', r'\bnewline\b': '\n', r'\bnew paragraph\b': '\n\n',
    r'\btab\b': '\t', r'\bopen paren\b': '(', r'\bclose paren\b': ')',
    r'\bopen bracket\b': '[', r'\bclose bracket\b': ']',
    r'\bopen brace\b': '{', r'\bclose brace\b': '}',
}

class VoiceClient:
    def __init__(self, args):
        self.wake_word = args.wake_word.lower() if args.wake_word else None
        self.server = args.server
        self.language = args.language
        self.continuous = args.continuous
        self.hotkey_mode = args.hotkey
        self.sound_feedback = not args.no_sound
        self.auto_punctuation = not args.no_punctuation
        self.sensitivity = args.sensitivity
        
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.running = False
        self.listening = False
        self.hotkey_active = False
        
        # Configure recognizer
        self.recognizer.energy_threshold = 300 * self.sensitivity
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        
        # Socket.IO client
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=0)
        self._setup_socket_events()
        
    def _setup_socket_events(self):
        @self.sio.event
        def connect():
            self._print_status("Connected to server!", "success")
            mode = "continuous" if self.continuous else ("hotkey" if self.hotkey_mode else f'wake word "{self.wake_word}"')
            self.sio.emit('client_register', {
                'wake_word': self.wake_word or 'hotkey',
                'language': self.language,
                'name': f"{(self.wake_word or 'Voice').title()} Client",
                'mode': mode
            })
            
        @self.sio.event
        def disconnect():
            self._print_status("Disconnected from server", "warning")
            
        @self.sio.on('settings_update')
        def on_settings(data):
            if 'language' in data:
                self.language = data['language']
                self._print_status(f"Language changed to {self.language}", "info")
            if 'continuous' in data:
                self.continuous = data['continuous']
            if 'sound' in data:
                self.sound_feedback = data['sound']
            if 'punctuation' in data:
                self.auto_punctuation = data['punctuation']
                
    def _print_status(self, message, status_type="info"):
        icons = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️", "listen": "🎙️"}
        icon = icons.get(status_type, "•")
        timestamp = time.strftime("%H:%M:%S")
        print(f"  {icon} [{timestamp}] {message}")
        
    def _play_sound(self, sound_type="start"):
        if not self.sound_feedback:
            return
        try:
            if PLATFORM == "Darwin":
                import subprocess
                sounds = {
                    "start": "/System/Library/Sounds/Pop.aiff",
                    "stop": "/System/Library/Sounds/Bottle.aiff",
                    "error": "/System/Library/Sounds/Basso.aiff"
                }
                subprocess.run(["afplay", sounds.get(sound_type, sounds["start"])], 
                             capture_output=True, timeout=1)
            elif PLATFORM == "Windows":
                import winsound
                freqs = {"start": 800, "stop": 600, "error": 400}
                winsound.Beep(freqs.get(sound_type, 800), 150)
        except:
            pass
            
    def _send_activity(self, message, activity_type="info", words=0):
        try:
            self.sio.emit('client_activity', {
                'message': message,
                'type': activity_type,
                'words': words
            })
        except:
            pass
            
    def _apply_punctuation(self, text):
        if not self.auto_punctuation:
            return text
        for pattern, replacement in PUNCTUATION_MAP.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        # Capitalize after sentence endings
        text = re.sub(r'([.!?]\s*)(\w)', lambda m: m.group(1) + m.group(2).upper(), text)
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        return text
        
    def _type_text(self, text):
        """Type text using clipboard for speed and reliability"""
        try:
            pyperclip.copy(text)
            time.sleep(0.02)
            if PLATFORM == "Darwin":
                pyautogui.hotkey('command', 'v')
            else:
                pyautogui.hotkey('ctrl', 'v')
            return True
        except Exception as e:
            self._print_status(f"Failed to type: {e}", "error")
            return False
            
    def init_audio(self):
        """Initialize microphone"""
        try:
            mics = sr.Microphone.list_microphone_names()
            self._print_status(f"Found {len(mics)} microphones", "info")
            
            # Try to find preferred microphones
            preferred = ["airpod", "bluetooth", "wireless", "usb", "external"]
            selected_index = None
            
            for i, mic_name in enumerate(mics):
                mic_lower = mic_name.lower()
                if any(p in mic_lower for p in preferred):
                    selected_index = i
                    break
                    
            if selected_index is not None:
                self.microphone = sr.Microphone(device_index=selected_index)
                self._print_status(f"Using: {mics[selected_index]}", "success")
            else:
                self.microphone = sr.Microphone()
                self._print_status("Using default microphone", "info")
                
            # Calibrate
            self._print_status("Calibrating for ambient noise...", "info")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
            self._print_status("Audio ready!", "success")
            return True
            
        except Exception as e:
            self._print_status(f"Audio initialization failed: {e}", "error")
            return False
            
    def connect_server(self):
        """Connect to the Voice Hub server"""
        try:
            self._print_status(f"Connecting to {self.server}...", "info")
            self.sio.connect(self.server)
            return True
        except Exception as e:
            self._print_status(f"Connection failed: {e}", "error")
            return False
            
    def listen_for_wake_word(self):
        """Listen for wake word"""
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=3)
            text = self.recognizer.recognize_google(audio, language=self.language)
            if self.wake_word and self.wake_word in text.lower():
                self._print_status(f'Wake word detected: "{text}"', "success")
                return True
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            if "connection" in str(e).lower():
                self._print_status("Network error, retrying...", "warning")
                time.sleep(1)
        return False
        
    def capture_dictation(self):
        """Capture and transcribe speech"""
        self._play_sound("start")
        self._print_status("Listening...", "listen")
        self.listening = True
        
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source, 
                    timeout=8 if self.continuous else 5,
                    phrase_time_limit=30
                )
                
            self._print_status("Processing...", "info")
            text = self.recognizer.recognize_google(audio, language=self.language)
            
            # Check for stop commands
            if text.lower().strip() in ["stop", "quit", "exit", "stop listening"]:
                self._print_status("Stop command received", "info")
                self.running = False
                return None
                
            # Apply punctuation
            text = self._apply_punctuation(text)
            
            # Type the text
            if self._type_text(text):
                word_count = len(text.split())
                preview = text[:50] + "..." if len(text) > 50 else text
                self._print_status(f'Typed: "{preview}"', "success")
                self._send_activity(
                    f'Typed: "{preview}"',
                    "success",
                    word_count
                )
                self._play_sound("stop")
                return text
                
        except sr.WaitTimeoutError:
            self._print_status("No speech detected", "warning")
            self._play_sound("error")
        except sr.UnknownValueError:
            self._print_status("Couldn't understand audio", "warning")
            self._play_sound("error")
        except Exception as e:
            self._print_status(f"Error: {e}", "error")
            self._play_sound("error")
        finally:
            self.listening = False
            
        return None
        
    def _hotkey_listener(self):
        """Listen for hotkey (Ctrl+Shift+V)"""
        current_keys = set()
        
        def on_press(key):
            current_keys.add(key)
            # Check for Ctrl+Shift+V
            if (keyboard.Key.ctrl_l in current_keys or keyboard.Key.ctrl_r in current_keys) and \
               (keyboard.Key.shift_l in current_keys or keyboard.Key.shift_r in current_keys):
                try:
                    if hasattr(key, 'char') and key.char and key.char.lower() == 'v':
                        if not self.listening:
                            self.hotkey_active = True
                except:
                    pass
                    
        def on_release(key):
            try:
                current_keys.discard(key)
            except:
                pass
                
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        return listener
        
    def run(self):
        """Main run loop"""
        print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       🎤 VOICE HUB CLIENT v2.0                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Mode: {"Continuous" if self.continuous else ("Hotkey (Ctrl+Shift+V)" if self.hotkey_mode else f'Wake Word "{self.wake_word}"'):50} ║
║  Language: {self.language:56} ║
║  Server: {self.server[:55]:55} ║
╚═══════════════════════════════════════════════════════════════════════════════╝
        """)
        
        if not self.init_audio():
            return
            
        self.connect_server()
        self.running = True
        
        # Start hotkey listener if in hotkey mode
        hotkey_listener = None
        if self.hotkey_mode:
            hotkey_listener = self._hotkey_listener()
            self._print_status("Press Ctrl+Shift+V to start dictation", "info")
            
        print()
        
        try:
            while self.running:
                if self.continuous:
                    # Continuous mode - always listening
                    self._print_status("Listening continuously (say 'stop' to exit)...", "listen")
                    self._send_activity("Continuous listening active", "wake_word")
                    self.capture_dictation()
                    time.sleep(0.5)
                    
                elif self.hotkey_mode:
                    # Hotkey mode
                    if self.hotkey_active:
                        self._send_activity("Hotkey activated", "wake_word")
                        self.capture_dictation()
                        self.hotkey_active = False
                    time.sleep(0.1)
                    
                else:
                    # Wake word mode
                    if self.listen_for_wake_word():
                        self._send_activity("Wake word detected!", "wake_word")
                        self.capture_dictation()
                        print()
                        self._print_status(f'Say "{self.wake_word}" to continue...', "info")
                        
        except KeyboardInterrupt:
            print()
            self._print_status("Shutting down...", "info")
        finally:
            self.running = False
            if hotkey_listener:
                hotkey_listener.stop()
            try:
                self.sio.disconnect()
            except:
                pass
            self._print_status("Goodbye! 👋", "success")


def main():
    parser = argparse.ArgumentParser(
        description="Voice Hub Client - Voice-to-text for your devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --wake-word cortana --server https://myapp.railway.app
  %(prog)s --continuous --server https://myapp.railway.app
  %(prog)s --hotkey --server https://myapp.railway.app
  %(prog)s --list-mics
        """
    )
    
    parser.add_argument('--wake-word', '-w', 
                        help='Wake word to trigger dictation (e.g., "cortana", "jarvis")')
    parser.add_argument('--server', '-s', default='http://localhost:5000',
                        help='Voice Hub server URL')
    parser.add_argument('--language', '-l', default='en-US',
                        help='Recognition language (e.g., en-US, es-ES, fr-FR)')
    parser.add_argument('--continuous', '-c', action='store_true',
                        help='Continuous listening mode (no wake word needed)')
    parser.add_argument('--hotkey', '-k', action='store_true',
                        help='Hotkey mode (Ctrl+Shift+V to toggle)')
    parser.add_argument('--no-sound', action='store_true',
                        help='Disable sound feedback')
    parser.add_argument('--no-punctuation', action='store_true',
                        help='Disable auto-punctuation')
    parser.add_argument('--sensitivity', type=float, default=1.0,
                        help='Microphone sensitivity multiplier (default: 1.0)')
    parser.add_argument('--list-mics', action='store_true',
                        help='List available microphones and exit')
    
    args = parser.parse_args()
    
    if args.list_mics:
        print("\n📢 Available Microphones:\n")
        for i, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"  [{i}] {name}")
        print()
        return
        
    # Validate mode
    if not args.wake_word and not args.continuous and not args.hotkey:
        print("❌ Please specify a mode: --wake-word, --continuous, or --hotkey")
        parser.print_help()
        return
        
    # Ensure server URL has protocol
    if not args.server.startswith('http'):
        args.server = f'http://{args.server}'
        
    client = VoiceClient(args)
    client.run()


if __name__ == '__main__':
    main()
'''

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_PAGE, user=current_user, server=request.host_url.rstrip('/'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username', '').strip(), request.form.get('password', '')
        if u in USERS and check_password_hash(USERS[u]['password_hash'], p):
            login_user(User(u))
            return redirect(url_for('dashboard'))
        return render_template_string(LOGIN_PAGE, error='Invalid credentials')
    return render_template_string(LOGIN_PAGE, error=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/download')
def download():
    return Response(VOICE_CLIENT, mimetype='text/plain', 
                   headers={'Content-Disposition': 'attachment; filename=voice_client.py'})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'clients': len(connected_clients)})

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    if request.method == 'POST':
        data = request.json
        # Broadcast settings to all clients
        socketio.emit('settings_update', data, room='clients')
        return jsonify({'status': 'ok'})
    return jsonify(default_settings)

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('dashboard_join')
def on_dashboard_join():
    join_room('dashboard')
    emit('clients_update', {'clients': connected_clients})

@socketio.on('client_register')
def on_client_register(data):
    cid = request.sid
    join_room('clients')
    connected_clients[cid] = {
        'id': cid,
        'wake_word': data.get('wake_word', '?'),
        'name': data.get('name', 'Client'),
        'language': data.get('language', 'en-US'),
        'mode': data.get('mode', 'wake_word'),
        'online': True,
        'words_typed': 0,
        'sessions': 0,
        'logs': [{
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': 'Connected',
            'type': 'success'
        }]
    }
    socketio.emit('clients_update', {'clients': connected_clients}, room='dashboard')
    print(f"✅ Client connected: {data.get('wake_word')} ({data.get('mode', 'wake_word')} mode)")

@socketio.on('client_activity')
def on_activity(data):
    cid = request.sid
    if cid in connected_clients:
        socketio.emit('client_activity', {'client_id': cid, **data}, room='dashboard')

@socketio.on('update_settings')
def on_update_settings(data):
    socketio.emit('settings_update', data, room='clients')

@socketio.on('disconnect')
def on_disconnect():
    cid = request.sid
    if cid in connected_clients:
        connected_clients[cid]['online'] = False
        socketio.emit('clients_update', {'clients': connected_clients}, room='dashboard')
        print(f"📴 Client disconnected: {connected_clients[cid]['wake_word']}")

# ============================================================================
# START SERVER
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       🎛️  VOICE HUB SERVER v2.0  🎛️                          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  URL: http://localhost:{port:<52} ║
║  Login: admin / {ADMIN_PASSWORD:<51} ║
║                                                                               ║
║  Features:                                                                    ║
║  • Modern dashboard with real-time updates                                    ║
║  • Customizable settings (language, colors, modes)                            ║
║  • Multiple client modes (wake word, continuous, hotkey)                      ║
║  • Auto-punctuation and smart formatting                                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host='0.0.0.0', port=port)
