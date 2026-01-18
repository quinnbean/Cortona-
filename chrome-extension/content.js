// Cortona AI Watcher - Content Script
// Runs on ChatGPT, Claude, Gemini, etc. to detect when AI finishes responding

console.log('[Cortona] AI Watcher loaded on', window.location.hostname);

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  // How long AI must be idle before we consider it "done"
  idleThreshold: 1500, // 1.5 seconds
  
  // How often to check for changes
  checkInterval: 200, // 200ms
  
  // Debug logging
  debug: true
};

// ============================================================================
// STATE
// ============================================================================

let isAIResponding = false;
let lastActivityTime = 0;
let lastContentHash = '';
let idleTimer = null;
let checkInterval = null;
let hasNotifiedDone = false;

// ============================================================================
// SITE-SPECIFIC DETECTORS
// ============================================================================

const SITE_DETECTORS = {
  // ChatGPT / OpenAI
  'chat.openai.com': {
    isStreaming: () => {
      // Look for streaming indicator
      const streamingDot = document.querySelector('[data-testid="stop-button"]');
      const stopButton = document.querySelector('button[aria-label="Stop generating"]');
      const thinkingIndicator = document.querySelector('.result-streaming');
      return !!(streamingDot || stopButton || thinkingIndicator);
    },
    getResponseArea: () => {
      return document.querySelector('[data-message-author-role="assistant"]:last-child');
    },
    getName: () => 'ChatGPT'
  },
  
  // ChatGPT new domain
  'chatgpt.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('button[aria-label="Stop generating"]');
      const streamingIndicator = document.querySelector('[data-testid="stop-button"]');
      return !!(stopButton || streamingIndicator);
    },
    getResponseArea: () => {
      return document.querySelector('[data-message-author-role="assistant"]:last-child');
    },
    getName: () => 'ChatGPT'
  },
  
  // Claude
  'claude.ai': {
    isStreaming: () => {
      // Claude shows a "Stop" button or pulsing indicator while responding
      const stopButton = document.querySelector('button[aria-label="Stop Response"]');
      const streamingDot = document.querySelector('[class*="streaming"]');
      const thinkingText = document.body.innerText.includes('Claude is thinking');
      return !!(stopButton || streamingDot || thinkingText);
    },
    getResponseArea: () => {
      // Claude's response container
      return document.querySelector('[class*="response"]:last-child, [class*="message"]:last-child');
    },
    getName: () => 'Claude'
  },
  
  // Gemini (Google)
  'gemini.google.com': {
    isStreaming: () => {
      // Gemini shows typing indicator
      const typingIndicator = document.querySelector('[class*="typing"], [class*="loading"]');
      const stopButton = document.querySelector('button[aria-label="Stop"]');
      return !!(typingIndicator || stopButton);
    },
    getResponseArea: () => {
      return document.querySelector('[class*="response-container"]:last-child');
    },
    getName: () => 'Gemini'
  },
  
  // Bard (old Google AI)
  'bard.google.com': {
    isStreaming: () => {
      const typingIndicator = document.querySelector('[class*="typing"]');
      return !!typingIndicator;
    },
    getResponseArea: () => {
      return document.querySelector('[class*="response"]:last-child');
    },
    getName: () => 'Bard'
  },
  
  // Poe (multi-model)
  'poe.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('[class*="StopButton"]');
      const typing = document.querySelector('[class*="typing"]');
      return !!(stopButton || typing);
    },
    getResponseArea: () => {
      return document.querySelector('[class*="Message_bot"]:last-child');
    },
    getName: () => 'Poe'
  },
  
  // Perplexity
  'perplexity.ai': {
    isStreaming: () => {
      const loading = document.querySelector('[class*="loading"], [class*="streaming"]');
      const stopButton = document.querySelector('button[aria-label="Stop"]');
      return !!(loading || stopButton);
    },
    getResponseArea: () => {
      return document.querySelector('[class*="prose"]:last-child');
    },
    getName: () => 'Perplexity'
  },
  'www.perplexity.ai': {
    isStreaming: () => {
      const loading = document.querySelector('[class*="loading"], [class*="streaming"]');
      return !!loading;
    },
    getResponseArea: () => {
      return document.querySelector('[class*="prose"]:last-child');
    },
    getName: () => 'Perplexity'
  }
};

// ============================================================================
// DETECTION LOGIC
// ============================================================================

function getDetector() {
  const hostname = window.location.hostname;
  return SITE_DETECTORS[hostname] || null;
}

function hashContent(element) {
  if (!element) return '';
  return element.innerText?.length + '-' + element.innerHTML?.length;
}

function checkForActivity() {
  const detector = getDetector();
  if (!detector) return;
  
  const streaming = detector.isStreaming();
  const responseArea = detector.getResponseArea();
  const currentHash = hashContent(responseArea);
  
  // Check if content changed
  const contentChanged = currentHash !== lastContentHash;
  lastContentHash = currentHash;
  
  // Determine if AI is active
  const nowActive = streaming || contentChanged;
  
  if (nowActive) {
    // AI is responding
    if (!isAIResponding) {
      // Just started responding
      isAIResponding = true;
      hasNotifiedDone = false;
      log('AI started responding');
      notifyCortona('started', detector.getName());
    }
    
    lastActivityTime = Date.now();
    
    // Clear any pending "done" notification
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  } else if (isAIResponding) {
    // AI was responding but now seems idle
    const idleTime = Date.now() - lastActivityTime;
    
    if (idleTime >= CONFIG.idleThreshold && !hasNotifiedDone) {
      // AI has been idle long enough - it's done
      log('AI finished responding (idle for ' + idleTime + 'ms)');
      isAIResponding = false;
      hasNotifiedDone = true;
      notifyCortona('finished', detector.getName());
    }
  }
}

// ============================================================================
// MUTATION OBSERVER (Backup detection)
// ============================================================================

let mutationCount = 0;
let lastMutationTime = 0;

function setupMutationObserver() {
  const detector = getDetector();
  if (!detector) return;
  
  const observer = new MutationObserver((mutations) => {
    mutationCount += mutations.length;
    lastMutationTime = Date.now();
    
    // If we see lots of mutations, AI is probably responding
    if (mutationCount > 5 && !isAIResponding) {
      isAIResponding = true;
      hasNotifiedDone = false;
      log('AI activity detected via mutations');
      notifyCortona('started', detector.getName());
    }
    
    // Reset mutation count periodically
    setTimeout(() => {
      if (Date.now() - lastMutationTime > 1000) {
        mutationCount = 0;
      }
    }, 1000);
  });
  
  // Watch the main content area
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
  
  log('Mutation observer started');
}

// ============================================================================
// COMMUNICATION WITH CORTONA
// ============================================================================

async function notifyCortona(event, aiName) {
  const data = {
    type: 'ai_activity',
    event: event,  // 'started' or 'finished'
    ai: aiName,
    url: window.location.href,
    timestamp: Date.now()
  };
  
  log('Notifying Cortona:', event, aiName);
  
  // Send to background script (which forwards to Cortona)
  // Background script has permission to call localhost without popup
  try {
    chrome.runtime.sendMessage(data);
  } catch (e) {
    log('Failed to send to background:', e.message);
  }
}

// ============================================================================
// UTILITIES
// ============================================================================

function log(...args) {
  if (CONFIG.debug) {
    console.log('[Cortona]', ...args);
  }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

function init() {
  const detector = getDetector();
  
  if (!detector) {
    log('No detector for this site, disabling');
    return;
  }
  
  log('Initialized for', detector.getName());
  
  // Start periodic checking
  checkInterval = setInterval(checkForActivity, CONFIG.checkInterval);
  
  // Setup mutation observer as backup
  setupMutationObserver();
  
  // Notify that we're watching
  chrome.runtime.sendMessage({
    type: 'watcher_active',
    site: detector.getName(),
    url: window.location.href
  });
}

// Start when page is ready
if (document.readyState === 'complete') {
  init();
} else {
  window.addEventListener('load', init);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (checkInterval) clearInterval(checkInterval);
  if (idleTimer) clearTimeout(idleTimer);
});
