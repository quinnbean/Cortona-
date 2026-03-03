const vscode = require('vscode');
const http = require('http');

// ============================================================================
// CORTONA AI WATCHER - Cursor Extension
// Detects AI agent activity and notifies Cortona desktop app
// With heartbeat system for reliable connection and remote enable/disable
// ============================================================================

let isWatching = false;
let isAgentWorking = false;
let lastEditTime = 0;
let lastEditFile = '';
let editCount = 0;
let idleCheckInterval = null;
let statusBarItem = null;

// Connection state (circuit breaker pattern)
let isServerConnected = false;
let isExtensionEnabled = true;
let heartbeatInterval = null;
let consecutiveFailures = 0;
const MAX_FAILURES = 3;  // After 3 failures, stop trying until heartbeat succeeds

// Configuration
const CONFIG = {
    serverUrl: 'http://localhost:5050',
    heartbeatInterval: 5000,   // 5 seconds between heartbeats
    heartbeatTimeout: 500,     // 500ms timeout (fail fast!)
    eventTimeout: 1000,        // 1s timeout for events
    idleThreshold: 3000,       // 3 seconds of no edits = done
    burstThreshold: 5,         // 5+ rapid edits = likely AI agent
    burstWindow: 1000,         // Within 1 second
};

// ============================================================================
// ACTIVATION
// ============================================================================

function activate(context) {
    console.log('[Cortona] Extension activated!');
    
    // Load config
    const config = vscode.workspace.getConfiguration('cortona');
    CONFIG.serverUrl = config.get('serverUrl', CONFIG.serverUrl);
    CONFIG.idleThreshold = config.get('idleThreshold', CONFIG.idleThreshold);
    
    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.text = '$(eye) Cortona';
    statusBarItem.tooltip = 'Cortona AI Watcher - Connecting...';
    statusBarItem.command = 'cortona.toggleWatching';
    context.subscriptions.push(statusBarItem);
    statusBarItem.show();
    
    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('cortona.startWatching', startWatching),
        vscode.commands.registerCommand('cortona.stopWatching', stopWatching),
        vscode.commands.registerCommand('cortona.toggleWatching', () => {
            if (isWatching) {
                stopWatching();
            } else {
                startWatching();
            }
        }),
        vscode.commands.registerCommand('cortona.notifyNow', () => {
            notifyCortona('test', { message: 'Manual test notification' });
            vscode.window.showInformationMessage('Cortona: Test notification sent!');
        })
    );
    
    // ========================================================================
    // EVENT WATCHERS
    // ========================================================================
    
    // Watch for document changes (AI typing)
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument((event) => {
            if (!shouldSendEvents()) return;
            if (event.document.uri.scheme !== 'file') return;
            
            const now = Date.now();
            const fileName = event.document.fileName;
            
            // Count rapid edits (likely AI agent)
            if (now - lastEditTime < CONFIG.burstWindow) {
                editCount++;
            } else {
                editCount = 1;
            }
            
            lastEditTime = now;
            lastEditFile = fileName;
            
            // Detect agent starting (burst of edits)
            if (!isAgentWorking && editCount >= CONFIG.burstThreshold) {
                isAgentWorking = true;
                updateStatusBar('working');
                notifyCortona('agent_started', {
                    file: fileName,
                    editCount: editCount
                });
                console.log('[Cortona] AI agent started working!');
            }
        })
    );
    
    // Watch for file saves
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument((document) => {
            if (!shouldSendEvents()) return;
            
            notifyCortona('file_saved', {
                file: document.fileName,
                languageId: document.languageId
            });
            console.log('[Cortona] File saved:', document.fileName);
        })
    );
    
    // Watch for file creation
    context.subscriptions.push(
        vscode.workspace.onDidCreateFiles((event) => {
            if (!shouldSendEvents()) return;
            
            const files = event.files.map(f => f.fsPath);
            notifyCortona('files_created', { files });
            console.log('[Cortona] Files created:', files);
        })
    );
    
    // Watch for terminal output
    context.subscriptions.push(
        vscode.window.onDidWriteTerminalData((event) => {
            if (!shouldSendEvents()) return;
            
            const data = event.data;
            
            // Detect common completion patterns
            const completionPatterns = [
                /done/i,
                /completed/i,
                /finished/i,
                /success/i,
                /built in/i,
                /compiled/i,
                /\$ $/,  // Shell prompt returned
            ];
            
            const errorPatterns = [
                /error/i,
                /failed/i,
                /exception/i,
            ];
            
            for (const pattern of completionPatterns) {
                if (pattern.test(data)) {
                    notifyCortona('terminal_done', { output: data.substring(0, 200) });
                    break;
                }
            }
            
            for (const pattern of errorPatterns) {
                if (pattern.test(data)) {
                    notifyCortona('terminal_error', { output: data.substring(0, 200) });
                    break;
                }
            }
        })
    );
    
    // Watch for diagnostics (errors/warnings)
    context.subscriptions.push(
        vscode.languages.onDidChangeDiagnostics((event) => {
            if (!shouldSendEvents()) return;
            
            // Count errors across changed files
            let errorCount = 0;
            let warningCount = 0;
            
            for (const uri of event.uris) {
                const diagnostics = vscode.languages.getDiagnostics(uri);
                for (const d of diagnostics) {
                    if (d.severity === vscode.DiagnosticSeverity.Error) errorCount++;
                    if (d.severity === vscode.DiagnosticSeverity.Warning) warningCount++;
                }
            }
            
            if (errorCount > 0) {
                notifyCortona('diagnostics_error', { errors: errorCount, warnings: warningCount });
            }
        })
    );
    
    // Start heartbeat immediately
    startHeartbeat();
    
    // Auto-start watching if configured
    if (config.get('autoWatch', true)) {
        startWatching();
    }
}

// ============================================================================
// CIRCUIT BREAKER - Should we send events?
// ============================================================================

function shouldSendEvents() {
    // Must be watching, server must be connected, and extension must be enabled
    return isWatching && isServerConnected && isExtensionEnabled;
}

// ============================================================================
// HEARTBEAT SYSTEM
// ============================================================================

function startHeartbeat() {
    // Send immediate heartbeat
    sendHeartbeat();
    
    // Then send every 5 seconds
    heartbeatInterval = setInterval(sendHeartbeat, CONFIG.heartbeatInterval);
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

function sendHeartbeat() {
    const payload = JSON.stringify({
        type: 'cursor',
        workspace: vscode.workspace.name || 'unknown',
        version: '1.1.0'
    });
    
    const url = new URL(CONFIG.serverUrl + '/api/extension/heartbeat');
    
    const options = {
        hostname: url.hostname,
        port: url.port || 5050,
        path: url.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
        },
        timeout: CONFIG.heartbeatTimeout  // Fast timeout!
    };
    
    const req = http.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
            try {
                const response = JSON.parse(data);
                
                // Update connection state
                const wasConnected = isServerConnected;
                isServerConnected = true;
                consecutiveFailures = 0;
                
                // Update enabled state from server
                const wasEnabled = isExtensionEnabled;
                isExtensionEnabled = response.enabled !== false;
                
                // Log state changes
                if (!wasConnected) {
                    console.log('[Cortona] Connected to server');
                }
                if (wasEnabled !== isExtensionEnabled) {
                    console.log(`[Cortona] Extension ${isExtensionEnabled ? 'enabled' : 'disabled'} by server`);
                }
                
                // Update status bar
                updateStatusBar(isWatching ? (isAgentWorking ? 'working' : 'watching') : 'off');
                
            } catch (e) {
                // Couldn't parse response, but connection worked
                isServerConnected = true;
                consecutiveFailures = 0;
            }
        });
    });
    
    req.on('error', (e) => {
        consecutiveFailures++;
        if (consecutiveFailures >= MAX_FAILURES && isServerConnected) {
            isServerConnected = false;
            console.log('[Cortona] Server disconnected (heartbeat failed)');
            updateStatusBar('disconnected');
        }
    });
    
    req.on('timeout', () => {
        req.destroy();
        consecutiveFailures++;
        if (consecutiveFailures >= MAX_FAILURES && isServerConnected) {
            isServerConnected = false;
            console.log('[Cortona] Server disconnected (heartbeat timeout)');
            updateStatusBar('disconnected');
        }
    });
    
    req.write(payload);
    req.end();
}

// ============================================================================
// WATCHING CONTROL
// ============================================================================

function startWatching() {
    if (isWatching) return;
    
    isWatching = true;
    isAgentWorking = false;
    lastEditTime = 0;
    editCount = 0;
    
    updateStatusBar(isServerConnected ? 'watching' : 'disconnected');
    
    // Start idle check interval
    idleCheckInterval = setInterval(() => {
        if (!isAgentWorking) return;
        if (!shouldSendEvents()) return;
        
        const idleTime = Date.now() - lastEditTime;
        
        if (idleTime >= CONFIG.idleThreshold) {
            // Agent has been idle - it's done!
            isAgentWorking = false;
            updateStatusBar('done');
            
            notifyCortona('agent_finished', {
                file: lastEditFile,
                idleTime: idleTime
            });
            
            console.log('[Cortona] AI agent finished! Idle for', idleTime, 'ms');
            
            // Reset status after a moment
            setTimeout(() => {
                if (isWatching && !isAgentWorking) {
                    updateStatusBar(isServerConnected ? 'watching' : 'disconnected');
                }
            }, 3000);
        }
    }, 500);
    
    if (isServerConnected) {
        notifyCortona('watching_started', { workspace: vscode.workspace.name });
    }
    
    console.log('[Cortona] Started watching');
}

function stopWatching() {
    if (!isWatching) return;
    
    isWatching = false;
    isAgentWorking = false;
    
    if (idleCheckInterval) {
        clearInterval(idleCheckInterval);
        idleCheckInterval = null;
    }
    
    updateStatusBar('off');
    
    if (isServerConnected) {
        notifyCortona('watching_stopped', {});
    }
    
    console.log('[Cortona] Stopped watching');
}

// ============================================================================
// STATUS BAR
// ============================================================================

function updateStatusBar(state) {
    if (!statusBarItem) return;
    
    switch (state) {
        case 'off':
            statusBarItem.text = '$(eye-closed) Cortona';
            statusBarItem.tooltip = 'Cortona: Click to start watching';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'disconnected':
            statusBarItem.text = '$(debug-disconnect) Cortona';
            statusBarItem.tooltip = 'Cortona: Server not connected';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'watching':
            if (!isExtensionEnabled) {
                statusBarItem.text = '$(eye-closed) Cortona (disabled)';
                statusBarItem.tooltip = 'Cortona: Disabled by server';
                statusBarItem.backgroundColor = undefined;
            } else {
                statusBarItem.text = '$(eye) Cortona';
                statusBarItem.tooltip = 'Cortona: Watching for AI activity';
                statusBarItem.backgroundColor = undefined;
            }
            break;
        case 'working':
            statusBarItem.text = '$(sync~spin) Cortona: AI Working...';
            statusBarItem.tooltip = 'Cortona: AI agent detected';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            break;
        case 'done':
            statusBarItem.text = '$(check) Cortona: Done!';
            statusBarItem.tooltip = 'Cortona: AI agent finished';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
            break;
    }
    
    statusBarItem.show();
}

// ============================================================================
// CORTONA COMMUNICATION
// ============================================================================

function notifyCortona(event, data) {
    // Circuit breaker: don't even try if we know server is down
    if (!isServerConnected) {
        return;
    }
    
    // Don't send if disabled by server
    if (!isExtensionEnabled && event !== 'watching_started' && event !== 'watching_stopped') {
        return;
    }
    
    const payload = JSON.stringify({
        type: 'cursor_extension',
        event: event,
        data: data,
        timestamp: Date.now(),
        workspace: vscode.workspace.name || 'unknown'
    });
    
    const url = new URL(CONFIG.serverUrl + '/api/cursor-event');
    
    const options = {
        hostname: url.hostname,
        port: url.port || 5050,
        path: url.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
        },
        timeout: CONFIG.eventTimeout
    };
    
    const req = http.request(options, (res) => {
        // Success - server received the event
    });
    
    req.on('error', (e) => {
        // Event failed - heartbeat will handle reconnection
    });
    
    req.on('timeout', () => {
        req.destroy();
    });
    
    req.write(payload);
    req.end();
}

// ============================================================================
// DEACTIVATION
// ============================================================================

function deactivate() {
    stopHeartbeat();
    stopWatching();
    if (isServerConnected) {
        notifyCortona('extension_deactivated', {});
    }
    console.log('[Cortona] Extension deactivated');
}

module.exports = {
    activate,
    deactivate
};
