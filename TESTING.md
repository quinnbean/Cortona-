# Cortona Testing Checklist

## When to Run This Checklist

| Situation | Run Full | Run Quick |
|-----------|----------|-----------|
| After editing Chrome extension files | ✓ | |
| After editing `app.py` (Flask) | | ✓ |
| After editing Electron files | ✓ | |
| Before creating a PR | ✓ | |
| After pulling changes from git | ✓ | |
| Before deploying to production | ✓ | |

---

## Quick Smoke Test (2 minutes)

Run these commands to verify basic functionality:

```bash
# 1. Check Flask is running
curl -s http://localhost:5001/health
# Expected: {"devices":...,"status":"ok"}

# 2. Check Chrome extension syntax
cd chrome-extension && node -c content.js && node -c background.js && echo "✓ No syntax errors"

# 3. Check Electron syntax  
cd cortona-desktop && node -c main.js && node -c preload.js && echo "✓ No syntax errors"
```

---

## Full Test Checklist

### 1. Setup Verification
- [ ] Flask server running on port 5001
- [ ] Electron app running and logged in
- [ ] Chrome extension loaded (check `chrome://extensions`)
- [ ] Extension badge shows ✓ (green) = connected

### 2. Chrome Extension - AI Detection
- [ ] Open Claude in Chrome
- [ ] Cortona shows "Claude tab opened" in activity log
- [ ] Ask Claude a question
- [ ] Cortona detects "Claude started" (or shows activity)
- [ ] When Claude finishes, Cortona detects "Claude finished"
- [ ] Say "What did Claude say" - reads response aloud

### 3. Chrome Extension - Other AIs (optional)
- [ ] ChatGPT detection works
- [ ] Gemini detection works

### 4. Voice Commands
- [ ] Click mic button - turns green (recording)
- [ ] Speak a command - transcription appears
- [ ] AI responds appropriately
- [ ] TTS speaks the response

### 5. Wake Word (if enabled)
- [ ] Toggle "Always Listen" on - mic turns yellow
- [ ] Say wake word ("Jarvis") - mic turns green
- [ ] Speak command - processes correctly
- [ ] After TTS finishes, returns to yellow (listening)
- [ ] No echo/feedback loop (Jarvis doesn't hear itself)

### 6. Watch Commands
- [ ] Say "Watch Claude" - confirms watching
- [ ] Say "Watch Cursor" - starts native watcher

### 7. UI State
- [ ] Mic color matches actual state:
  - Gray = idle
  - Yellow = waiting for wake word
  - Green = recording
  - Red = processing
- [ ] Chat messages don't duplicate
- [ ] Activity log updates correctly

---

## Known Issues to Watch For

1. **False positives in Claude detection** - Triggers when typing in input
2. **Echo loop** - Jarvis hears its own TTS and triggers wake word
3. **Mic color out of sync** - Shows recording when waiting for wake word
4. **Chrome extension disconnects** - Badge shows ! instead of ✓

---

## If Something Breaks

1. **Check browser console** (F12) on Claude tab for `[Cortona]` errors
2. **Check extension background logs**: `chrome://extensions` → Cortona → "service worker"
3. **Check Flask logs** in terminal
4. **Check Electron logs** in terminal

### Quick Reset
```bash
# Kill everything and restart
pkill -f "python3 app.py"
pkill -f "Electron"
lsof -ti:5001 | xargs kill -9

# Restart Flask
cd /Users/quinnbean/Cortona- && PORT=5001 python3 app.py &

# Restart Electron
cd /Users/quinnbean/Cortona-/cortona-desktop && npm start &

# Reload Chrome extension at chrome://extensions
```

---

## Test Log

Use this to track test runs:

| Date | Tester | Result | Notes |
|------|--------|--------|-------|
| | | | |
