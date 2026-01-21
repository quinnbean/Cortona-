// Cortona AI Watcher - Popup Script

document.addEventListener('DOMContentLoaded', async () => {
  // Check Cortona desktop connection
  const cortonaStatus = document.getElementById('cortona-status');
  const pageStatus = document.getElementById('page-status');
  const autoFocusToggle = document.getElementById('auto-focus-toggle');
  
  // Load settings
  chrome.storage.local.get(['autoFocus', 'monitoredSites'], (result) => {
    autoFocusToggle.checked = result.autoFocus || false;
    
    // Load monitored sites (default all enabled)
    const monitored = result.monitoredSites || { 
      claude: true, 
      chatgpt: true, 
      gemini: true, 
      perplexity: true, 
      poe: true 
    };
    
    document.getElementById('monitor-claude').checked = monitored.claude !== false;
    document.getElementById('monitor-chatgpt').checked = monitored.chatgpt !== false;
    document.getElementById('monitor-gemini').checked = monitored.gemini !== false;
    document.getElementById('monitor-perplexity').checked = monitored.perplexity !== false;
    document.getElementById('monitor-poe').checked = monitored.poe !== false;
  });
  
  // Save auto-focus setting when toggled
  autoFocusToggle.addEventListener('change', () => {
    chrome.storage.local.set({ autoFocus: autoFocusToggle.checked });
    console.log('[Popup] Auto-focus set to:', autoFocusToggle.checked);
  });
  
  // Save monitored sites when toggled
  const siteToggles = ['claude', 'chatgpt', 'gemini', 'perplexity', 'poe'];
  siteToggles.forEach(site => {
    document.getElementById(`monitor-${site}`).addEventListener('change', () => {
      chrome.storage.local.get(['monitoredSites'], (result) => {
        const monitored = result.monitoredSites || { 
          claude: true, chatgpt: true, gemini: true, perplexity: true, poe: true 
        };
        monitored[site] = document.getElementById(`monitor-${site}`).checked;
        chrome.storage.local.set({ monitoredSites: monitored });
        console.log('[Popup] Monitoring for', site, ':', monitored[site]);
      });
    });
  });
  
  // Check if Cortona is running
  try {
    const response = await fetch('http://localhost:5001/health', {
      method: 'GET'
    });
    
    if (response.ok) {
      cortonaStatus.textContent = 'Connected';
      cortonaStatus.className = 'status-value connected';
    } else {
      cortonaStatus.textContent = 'Error';
      cortonaStatus.className = 'status-value disconnected';
    }
  } catch (e) {
    cortonaStatus.textContent = 'Not Running';
    cortonaStatus.className = 'status-value disconnected';
  }
  
  // Check current tab
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    const aiSites = {
      'chat.openai.com': 'ChatGPT',
      'chatgpt.com': 'ChatGPT',
      'claude.ai': 'Claude',
      'gemini.google.com': 'Gemini',
      'bard.google.com': 'Bard',
      'poe.com': 'Poe',
      'perplexity.ai': 'Perplexity',
      'www.perplexity.ai': 'Perplexity'
    };
    
    const hostname = new URL(tab.url).hostname;
    const aiName = aiSites[hostname];
    
    if (aiName) {
      pageStatus.textContent = 'Watching ' + aiName;
      pageStatus.className = 'status-value connected';
      
      // Highlight the active site badge
      document.querySelectorAll('.site-badge').forEach(badge => {
        if (badge.textContent === aiName) {
          badge.classList.add('active');
        }
      });
    } else {
      pageStatus.textContent = 'Not an AI site';
      pageStatus.className = 'status-value';
    }
  } catch (e) {
    pageStatus.textContent = 'Unknown';
  }
  
  // Test send button
  const testButton = document.getElementById('test-claude');
  const testInput = document.getElementById('test-message');
  const testResult = document.getElementById('test-result');
  
  testButton.addEventListener('click', async () => {
    const message = testInput.value || 'Hello from Cortona test!';
    testResult.textContent = 'Sending...';
    testResult.style.color = '#888';
    
    try {
      // Send message to background script to forward to Claude
      chrome.runtime.sendMessage({
        type: 'send_to_ai',
        ai: 'claude',
        text: message
      }, (response) => {
        console.log('[Popup] Response:', response);
        testResult.textContent = 'Sent! Check Claude tab console for logs.';
        testResult.style.color = '#4CAF50';
      });
    } catch (e) {
      testResult.textContent = 'Error: ' + e.message;
      testResult.style.color = '#f44336';
    }
  });
});
