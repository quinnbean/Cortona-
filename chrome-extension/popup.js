// Cortona AI Watcher - Popup Script

document.addEventListener('DOMContentLoaded', async () => {
  // Check Cortona desktop connection
  const cortonaStatus = document.getElementById('cortona-status');
  const pageStatus = document.getElementById('page-status');
  
  // Check if Cortona is running
  try {
    const response = await fetch('http://localhost:5050/health', {
      method: 'GET',
      timeout: 2000
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
});
