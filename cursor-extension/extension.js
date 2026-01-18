const vscode = require('vscode');
const http = require('http');

// ============================================================================
// CORTONA AI WATCHER - Cursor Extension
// Detects AI agent activity and notifies Cortona desktop app
// ============================================================================

let isWatching = false;
let isAgentWorking = false;
let lastEditTime = 0;
let lastEditFile = '';
let editCount = 0;
let idleCheckInterval = null;
let statusBarItem = null;

// Configuration
const CONFIG = {
    serverUrl: 'http://localhost:5050',
    idleThreshold: 3000,  // 3 seconds of no edits = done
    burstThreshold: 5,    // 5+ rapid edits = likely AI agent
    burstWindow: 1000,    // Within 1 second
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
    statusBarItem.tooltip = 'Cortona AI Watcher';
    statusBarItem.command = 'cortona.startWatching';
    context.subscriptions.push(statusBarItem);
    
    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('cortona.startWatching', startWatching),
        vscode.commands.registerCommand('cortona.stopWatching', stopWatching),
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
            if (!isWatching) return;
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
            if (!isWatching) return;
            
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
            if (!isWatching) return;
            
            const files = event.files.map(f => f.fsPath);
            notifyCortona('files_created', { files });
            console.log('[Cortona] Files created:', files);
        })
    );
    
    // Watch for terminal output
    context.subscriptions.push(
        vscode.window.onDidWriteTerminalData((event) => {
            if (!isWatching) return;
            
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
            if (!isWatching) return;
            
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
    
    // Auto-start if configured
    if (config.get('autoWatch', true)) {
        startWatching();
    }
    
    // Notify Cortona that extension is ready
    notifyCortona('extension_ready', { 
        workspace: vscode.workspace.name,
        version: '1.0.0'
    });
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
    
    updateStatusBar('watching');
    
    // Start idle check interval
    idleCheckInterval = setInterval(() => {
        if (!isAgentWorking) return;
        
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
                    updateStatusBar('watching');
                }
            }, 3000);
        }
    }, 500);
    
    notifyCortona('watching_started', { workspace: vscode.workspace.name });
    vscode.window.showInformationMessage('Cortona: Now watching for AI activity');
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
    
    notifyCortona('watching_stopped', {});
    vscode.window.showInformationMessage('Cortona: Stopped watching');
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
            statusBarItem.backgroundColor = undefined;
            statusBarItem.command = 'cortona.startWatching';
            break;
        case 'watching':
            statusBarItem.text = '$(eye) Cortona';
            statusBarItem.backgroundColor = undefined;
            statusBarItem.command = 'cortona.stopWatching';
            break;
        case 'working':
            statusBarItem.text = '$(sync~spin) Cortona: AI Working...';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            break;
        case 'done':
            statusBarItem.text = '$(check) Cortona: Done!';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
            break;
    }
    
    statusBarItem.show();
}

// ============================================================================
// CORTONA COMMUNICATION
// ============================================================================

function notifyCortona(event, data) {
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
        timeout: 2000
    };
    
    const req = http.request(options, (res) => {
        // Response received - Cortona is running
    });
    
    req.on('error', (e) => {
        // Cortona might not be running - that's okay
        // Don't spam console with errors
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
    stopWatching();
    notifyCortona('extension_deactivated', {});
    console.log('[Cortona] Extension deactivated');
}

module.exports = {
    activate,
    deactivate
};
