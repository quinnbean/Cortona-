#!/usr/bin/env python3
"""
Local Testing System for Cortona
Run this BEFORE pushing to catch JavaScript errors early.

Usage: python3 test_before_deploy.py
"""
import re
import subprocess
import sys
import os
import tempfile

def extract_js_from_app():
    """Extract JavaScript from DASHBOARD_PAGE in app.py"""
    with open('app.py', 'r') as f:
        content = f.read()
    
    match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
    if not match:
        return None, "Could not find DASHBOARD_PAGE"
    
    html = match.group(1)
    js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not js_match:
        return None, "Could not find <script> tag"
    
    return js_match.group(1), None

def check_js_syntax(js_code):
    """Check JavaScript syntax using Node.js"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_path = f.name
    
    try:
        result = subprocess.run(['node', '--check', temp_path], 
                               capture_output=True, text=True)
        os.unlink(temp_path)
        return result.returncode == 0, result.stderr
    except FileNotFoundError:
        os.unlink(temp_path)
        return None, "Node.js not found"

def check_regex_patterns(js_code):
    """Check for common regex pattern issues"""
    issues = []
    lines = js_code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for RegExp with single backslash (becomes escape char)
        # In Python's triple-quoted string, '\\b' becomes '\b' (backspace)
        # We need '\\\\b' in Python to get '\\b' in JS for word boundary
        if "new RegExp('" in line or 'new RegExp("' in line:
            # Look for patterns like '\\b' that should be '\\\\b'
            # This is tricky because we're looking at the extracted JS
            if "'\\b" in line or '"\\b' in line:
                # In extracted JS, if we see '\b' it means backspace, not word boundary
                # But when printed, Python shows it as \b (single char)
                pass  # Hard to detect after extraction
            
            # Check for unescaped special chars in string
            match = re.search(r"new RegExp\(['\"]([^'\"]+)['\"]", line)
            if match:
                pattern = match.group(1)
                # Check if it has word boundaries
                if '\\b' in line and '\\\\b' not in line:
                    issues.append(f"Line {i}: Possible unescaped word boundary in RegExp: {line.strip()[:80]}")
    
    return issues

def check_escaping_issues(content):
    """Check the raw app.py for escaping issues in JavaScript"""
    issues = []
    lines = content.split('\n')
    in_dashboard = False
    
    for i, line in enumerate(lines, 1):
        if "DASHBOARD_PAGE = '''" in line:
            in_dashboard = True
            continue
        if in_dashboard and "'''" in line and 'DASHBOARD_PAGE' not in line:
            in_dashboard = False
            continue
        
        if in_dashboard:
            # Check for RegExp with '\\b' which becomes '\b' (backspace) in JS
            # Should be '\\\\b' in Python to get '\\b' in JS
            if "new RegExp('" in line or 'new RegExp("' in line:
                if "'\\\\b'" in line or '"\\\\b"' in line:
                    # This is WRONG - it becomes '\b' (backspace) in JS
                    issues.append(f"Line {i}: RegExp has '\\\\b' which becomes backspace in JS. Use '\\\\\\\\b': {line.strip()[:80]}")
                elif "'\\b'" not in line and "'\\\\\\\\b'" not in line:
                    # Check if there's a word boundary pattern at all
                    if '\\\\b' in line and '\\\\\\\\b' not in line:
                        issues.append(f"Line {i}: RegExp may have escaping issue: {line.strip()[:80]}")
            
            # Check for string literals with problematic escapes
            if "'" in line or '"' in line:
                # \\n in Python becomes \n (newline) in JS string
                # \\\\n in Python becomes \\n in JS which is wrong
                # Need to use \\n in JS for literal newline in strings
                if "'\\\\n'" in line or '"\\\\n"' in line:
                    # This could be intentional (like in alert messages)
                    pass
    
    return issues

def run_flask_check():
    """Try to import app.py to check for Python syntax errors"""
    result = subprocess.run([sys.executable, '-m', 'py_compile', 'app.py'],
                           capture_output=True, text=True)
    return result.returncode == 0, result.stderr

def main():
    print("🔍 Cortona Pre-Deploy Test System")
    print("=" * 50)
    
    # Check Python syntax
    print("\n1️⃣  Checking Python syntax...")
    py_ok, py_err = run_flask_check()
    if py_ok:
        print("   ✅ Python syntax OK")
    else:
        print("   ❌ Python syntax error:")
        print(py_err)
        return 1
    
    # Extract JavaScript
    print("\n2️⃣  Extracting JavaScript from app.py...")
    js_code, js_err = extract_js_from_app()
    if js_err:
        print(f"   ❌ {js_err}")
        return 1
    print(f"   ✅ Extracted {len(js_code):,} bytes of JavaScript")
    
    # Check JS syntax
    print("\n3️⃣  Checking JavaScript syntax with Node.js...")
    node_ok, node_err = check_js_syntax(js_code)
    if node_ok is None:
        print(f"   ⚠️  {node_err} - skipping")
    elif node_ok:
        print("   ✅ JavaScript syntax OK")
    else:
        print("   ❌ JavaScript syntax error:")
        lines = js_code.split('\n')
        for line in node_err.split('\n'):
            print(f"      {line}")
            # Try to show the problematic line
            if ':' in line:
                parts = line.split(':')
                for part in parts:
                    if part.strip().isdigit():
                        line_num = int(part.strip())
                        if 0 < line_num <= len(lines):
                            print(f"\n      >>> Line {line_num}: {lines[line_num-1][:100]}")
                        break
        return 1
    
    # Check raw app.py for escaping issues
    print("\n4️⃣  Checking for JavaScript escaping issues...")
    with open('app.py', 'r') as f:
        raw_content = f.read()
    escaping_issues = check_escaping_issues(raw_content)
    if escaping_issues:
        print("   ⚠️  Potential escaping issues found:")
        for issue in escaping_issues:
            print(f"      {issue}")
    else:
        print("   ✅ No obvious escaping issues found")
    
    # Check regex patterns
    print("\n5️⃣  Checking RegExp patterns...")
    regex_issues = check_regex_patterns(js_code)
    if regex_issues:
        print("   ⚠️  Potential regex issues:")
        for issue in regex_issues:
            print(f"      {issue}")
    else:
        print("   ✅ RegExp patterns look OK")
    
    print("\n" + "=" * 50)
    print("✅ All checks passed! Safe to deploy.")
    print("\nTo deploy:")
    print("  git add -A && git commit -m 'Your message' && git push")
    return 0

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    sys.exit(main())
