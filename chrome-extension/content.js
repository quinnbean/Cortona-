// Cortona AI Watcher - Content Script
// Runs on ChatGPT, Claude, Gemini, etc. to detect when AI finishes responding

console.log('[Cortona] AI Watcher loaded on', window.location.hostname);

// Determine site key for settings
const currentHostname = window.location.hostname;
const siteKey = currentHostname.includes('claude') ? 'claude' :
                currentHostname.includes('chatgpt') || currentHostname.includes('openai') ? 'chatgpt' :
                currentHostname.includes('gemini') ? 'gemini' :
                currentHostname.includes('perplexity') ? 'perplexity' :
                currentHostname.includes('poe') ? 'poe' : null;

let monitoringEnabled = true; // Default to enabled

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  // How long AI must be idle before we consider it "done"
  idleThreshold: 2000, // 2 seconds
  
  // How often to check for changes
  checkInterval: 250, // 250ms
  
  // Minimum response length to consider valid (prevents false positives)
  minResponseLength: 20,
  
  // Minimum duration of activity before we notify "started" (prevents brief flickers)
  minActivityDuration: 800, // 0.8 seconds of continuous activity
  
  // Debug logging - enable to see what's happening
  debug: true
};

// ============================================================================
// STATE
// ============================================================================

let isAIResponding = false;
let lastActivityTime = 0;
let lastContentHash = '';
let lastResponseLength = 0;
let idleTimer = null;
let checkInterval = null;
let hasNotifiedStart = false;
let hasNotifiedDone = false;
let responseStartTime = 0;
let activityStartTime = 0; // When continuous activity began
let initTime = 0; // Track when we initialized
const WARMUP_PERIOD = 3000; // Don't notify for first 3 seconds after init
let lastAIResponse = ''; // Store the last AI response for reading back

// ============================================================================
// SITE-SPECIFIC DETECTORS
// ============================================================================

const SITE_DETECTORS = {
  // ChatGPT / OpenAI
  'chat.openai.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('[data-testid="stop-button"], button[aria-label="Stop generating"]');
      const streaming = document.querySelector('.result-streaming, [class*="streaming"]');
      return !!(stopButton || streaming);
    },
    getResponseArea: () => {
      const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
      return messages.length > 0 ? messages[messages.length - 1] : null;
    },
    getName: () => 'ChatGPT'
  },
  
  // ChatGPT new domain
  'chatgpt.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('button[aria-label="Stop generating"], [data-testid="stop-button"]');
      const streaming = document.querySelector('[class*="streaming"], .result-streaming');
      return !!(stopButton || streaming);
    },
    getResponseArea: () => {
      const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
      return messages.length > 0 ? messages[messages.length - 1] : null;
    },
    getName: () => 'ChatGPT'
  },
  
  // Claude - track only AI responses, not user input
  'claude.ai': {
    isStreaming: () => {
      // Method 1: Look for ANY button with "stop" text
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        const text = (btn.innerText || btn.ariaLabel || btn.title || '').toLowerCase();
        if (text.includes('stop')) {
          return true;
        }
      }
      
      // Method 2: Look for data attributes indicating streaming
      if (document.querySelector('[data-is-streaming="true"]')) return true;
      
      // Method 3: Look for SVG loading spinners (Claude uses these)
      const svgs = document.querySelectorAll('svg');
      for (const svg of svgs) {
        const cls = svg.className?.baseVal || svg.getAttribute('class') || '';
        if (cls.includes('animate') || cls.includes('spin') || cls.includes('loading')) {
          return true;
        }
      }
      
      return false;
    },
    getResponseArea: () => {
      return document.querySelector('main') || document.body;
    },
    getResponseText: () => {
      // Simple: just get main text (we mainly use streaming detection anyway)
      const main = document.querySelector('main');
      return main ? main.innerText.substring(0, 10000) : '';
    },
    getName: () => 'Claude'
  },
  
  // Gemini (Google)
  'gemini.google.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('button[aria-label="Stop"]');
      const loading = document.querySelector('[class*="loading"], [class*="typing"]');
      return !!(stopButton || loading);
    },
    getResponseArea: () => {
      const responses = document.querySelectorAll('[class*="response-container"], model-response');
      return responses.length > 0 ? responses[responses.length - 1] : null;
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
      const responses = document.querySelectorAll('[class*="response"]');
      return responses.length > 0 ? responses[responses.length - 1] : null;
    },
    getName: () => 'Bard'
  },
  
  // Poe (multi-model)
  'poe.com': {
    isStreaming: () => {
      const stopButton = document.querySelector('[class*="StopButton"], button[class*="stop"]');
      const typing = document.querySelector('[class*="typing"], [class*="loading"]');
      return !!(stopButton || typing);
    },
    getResponseArea: () => {
      const messages = document.querySelectorAll('[class*="Message_bot"], [class*="botMessage"]');
      return messages.length > 0 ? messages[messages.length - 1] : null;
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
      const responses = document.querySelectorAll('[class*="prose"]');
      return responses.length > 0 ? responses[responses.length - 1] : null;
    },
    getName: () => 'Perplexity'
  },
  'www.perplexity.ai': {
    isStreaming: () => {
      const loading = document.querySelector('[class*="loading"], [class*="streaming"]');
      return !!loading;
    },
    getResponseArea: () => {
      const responses = document.querySelectorAll('[class*="prose"]');
      return responses.length > 0 ? responses[responses.length - 1] : null;
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

function getResponseLength(detector) {
  if (detector.getResponseText) {
    return detector.getResponseText().length;
  }
  const responseArea = detector.getResponseArea();
  if (!responseArea) return 0;
  
  // Make sure we're not accidentally reading from an input field
  if (responseArea.tagName === 'TEXTAREA' || responseArea.tagName === 'INPUT') {
    return 0;
  }
  
  return responseArea?.innerText?.length || 0;
}

// Check if the user is currently typing in an input field
function isUserTyping() {
  const activeEl = document.activeElement;
  if (!activeEl) return false;
  
  const tag = activeEl.tagName.toLowerCase();
  if (tag === 'textarea' || tag === 'input') return true;
  if (activeEl.getAttribute('contenteditable') === 'true') return true;
  if (activeEl.getAttribute('role') === 'textbox') return true;
  
  return false;
}

function hashContent(element) {
  if (!element) return '';
  const text = element.innerText || '';
  return text.length + '-' + text.slice(-50); // Use length + last 50 chars
}

let checkCount = 0;

function checkForActivity() {
  const detector = getDetector();
  if (!detector) return;
  
  checkCount++;
  
  const isStreaming = detector.isStreaming();
  
  // Log status every 5 checks or when streaming changes
  if (checkCount % 5 === 0 || isStreaming !== wasStreaming) {
    log(`[${checkCount}] streaming=${isStreaming}, wasStreaming=${wasStreaming}, notifiedStart=${hasNotifiedStart}, notifiedDone=${hasNotifiedDone}`);
  }
  
  // Simple state machine:
  // 1. If streaming and haven't notified start -> notify start
  // 2. If not streaming and notified start but not done -> notify done
  
  if (isStreaming) {
    // AI is actively generating
    wasStreaming = true;
    lastActivityTime = Date.now();
    
    if (!hasNotifiedStart) {
      hasNotifiedStart = true;
      hasNotifiedDone = false;
      log('>>> AI STARTED <<<');
      notifyCortona('started', detector.getName());
    }
  } else {
    // AI is not generating
    if (wasStreaming && hasNotifiedStart && !hasNotifiedDone) {
      // Was streaming, now stopped - wait a moment then notify done
      const idleTime = Date.now() - lastActivityTime;
      
      if (idleTime >= 1500) { // 1.5 seconds of not streaming
        log('>>> AI FINISHED (idle ' + idleTime + 'ms) <<<');
        hasNotifiedDone = true;
        hasNotifiedStart = false; // Reset for next time
        wasStreaming = false;
        
        // Store response
        lastAIResponse = getLastAIResponse();
        
        notifyCortona('finished', detector.getName());
      }
    } else if (!wasStreaming) {
      // Wasn't streaming, still not streaming - reset state
      hasNotifiedStart = false;
      hasNotifiedDone = false;
    }
  }
}

// Track previous streaming state
let wasStreaming = false;

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
  
  // Initialize response tracking with current page state
  lastResponseLength = getResponseLength(detector);
  initTime = Date.now(); // Track init time for warm-up period
  
  log('=== CORTONA INITIALIZED ===');
  log('Site:', detector.getName());
  log('Initial text length:', lastResponseLength);
  log('Warm-up period:', WARMUP_PERIOD, 'ms');
  log('Checking every', CONFIG.checkInterval, 'ms');
  log('===========================');
  
  // Start periodic checking
  checkInterval = setInterval(checkForActivity, CONFIG.checkInterval);
  
  // Notify background that we're watching (this just marks the tab as "open", not "finished")
  chrome.runtime.sendMessage({
    type: 'watcher_active',
    site: detector.getName(),
    url: window.location.href
  });
}

// ============================================================================
// RECEIVE COMMANDS FROM CORTONA (type and send messages)
// ============================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[Cortona] Received message:', message);
  
  // Respond to ping (used to check if content script is already loaded)
  if (message.type === 'ping') {
    sendResponse({ pong: true, site: siteKey });
    return false;
  }
  
  // Get the last AI response for reading back
  if (message.type === 'get_last_response') {
    // First try the stored response (most accurate - captured when AI finished)
    let response = lastAIResponse;
    
    // If no stored response, try to scrape it from the page
    if (!response || response.length < 20) {
      console.log('[Cortona] No stored response, scraping from page...');
      response = getLastAIResponse();
    }
    
    console.log('[Cortona] Returning last response (' + response.length + ' chars):', response.substring(0, 100) + '...');
    sendResponse({ 
      success: response.length > 20, 
      response: response,
      ai: getDetector()?.getName() || 'AI'
    });
    return false;
  }
  
  if (message.type === 'send_message') {
    // Execute async but don't wait for response
    typeAndSendMessage(message.text).then(result => {
      console.log('[Cortona] Send result:', result);
    }).catch(e => {
      console.error('[Cortona] Send error:', e);
    });
    sendResponse({ received: true });
  }
  
  // Start actively watching this AI tab
  if (message.type === 'start_watching') {
    console.log('[Cortona] Start watching requested for:', message.ai);
    // The content script is already watching via observer, but we can confirm
    sendResponse({ success: true, watching: true, site: siteKey });
    
    // Notify background that we're actively watching
    chrome.runtime.sendMessage({
      type: 'watcher_active',
      site: siteKey,
      url: window.location.href
    });
  }
  
  return false; // Synchronous response
});

// Get the last AI response from the page
function getLastAIResponse() {
  const hostname = window.location.hostname;
  
  if (hostname.includes('claude.ai')) {
    // Claude: Find the actual conversation messages
    // Claude's messages are in a scrollable conversation area
    
    // Method 1: Look for the conversation container and find assistant messages
    // Claude typically has human/assistant turn structure
    const conversationArea = document.querySelector('[class*="conversation"], [class*="chat-messages"], main [class*="scroll"]');
    
    if (conversationArea) {
      // Look for message blocks - Claude alternates between human and assistant
      const allBlocks = conversationArea.querySelectorAll('[class*="message"], [class*="block"], [class*="turn"]');
      
      // Find the last block that looks like an assistant message (longer text, not user input)
      for (let i = allBlocks.length - 1; i >= 0; i--) {
        const block = allBlocks[i];
        const text = block.innerText?.trim() || '';
        
        // Skip if it contains input elements (user's typing area)
        if (block.querySelector('textarea, input, [contenteditable]')) continue;
        // Skip very short text (likely UI elements)
        if (text.length < 50) continue;
        // Skip if it looks like it's the user's message (has "You" label or is a human turn)
        if (block.querySelector('[class*="human"], [class*="user"]')) continue;
        
        return text;
      }
    }
    
    // Method 2: Look for prose/markdown rendered content (Claude renders responses as markdown)
    const proseBlocks = document.querySelectorAll('[class*="prose"], [class*="markdown"], [class*="rendered"]');
    if (proseBlocks.length > 0) {
      // Get the last substantial prose block
      for (let i = proseBlocks.length - 1; i >= 0; i--) {
        const text = proseBlocks[i].innerText?.trim() || '';
        if (text.length > 50) {
          return text;
        }
      }
    }
    
    // Method 3: Look for specific Claude message structure
    // Claude often has a grid/flex layout with messages
    const gridItems = document.querySelectorAll('[class*="grid"] > div, [class*="flex-col"] > div');
    for (let i = gridItems.length - 1; i >= 0; i--) {
      const item = gridItems[i];
      const text = item.innerText?.trim() || '';
      
      // Skip UI elements, short text, and input areas
      if (item.querySelector('textarea, input, [contenteditable], button')) continue;
      if (text.length < 100) continue;
      // Skip if contains common UI text
      if (text.includes('Start a new chat') || text.includes('Upgrade') || text.includes('Settings')) continue;
      
      return text;
    }
    
    // Method 4: Fallback - find any substantial text block in main content
    const mainContent = document.querySelector('main') || document.body;
    const allDivs = mainContent.querySelectorAll('div');
    let bestMatch = '';
    let bestLength = 0;
    
    for (const div of allDivs) {
      // Skip if has children divs (we want leaf nodes with text)
      if (div.querySelectorAll('div').length > 5) continue;
      // Skip inputs and interactive elements
      if (div.querySelector('textarea, input, [contenteditable], button')) continue;
      
      const text = div.innerText?.trim() || '';
      // Look for substantial text that's not UI
      if (text.length > 100 && text.length > bestLength) {
        if (!text.includes('Start a new chat') && !text.includes('brand') && !text.includes('guideline')) {
          bestMatch = text;
          bestLength = text.length;
        }
      }
    }
    
    if (bestMatch) return bestMatch;
    
    // Final fallback
    return lastAIResponse || 'Could not find Claude response. Try scrolling to the response first.';
    
  } else if (hostname.includes('chatgpt') || hostname.includes('openai')) {
    // ChatGPT: find assistant messages
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (messages.length > 0) {
      return messages[messages.length - 1].innerText || '';
    }
  } else if (hostname.includes('gemini')) {
    // Gemini
    const responses = document.querySelectorAll('[class*="response-container"], model-response');
    if (responses.length > 0) {
      return responses[responses.length - 1].innerText || '';
    }
  } else if (hostname.includes('perplexity')) {
    // Perplexity
    const answers = document.querySelectorAll('[class*="answer"], [class*="response"]');
    if (answers.length > 0) {
      return answers[answers.length - 1].innerText || '';
    }
  }
  
  // Generic fallback: return stored response
  return lastAIResponse || 'No response found';
}

async function typeAndSendMessage(text) {
  const hostname = window.location.hostname;
  console.log('[Cortona] === SEND MESSAGE ===');
  console.log('[Cortona] Hostname:', hostname);
  console.log('[Cortona] Text:', text);
  
  let input, sendButton;
  
  // Find input and send button based on site
  if (hostname.includes('claude.ai')) {
    // Claude - try multiple selectors
    console.log('[Cortona] Detecting Claude input...');
    
    // Claude uses ProseMirror editor - look for it
    input = document.querySelector('.ProseMirror[contenteditable="true"]') ||
            document.querySelector('[contenteditable="true"].ProseMirror') ||
            document.querySelector('div[contenteditable="true"]') ||
            document.querySelector('[contenteditable="true"]') ||
            document.querySelector('textarea');
    
    console.log('[Cortona] Found input:', input?.tagName, input?.className);
    
    // Find send button - Claude uses an arrow/send icon button
    const allButtons = document.querySelectorAll('button');
    console.log('[Cortona] Found', allButtons.length, 'buttons');
    
    for (const btn of allButtons) {
      const ariaLabel = btn.getAttribute('aria-label') || '';
      const hasArrow = btn.querySelector('svg');
      const isNearInput = btn.closest('form') || btn.closest('[class*="input"]') || btn.closest('[class*="composer"]');
      
      // Look for send button near the input area
      if (ariaLabel.toLowerCase().includes('send') || 
          (hasArrow && isNearInput && !ariaLabel.toLowerCase().includes('attach'))) {
        sendButton = btn;
        console.log('[Cortona] Found send button:', btn.outerHTML.substring(0, 100));
        break;
      }
    }
    
    // Fallback - find button at bottom of page with SVG
    if (!sendButton) {
      const bottomButtons = Array.from(allButtons).filter(b => {
        const rect = b.getBoundingClientRect();
        return rect.bottom > window.innerHeight - 200 && b.querySelector('svg');
      });
      if (bottomButtons.length > 0) {
        sendButton = bottomButtons[bottomButtons.length - 1];
        console.log('[Cortona] Using fallback send button');
      }
    }
    
  } else if (hostname.includes('chatgpt') || hostname.includes('openai')) {
    // ChatGPT
    input = document.querySelector('#prompt-textarea') ||
            document.querySelector('textarea[data-id="root"]') ||
            document.querySelector('textarea');
    sendButton = document.querySelector('[data-testid="send-button"]') ||
                 document.querySelector('button[aria-label*="Send"]');
  } else if (hostname.includes('gemini')) {
    // Gemini
    input = document.querySelector('textarea') ||
            document.querySelector('[contenteditable="true"]');
    sendButton = document.querySelector('button[aria-label*="Send"]');
  } else if (hostname.includes('perplexity')) {
    // Perplexity
    input = document.querySelector('textarea');
    sendButton = document.querySelector('button[aria-label*="Submit"]') ||
                 document.querySelector('button[type="submit"]');
  } else if (hostname.includes('poe.com')) {
    // Poe
    input = document.querySelector('textarea');
    sendButton = document.querySelector('button[class*="Send"]');
  }
  
  if (!input) {
    console.error('[Cortona] Could not find input field!');
    console.log('[Cortona] Page HTML sample:', document.body.innerHTML.substring(0, 500));
    return { success: false, error: 'Input field not found' };
  }
  
  // Focus the input first
  input.focus();
  await new Promise(r => setTimeout(r, 100));
  
  // Type the message based on input type
  console.log('[Cortona] Input type:', input.tagName, 'contentEditable:', input.contentEditable);
  
  if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
    // Standard input
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  } else if (input.contentEditable === 'true') {
    // ContentEditable (Claude uses this)
    // Clear existing content
    input.innerHTML = '';
    
    // Create a paragraph with the text
    const p = document.createElement('p');
    p.textContent = text;
    input.appendChild(p);
    
    // Dispatch events that Claude's editor listens to
    input.dispatchEvent(new InputEvent('input', { 
      bubbles: true, 
      cancelable: true,
      inputType: 'insertText',
      data: text 
    }));
    
    // Also try setting innerText
    if (input.innerText.trim() !== text.trim()) {
      input.innerText = text;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }
  
  console.log('[Cortona] Message typed. Input now contains:', input.innerText || input.value);
  
  // Wait a bit for the UI to update
  await new Promise(r => setTimeout(r, 200));
  
  // Try to click send button
  if (sendButton) {
    console.log('[Cortona] Clicking send button');
    sendButton.click();
    
    // If that didn't work, try dispatching events
    await new Promise(r => setTimeout(r, 100));
    sendButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  } else {
    // Try pressing Enter
    console.log('[Cortona] No send button, pressing Enter');
    input.dispatchEvent(new KeyboardEvent('keydown', { 
      key: 'Enter', 
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true 
    }));
    input.dispatchEvent(new KeyboardEvent('keypress', { 
      key: 'Enter', 
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true 
    }));
    input.dispatchEvent(new KeyboardEvent('keyup', { 
      key: 'Enter', 
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true 
    }));
  }
  
  console.log('[Cortona] === SEND COMPLETE ===');
  return { success: true };
}

// Prevent double-initialization
if (window.__cortonaInitialized) {
  console.log('[Cortona] Already initialized, skipping');
} else {
  window.__cortonaInitialized = true;
  checkMonitoringAndStart();
}

// Check if monitoring is enabled for this site (from Cortona server, fallback to local)
async function checkMonitoringAndStart() {
  let monitored = { claude: true, chatgpt: true, gemini: true, perplexity: true, poe: true };
  
  // Try to get settings from Cortona server
  try {
    const response = await fetch('http://localhost:5001/api/get-monitored-sites', { 
      method: 'GET',
      mode: 'cors'
    });
    if (response.ok) {
      const data = await response.json();
      monitored = data.sites || monitored;
      console.log('[Cortona] Got monitoring settings from server:', monitored);
    }
  } catch (e) {
    // Fall back to local storage
    console.log('[Cortona] Using local settings (server unavailable):', e.message);
    try {
      const result = await chrome.storage.local.get(['monitoredSites']);
      monitored = result.monitoredSites || monitored;
    } catch (e2) {
      console.log('[Cortona] Using defaults');
    }
  }
  
  if (siteKey && monitored[siteKey] === false) {
    console.log('[Cortona] Monitoring DISABLED for', siteKey);
    monitoringEnabled = false;
    return; // Don't initialize monitoring
  }
  
  console.log('[Cortona] Monitoring ENABLED for', siteKey);
  
  // Start immediately if page is ready, otherwise wait
  if (document.readyState === 'complete') {
    // Page already loaded (e.g., injected into existing tab)
    console.log('[Cortona] Page ready, initializing immediately');
    setTimeout(init, 100); // Short delay
  } else {
    // Page still loading
    console.log('[Cortona] Waiting for page load');
    window.addEventListener('load', () => setTimeout(init, 500));
  }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (checkInterval) clearInterval(checkInterval);
  if (idleTimer) clearTimeout(idleTimer);
});
