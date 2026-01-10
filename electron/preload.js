const { contextBridge, ipcRenderer } = require('electron');

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
  
  // ========== WHISPER SPEECH-TO-TEXT ==========
  // Check if Whisper service is running
  whisperHealth: () => ipcRenderer.invoke('whisper-health'),
  
  // Transcribe audio using local Whisper
  whisperTranscribe: (audioBlob) => ipcRenderer.invoke('whisper-transcribe', audioBlob),
  
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

