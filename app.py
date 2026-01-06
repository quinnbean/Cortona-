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

# Use gevent for Python 3.13 compatibility
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Password from environment variable or default
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'voicehub123')
USERS = {'admin': {'password_hash': generate_password_hash(ADMIN_PASSWORD), 'name': 'Admin'}}

# Store connected voice clients
connected_clients = {}

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
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Syne',sans-serif;background:#0a0a0f;min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}
        .card{background:#1a1a24;border:1px solid #2a2a3a;border-radius:24px;padding:48px;width:100%;max-width:400px}
        .logo{text-align:center;margin-bottom:32px}
        .logo-icon{width:64px;height:64px;background:linear-gradient(135deg,#00f5d4,#7b2cbf);border-radius:16px;display:inline-flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:16px}
        h1{font-size:28px}
        h1 span{background:linear-gradient(135deg,#00f5d4,#f72585);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .form-group{margin-bottom:20px}
        label{display:block;font-size:14px;color:#a0a0b0;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
        input{width:100%;background:#12121a;border:1px solid #2a2a3a;border-radius:12px;padding:16px;font-size:16px;color:#fff}
        input:focus{outline:none;border-color:#00f5d4}
        .btn{width:100%;background:linear-gradient(135deg,#00f5d4,#7b2cbf);color:#0a0a0f;border:none;border-radius:12px;padding:16px;font-size:16px;font-weight:700;cursor:pointer;margin-top:12px}
        .btn:hover{opacity:0.9}
        .error{background:rgba(247,37,133,0.1);border:1px solid rgba(247,37,133,0.3);color:#f72585;padding:12px;border-radius:10px;margin-bottom:20px;font-size:14px}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">
            <div class="logo-icon">🎛️</div>
            <h1><span>Voice Hub</span></h1>
        </div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <div class="form-group"><label>Username</label><input type="text" name="username" required autofocus></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>
'''

# ============================================================================
# DASHBOARD PAGE
# ============================================================================

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Hub Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono&family=Syne:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        :root{--bg:#0a0a0f;--card:#1a1a24;--border:#2a2a3a;--cyan:#00f5d4;--magenta:#f72585;--green:#06d6a0;--text:#fff;--muted:#606070}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Syne',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
        header{padding:20px 30px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px}
        .logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700}
        .logo span{color:var(--cyan)}
        .logo-icon{width:36px;height:36px;background:linear-gradient(135deg,var(--cyan),#7b2cbf);border-radius:8px;display:flex;align-items:center;justify-content:center}
        .btn{padding:10px 20px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;border:none;text-decoration:none;font-family:'Syne',sans-serif;background:var(--card);color:var(--text);border:1px solid var(--border)}
        .btn:hover{border-color:var(--cyan)}
        main{max-width:1200px;margin:0 auto;padding:30px}
        .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:30px}
        .stat{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;display:flex;align-items:center;gap:12px}
        .stat .icon{font-size:28px}
        .stat .value{font-size:24px;font-weight:700}
        .stat .value.green{color:var(--green)}
        .stat .label{font-size:11px;color:var(--muted);text-transform:uppercase}
        .connect-box{background:linear-gradient(135deg,rgba(0,245,212,0.1),rgba(123,44,191,0.1));border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:30px}
        .connect-box h3{margin-bottom:12px;font-size:18px}
        .connect-box p{color:#a0a0b0;font-size:14px;margin-bottom:10px}
        .connect-box code{display:block;background:var(--bg);padding:14px;border-radius:8px;font-family:'Space Mono',monospace;font-size:12px;color:var(--cyan);word-break:break-all;margin:10px 0}
        .connect-box a{color:var(--cyan)}
        h2{font-size:20px;margin-bottom:20px}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}
        .client{background:var(--card);border:2px solid var(--border);border-radius:16px;overflow:hidden;transition:0.3s}
        .client.online{border-color:var(--green)}
        .client-header{padding:16px;background:#12121a;display:flex;justify-content:space-between;align-items:center}
        .client.online .client-header{background:linear-gradient(135deg,rgba(6,214,160,0.15),transparent)}
        .client-id{display:flex;align-items:center;gap:12px}
        .avatar{width:44px;height:44px;background:var(--card);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px}
        .client-id h3{font-size:16px}
        .wake{font-family:'Space Mono',monospace;font-size:12px;color:var(--cyan);background:rgba(0,0,0,0.3);padding:2px 8px;border-radius:4px}
        .status{display:flex;align-items:center;gap:6px;padding:5px 12px;background:rgba(0,0,0,0.3);border-radius:50px;font-size:12px}
        .dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}
        .dot.on{background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2s infinite}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
        .client-body{padding:16px}
        .mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}
        .mini{background:#12121a;border-radius:8px;padding:10px;text-align:center}
        .mini .val{font-size:18px;font-weight:700;color:var(--cyan)}
        .mini .lbl{font-size:10px;color:var(--muted);text-transform:uppercase}
        .log{background:#12121a;border-radius:8px;padding:10px;max-height:100px;overflow-y:auto;font-size:12px}
        .log-entry{padding:4px 0;border-bottom:1px solid var(--border);display:flex;gap:8px}
        .log-entry:last-child{border:none}
        .log-time{font-family:'Space Mono',monospace;color:var(--muted)}
        .log-msg{color:#a0a0b0}
        .log-msg.success{color:var(--green)}
        .log-msg.error{color:var(--magenta)}
        .empty{grid-column:1/-1;text-align:center;padding:50px;color:var(--muted)}
        .empty .icon{font-size:40px;margin-bottom:12px}
        @media(max-width:600px){header{padding:16px}main{padding:16px}.grid{grid-template-columns:1fr}}
    </style>
</head>
<body>
    <header>
        <div class="logo"><div class="logo-icon">🎛️</div><span>Voice</span> Hub</div>
        <div><span style="color:var(--muted);margin-right:16px">👤 {{ user.name }}</span><a href="/logout" class="btn">Logout</a></div>
    </header>
    <main>
        <div class="stats">
            <div class="stat"><div class="icon">🖥️</div><div><div class="value" id="total">0</div><div class="label">Computers</div></div></div>
            <div class="stat"><div class="icon">✅</div><div><div class="value green" id="online">0</div><div class="label">Online</div></div></div>
            <div class="stat"><div class="icon">📝</div><div><div class="value" id="words">0</div><div class="label">Words</div></div></div>
            <div class="stat"><div class="icon">🎤</div><div><div class="value" id="sessions">0</div><div class="label">Sessions</div></div></div>
        </div>
        <div class="connect-box">
            <h3>🔗 Connect Your Computers</h3>
            <p><strong>Step 1:</strong> Download the voice client: <a href="/download">📥 voice_client.py</a></p>
            <p><strong>Step 2:</strong> Install dependencies on your computer:</p>
            <code>pip install SpeechRecognition pyaudio pynput pyautogui pyperclip python-socketio</code>
            <p><strong>Step 3:</strong> Run this command (change "cortana" to "jarvis" for 2nd computer):</p>
            <code>python voice_client.py --wake-word cortana --server {{ server }}</code>
        </div>
        <h2>🖥️ Connected Computers</h2>
        <div class="grid" id="grid"><div class="empty"><div class="icon">📡</div><h3>No computers connected</h3><p>Run the voice client on your computers</p></div></div>
    </main>
    <script>
        const socket=io();let clients={};
        socket.on('connect',()=>socket.emit('dashboard_join'));
        socket.on('clients_update',d=>{clients=d.clients||{};render();stats()});
        socket.on('client_activity',d=>{if(clients[d.client_id]){const c=clients[d.client_id];c.logs=c.logs||[];c.logs.unshift({time:new Date().toLocaleTimeString(),message:d.message,type:d.type});c.logs=c.logs.slice(0,10);if(d.words)c.words_typed=(c.words_typed||0)+d.words;if(d.type==='wake_word')c.sessions=(c.sessions||0)+1;render();stats()}});
        function render(){const g=document.getElementById('grid'),list=Object.values(clients);if(!list.length){g.innerHTML='<div class="empty"><div class="icon">📡</div><h3>No computers connected</h3><p>Run the voice client</p></div>';return}g.innerHTML=list.map(c=>`<div class="client ${c.online?'online':''}"><div class="client-header"><div class="client-id"><div class="avatar">${icon(c.wake_word)}</div><div><h3>${c.name||c.wake_word}</h3><span class="wake">"${c.wake_word}"</span></div></div><div class="status"><span class="dot ${c.online?'on':''}"></span>${c.online?'Online':'Offline'}</div></div><div class="client-body"><div class="mini-stats"><div class="mini"><div class="val">${c.words_typed||0}</div><div class="lbl">Words</div></div><div class="mini"><div class="val">${c.sessions||0}</div><div class="lbl">Sessions</div></div><div class="mini"><div class="val">${(c.language||'en').slice(0,2)}</div><div class="lbl">Lang</div></div></div><div class="log">${(c.logs||[]).map(l=>`<div class="log-entry"><span class="log-time">${l.time}</span><span class="log-msg ${l.type}">${l.message}</span></div>`).join('')||'<div class="log-entry"><span class="log-msg">Waiting...</span></div>'}</div></div></div>`).join('')}
        function stats(){const l=Object.values(clients);document.getElementById('total').textContent=l.length;document.getElementById('online').textContent=l.filter(c=>c.online).length;document.getElementById('words').textContent=l.reduce((s,c)=>s+(c.words_typed||0),0);document.getElementById('sessions').textContent=l.reduce((s,c)=>s+(c.sessions||0),0)}
        function icon(w){return{cortana:'🤖',jarvis:'🦾',alexa:'🔵',siri:'🍎',computer:'💻'}[(w||'').toLowerCase()]||'🎤'}
    </script>
</body>
</html>
'''

# ============================================================================
# VOICE CLIENT SCRIPT (downloadable)
# ============================================================================

VOICE_CLIENT = r'''#!/usr/bin/env python3
"""
Voice Client - Run this on each computer you want to control
Usage: python voice_client.py --wake-word cortana --server https://your-app.railway.app
"""
import argparse,sys,time
try:
    import speech_recognition as sr
    from pynput.keyboard import Controller
    import pyautogui,pyperclip,socketio
except ImportError as e:
    print(f"Missing: {e}\nRun: pip install SpeechRecognition pyaudio pynput pyautogui pyperclip python-socketio")
    sys.exit(1)

PLATFORM=__import__('platform').system()

class Client:
    def __init__(s,wake,server,lang="en-US"):
        s.wake,s.server,s.lang=wake.lower(),server,lang
        s.rec=sr.Recognizer();s.mic=None;s.running=False;s.sio=socketio.Client()
        s.rec.energy_threshold=300;s.rec.dynamic_energy_threshold=True
        @s.sio.event
        def connect():print(f"🔗 Connected!");s.sio.emit('client_register',{'wake_word':s.wake,'language':s.lang,'name':f"{s.wake.title()} PC"})
        @s.sio.event
        def disconnect():print("📴 Disconnected")
    
    def connect(s):
        try:print(f"🔌 Connecting to {s.server}...");s.sio.connect(s.server);return True
        except Exception as e:print(f"⚠️ {e}");return False
    
    def send(s,msg,t="info",w=0):
        try:s.sio.emit('client_activity',{'message':msg,'type':t,'words':w})
        except:pass
    
    def init_audio(s):
        try:
            mics=sr.Microphone.list_microphone_names()
            print("\n📢 Microphones:")
            for i,m in enumerate(mics):print(f"  [{i}] {m}")
            for i,m in enumerate(mics):
                if any(k in m.lower() for k in["airpod","bluetooth","wireless"]):
                    s.mic=sr.Microphone(device_index=i);print(f"\n🎧 Using: {m}");break
            else:s.mic=sr.Microphone();print("\n🎤 Default mic")
            print("🔊 Calibrating...");
            with s.mic as src:s.rec.adjust_for_ambient_noise(src,duration=2)
            print("✅ Ready!");return True
        except Exception as e:print(f"❌ {e}");return False
    
    def listen_wake(s):
        try:
            with s.mic as src:audio=s.rec.listen(src,timeout=None,phrase_time_limit=3)
            text=s.rec.recognize_google(audio,language=s.lang)
            if s.wake in text.lower():print(f"✨ Wake word! ('{text}')");return True
        except:pass
        return False
    
    def capture(s):
        try:
            if PLATFORM=="Darwin":__import__('subprocess').run(["afplay","/System/Library/Sounds/Pop.aiff"],capture_output=True,timeout=1)
            elif PLATFORM=="Windows":__import__('winsound').Beep(800,200)
        except:pass
        try:
            with s.mic as src:print("🎙️ Listening...");audio=s.rec.listen(src,timeout=5,phrase_time_limit=15)
            text=s.rec.recognize_google(audio,language=s.lang);print(f"📝 Got: '{text}'")
            if text.lower() in["stop","quit","exit"]:s.running=False;return None
            for k,v in{"new line":"\n","period":".","comma":",","question mark":"?","exclamation mark":"!","colon":":","quote":'"',"at sign":"@","hashtag":"#"}.items():text=text.replace(k,v).replace(k.title(),v)
            pyperclip.copy(text);time.sleep(0.05)
            pyautogui.hotkey('command'if PLATFORM=="Darwin"else'ctrl','v')
            print("✅ Typed!");return text
        except Exception as e:print(f"❌ {e}");return None
    
    def run(s):
        print(f"\n{'='*50}\n  🎤 VOICE CLIENT - \"{s.wake.upper()}\"\n{'='*50}")
        if not s.init_audio():return
        s.connect();s.running=True
        print(f"\n👂 Say '{s.wake}' to dictate...\n")
        try:
            while s.running:
                if s.listen_wake():
                    s.send("Wake word!","wake_word")
                    text=s.capture()
                    if text:s.send(f'Typed: "{text[:30]}..."'if len(text)>30 else f'Typed: "{text}"',"success",len(text.split()))
                    print(f"\n👂 Say '{s.wake}'...")
        except KeyboardInterrupt:print("\n👋 Bye!")
        finally:
            try:s.sio.disconnect()
            except:pass

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--wake-word','-w',default='cortana')
    p.add_argument('--server','-s',default='http://localhost:5000')
    p.add_argument('--language','-l',default='en-US')
    p.add_argument('--list-mics',action='store_true')
    a=p.parse_args()
    if a.list_mics:[print(f"[{i}] {m}")for i,m in enumerate(sr.Microphone.list_microphone_names())];sys.exit()
    Client(a.wake_word,a.server if a.server.startswith('http')else f'http://{a.server}',a.language).run()
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
    return Response(VOICE_CLIENT, mimetype='text/plain', headers={'Content-Disposition': 'attachment; filename=voice_client.py'})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'clients': len(connected_clients)})

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
    connected_clients[cid] = {
        'id': cid, 'wake_word': data.get('wake_word', '?'), 'name': data.get('name', 'Client'),
        'language': data.get('language', 'en-US'), 'online': True, 'words_typed': 0, 'sessions': 0,
        'logs': [{'time': datetime.now().strftime('%H:%M:%S'), 'message': 'Connected', 'type': 'success'}]
    }
    socketio.emit('clients_update', {'clients': connected_clients}, room='dashboard')
    print(f"✅ {data.get('wake_word')} connected")

@socketio.on('client_activity')
def on_activity(data):
    cid = request.sid
    if cid in connected_clients:
        socketio.emit('client_activity', {'client_id': cid, **data}, room='dashboard')

@socketio.on('disconnect')
def on_disconnect():
    cid = request.sid
    if cid in connected_clients:
        connected_clients[cid]['online'] = False
        socketio.emit('clients_update', {'clients': connected_clients}, room='dashboard')
        print(f"📴 {connected_clients[cid]['wake_word']} disconnected")

# ============================================================================
# START SERVER
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║              🎛️  VOICE HUB SERVER RUNNING  🎛️                ║
╠═══════════════════════════════════════════════════════════════╣
║  URL: http://localhost:{port}                                  ║
║  Login: admin / {ADMIN_PASSWORD}                              ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host='0.0.0.0', port=port)

