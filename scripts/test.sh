#!/bin/bash
# Cortona Test Script
# Run: ./scripts/test.sh [quick|full]

MODE=${1:-quick}
ERRORS=0
WARNINGS=0

echo "========================================"
echo "  CORTONA TEST SUITE ($MODE mode)"
echo "========================================"
echo ""

# --- SYNTAX CHECKS ---
echo "📝 SYNTAX CHECKS"
echo "----------------------------------------"

echo -n "  content.js........... "
if node -c chrome-extension/content.js 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo -n "  background.js........ "
if node -c chrome-extension/background.js 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo -n "  popup.js............. "
if node -c chrome-extension/popup.js 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo -n "  main.js (Electron)... "
if node -c cortona-desktop/main.js 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo -n "  preload.js........... "
if node -c cortona-desktop/preload.js 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo -n "  app.py (Flask)....... "
if python3 -m py_compile app.py 2>/dev/null; then
    echo "✓"
else
    echo "✗ ERROR"; ERRORS=$((ERRORS + 1))
fi

echo ""

# --- SERVER CHECKS (if full mode) ---
if [ "$MODE" = "full" ]; then
    echo "🌐 SERVER CHECKS"
    echo "----------------------------------------"
    
    echo -n "  Flask health......... "
    HEALTH=$(curl -s http://localhost:5001/health 2>/dev/null)
    if echo "$HEALTH" | grep -q '"status":"ok"'; then
        echo "✓ (running)"
    else
        echo "⚠ NOT RUNNING"; WARNINGS=$((WARNINGS + 1))
    fi
    
    echo -n "  Extension endpoint... "
    EXT=$(curl -s -X POST http://localhost:5001/api/extension/heartbeat \
        -H "Content-Type: application/json" \
        -d '{"type":"test"}' 2>/dev/null)
    if echo "$EXT" | grep -q '"status":"ok"'; then
        echo "✓"
    else
        echo "⚠ Not responding"; WARNINGS=$((WARNINGS + 1))
    fi
    
    echo ""
fi

# --- SUMMARY ---
echo "========================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "  ✅ ALL CHECKS PASSED"
elif [ $ERRORS -eq 0 ]; then
    echo "  ⚠️  PASSED with $WARNINGS warning(s)"
else
    echo "  ❌ FAILED: $ERRORS error(s), $WARNINGS warning(s)"
fi
echo "========================================"

# --- MANUAL TESTS REMINDER ---
if [ "$MODE" = "full" ]; then
    echo ""
    echo "📋 MANUAL TESTS NEEDED:"
    echo "   □ Chrome extension badge shows ✓"
    echo "   □ Claude detection (start/finish)"
    echo "   □ Voice commands work"
    echo "   □ TTS speaks responses"
    echo ""
fi

exit $ERRORS
