#!/usr/bin/env python3
"""
Extract and validate JavaScript from app.py
"""
import re
import subprocess
import sys

# Read app.py
with open('app.py', 'r') as f:
    content = f.read()

# Find DASHBOARD_PAGE
match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
if not match:
    print("Could not find DASHBOARD_PAGE")
    sys.exit(1)

html = match.group(1)

# Extract JavaScript between <script> and </script>
js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
if not js_match:
    print("Could not find <script> tag")
    sys.exit(1)

js_code = js_match.group(1)

# Write to temp file
with open('/tmp/test_cortona.js', 'w') as f:
    f.write(js_code)

print(f"Extracted {len(js_code)} bytes of JavaScript")
print(f"Written to /tmp/test_cortona.js")

# Try to parse with node
result = subprocess.run(['node', '--check', '/tmp/test_cortona.js'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("✅ JavaScript syntax is valid!")
else:
    print("❌ JavaScript syntax error:")
    print(result.stderr)
    
    # Try to find the line
    for line in result.stderr.split('\n'):
        if ':' in line and 'SyntaxError' not in line:
            parts = line.split(':')
            if len(parts) >= 2 and parts[1].strip().isdigit():
                line_num = int(parts[1].strip())
                lines = js_code.split('\n')
                print(f"\n--- Around line {line_num} ---")
                for i in range(max(0, line_num-3), min(len(lines), line_num+3)):
                    marker = ">>> " if i == line_num-1 else "    "
                    print(f"{marker}{i+1}: {lines[i][:100]}")
                break
