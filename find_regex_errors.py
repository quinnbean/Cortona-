#!/usr/bin/env python3
"""
Find potentially broken regex patterns in app.py JavaScript
"""
import re

with open('app.py', 'r') as f:
    content = f.read()

# Find DASHBOARD_PAGE
match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
html = match.group(1)

# Extract JavaScript
js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
js_code = js_match.group(1)

lines = js_code.split('\n')

# Look for problematic patterns
print("=== Checking RegExp patterns ===")
for i, line in enumerate(lines, 1):
    # Look for new RegExp with potential issues
    if 'new RegExp' in line or 'RegExp(' in line:
        print(f"Line {i}: {line.strip()[:120]}")
    # Look for regex literals that might be broken
    if re.search(r'/[^/]+/[gim]*', line) and ('\\n' in line or '\\b' in line):
        print(f"Line {i} (literal): {line.strip()[:120]}")

print("\n=== Lines around 1461 ===")
for i in range(max(0, 1458), min(len(lines), 1465)):
    print(f"{i+1}: {lines[i][:150]}")

print("\n=== Searching for escaped backslashes in strings ===")
for i, line in enumerate(lines, 1):
    # Look for \\n or \\b in JavaScript strings (which become \n or \b)
    if "'\\\\n" in line or '"\\\\n' in line or "'\\\\b" in line or '"\\\\b' in line:
        print(f"Line {i}: {line.strip()[:120]}")
