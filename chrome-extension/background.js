// Cortona AI Watcher - Background Service Worker
// Receives events from content scripts and forwards to Cortona desktop app

console.log('[Cortona Background] Service worker started');

// ============================================================================
// CONFIGURATION
// ============================================================================

const CORTONA_BASE_URL = 'http://localhost:5001';
const CORTONA_EVENT_URL = CORTONA_BASE_URL + '/api/chrome-event';
const CORTONA_HEARTBEAT_URL = CORTONA_BASE_URL + '/api/extension/heartbeat';
const HEARTBEAT_INTERVAL = 2000; // 2 seconds for faster command delivery

// Track active watchers
const activeWatchers = new Map();

// Connection state
let isServerConnected = false;
let isExtensionEnabled = true;
let autoFocusEnabled = false;  // Auto-focus tab when AI finishes

// Load settings from storage
chrome.storage.local.get(['autoFocus'], (result) => {
  autoFocusEnabled = result.autoFocus || false;
  console.log('[Cortona Background] Auto-focus:', autoFocusEnabled);
});

// Listen for settings changes
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (changes.autoFocus) {
    autoFocusEnabled = changes.autoFocus.newValue;
    console.log('[Cortona Background] Auto-focus changed to:', autoFocusEnabled);
  }
});

// ============================================================================
// HEARTBEAT SYSTEM
// ============================================================================

async function sendHeartbeat() {
  try {
    console.log('[Cortona Background] Sending heartbeat to', CORTONA_HEARTBEAT_URL);
    const response = await fetch(CORTONA_HEARTBEAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'chrome',
        version: '1.1.0',
        activeWatchers: activeWatchers.size
      })
    });
    
    console.log('[Cortona Background] Heartbeat response:', response.status);
    
    if (response.ok) {
      const data = await response.json();
      const wasConnected = isServerConnected;
      isServerConnected = true;
      isExtensionEnabled = data.enabled !== false;
      
      if (!wasConnected) {
        console.log('[Cortona Background] Connected to server');
        updateBadge('connected');
        
        // Scan for existing AI tabs now that we're connected
        console.log('[Cortona Background] Scanning for existing AI tabs on connect...');
        setTimeout(scanExistingAiTabs, 500);
      }
      
      // Process any pending commands
      if (data.commands && data.commands.length > 0) {
        console.log('[Cortona Background] Received commands:', data.commands.length);
        for (const cmd of data.commands) {
          if (cmd.type === 'get_response') {
            // Handle get response command
            handleGetResponse(cmd.ai);
          } else if (cmd.type === 'rescan_tabs') {
            // Rescan for AI tabs
            console.log('[Cortona Background] Received rescan_tabs command');
            scanExistingAiTabs();
          } else if (cmd.type === 'watch_ai') {
            // Start watching specific AI
            console.log('[Cortona Background] Received watch_ai command for:', cmd.ai);
            startWatchingAi(cmd.ai);
          } else if (cmd.ai && cmd.text) {
            handleSendToAi(cmd.ai, cmd.text);
          }
        }
      }
    } else {
      console.log('[Cortona Background] Heartbeat failed:', response.status);
      handleDisconnect();
    }
  } catch (e) {
    console.log('[Cortona Background] Heartbeat error:', e.message);
    handleDisconnect();
  }
}

function handleDisconnect() {
  if (isServerConnected) {
    console.log('[Cortona Background] Disconnected from server');
    isServerConnected = false;
    updateBadge('disconnected');
  }
}

function updateBadge(state) {
  if (state === 'connected') {
    chrome.action.setBadgeText({ text: '✓' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else if (state === 'disconnected') {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#666' });
  }
}

// ============================================================================
// HEARTBEAT USING ALARMS (persists across service worker suspension)
// ============================================================================

// Start heartbeat immediately
sendHeartbeat();

// Use setInterval for frequent heartbeats (works while service worker is active)
setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);

// Use Chrome alarms to wake up service worker periodically (minimum 1 min in production)
// This ensures the service worker doesn't stay suspended forever
chrome.alarms.create('cortona-keepalive', {
  delayInMinutes: 0.5,   // First alarm in 30 seconds
  periodInMinutes: 0.5   // Then every 30 seconds
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'cortona-keepalive') {
    console.log('[Cortona Background] Keepalive alarm - sending heartbeat');
    sendHeartbeat();
    // Scan for AI tabs in case we missed any while suspended
    if (isServerConnected) {
      scanExistingAiTabs();
    }
  }
});

// Also send heartbeat when service worker wakes up from any event
chrome.runtime.onStartup.addListener(() => {
  console.log('[Cortona Background] Browser started, connecting to Cortona...');
  sendHeartbeat();
  setTimeout(scanExistingAiTabs, 1000);
});

// Send heartbeat when extension is installed/updated
chrome.runtime.onInstalled.addListener(() => {
  console.log('[Cortona Background] Extension installed/updated, connecting...');
  sendHeartbeat();
  setTimeout(scanExistingAiTabs, 1000);
  
  // Re-create alarm in case it was lost
  chrome.alarms.create('cortona-keepalive', {
    delayInMinutes: 0.5,
    periodInMinutes: 0.5
  });
});

// ============================================================================
// SCAN FOR EXISTING AI TABS ON STARTUP
// ============================================================================

const AI_URL_PATTERNS = [
  'chat.openai.com',
  'chatgpt.com', 
  'claude.ai',
  'gemini.google.com',
  'perplexity.ai',
  'www.perplexity.ai',
  'poe.com'
];

async function scanExistingAiTabs() {
  console.log('[Cortona Background] Scanning for existing AI tabs... (connected=' + isServerConnected + ')');
  
  // Don't scan if not connected - the events won't be forwarded anyway
  if (!isServerConnected) {
    console.log('[Cortona Background] Not connected to server, skipping scan');
    return;
  }
  
  try {
    const tabs = await chrome.tabs.query({});
    console.log('[Cortona Background] Found', tabs.length, 'total tabs');
    let aiTabsFound = 0;
    
    for (const tab of tabs) {
      if (!tab.url) continue;
      
      const isAiTab = AI_URL_PATTERNS.some(pattern => tab.url.includes(pattern));
      if (isAiTab) {
        console.log('[Cortona Background] Found AI tab:', tab.id, tab.url);
        aiTabsFound++;
        
        // Determine AI name from URL
        const aiName = tab.url.includes('claude') ? 'Claude' :
                      tab.url.includes('chatgpt') || tab.url.includes('openai') ? 'ChatGPT' :
                      tab.url.includes('gemini') ? 'Gemini' :
                      tab.url.includes('perplexity') ? 'Perplexity' :
                      tab.url.includes('poe') ? 'Poe' : 'Unknown';
        
        // Try to check if content script is already running
        try {
          await chrome.tabs.sendMessage(tab.id, { type: 'ping' });
          console.log('[Cortona Background] Content script already active on tab', tab.id);
          
          // IMPORTANT: Still notify Cortona about this existing tab!
          forwardToCortona({
            type: 'ai_activity',
            event: 'tab_opened',
            ai: aiName,
            url: tab.url,
            timestamp: Date.now()
          });
          console.log('[Cortona Background] Notified Cortona about existing', aiName, 'tab');
          
        } catch (e) {
          // Content script not running, inject it
          console.log('[Cortona Background] Injecting content script into tab', tab.id);
          try {
            await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              files: ['content.js']
            });
            console.log('[Cortona Background] Successfully injected into tab', tab.id);
            
            // Notify Cortona that we found an existing AI tab
            forwardToCortona({
              type: 'ai_activity',
              event: 'tab_opened',
              ai: aiName,
              url: tab.url,
              timestamp: Date.now()
            });
            
          } catch (injectErr) {
            console.log('[Cortona Background] Could not inject into tab', tab.id, ':', injectErr.message);
          }
        }
      }
    }
    
    console.log('[Cortona Background] Found', aiTabsFound, 'AI tabs');
  } catch (e) {
    console.log('[Cortona Background] Error scanning tabs:', e.message);
  }
}

// Scan on startup
scanExistingAiTabs();

// ============================================================================
// START WATCHING SPECIFIC AI
// ============================================================================

async function startWatchingAi(aiName) {
  console.log('[Cortona Background] Starting to watch:', aiName);
  
  const aiSites = {
    'chatgpt': ['chat.openai.com', 'chatgpt.com'],
    'claude': ['claude.ai'],
    'gemini': ['gemini.google.com'],
    'perplexity': ['perplexity.ai', 'www.perplexity.ai'],
    'poe': ['poe.com']
  };
  
  const targetSites = aiSites[aiName.toLowerCase()] || [];
  if (targetSites.length === 0) {
    console.log('[Cortona Background] Unknown AI:', aiName);
    return;
  }
  
  try {
    const tabs = await chrome.tabs.query({});
    let foundTab = null;
    
    for (const tab of tabs) {
      if (!tab.url) continue;
      
      for (const site of targetSites) {
        if (tab.url.includes(site)) {
          foundTab = tab;
          break;
        }
      }
      if (foundTab) break;
    }
    
    if (foundTab) {
      console.log('[Cortona Background] Found', aiName, 'tab:', foundTab.id);
      
      // Ensure content script is running
      try {
        await chrome.tabs.sendMessage(foundTab.id, { type: 'ping' });
      } catch (e) {
        // Inject content script if not running
        await chrome.scripting.executeScript({
          target: { tabId: foundTab.id },
          files: ['content.js']
        });
      }
      
      // Tell content script to start active watching
      chrome.tabs.sendMessage(foundTab.id, { 
        type: 'start_watching',
        ai: aiName 
      });
      
      // Notify Cortona that we're watching
      forwardToCortona({
        type: 'ai_activity',
        event: 'watching_started',
        ai: aiName,
        url: foundTab.url,
        timestamp: Date.now()
      });
      
      console.log('[Cortona Background] Now actively watching', aiName);
    } else {
      console.log('[Cortona Background] No tab found for', aiName);
      
      // Notify Cortona that we couldn't find the tab
      forwardToCortona({
        type: 'ai_activity',
        event: 'tab_not_found',
        ai: aiName,
        timestamp: Date.now()
      });
    }
  } catch (e) {
    console.log('[Cortona Background] Error starting watch:', e.message);
  }
}

// ============================================================================
// MESSAGE HANDLING
// ============================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[Cortona Background] Received:', message.type, message);
  
  if (message.type === 'watcher_active') {
    // A content script is now watching an AI site
    const tabId = sender.tab?.id;
    if (tabId) {
      activeWatchers.set(tabId, {
        site: message.site,
        url: message.url,
        startTime: Date.now()
      });
      console.log('[Cortona Background] Watcher active on', message.site);
      
      // Update badge
      chrome.action.setBadgeText({ text: '👁', tabId });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50', tabId });
      
      // Notify Cortona that an AI tab is open
      forwardToCortona({
        type: 'ai_activity',
        event: 'tab_opened',
        ai: message.site,
        url: message.url,
        timestamp: Date.now()
      });
    }
  }
  
  if (message.type === 'ai_activity') {
    // AI started or finished responding
    if (isServerConnected && isExtensionEnabled) {
      forwardToCortona(message);
    }
    
    // Update badge based on state
    const tabId = sender.tab?.id;
    if (tabId) {
      if (message.event === 'started') {
        chrome.action.setBadgeText({ text: '⚡', tabId });
        chrome.action.setBadgeBackgroundColor({ color: '#FF9800', tabId });
      } else if (message.event === 'finished') {
        chrome.action.setBadgeText({ text: '✓', tabId });
        chrome.action.setBadgeBackgroundColor({ color: '#4CAF50', tabId });
        
        // Show notification
        showNotification(message.ai + ' finished responding');
        
        // Auto-focus the tab if enabled
        if (autoFocusEnabled) {
          chrome.tabs.update(tabId, { active: true });
          chrome.windows.update(sender.tab.windowId, { focused: true });
          console.log('[Cortona Background] Auto-focused tab:', tabId);
        }
      }
    }
  }
  
  // Handle status request from popup
  if (message.type === 'get_status') {
    sendResponse({
      connected: isServerConnected,
      enabled: isExtensionEnabled,
      activeWatchers: activeWatchers.size
    });
  }
  
  // Handle send_to_ai request (from Cortona via external message)
  if (message.type === 'send_to_ai') {
    handleSendToAi(message.ai, message.text);
  }
  
  // Handle get_last_response request
  if (message.type === 'get_last_response') {
    getLastResponseFromAi(message.ai).then(sendResponse);
    return true; // Async response
  }
  
  return true;
});

// Handle get response command - gets response and sends to Cortona
async function handleGetResponse(aiName) {
  console.log('[Cortona Background] Getting response to send to Cortona');
  const result = await getLastResponseFromAi(aiName);
  
  // Send the response back to Cortona via the event API
  try {
    await fetch(CORTONA_EVENT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'ai_response',
        event: 'response_received',
        ai: result.ai || aiName || 'AI',
        response: result.response || '',
        success: result.success,
        error: result.error,
        timestamp: Date.now()
      })
    });
    console.log('[Cortona Background] Sent response to Cortona');
  } catch (e) {
    console.log('[Cortona Background] Failed to send response:', e);
  }
}

// Get the last response from an AI tab
async function getLastResponseFromAi(aiName) {
  console.log('[Cortona Background] Getting last response from', aiName || 'any AI');
  
  const aiSites = {
    'chatgpt': ['chat.openai.com', 'chatgpt.com'],
    'claude': ['claude.ai'],
    'gemini': ['gemini.google.com'],
    'perplexity': ['perplexity.ai', 'www.perplexity.ai'],
    'poe': ['poe.com']
  };
  
  // If specific AI requested, look for that
  let targetSites = [];
  if (aiName) {
    targetSites = aiSites[aiName.toLowerCase()] || [];
  } else {
    // Look for any AI site
    targetSites = Object.values(aiSites).flat();
  }
  
  const tabs = await chrome.tabs.query({});
  let targetTab = null;
  
  for (const tab of tabs) {
    if (tab.url) {
      for (const site of targetSites) {
        if (tab.url.includes(site)) {
          targetTab = tab;
          break;
        }
      }
      if (targetTab) break;
    }
  }
  
  if (!targetTab) {
    return { success: false, error: 'No AI tab found' };
  }
  
  try {
    const response = await chrome.tabs.sendMessage(targetTab.id, {
      type: 'get_last_response'
    });
    return response;
  } catch (e) {
    console.log('[Cortona Background] Error getting response:', e);
    return { success: false, error: e.message };
  }
}

// Handle external messages from Cortona (via native messaging or fetch)
chrome.runtime.onMessageExternal?.addListener((message, sender, sendResponse) => {
  console.log('[Cortona Background] External message:', message);
  if (message.type === 'send_to_ai') {
    handleSendToAi(message.ai, message.text).then(sendResponse);
    return true; // Keep channel open for async response
  }
});

// Send a message to an AI chat
async function handleSendToAi(aiName, text) {
  console.log('[Cortona Background] ====== SEND TO AI ======');
  console.log('[Cortona Background] AI:', aiName);
  console.log('[Cortona Background] Text:', text);
  
  // Find a tab with this AI
  const aiSites = {
    'chatgpt': ['chat.openai.com', 'chatgpt.com'],
    'claude': ['claude.ai'],
    'gemini': ['gemini.google.com'],
    'perplexity': ['perplexity.ai', 'www.perplexity.ai'],
    'poe': ['poe.com']
  };
  
  const targetSites = aiSites[aiName.toLowerCase()] || [];
  console.log('[Cortona Background] Looking for sites:', targetSites);
  
  // Find matching tab
  const tabs = await chrome.tabs.query({});
  console.log('[Cortona Background] Found', tabs.length, 'total tabs');
  
  let targetTab = null;
  
  for (const tab of tabs) {
    if (tab.url) {
      console.log('[Cortona Background] Checking tab:', tab.id, tab.url.substring(0, 50));
      for (const site of targetSites) {
        if (tab.url.includes(site)) {
          targetTab = tab;
          console.log('[Cortona Background] MATCH! Tab', tab.id);
          break;
        }
      }
      if (targetTab) break;
    }
  }
  
  if (!targetTab) {
    console.log('[Cortona Background] ERROR: No tab found for', aiName);
    console.log('[Cortona Background] Available URLs:', tabs.map(t => t.url).filter(Boolean));
    return { success: false, error: 'No ' + aiName + ' tab open' };
  }
  
  // Focus the tab FIRST so content script can interact with the DOM
  try {
    console.log('[Cortona Background] Focusing window', targetTab.windowId);
    await chrome.windows.update(targetTab.windowId, { focused: true });
    
    console.log('[Cortona Background] Activating tab', targetTab.id);
    await chrome.tabs.update(targetTab.id, { active: true });
    
    // Wait for tab to become active
    console.log('[Cortona Background] Waiting 500ms...');
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Send message
    console.log('[Cortona Background] Sending message to content script...');
    try {
      await chrome.tabs.sendMessage(targetTab.id, {
        type: 'send_message',
        text: text
      });
      console.log('[Cortona Background] Message sent successfully!');
    } catch (sendError) {
      console.log('[Cortona Background] Send error:', sendError.message);
      // Try injecting content script and resending
      console.log('[Cortona Background] Trying to inject content script...');
      try {
        await chrome.scripting.executeScript({
          target: { tabId: targetTab.id },
          files: ['content.js']
        });
        await new Promise(resolve => setTimeout(resolve, 500));
        await chrome.tabs.sendMessage(targetTab.id, {
          type: 'send_message',
          text: text
        });
        console.log('[Cortona Background] Message sent after injection!');
      } catch (injectError) {
        console.log('[Cortona Background] Injection failed:', injectError.message);
      }
    }
    
    console.log('[Cortona Background] ====== DONE ======');
    return { success: true };
  } catch (e) {
    console.log('[Cortona Background] Error:', e);
    return { success: false, error: e.message };
  }
}

// ============================================================================
// FORWARD TO CORTONA
// ============================================================================

async function forwardToCortona(data) {
  console.log('[Cortona Background] forwardToCortona called:', data.event, data.ai, 'connected=' + isServerConnected);
  
  if (!isServerConnected || !isExtensionEnabled) {
    console.log('[Cortona Background] Not forwarding - connected=' + isServerConnected + ', enabled=' + isExtensionEnabled);
    return;
  }
  
  try {
    console.log('[Cortona Background] Sending to', CORTONA_EVENT_URL);
    const response = await fetch(CORTONA_EVENT_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    if (response.ok) {
      console.log('[Cortona Background] Successfully forwarded:', data.event, data.ai);
    } else {
      console.log('[Cortona Background] Cortona returned:', response.status);
    }
  } catch (e) {
    console.log('[Cortona Background] Could not reach Cortona:', e.message);
  }
}

// ============================================================================
// NOTIFICATIONS
// ============================================================================

function showNotification(message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon128.png',
    title: 'Cortona AI Watcher',
    message: message,
    silent: false
  }, (notificationId) => {
    setTimeout(() => {
      chrome.notifications.clear(notificationId);
    }, 5000);
  });
}

// ============================================================================
// TAB EVENTS
// ============================================================================

chrome.tabs.onRemoved.addListener((tabId) => {
  if (activeWatchers.has(tabId)) {
    const watcher = activeWatchers.get(tabId);
    console.log('[Cortona Background] Watcher closed for tab', tabId, watcher.site);
    
    // Notify Cortona that AI tab was closed
    forwardToCortona({
      type: 'ai_activity',
      event: 'tab_closed',
      ai: watcher.site,
      url: watcher.url,
      timestamp: Date.now()
    });
    
    activeWatchers.delete(tabId);
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    const aiSites = [
      'chat.openai.com',
      'chatgpt.com',
      'claude.ai',
      'gemini.google.com',
      'bard.google.com',
      'poe.com',
      'perplexity.ai'
    ];
    
    const isAISite = aiSites.some(site => tab.url.includes(site));
    if (isAISite) {
      console.log('[Cortona Background] AI site detected:', tab.url);
    }
  }
});

// ============================================================================
// EXTENSION ICON CLICK
// ============================================================================

chrome.action.onClicked.addListener((tab) => {
  console.log('[Cortona Background] Extension icon clicked');
});

console.log('[Cortona Background] Service worker ready');
