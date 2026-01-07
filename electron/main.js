const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, Notification, ipcMain, shell, session } = require('electron');
const path = require('path');
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
      webSecurity: true
    },
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png')
  });

  // Load the app
  const appUrl = IS_DEV ? DEV_URL : RENDER_URL;
  mainWindow.loadURL(appUrl);

  // Show when ready
  mainWindow.once('ready-to-show', () => {
    if (!store.get('startMinimized')) {
      mainWindow.show();
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

  // Quick record shortcut (hold to record)
  globalShortcut.register('CommandOrControl+Shift+V', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send('start-recording');
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

// App ready
app.whenReady().then(async () => {
  // Set up permission handler for microphone access
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowedPermissions = ['media', 'microphone', 'audio', 'audioCapture'];
    if (allowedPermissions.includes(permission)) {
      console.log(`✅ Granting permission: ${permission}`);
      callback(true);
    } else {
      console.log(`⚠️ Permission requested: ${permission}`);
      callback(true); // Allow all for now, can restrict later
    }
  });

  // Also handle permission checks (for some Electron versions)
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    const allowedPermissions = ['media', 'microphone', 'audio', 'audioCapture'];
    return allowedPermissions.includes(permission) || true;
  });

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
});

// Handle certificate errors for development
if (IS_DEV) {
  app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
    event.preventDefault();
    callback(true);
  });
}

