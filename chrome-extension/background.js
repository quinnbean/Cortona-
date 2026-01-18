// Cortona AI Watcher - Background Service Worker
// Receives events from content scripts and forwards to Cortona desktop app

console.log('[Cortona Background] Service worker started');

// ============================================================================
// CONFIGURATION
// ============================================================================

const CORTONA_URL = 'http://localhost:5050/api/chrome-event';

// Track active watchers
const activeWatchers = new Map();

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
    }
  }
  
  if (message.type === 'ai_activity') {
    // AI started or finished responding
    forwardToCortona(message);
    
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
      }
    }
  }
  
  return true;
});

// ============================================================================
// FORWARD TO CORTONA
// ============================================================================

async function forwardToCortona(data) {
  try {
    const response = await fetch(CORTONA_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    if (response.ok) {
      console.log('[Cortona Background] Successfully forwarded to Cortona');
    } else {
      console.log('[Cortona Background] Cortona returned:', response.status);
    }
  } catch (e) {
    console.log('[Cortona Background] Could not reach Cortona:', e.message);
    // Cortona desktop app might not be running - that's okay
  }
}

// ============================================================================
// NOTIFICATIONS
// ============================================================================

function showNotification(message) {
  // Check if we have permission
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon128.png',
    title: 'Cortona AI Watcher',
    message: message,
    silent: false
  }, (notificationId) => {
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      chrome.notifications.clear(notificationId);
    }, 5000);
  });
}

// ============================================================================
// TAB EVENTS
// ============================================================================

// Clean up when tab closes
chrome.tabs.onRemoved.addListener((tabId) => {
  if (activeWatchers.has(tabId)) {
    console.log('[Cortona Background] Watcher closed for tab', tabId);
    activeWatchers.delete(tabId);
  }
});

// Re-inject content script when tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    // Check if this is an AI site we care about
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
  // Toggle watching status or show popup
  console.log('[Cortona Background] Extension icon clicked');
});

console.log('[Cortona Background] Service worker ready');
