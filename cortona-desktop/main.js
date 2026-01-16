const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, Notification, ipcMain, shell, session, systemPreferences, clipboard } = require('electron');
const path = require('path');
const { exec, execSync } = require('child_process');
const Store = require('electron-store');
const AutoLaunch = require('auto-launch');
const chokidar = require('chokidar');

// Porcupine for wake word detection
let Porcupine, BuiltinKeyword;
try {
  const porcupineModule = require('@picovoice/porcupine-node');
  Porcupine = porcupineModule.Porcupine;
  BuiltinKeyword = porcupineModule.BuiltinKeyword;
  console.log('[PORCUPINE] Node module loaded successfully');
  console.log('[PORCUPINE] Available keywords:', Object.keys(BuiltinKeyword || {}));
} catch (e) {
  console.log('[PORCUPINE] Node module not available:', e.message);
  Porcupine = null;
}

// Leopard for speech-to-text transcription
let Leopard;
try {
  const leopardModule = require('@picovoice/leopard-node');
  Leopard = leopardModule.Leopard;
  console.log('[LEOPARD] Node module loaded successfully');
} catch (e) {
  console.log('[LEOPARD] Node module not available:', e.message);
  Leopard = null;
}

// node-record-lpcm16 for audio capture (uses sox, more stable than naudiodon)
let record;
try {
  record = require('node-record-lpcm16');
  console.log('[AUDIO] node-record-lpcm16 loaded successfully');
} catch (e) {
  console.log('[AUDIO] node-record-lpcm16 not available:', e.message);
  record = null;
}

// ============================================================================
// HANDLE EPIPE ERRORS (prevents crash when Whisper subprocess closes)
// ============================================================================
process.on('uncaughtException', (err) => {
  if (err.code === 'EPIPE') {
    // Silently ignore EPIPE - happens when subprocess stream closes
    return;
  }
  console.error('Uncaught exception:', err);
});

process.stdout.on('error', (err) => {
  if (err.code === 'EPIPE') return;
});

process.stderr.on('error', (err) => {
  if (err.code === 'EPIPE') return;
});

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
let porcupineHandle = null;
let porcupineListening = false;
let audioInputStream = null;
let wakeWordAccessKey = null;

// Agent watcher state
let agentWatcher = null;
let agentWatcherEnabled = false;
let lastFileChange = null;
let agentIdleTimer = null;
const AGENT_IDLE_THRESHOLD = 3000; // 3 seconds of no changes = agent done

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
// AGENT WATCHER - Detect when AI agents (like Cursor) finish working
// ============================================================================

function startAgentWatcher(watchPath, options = {}) {
  const {
    idleThreshold = AGENT_IDLE_THRESHOLD,
    ignoredPatterns = [
      '**/node_modules/**',
      '**/.git/**',
      '**/dist/**',
      '**/build/**',
      '**/*.log',
      '**/package-lock.json',
      '**/.DS_Store'
    ]
  } = options;

  if (agentWatcher) {
    console.log('[AGENT-WATCHER] Already running, stopping first...');
    stopAgentWatcher();
  }

  console.log('[AGENT-WATCHER] Starting to watch:', watchPath);
  console.log('[AGENT-WATCHER] Idle threshold:', idleThreshold, 'ms');

  // Track if we've seen any activity (to avoid false positives on startup)
  let hasSeenActivity = false;
  let changedFiles = [];

  agentWatcher = chokidar.watch(watchPath, {
    ignored: ignoredPatterns,
    persistent: true,
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 500,
      pollInterval: 100
    }
  });

  agentWatcher.on('change', (filePath) => {
    console.log('[AGENT-WATCHER] File changed:', path.basename(filePath));
    hasSeenActivity = true;
    lastFileChange = Date.now();
    
    // Track changed files for summary
    const relativePath = path.relative(watchPath, filePath);
    if (!changedFiles.includes(relativePath)) {
      changedFiles.push(relativePath);
    }

    // Clear existing timer
    if (agentIdleTimer) {
      clearTimeout(agentIdleTimer);
    }

    // Set new timer
    agentIdleTimer = setTimeout(() => {
      if (hasSeenActivity && agentWatcherEnabled) {
        console.log('[AGENT-WATCHER] Agent appears to be DONE!');
        console.log('[AGENT-WATCHER] Changed files:', changedFiles);
        
        // Notify the renderer
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('agent-finished', {
            changedFiles: changedFiles,
            watchPath: watchPath,
            duration: Date.now() - (lastFileChange - idleThreshold)
          });
        }

        // Show system notification
        showNotification(
          'Agent Finished',
          `${changedFiles.length} file${changedFiles.length !== 1 ? 's' : ''} modified`
        );

        // Reset for next detection
        changedFiles = [];
        hasSeenActivity = false;
      }
    }, idleThreshold);
  });

  agentWatcher.on('add', (filePath) => {
    console.log('[AGENT-WATCHER] File added:', path.basename(filePath));
    // Trigger same logic as change
    agentWatcher.emit('change', filePath);
  });

  agentWatcher.on('error', (error) => {
    console.error('[AGENT-WATCHER] Error:', error);
  });

  agentWatcher.on('ready', () => {
    console.log('[AGENT-WATCHER] Ready and watching for changes');
    agentWatcherEnabled = true;
  });

  return { success: true, watchPath };
}

function stopAgentWatcher() {
  console.log('[AGENT-WATCHER] Stopping...');
  
  agentWatcherEnabled = false;
  
  if (agentIdleTimer) {
    clearTimeout(agentIdleTimer);
    agentIdleTimer = null;
  }

  if (agentWatcher) {
    agentWatcher.close();
    agentWatcher = null;
  }

  lastFileChange = null;
  console.log('[AGENT-WATCHER] Stopped');
  return { success: true };
}

function getAgentWatcherStatus() {
  return {
    enabled: agentWatcherEnabled,
    watching: !!agentWatcher,
    lastChange: lastFileChange
  };
}

// ============================================================================
// UNIVERSAL WINDOW WATCHER - Detect when ANY AI app finishes
// ============================================================================

// Window watcher state
let windowWatcher = null;
let windowWatcherEnabled = false;
let windowWatcherApp = null;
let windowWatcherInterval = null;
let lastWindowHash = null;
let lastWindowActivity = null;
let windowIdleTimer = null;
let windowWatcherConfig = {
  idleThreshold: 5000,      // 5 seconds of no changes = done
  captureInterval: 500,     // Check every 500ms
  sensitivity: 'medium'     // low, medium, high
};

// Common AI app identifiers
const AI_APP_ALIASES = {
  'cursor': ['Cursor', 'cursor'],
  'vscode': ['Visual Studio Code', 'Code', 'code'],
  'chrome': ['Google Chrome', 'Chrome'],
  'safari': ['Safari'],
  'firefox': ['Firefox'],
  'chatgpt': ['Google Chrome', 'Safari', 'Firefox'], // Web-based
  'claude': ['Google Chrome', 'Safari', 'Firefox'],
  'gemini': ['Google Chrome', 'Safari', 'Firefox'],
  'discord': ['Discord'], // For Midjourney
  'windsurf': ['Windsurf', 'windsurf'],
  'terminal': ['Terminal', 'iTerm', 'iTerm2']
};

// Get list of running applications
function getRunningApps() {
  try {
    const script = `
      tell application "System Events"
        set appList to name of every process whose background only is false
        return appList
      end tell
    `;
    const result = execSync(`osascript -e '${script.replace(/'/g, "\\'")}'`, { encoding: 'utf8' });
    return result.trim().split(', ').filter(a => a);
  } catch (e) {
    console.error('[WINDOW-WATCHER] Failed to get running apps:', e.message);
    return [];
  }
}

// Find app by name (with alias support)
function findAppByName(searchName) {
  const lower = searchName.toLowerCase();
  const aliases = AI_APP_ALIASES[lower] || [searchName];
  const running = getRunningApps();
  
  for (const alias of aliases) {
    const found = running.find(app => 
      app.toLowerCase().includes(alias.toLowerCase()) ||
      alias.toLowerCase().includes(app.toLowerCase())
    );
    if (found) return found;
  }
  return null;
}

// Get ALL windows for an app (with titles)
function getAllWindows(appName) {
  try {
    const script = `
      tell application "System Events"
        tell process "${appName}"
          set windowList to {}
          set winCount to count of windows
          repeat with i from 1 to winCount
            set win to window i
            set winPos to position of win
            set winSize to size of win
            set winTitle to name of win
            set end of windowList to (i as text) & "|" & (item 1 of winPos as text) & "|" & (item 2 of winPos as text) & "|" & (item 1 of winSize as text) & "|" & (item 2 of winSize as text) & "|" & winTitle
          end repeat
          set AppleScript's text item delimiters to ";;;"
          return windowList as text
        end tell
      end tell
    `;
    const result = execSync(`osascript -e '${script}'`, { encoding: 'utf8', timeout: 5000 });
    if (!result.trim()) return [];
    
    return result.trim().split(';;;').map(w => {
      const [index, x, y, width, height, ...titleParts] = w.split('|');
      return {
        index: parseInt(index),
        x: parseInt(x),
        y: parseInt(y),
        width: parseInt(width),
        height: parseInt(height),
        title: titleParts.join('|'),
        app: appName
      };
    });
  } catch (e) {
    console.error('[WINDOW-WATCHER] Failed to get all windows:', e.message);
    return [];
  }
}

// Get window bounds and info for a specific window (by index or title match)
function getWindowInfo(appName, windowSelector = 1) {
  try {
    // If windowSelector is a string, find window by title
    if (typeof windowSelector === 'string') {
      const allWindows = getAllWindows(appName);
      const match = allWindows.find(w => 
        w.title.toLowerCase().includes(windowSelector.toLowerCase())
      );
      if (match) return match;
      // Fall back to first window if no title match
      windowSelector = 1;
    }
    
    const script = `
      tell application "System Events"
        tell process "${appName}"
          if (count of windows) >= ${windowSelector} then
            set win to window ${windowSelector}
            set winPos to position of win
            set winSize to size of win
            set winTitle to name of win
            return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text) & "," & winTitle
          end if
        end tell
      end tell
    `;
    const result = execSync(`osascript -e '${script}'`, { encoding: 'utf8', timeout: 5000 });
    const [x, y, width, height, ...titleParts] = result.trim().split(',');
    return {
      index: windowSelector,
      x: parseInt(x),
      y: parseInt(y),
      width: parseInt(width),
      height: parseInt(height),
      title: titleParts.join(','),
      app: appName
    };
  } catch (e) {
    console.error('[WINDOW-WATCHER] Failed to get window info:', e.message);
    return null;
  }
}

// Capture a region of screen and return hash (for change detection)
function captureWindowHash(windowInfo) {
  if (!windowInfo) return null;
  
  try {
    const { x, y, width, height } = windowInfo;
    // Use screencapture with -R for region, output to /dev/null but get hash
    // We'll capture to a temp file and hash it
    const tempFile = `/tmp/cortona_capture_${Date.now()}.png`;
    
    // Capture the window region
    execSync(`screencapture -R${x},${y},${width},${height} -x "${tempFile}"`, { timeout: 3000 });
    
    // Get file hash (fast comparison)
    const hash = execSync(`md5 -q "${tempFile}"`, { encoding: 'utf8', timeout: 2000 }).trim();
    
    // Clean up
    try { require('fs').unlinkSync(tempFile); } catch(e) {}
    
    return hash;
  } catch (e) {
    console.error('[WINDOW-WATCHER] Capture failed:', e.message);
    return null;
  }
}

// Alternative: Monitor window title changes (faster, less resource intensive)
function getWindowTitle(appName) {
  try {
    const script = `
      tell application "System Events"
        tell process "${appName}"
          if (count of windows) > 0 then
            return name of window 1
          end if
        end tell
      end tell
    `;
    return execSync(`osascript -e '${script}'`, { encoding: 'utf8', timeout: 2000 }).trim();
  } catch (e) {
    return null;
  }
}

// Check if app's frontmost window is active (has focus and receiving input)
function isAppActive(appName) {
  try {
    const script = `
      tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        return frontApp
      end tell
    `;
    const frontApp = execSync(`osascript -e '${script}'`, { encoding: 'utf8', timeout: 2000 }).trim();
    return frontApp.toLowerCase().includes(appName.toLowerCase());
  } catch (e) {
    return false;
  }
}

// Window selector for multi-window apps
let windowWatcherSelector = 1;
let windowWatcherTitle = null;

// Start universal window watcher
function startWindowWatcher(appNameOrAlias, options = {}) {
  console.log('[WINDOW-WATCHER] Starting for:', appNameOrAlias, 'options:', options);

  // Stop existing watcher
  stopWindowWatcher();

  // Find the actual app
  const appName = findAppByName(appNameOrAlias);
  if (!appName) {
    console.error('[WINDOW-WATCHER] App not found:', appNameOrAlias);
    return {
      success: false,
      error: `App "${appNameOrAlias}" not found or not running`,
      runningApps: getRunningApps()
    };
  }

  console.log('[WINDOW-WATCHER] Found app:', appName);

  // Update config
  Object.assign(windowWatcherConfig, options);
  
  // Handle window selector (number or title string)
  windowWatcherSelector = options.windowSelector || 1;

  windowWatcherEnabled = true;
  windowWatcherApp = appName;
  lastWindowActivity = Date.now();

  // Get initial state (with selector support)
  const windowInfo = getWindowInfo(appName, windowWatcherSelector);
  if (windowInfo) {
    windowWatcherTitle = windowInfo.title;
    lastWindowHash = captureWindowHash(windowInfo);
    console.log('[WINDOW-WATCHER] Watching window:', windowInfo.title);
    console.log('[WINDOW-WATCHER] Initial hash:', lastWindowHash?.substring(0, 8));
  } else {
    console.error('[WINDOW-WATCHER] Could not get window info');
    return {
      success: false,
      error: `Could not find window ${windowWatcherSelector} for ${appName}`,
      windows: getAllWindows(appName)
    };
  }
  
  // Start monitoring loop
  windowWatcherInterval = setInterval(() => {
    if (!windowWatcherEnabled) return;

    const currentInfo = getWindowInfo(windowWatcherApp, windowWatcherSelector);
    if (!currentInfo) {
      console.log('[WINDOW-WATCHER] Window not found, app may have closed');
      return;
    }
    
    // Method 1: Screenshot hash comparison (detects any visual change)
    const currentHash = captureWindowHash(currentInfo);
    
    // Method 2: Title change detection (fast, catches "Generating..." → "Done")
    const hasHashChanged = currentHash && currentHash !== lastWindowHash;
    
    if (hasHashChanged) {
      console.log('[WINDOW-WATCHER] Activity detected! Hash changed.');
      lastWindowHash = currentHash;
      lastWindowActivity = Date.now();
      
      // Clear any pending "done" timer
      if (windowIdleTimer) {
        clearTimeout(windowIdleTimer);
        windowIdleTimer = null;
      }
      
      // Notify renderer of activity
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('window-activity', {
          app: windowWatcherApp,
          title: currentInfo.title,
          timestamp: lastWindowActivity
        });
      }
    } else {
      // No change - check if we've been idle long enough
      const idleTime = Date.now() - lastWindowActivity;
      
      if (idleTime >= windowWatcherConfig.idleThreshold && !windowIdleTimer) {
        console.log('[WINDOW-WATCHER] Idle threshold reached, starting done timer...');
        
        // Wait a bit more to confirm it's really done
        windowIdleTimer = setTimeout(() => {
          const finalIdleTime = Date.now() - lastWindowActivity;
          if (finalIdleTime >= windowWatcherConfig.idleThreshold) {
            console.log('[WINDOW-WATCHER] Agent appears to be DONE!');
            
            // Notify renderer
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('window-agent-finished', {
                app: windowWatcherApp,
                title: currentInfo.title,
                idleTime: finalIdleTime
              });
            }
            
            // Show system notification
            new Notification({
              title: '🎉 Agent Finished!',
              body: `${windowWatcherApp} has been idle for ${Math.round(finalIdleTime/1000)}s`,
              silent: false
            }).show();
          }
          windowIdleTimer = null;
        }, 2000); // Extra 2s confirmation
      }
    }
  }, windowWatcherConfig.captureInterval);
  
  console.log('[WINDOW-WATCHER] Started monitoring', appName, 'window:', windowWatcherTitle);
  
  return {
    success: true,
    app: appName,
    windowTitle: windowWatcherTitle,
    windowSelector: windowWatcherSelector,
    config: windowWatcherConfig
  };
}

// Stop window watcher
function stopWindowWatcher() {
  console.log('[WINDOW-WATCHER] Stopping...');
  
  windowWatcherEnabled = false;
  
  if (windowWatcherInterval) {
    clearInterval(windowWatcherInterval);
    windowWatcherInterval = null;
  }
  
  if (windowIdleTimer) {
    clearTimeout(windowIdleTimer);
    windowIdleTimer = null;
  }
  
  const wasWatching = windowWatcherApp;
  const wasTitle = windowWatcherTitle;
  windowWatcherApp = null;
  windowWatcherTitle = null;
  windowWatcherSelector = 1;
  lastWindowHash = null;
  lastWindowActivity = null;
  
  console.log('[WINDOW-WATCHER] Stopped');
  return { success: true, wasWatching };
}

// Get window watcher status
function getWindowWatcherStatus() {
  return {
    enabled: windowWatcherEnabled,
    app: windowWatcherApp,
    windowTitle: windowWatcherTitle,
    windowSelector: windowWatcherSelector,
    lastActivity: lastWindowActivity,
    idleSince: lastWindowActivity ? Date.now() - lastWindowActivity : null,
    config: windowWatcherConfig
  };
}

// ============================================================================
// NATIVE WAKE WORD DETECTION (using node-record-lpcm16 + porcupine)
// ============================================================================

function startNativeWakeWordListening(accessKey, keyword) {
  if (!record || !Porcupine) {
    console.error('[WAKE-WORD] node-record-lpcm16 or Porcupine not available');
    return { success: false, error: 'Audio recording or Porcupine not available' };
  }
  
  if (porcupineListening) {
    console.log('[WAKE-WORD] Already listening');
    return { success: true, message: 'Already listening' };
  }
  
  try {
    // Stop any existing instances
    stopNativeWakeWordListening();
    
    // Map keyword string to built-in keyword
    const keywordUpper = keyword.toUpperCase();
    const builtinKeyword = BuiltinKeyword[keywordUpper];
    
    if (!builtinKeyword) {
      console.error('[WAKE-WORD] Unknown keyword:', keyword);
      return { success: false, error: `Unknown keyword: ${keyword}` };
    }
    
    console.log('[WAKE-WORD] Initializing Porcupine with keyword:', keyword);
    
    // Get path to porcupine-node module root (not dist/)
    const porcupineModule = require.resolve('@picovoice/porcupine-node');
    // require.resolve gives us .../dist/index.js, go up to module root
    const porcupineRoot = path.join(path.dirname(porcupineModule), '..');
    
    let keywordPath = path.join(porcupineRoot, 'resources', 'keyword_files', 'mac', `${keyword.toLowerCase()}_mac.ppn`);
    let modelPath = path.join(porcupineRoot, 'lib', 'common', 'porcupine_params.pv');
    
    // Replace app.asar with app.asar.unpacked for native file access
    keywordPath = keywordPath.replace('app.asar', 'app.asar.unpacked');
    modelPath = modelPath.replace('app.asar', 'app.asar.unpacked');
    
    console.log('[WAKE-WORD] Keyword path:', keywordPath);
    console.log('[WAKE-WORD] Model path:', modelPath);
    
    // Verify files exist
    const fs = require('fs');
    if (!fs.existsSync(keywordPath)) {
      console.error('[WAKE-WORD] Keyword file not found:', keywordPath);
      return { success: false, error: `Keyword file not found: ${keywordPath}` };
    }
    if (!fs.existsSync(modelPath)) {
      console.error('[WAKE-WORD] Model file not found:', modelPath);
      return { success: false, error: `Model file not found: ${modelPath}` };
    }
    
    // Initialize Porcupine with explicit paths
    porcupineHandle = new Porcupine(
      accessKey,
      [keywordPath],
      [0.7], // sensitivity
      modelPath
    );
    
    const frameLength = porcupineHandle.frameLength;
    const sampleRate = porcupineHandle.sampleRate;
    
    console.log('[WAKE-WORD] Porcupine initialized. Sample rate:', sampleRate, 'Frame length:', frameLength);
    
    // Create audio input stream using sox (via node-record-lpcm16)
    audioInputStream = record.record({
      sampleRate: sampleRate,
      channels: 1,
      audioType: 'raw',
      recorder: 'sox',
      endOnSilence: false,
      threshold: 0
    });
    
    // Buffer to accumulate audio data
    let audioBuffer = Buffer.alloc(0);
    const bytesPerFrame = frameLength * 2; // 16-bit = 2 bytes per sample
    
    const audioStream = audioInputStream.stream();
    
    audioStream.on('data', (data) => {
      if (!porcupineListening || !porcupineHandle) return;
      
      // Accumulate audio data
      audioBuffer = Buffer.concat([audioBuffer, data]);
      
      // Process complete frames
      while (audioBuffer.length >= bytesPerFrame) {
        // Extract one frame
        const frameBuffer = audioBuffer.slice(0, bytesPerFrame);
        audioBuffer = audioBuffer.slice(bytesPerFrame);
        
        // Convert to Int16Array
        const frame = new Int16Array(frameBuffer.buffer, frameBuffer.byteOffset, frameLength);
        
        try {
          const keywordIndex = porcupineHandle.process(frame);
          
          if (keywordIndex >= 0) {
            console.log('[WAKE-WORD] >>> WAKE WORD DETECTED! <<<');
            
            // Notify the renderer
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('wake-word-detected', { keywordIndex });
            }
          }
        } catch (e) {
          // Ignore processing errors, just continue
        }
      }
    });
    
    audioStream.on('error', (err) => {
      console.error('[WAKE-WORD] Audio stream error:', err.message);
    });
    
    porcupineListening = true;
    wakeWordAccessKey = accessKey;
    
    console.log('[WAKE-WORD] Started listening for wake word:', keyword);
    
    return { 
      success: true, 
      sampleRate: sampleRate,
      frameLength: frameLength
    };
    
  } catch (e) {
    console.error('[WAKE-WORD] Failed to start:', e.message);
    stopNativeWakeWordListening();
    return { success: false, error: e.message };
  }
}

function stopNativeWakeWordListening() {
  console.log('[WAKE-WORD] Stopping...');
  
  porcupineListening = false;
  
  if (audioInputStream) {
    try {
      audioInputStream.stop();
    } catch (e) {
      console.log('[WAKE-WORD] Error stopping audio stream:', e.message);
    }
    audioInputStream = null;
  }
  
  if (porcupineHandle) {
    try {
      porcupineHandle.release();
    } catch (e) {
      console.log('[WAKE-WORD] Error releasing Porcupine:', e.message);
    }
    porcupineHandle = null;
  }
  
  console.log('[WAKE-WORD] Stopped');
  return { success: true };
}

// ============================================================================
// NATIVE SPEECH-TO-TEXT (Leopard - records audio then transcribes)
// ============================================================================

let leopardHandle = null;
let leopardRecording = null;
let leopardAccessKey = null;

async function startNativeLeopardRecording(accessKey) {
  if (!record || !Leopard) {
    console.error('[LEOPARD] node-record-lpcm16 or Leopard not available');
    return { success: false, error: 'Native recording or Leopard not available' };
  }
  
  try {
    console.log('[LEOPARD] Starting native recording for transcription...');
    
    // Initialize Leopard if not done
    if (!leopardHandle || leopardAccessKey !== accessKey) {
      console.log('[LEOPARD] Initializing Leopard...');
      
      if (leopardHandle) {
        leopardHandle.release();
      }
      
      leopardHandle = new Leopard(accessKey, {
        enableAutomaticPunctuation: true
      });
      leopardAccessKey = accessKey;
      console.log('[LEOPARD] Initialized successfully');
    }
    
    // Start recording audio with sox
    leopardRecording = record.record({
      sampleRate: 16000,
      channels: 1,
      audioType: 'raw',
      recorder: 'sox',
      endOnSilence: false,
      threshold: 0
    });
    
    // Collect audio data
    const audioChunks = [];
    const audioStream = leopardRecording.stream();
    
    audioStream.on('data', (data) => {
      audioChunks.push(data);
      
      // Calculate audio level and send to renderer
      if (mainWindow && !mainWindow.isDestroyed()) {
        // Convert buffer to Int16 samples
        const samples = new Int16Array(data.buffer, data.byteOffset, data.length / 2);
        
        // Calculate RMS (root mean square) for audio level
        let sumSquares = 0;
        for (let i = 0; i < samples.length; i++) {
          const normalized = samples[i] / 32768; // Normalize to -1 to 1
          sumSquares += normalized * normalized;
        }
        const rms = Math.sqrt(sumSquares / samples.length);
        
        // Normalize to 0-1 range (multiply by 4 for sensitivity)
        const level = Math.min(1, rms * 4);
        
        // Send to renderer
        mainWindow.webContents.send('audio-level', { level });
      }
    });
    
    audioStream.on('error', (err) => {
      console.error('[LEOPARD] Audio stream error:', err.message);
    });
    
    // Store the chunks collector for later use
    leopardRecording.audioChunks = audioChunks;
    
    console.log('[LEOPARD] Recording started');
    return { success: true };
    
  } catch (e) {
    console.error('[LEOPARD] Failed to start recording:', e.message);
    return { success: false, error: e.message };
  }
}

async function stopNativeLeopardRecording() {
  if (!leopardRecording) {
    console.log('[LEOPARD] No active recording');
    return { success: false, error: 'No active recording' };
  }
  
  try {
    console.log('[LEOPARD] Stopping recording and transcribing...');
    
    // Get collected audio chunks
    const audioChunks = leopardRecording.audioChunks || [];
    
    // Stop recording
    leopardRecording.stop();
    leopardRecording = null;
    
    if (audioChunks.length === 0) {
      console.log('[LEOPARD] No audio recorded');
      return { success: false, error: 'No audio recorded' };
    }
    
    // Combine audio chunks into a single buffer
    const audioBuffer = Buffer.concat(audioChunks);
    console.log('[LEOPARD] Audio buffer size:', audioBuffer.length, 'bytes');
    
    // Convert to Int16Array for Leopard
    const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
    
    // Transcribe with Leopard
    console.log('[LEOPARD] Transcribing', samples.length, 'samples...');
    const result = leopardHandle.process(samples);
    
    console.log('[LEOPARD] Transcription:', result.transcript);
    
    return {
      success: true,
      transcript: result.transcript,
      words: result.words,
      audioBytes: audioBuffer.length,
      samples: samples.length
    };
    
  } catch (e) {
    console.error('[LEOPARD] Transcription failed:', e.message);
    if (leopardRecording) {
      leopardRecording.stop();
      leopardRecording = null;
    }
    return { success: false, error: e.message };
  }
}

function releaseLeopard() {
  if (leopardRecording) {
    leopardRecording.stop();
    leopardRecording = null;
  }
  if (leopardHandle) {
    leopardHandle.release();
    leopardHandle = null;
  }
  console.log('[LEOPARD] Released');
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

  // Push-to-Talk shortcut (customizable, defaults to Cmd+Shift+Space)
  // Tracks state to toggle recording on/off
  let pttRecording = false;
  const pttShortcut = store.get('pttShortcut') || 'CommandOrControl+Shift+Space';
  console.log('[PTT] Registering shortcut:', pttShortcut);
  
  globalShortcut.register(pttShortcut, () => {
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

  // ========== SYSTEM PREFERENCES ==========
  
  // Open Accessibility settings
  ipcMain.handle('open-accessibility-settings', async () => {
    try {
      if (process.platform === 'darwin') {
        exec('open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"');
        return { success: true };
      }
      return { success: false, error: 'Not macOS' };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Check Accessibility permission (approximate - can't directly check)
  ipcMain.handle('check-accessibility', async () => {
    try {
      if (process.platform === 'darwin') {
        // Try a harmless AppleScript to test if we have accessibility
        const result = execSync('osascript -e "tell application \\"System Events\\" to get name of first process"', { timeout: 2000 });
        return { granted: true };
      }
      return { granted: true };
    } catch (e) {
      return { granted: false, error: e.message };
    }
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
  
  // ========== NATIVE WAKE WORD IPC HANDLERS ==========
  
  // Check if native wake word is available
  ipcMain.handle('porcupine-available', () => {
    return { available: Porcupine !== null && portAudio !== null };
  });
  
  // Get available keywords
  ipcMain.handle('porcupine-keywords', () => {
    if (!BuiltinKeyword) {
      return { keywords: [] };
    }
    return { keywords: Object.keys(BuiltinKeyword) };
  });
  
  // Start native wake word listening (captures audio in main process)
  ipcMain.handle('porcupine-start', async (event, { accessKey, keyword }) => {
    console.log('[IPC] Starting native wake word with keyword:', keyword);
    return startNativeWakeWordListening(accessKey, keyword);
  });
  
  // Stop native wake word listening
  ipcMain.handle('porcupine-stop', async () => {
    console.log('[IPC] Stopping native wake word');
    return stopNativeWakeWordListening();
  });
  
  // Check if currently listening
  ipcMain.handle('porcupine-status', () => {
    return { listening: porcupineListening };
  });
  
  // ========== NATIVE LEOPARD SPEECH-TO-TEXT ==========
  
  // Check if Leopard is available
  ipcMain.handle('leopard-available', () => {
    return { available: !!Leopard && !!record };
  });
  
  // Start recording for transcription
  ipcMain.handle('leopard-start', async (event, { accessKey }) => {
    console.log('[IPC] Starting Leopard recording');
    return await startNativeLeopardRecording(accessKey);
  });
  
  // Stop recording and get transcription
  ipcMain.handle('leopard-stop', async () => {
    console.log('[IPC] Stopping Leopard recording and transcribing');
    return await stopNativeLeopardRecording();
  });
  
  // Check if currently recording
  ipcMain.handle('leopard-recording', () => {
    return { recording: !!leopardRecording };
  });
  
  // ========== KEYBIND SETTINGS ==========
  
  // Update the push-to-talk shortcut
  ipcMain.handle('update-ptt-shortcut', (event, keybind) => {
    console.log('[IPC] Updating PTT shortcut to:', keybind);
    
    try {
      // Unregister old PTT shortcut
      globalShortcut.unregister('CommandOrControl+Shift+Space');
      
      // Get current custom PTT shortcut from store and unregister it too
      const oldPTT = store.get('pttShortcut');
      if (oldPTT && oldPTT !== keybind) {
        try { globalShortcut.unregister(oldPTT); } catch (e) {}
      }
      
      // Register new shortcut
      const registered = globalShortcut.register(keybind, () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('start-recording');
        }
      });
      
      if (registered) {
        store.set('pttShortcut', keybind);
        console.log('[PTT] Shortcut registered:', keybind);
        return { success: true };
      } else {
        console.error('[PTT] Failed to register shortcut:', keybind);
        return { success: false, error: 'Shortcut already in use' };
      }
    } catch (e) {
      console.error('[PTT] Error updating shortcut:', e.message);
      return { success: false, error: e.message };
    }
  });
  
  // Get current PTT shortcut
  ipcMain.handle('get-ptt-shortcut', () => {
    return store.get('pttShortcut') || 'CommandOrControl+Shift+Space';
  });

  // ========== AGENT WATCHER ==========
  
  // Start watching a directory for agent activity
  ipcMain.handle('agent-watcher-start', async (event, { watchPath, idleThreshold }) => {
    console.log('[IPC] Starting agent watcher for:', watchPath);
    try {
      const result = startAgentWatcher(watchPath, { idleThreshold });
      store.set('agentWatcherPath', watchPath);
      return result;
    } catch (e) {
      console.error('[IPC] Agent watcher start error:', e);
      return { success: false, error: e.message };
    }
  });

  // Stop the agent watcher
  ipcMain.handle('agent-watcher-stop', async () => {
    console.log('[IPC] Stopping agent watcher');
    return stopAgentWatcher();
  });

  // Get agent watcher status
  ipcMain.handle('agent-watcher-status', async () => {
    return getAgentWatcherStatus();
  });

  // Get last watched path
  ipcMain.handle('agent-watcher-get-path', async () => {
    return store.get('agentWatcherPath') || null;
  });

  // ========== WINDOW WATCHER (Universal AI Detection) ==========

  // Get list of running applications
  ipcMain.handle('window-watcher-apps', async () => {
    console.log('[IPC] Getting running apps');
    return getRunningApps();
  });

  // Start watching a specific app window
  ipcMain.handle('window-watcher-start', async (event, { appName, idleThreshold, captureInterval, windowSelector }) => {
    console.log('[IPC] Starting window watcher for:', appName, 'window:', windowSelector);
    try {
      const result = startWindowWatcher(appName, { idleThreshold, captureInterval, windowSelector });
      if (result.success) {
        store.set('windowWatcherApp', appName);
        store.set('windowWatcherSelector', windowSelector);
      }
      return result;
    } catch (e) {
      console.error('[IPC] Window watcher start error:', e);
      return { success: false, error: e.message };
    }
  });

  // Stop the window watcher
  ipcMain.handle('window-watcher-stop', async () => {
    console.log('[IPC] Stopping window watcher');
    return stopWindowWatcher();
  });

  // Get window watcher status
  ipcMain.handle('window-watcher-status', async () => {
    return getWindowWatcherStatus();
  });

  // Get window info for a specific app
  ipcMain.handle('window-watcher-info', async (event, appName) => {
    return getWindowInfo(appName);
  });

  // List all windows for an app
  ipcMain.handle('window-watcher-list-windows', async (event, appName) => {
    const realAppName = findAppByName(appName);
    if (!realAppName) {
      return { success: false, error: `App "${appName}" not found`, runningApps: getRunningApps() };
    }
    const windows = getAllWindows(realAppName);
    return { success: true, app: realAppName, windows };
  });

  // Get last watched app
  ipcMain.handle('window-watcher-get-app', async () => {
    return store.get('windowWatcherApp') || null;
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

// Handle renderer crashes
app.on('render-process-gone', (event, webContents, details) => {
  console.error('[CRASH] Renderer process gone:', details.reason, details.exitCode);
  console.error('[CRASH] Details:', JSON.stringify(details));
});

// Handle GPU process crash
app.on('child-process-gone', (event, details) => {
  console.error('[CRASH] Child process gone:', details.type, details.reason);
});
