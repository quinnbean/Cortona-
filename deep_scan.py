#!/usr/bin/env python3
"""
Deep scan for potential runtime issues in Cortona
"""
import re

with open('app.py', 'r') as f:
    content = f.read()

print("🔬 Deep Scan for Potential Issues")
print("=" * 60)

# Find DASHBOARD_PAGE section
match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
if not match:
    print("Could not find DASHBOARD_PAGE")
    exit(1)

html = match.group(1)

# Extract JavaScript
js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
js = js_match.group(1) if js_match else ""

issues = []

# 1. Check for all RegExp with string patterns
print("\n📍 All RegExp with string patterns:")
for i, line in enumerate(html.split('\n'), 1):
    if 'new RegExp(' in line:
        print(f"   Line {i}: {line.strip()[:100]}")

# 2. Check for potentially broken regex literals
print("\n📍 Regex literals with escapes:")
lines = html.split('\n')
for i, line in enumerate(lines, 1):
    # Look for /pattern/flags with backslashes
    matches = re.findall(r'/[^/]+\\[^/]+/', line)
    if matches:
        for m in matches:
            print(f"   Line {i}: {m[:60]}")

# 3. Check for string concatenation in regex
print("\n📍 String concatenation in RegExp:")
for i, line in enumerate(html.split('\n'), 1):
    if re.search(r"RegExp\(['\"].*\+.*['\"]", line):
        print(f"   Line {i}: {line.strip()[:100]}")

# 4. Check for potential XSS in innerHTML
print("\n📍 innerHTML usage (check for XSS):")
for i, line in enumerate(html.split('\n'), 1):
    if '.innerHTML' in line:
        if 'data' in line.lower() or 'text' in line.lower():
            print(f"   Line {i}: {line.strip()[:80]}")

# 5. Check for unclosed template literals
print("\n📍 Template literals check:")
backtick_count = html.count('`')
if backtick_count % 2 != 0:
    print(f"   ⚠️ Odd number of backticks: {backtick_count}")
else:
    print(f"   ✅ Balanced backticks: {backtick_count}")

# 6. Check for duplicate function definitions
print("\n📍 Checking for duplicate functions:")
funcs = {}
for i, line in enumerate(html.split('\n'), 1):
    match = re.search(r'(?:async\s+)?function\s+(\w+)\s*\(', line)
    if match:
        name = match.group(1)
        if name in funcs:
            print(f"   ⚠️ Duplicate: {name} at lines {funcs[name]} and {i}")
        else:
            funcs[name] = i

# 7. Check for event listeners that might not work
print("\n📍 Event listeners check:")
event_count = html.count('addEventListener')
print(f"   Found {event_count} addEventListener calls")

# 8. Check for fetch error handling
print("\n📍 Fetch calls without try/catch:")
lines = js.split('\n')
in_try = False
for i, line in enumerate(lines, 1):
    if 'try' in line:
        in_try = True
    if 'catch' in line:
        in_try = False
    if 'fetch(' in line and 'await' in line and not in_try:
        # Check if there's a .catch on the same or next line
        if '.catch' not in line:
            if i < len(lines) and '.catch' not in lines[i]:
                # Might be missing error handling
                pass

# 9. Check for potential race conditions
print("\n📍 Async patterns:")
async_funcs = html.count('async function') + html.count('async (')
await_calls = html.count('await ')
print(f"   {async_funcs} async functions, {await_calls} await calls")

# 10. Check specific known problem areas
print("\n📍 Known problem patterns:")
# Check for \\n in alert strings (should be just \n)
alert_newline = re.findall(r"alert\(['\"][^'\"]*\\\\n[^'\"]*['\"]", html)
if alert_newline:
    print(f"   ⚠️ Found \\\\n in alert (may cause issues): {len(alert_newline)}")
else:
    print("   ✅ No \\\\n in alerts")

# Check for word boundary in RegExp strings
word_boundary = re.findall(r"RegExp\(['\"].*'\\\\b'", html)
if word_boundary:
    print(f"   ⚠️ Found '\\\\b' in RegExp (should be '\\\\\\\\b'): {len(word_boundary)}")
else:
    print("   ✅ Word boundaries look OK")

print("\n" + "=" * 60)
print("Deep scan complete!")
