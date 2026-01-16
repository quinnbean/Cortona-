const { contextBridge, ipcRenderer } = require('electron');

console.log('[PRELOAD] Loading preload.js - exposing electronAPI with porcupineStart');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Platform info
  platform: process.platform,
  isElectron: true,
  
  // Notifications
  showNotification: (title, body) => {
    ipcRenderer.send('show-notification', { title, body });
  },
  
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  setSetting: (key, value) => ipcRenderer.send('set-setting', { key, value }),
  
  // Microphone permissions (macOS)
  getMicStatus: () => ipcRenderer.invoke('get-mic-status'),
  requestMicPermission: () => ipcRenderer.invoke('request-mic-permission'),
  
  // Window control
  hideWindow: () => ipcRenderer.send('hide-window'),
  minimizeToTray: () => ipcRenderer.send('minimize-to-tray'),
  
  // ========== APP CONTROL ==========
  // Focus an app by name
  focusApp: (appName) => ipcRenderer.invoke('focus-app', appName),
  
  // Type text using clipboard + paste
  typeText: (text) => ipcRenderer.invoke('type-text', text),
  
  // Press a key (enter, tab, escape, etc.)
  pressKey: (key) => ipcRenderer.invoke('press-key', key),
  
  // Execute a full command (focus app + type + optional send)
  executeCommand: (action, command, targetApp) => 
    ipcRenderer.invoke('execute-command', { action, command, targetApp }),
  
  // Check if app control is available
  canControlApps: () => ipcRenderer.invoke('can-control-apps'),
  
  // ========== SYSTEM PREFERENCES ==========
  // Open Accessibility settings pane
  openAccessibilitySettings: () => ipcRenderer.invoke('open-accessibility-settings'),
  
  // Check if Accessibility permission is granted
  checkAccessibility: () => ipcRenderer.invoke('check-accessibility'),
  
  // ========== WHISPER SPEECH-TO-TEXT ==========
  // Check if Whisper service is running
  whisperHealth: () => ipcRenderer.invoke('whisper-health'),
  
  // Transcribe audio using local Whisper
  whisperTranscribe: (audioBlob) => ipcRenderer.invoke('whisper-transcribe', audioBlob),
  
  // ========== NATIVE WAKE WORD DETECTION ==========
  // Check if native wake word is available (Porcupine + naudiodon)
  porcupineAvailable: () => ipcRenderer.invoke('porcupine-available'),
  
  // Get available built-in keywords
  porcupineKeywords: () => ipcRenderer.invoke('porcupine-keywords'),
  
  // Start native wake word listening (audio captured in main process - no IPC overhead!)
  porcupineStart: (accessKey, keyword) => ipcRenderer.invoke('porcupine-start', { accessKey, keyword }),
  
  // Stop native wake word listening
  porcupineStop: () => ipcRenderer.invoke('porcupine-stop'),
  
  // Check if currently listening for wake word
  porcupineStatus: () => ipcRenderer.invoke('porcupine-status'),
  
  // Listen for wake word detection event (fired from main process when detected)
  onWakeWordDetected: (callback) => {
    ipcRenderer.on('wake-word-detected', (event, data) => callback(data));
  },
  
  // ========== NATIVE LEOPARD SPEECH-TO-TEXT ==========
  // Check if Leopard is available
  leopardAvailable: () => ipcRenderer.invoke('leopard-available'),
  
  // Start recording for transcription
  leopardStart: (accessKey) => ipcRenderer.invoke('leopard-start', { accessKey }),
  
  // Stop recording and get transcription
  leopardStop: () => ipcRenderer.invoke('leopard-stop'),
  
  // Check if currently recording
  leopardRecording: () => ipcRenderer.invoke('leopard-recording'),
  
  // Listen for real-time audio levels (for visualization)
  onAudioLevel: (callback) => {
    ipcRenderer.on('audio-level', (event, data) => callback(data));
  },
  
  // ========== KEYBIND SETTINGS ==========
  // Update the push-to-talk shortcut
  updatePTTShortcut: (keybind) => ipcRenderer.invoke('update-ptt-shortcut', keybind),
  
  // Get current PTT shortcut
  getPTTShortcut: () => ipcRenderer.invoke('get-ptt-shortcut'),
  
  // ========== AGENT WATCHER ==========
  // Start watching a directory for AI agent activity
  agentWatcherStart: (watchPath, idleThreshold) => 
    ipcRenderer.invoke('agent-watcher-start', { watchPath, idleThreshold }),
  
  // Stop the agent watcher
  agentWatcherStop: () => ipcRenderer.invoke('agent-watcher-stop'),
  
  // Get agent watcher status
  agentWatcherStatus: () => ipcRenderer.invoke('agent-watcher-status'),
  
  // Get last watched path
  agentWatcherGetPath: () => ipcRenderer.invoke('agent-watcher-get-path'),
  
  // Listen for agent finished events
  onAgentFinished: (callback) => {
    ipcRenderer.on('agent-finished', (event, data) => callback(data));
  },
  
  // ========== WINDOW WATCHER (Universal AI Detection) ==========
  // Get list of running applications
  windowWatcherApps: () => ipcRenderer.invoke('window-watcher-apps'),
  
  // Start watching a specific app window (with optional window selector)
  windowWatcherStart: (appName, idleThreshold, captureInterval, windowSelector) => 
    ipcRenderer.invoke('window-watcher-start', { appName, idleThreshold, captureInterval, windowSelector }),
  
  // List all windows for an app (to select which window to watch)
  windowWatcherListWindows: (appName) => ipcRenderer.invoke('window-watcher-list-windows', appName),
  
  // Stop the window watcher
  windowWatcherStop: () => ipcRenderer.invoke('window-watcher-stop'),
  
  // Get window watcher status
  windowWatcherStatus: () => ipcRenderer.invoke('window-watcher-status'),
  
  // Get window info for a specific app
  windowWatcherInfo: (appName) => ipcRenderer.invoke('window-watcher-info', appName),
  
  // Get last watched app
  windowWatcherGetApp: () => ipcRenderer.invoke('window-watcher-get-app'),
  
  // Listen for window activity
  onWindowActivity: (callback) => {
    ipcRenderer.on('window-activity', (event, data) => callback(data));
  },
  
  // Listen for window agent finished
  onWindowAgentFinished: (callback) => {
    ipcRenderer.on('window-agent-finished', (event, data) => callback(data));
  },
  
  // Listen for events from main process
  onActivateVoice: (callback) => {
    ipcRenderer.on('activate-voice', callback);
  },
  onStartRecording: (callback) => {
    ipcRenderer.on('start-recording', callback);
  },
  onStopRecording: (callback) => {
    ipcRenderer.on('stop-recording', callback);
  },
  
  // Remove listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// Inject a flag so the web app knows it's running in Electron
window.addEventListener('DOMContentLoaded', () => {
  console.log('[PRELOAD] DOMContentLoaded - checking electronAPI');
  console.log('[PRELOAD] electronAPI keys:', Object.keys(window.electronAPI || {}));
  console.log('[PRELOAD] porcupineStart exists:', typeof window.electronAPI?.porcupineStart);
  
  // Add electron class to body
  document.body.classList.add('electron-app');
  
  // Create a style element for Electron-specific styles
  const style = document.createElement('style');
  style.textContent = `
    /* Hide browser-specific elements in Electron */
    .electron-app .browser-only { display: none !important; }
    
    /* Custom title bar drag region */
    .electron-app .drag-region {
      -webkit-app-region: drag;
    }
    
    .electron-app .no-drag {
      -webkit-app-region: no-drag;
    }
    
    /* Adjust for hidden title bar */
    .electron-app .main-content {
      padding-top: 40px;
    }
    
    /* macOS traffic light spacing */
    .electron-app .top-bar {
      padding-left: 80px;
    }
  `;
  document.head.appendChild(style);
});

