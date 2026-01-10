const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, Notification, ipcMain, shell, session, systemPreferences, clipboard } = require('electron');
const path = require('path');
const { exec, execSync } = require('child_process');
const Store = require('electron-store');
const AutoLaunch = require('auto-launch');

// ============================================================================
// CONFIGURATION
// ============================================================================

const RENDER_URL = 'https://cortona.onrender.com';
const DEV_URL = 'http://localhost:5050';
const IS_DEV = process.env.NODE_ENV === 'development';

// Persistent settings
const store = new Store({
  defaults: {
    autoLaunch: true,
    globalShortcut: 'CommandOrControl+Shift+J',
    alwaysOnTop: false,
    startMinimized: false,
    showInDock: true
  }
});

// Auto-launch setup
const autoLauncher = new AutoLaunch({
  name: 'Cortona',
  mac: {
    useLaunchAgent: true
  }
});

// ============================================================================
// APP STATE
// ============================================================================

let mainWindow = null;
let tray = null;
let isQuitting = false;
let whisperProcess = null;

// ============================================================================
// WHISPER SERVICE MANAGEMENT
// ============================================================================

function startWhisperService() {
  const whisperPath = path.join(__dirname, '..', 'whisper-service', 'whisper_server.py');
  
  console.log('[WHISPER] Starting local Whisper service...');
  console.log('[WHISPER] Path:', whisperPath);
  
  // Check if whisper_server.py exists
  const fs = require('fs');
  if (!fs.existsSync(whisperPath)) {
    console.error('[WHISPER] whisper_server.py not found at:', whisperPath);
    return;
  }
  
  // Start the Whisper service
  const { spawn } = require('child_process');
  whisperProcess = spawn('python3', [whisperPath], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false
  });
  
  whisperProcess.stdout.on('data', (data) => {
    console.log('[WHISPER]', data.toString().trim());
  });
  
  whisperProcess.stderr.on('data', (data) => {
    console.error('[WHISPER ERROR]', data.toString().trim());
  });
  
  whisperProcess.on('close', (code) => {
    console.log('[WHISPER] Service exited with code:', code);
    whisperProcess = null;
  });
  
  whisperProcess.on('error', (err) => {
    console.error('[WHISPER] Failed to start service:', err);
    whisperProcess = null;
  });
}

function stopWhisperService() {
  if (whisperProcess) {
    console.log('[WHISPER] Stopping service...');
    whisperProcess.kill();
    whisperProcess = null;
  }
}

// ============================================================================
// WINDOW MANAGEMENT
// ============================================================================

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
    vibrancy: 'under-window',
    visualEffectState: 'active',
    backgroundColor: '#0a0a0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false, // Required for Speech Recognition API to reach Google servers
      allowRunningInsecureContent: false,
      webviewTag: false
    },
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png')
  });
  
  // Set user agent to standard Chrome (helps with Speech API compatibility)
  mainWindow.webContents.setUserAgent(
    mainWindow.webContents.getUserAgent().replace(/Electron\/\S+\s/, '')
  );

  // Load the app
  const appUrl = IS_DEV ? DEV_URL : RENDER_URL;
  mainWindow.loadURL(appUrl);

  // Show when ready
  mainWindow.once('ready-to-show', () => {
    if (!store.get('startMinimized')) {
      mainWindow.show();
    }
    
    // Open DevTools in development mode
    if (IS_DEV) {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
  });

  // Handle close - minimize to tray instead
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      
      // Show notification first time
      if (!store.get('hiddenNotificationShown')) {
        showNotification('Cortona is still running', 'Click the menubar icon or press ⌘+Shift+J to open');
        store.set('hiddenNotificationShown', true);
      }
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle dock visibility
  if (!store.get('showInDock')) {
    app.dock?.hide();
  }

  return mainWindow;
}

// ============================================================================
// TRAY (MENUBAR)
// ============================================================================

function createTray() {
  // Create tray icon (template image for macOS dark/light mode)
  const iconPath = path.join(__dirname, 'assets', 'trayTemplate.png');
  let trayIcon;
  
  try {
    trayIcon = nativeImage.createFromPath(iconPath);
    trayIcon = trayIcon.resize({ width: 18, height: 18 });
    trayIcon.setTemplateImage(true);
  } catch (e) {
    // Fallback: create a simple icon programmatically
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('Cortona - Jarvis Voice Assistant');

  // Build context menu
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '🎤 Open Cortona',
      accelerator: store.get('globalShortcut'),
      click: () => toggleWindow()
    },
    { type: 'separator' },
    {
      label: '⚙️ Settings',
      submenu: [
        {
          label: 'Start at Login',
          type: 'checkbox',
          checked: store.get('autoLaunch'),
          click: (item) => {
            store.set('autoLaunch', item.checked);
            updateAutoLaunch(item.checked);
          }
        },
        {
          label: 'Always on Top',
          type: 'checkbox',
          checked: store.get('alwaysOnTop'),
          click: (item) => {
            store.set('alwaysOnTop', item.checked);
            mainWindow?.setAlwaysOnTop(item.checked);
          }
        },
        {
          label: 'Show in Dock',
          type: 'checkbox',
          checked: store.get('showInDock'),
          click: (item) => {
            store.set('showInDock', item.checked);
            if (item.checked) {
              app.dock?.show();
            } else {
              app.dock?.hide();
            }
          }
        },
        {
          label: 'Start Minimized',
          type: 'checkbox',
          checked: store.get('startMinimized'),
          click: (item) => {
            store.set('startMinimized', item.checked);
          }
        }
      ]
    },
    { type: 'separator' },
    {
      label: '🔧 Developer Tools',
      accelerator: 'CommandOrControl+Shift+D',
      click: () => {
        if (mainWindow) {
          mainWindow.webContents.openDevTools({ mode: 'detach' });
        }
      }
    },
    {
      label: '🌐 Open in Browser',
      click: () => shell.openExternal(RENDER_URL)
    },
    {
      label: '📖 Help',
      click: () => shell.openExternal('https://github.com/quinnbean/Cortona-')
    },
    { type: 'separator' },
    {
      label: '❌ Quit Cortona',
      accelerator: 'CommandOrControl+Q',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);

  // Click to toggle window
  tray.on('click', () => toggleWindow());
}

function toggleWindow() {
  if (!mainWindow) {
    createWindow();
    return;
  }

  if (mainWindow.isVisible()) {
    if (mainWindow.isFocused()) {
      mainWindow.hide();
    } else {
      mainWindow.focus();
    }
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

// ============================================================================
// GLOBAL SHORTCUTS
// ============================================================================

function registerGlobalShortcuts() {
  const shortcut = store.get('globalShortcut');
  
  // Unregister all first
  globalShortcut.unregisterAll();

  // Main toggle shortcut
  const registered = globalShortcut.register(shortcut, () => {
    toggleWindow();
    
    // Send message to renderer to activate mic
    if (mainWindow?.isVisible()) {
      mainWindow.webContents.send('activate-voice');
    }
  });

  if (!registered) {
    console.error('Failed to register global shortcut:', shortcut);
  }

  // Quick record shortcut (toggle recording)
  globalShortcut.register('CommandOrControl+Shift+V', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send('start-recording');
    }
  });

  // Push-to-Talk shortcut (Cmd+Shift+Space)
  // Tracks state to toggle recording on/off
  let pttRecording = false;
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
      
      if (!pttRecording) {
        // Start recording
        console.log('[PTT] Starting recording');
        mainWindow.webContents.send('start-recording');
        pttRecording = true;
      } else {
        // Stop recording
        console.log('[PTT] Stopping recording');
        mainWindow.webContents.send('stop-recording');
        pttRecording = false;
      }
    }
  });

  // Toggle DevTools shortcut (for debugging)
  globalShortcut.register('CommandOrControl+Shift+D', () => {
    if (mainWindow) {
      mainWindow.webContents.toggleDevTools();
    }
  });
}

// ============================================================================
// AUTO-LAUNCH
// ============================================================================

async function updateAutoLaunch(enabled) {
  try {
    if (enabled) {
      await autoLauncher.enable();
    } else {
      await autoLauncher.disable();
    }
  } catch (e) {
    console.error('Auto-launch error:', e);
  }
}

async function initAutoLaunch() {
  try {
    const isEnabled = await autoLauncher.isEnabled();
    if (store.get('autoLaunch') && !isEnabled) {
      await autoLauncher.enable();
    }
  } catch (e) {
    console.error('Auto-launch init error:', e);
  }
}

// ============================================================================
// NOTIFICATIONS
// ============================================================================

function showNotification(title, body) {
  if (Notification.isSupported()) {
    const notification = new Notification({
      title,
      body,
      icon: path.join(__dirname, 'assets', 'icon.png'),
      silent: true
    });
    notification.show();
  }
}

// ============================================================================
// APP CONTROL (Focus apps, type text, etc.)
// ============================================================================

const APP_NAMES = {
  'cursor': 'Cursor',
  'vscode': 'Visual Studio Code',
  'chrome': 'Google Chrome',
  'safari': 'Safari',
  'terminal': 'Terminal',
  'iterm': 'iTerm',
  'slack': 'Slack',
  'discord': 'Discord',
  'notes': 'Notes',
  'finder': 'Finder',
  'messages': 'Messages',
  'mail': 'Mail'
};

function focusApp(appName) {
  return new Promise((resolve, reject) => {
    const macAppName = APP_NAMES[appName.toLowerCase()] || appName;
    const script = `tell application "${macAppName}" to activate`;
    
    exec(`osascript -e '${script}'`, (error) => {
      if (error) {
        console.log(`[APP] Failed to focus ${macAppName}:`, error.message);
        reject(error);
      } else {
        console.log(`[APP] ✅ Focused: ${macAppName}`);
        resolve(true);
      }
    });
  });
}

function typeText(text) {
  return new Promise((resolve, reject) => {
    try {
      // Use clipboard + paste for reliability
      clipboard.writeText(text);
      
      // Use AppleScript to paste
      const script = `
        tell application "System Events"
          keystroke "v" using command down
        end tell
      `;
      
      exec(`osascript -e '${script}'`, (error) => {
        if (error) {
          console.log('[APP] Failed to paste:', error.message);
          reject(error);
        } else {
          console.log(`[APP] ✅ Typed: ${text.substring(0, 50)}...`);
          resolve(true);
        }
      });
    } catch (e) {
      reject(e);
    }
  });
}

function pressKey(key) {
  return new Promise((resolve, reject) => {
    const keyMap = {
      'enter': 'return',
      'return': 'return',
      'tab': 'tab',
      'escape': 'escape',
      'space': 'space'
    };
    
    const mappedKey = keyMap[key.toLowerCase()] || key;
    const script = `
      tell application "System Events"
        key code ${mappedKey === 'return' ? 36 : mappedKey === 'tab' ? 48 : mappedKey === 'escape' ? 53 : 49}
      end tell
    `;
    
    exec(`osascript -e '${script}'`, (error) => {
      if (error) {
        reject(error);
      } else {
        console.log(`[APP] ✅ Pressed: ${key}`);
        resolve(true);
      }
    });
  });
}

async function executeCommand(action, command, targetApp) {
  console.log(`[APP] Executing: ${action} | App: ${targetApp} | Command: ${command?.substring(0, 50)}...`);
  
  try {
    // Focus the app if specified
    if (targetApp) {
      await focusApp(targetApp);
      await new Promise(r => setTimeout(r, 300)); // Wait for app to focus
    }
    
    // Execute based on action
    switch (action) {
      case 'type':
        await typeText(command);
        break;
      case 'type_and_send':
        await typeText(command);
        await new Promise(r => setTimeout(r, 100));
        await pressKey('enter');
        break;
      case 'open':
        await focusApp(command);
        break;
      case 'open_url':
        shell.openExternal(command);
        break;
      case 'search':
        shell.openExternal(`https://www.google.com/search?q=${encodeURIComponent(command)}`);
        break;
      default:
        await typeText(command);
    }
    
    return { success: true };
  } catch (error) {
    console.log('[APP] Error:', error.message);
    return { success: false, error: error.message };
  }
}

// ============================================================================
// IPC HANDLERS (Communication with renderer)
// ============================================================================

function setupIPC() {
  // Notification from web app
  ipcMain.on('show-notification', (event, { title, body }) => {
    showNotification(title, body);
  });

  // Get settings
  ipcMain.handle('get-settings', () => {
    return store.store;
  });

  // Update setting
  ipcMain.on('set-setting', (event, { key, value }) => {
    store.set(key, value);
  });

  // Hide window
  ipcMain.on('hide-window', () => {
    mainWindow?.hide();
  });

  // Minimize to tray
  ipcMain.on('minimize-to-tray', () => {
    mainWindow?.hide();
  });

  // Check microphone permission status
  ipcMain.handle('get-mic-status', async () => {
    if (process.platform === 'darwin') {
      return systemPreferences.getMediaAccessStatus('microphone');
    }
    return 'granted';
  });

  // Request microphone permission
  ipcMain.handle('request-mic-permission', async () => {
    if (process.platform === 'darwin') {
      const status = systemPreferences.getMediaAccessStatus('microphone');
      if (status === 'not-determined') {
        return await systemPreferences.askForMediaAccess('microphone');
      }
      return status === 'granted';
    }
    return true;
  });

  // ========== APP CONTROL ==========
  
  // Focus an app
  ipcMain.handle('focus-app', async (event, appName) => {
    try {
      await focusApp(appName);
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Type text
  ipcMain.handle('type-text', async (event, text) => {
    try {
      await typeText(text);
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Press a key
  ipcMain.handle('press-key', async (event, key) => {
    try {
      await pressKey(key);
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Execute a full command (focus app + type + optional enter)
  ipcMain.handle('execute-command', async (event, { action, command, targetApp }) => {
    return await executeCommand(action, command, targetApp);
  });

  // Check if app control is available
  ipcMain.handle('can-control-apps', () => {
    return process.platform === 'darwin'; // For now, only macOS
  });
  
  // ========== WHISPER IPC HANDLERS ==========
  
  // Check Whisper service health
  ipcMain.handle('whisper-health', async () => {
    try {
      const http = require('http');
      return new Promise((resolve) => {
        const req = http.get('http://127.0.0.1:5051/health', (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            try {
              const json = JSON.parse(data);
              resolve({ available: true, modelLoaded: json.model_loaded });
            } catch (e) {
              resolve({ available: false });
            }
          });
        });
        req.on('error', () => resolve({ available: false }));
        req.setTimeout(2000, () => {
          req.destroy();
          resolve({ available: false });
        });
      });
    } catch (e) {
      return { available: false };
    }
  });
  
  // Transcribe audio with Whisper
  ipcMain.handle('whisper-transcribe', async (event, audioArrayBuffer) => {
    try {
      const http = require('http');
      const FormData = require('form-data');
      
      // Convert ArrayBuffer to Buffer
      const audioBuffer = Buffer.from(audioArrayBuffer);
      
      return new Promise((resolve, reject) => {
        const boundary = '----FormBoundary' + Math.random().toString(36).substring(2);
        
        // Build multipart form data manually
        const header = `--${boundary}\r\nContent-Disposition: form-data; name="audio"; filename="audio.webm"\r\nContent-Type: audio/webm\r\n\r\n`;
        const footer = `\r\n--${boundary}--\r\n`;
        
        const bodyBuffer = Buffer.concat([
          Buffer.from(header),
          audioBuffer,
          Buffer.from(footer)
        ]);
        
        const options = {
          hostname: '127.0.0.1',
          port: 5051,
          path: '/transcribe',
          method: 'POST',
          headers: {
            'Content-Type': `multipart/form-data; boundary=${boundary}`,
            'Content-Length': bodyBuffer.length
          }
        };
        
        const req = http.request(options, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            try {
              const json = JSON.parse(data);
              resolve({ success: true, text: json.text || '' });
            } catch (e) {
              resolve({ success: false, error: 'Failed to parse response' });
            }
          });
        });
        
        req.on('error', (e) => {
          resolve({ success: false, error: e.message });
        });
        
        req.setTimeout(30000, () => {
          req.destroy();
          resolve({ success: false, error: 'Timeout' });
        });
        
        req.write(bodyBuffer);
        req.end();
      });
    } catch (e) {
      return { success: false, error: e.message };
    }
  });
}

// ============================================================================
// APP LIFECYCLE
// ============================================================================

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Request microphone permission on macOS
async function requestMicrophonePermission() {
  if (process.platform === 'darwin') {
    const status = systemPreferences.getMediaAccessStatus('microphone');
    console.log('[MIC] Current microphone permission status:', status);
    
    if (status === 'not-determined') {
      console.log('[MIC] Requesting microphone access...');
      const granted = await systemPreferences.askForMediaAccess('microphone');
      console.log('[MIC] Microphone access granted:', granted);
      return granted;
    } else if (status === 'denied') {
      console.log('[MIC] Microphone access denied. User needs to enable in System Preferences.');
      showNotification('Microphone Access Required', 'Please enable microphone access in System Preferences > Security & Privacy > Privacy > Microphone');
      return false;
    }
    return status === 'granted';
  }
  return true; // Non-macOS, assume granted
}

// App ready
app.whenReady().then(async () => {
  // Start local Whisper service for speech-to-text
  startWhisperService();
  
  // Request microphone permission FIRST on macOS
  const micGranted = await requestMicrophonePermission();
  console.log('[MIC] Microphone permission result:', micGranted);

  // Set up permission handler for microphone access
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowedPermissions = ['media', 'microphone', 'audio', 'audioCapture', 'clipboard-read', 'clipboard-write'];
    console.log(`[PERMISSION] Requested: ${permission}`);
    callback(true); // Allow all permissions
  });

  // Also handle permission checks (for some Electron versions)
  session.defaultSession.setPermissionCheckHandler((webContents, permission, requestingOrigin) => {
    console.log(`[PERMISSION CHECK] ${permission} from ${requestingOrigin}`);
    return true; // Allow all permission checks
  });
  
  // Clear any cached data that might interfere with Speech API
  session.defaultSession.clearCache();

  // Create tray first (so it appears in menubar)
  createTray();
  
  // Create main window
  createWindow();
  
  // Register shortcuts
  registerGlobalShortcuts();
  
  // Setup IPC
  setupIPC();
  
  // Init auto-launch
  await initAutoLaunch();

  // macOS: re-create window when dock icon clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      mainWindow?.show();
    }
  });
});

// Quit when all windows closed (except macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Before quit
app.on('before-quit', () => {
  isQuitting = true;
});

// Cleanup on quit
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  stopWhisperService();
});

// Handle certificate errors for development
if (IS_DEV) {
  app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
    event.preventDefault();
    callback(true);
  });
}

