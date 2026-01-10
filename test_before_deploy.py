#!/usr/bin/env python3
"""
Comprehensive Bug Checker for Cortona
Run this BEFORE pushing to catch errors early.

Usage: python3 test_before_deploy.py
       python3 test_before_deploy.py --verbose
       python3 test_before_deploy.py --fix  (attempts to fix common issues)
"""
import re
import subprocess
import sys
import os
import tempfile
import json

VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

def log(msg, level='info'):
    if level == 'debug' and not VERBOSE:
        return
    print(msg)

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

def check_python_syntax():
    """Check Python syntax"""
    result = subprocess.run([sys.executable, '-m', 'py_compile', 'app.py'],
                           capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr
    
    # Also check for common Python issues
    issues = []
    with open('app.py', 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # Check for tabs mixed with spaces
        if '\t' in line and '    ' in line:
            issues.append(f"Line {i}: Mixed tabs and spaces")
        
        # Check for trailing whitespace in critical areas
        if line.rstrip() != line.rstrip('\n') and 'DASHBOARD_PAGE' not in line:
            pass  # Allow trailing whitespace in HTML
    
    return True, issues

def check_js_syntax(js_code):
    """Check JavaScript syntax using Node.js"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_path = f.name
    
    try:
        result = subprocess.run(['node', '--check', temp_path], 
                               capture_output=True, text=True)
        os.unlink(temp_path)
        if result.returncode != 0:
            return False, result.stderr
        return True, None
    except FileNotFoundError:
        os.unlink(temp_path)
        return None, "Node.js not found"

def check_js_with_eslint(js_code):
    """Check JavaScript with ESLint if available"""
    try:
        result = subprocess.run(['which', 'eslint'], capture_output=True)
        if result.returncode != 0:
            return None, "ESLint not installed"
    except:
        return None, "ESLint not available"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_path = f.name
    
    try:
        result = subprocess.run(['eslint', '--no-eslintrc', '--env', 'browser,es2021', temp_path],
                               capture_output=True, text=True)
        os.unlink(temp_path)
        return result.returncode == 0, result.stdout
    except:
        os.unlink(temp_path)
        return None, "ESLint failed"

def check_escape_sequences(content):
    """Check for problematic escape sequences in Python strings that become JS"""
    issues = []
    lines = content.split('\n')
    in_dashboard = False
    
    for i, line in enumerate(lines, 1):
        if "DASHBOARD_PAGE = '''" in line:
            in_dashboard = True
            continue
        if in_dashboard and line.strip() == "'''":
            in_dashboard = False
            continue
        
        if in_dashboard:
            # Check for RegExp with problematic escapes
            if "new RegExp(" in line:
                # '\\b' in Python becomes '\b' (backspace) in JS - WRONG
                # Need '\\\\b' in Python to get '\\b' in JS
                if re.search(r"'\\\\b'|\"\\\\b\"", line) and not re.search(r"'\\\\\\\\b'|\"\\\\\\\\b\"", line):
                    issues.append((i, "RegExp word boundary", 
                        "'\\\\b' becomes backspace in JS. Use '\\\\\\\\b' for word boundary", "error"))
                
                # Same for \\s, \\w, \\d, etc.
                for char in ['s', 'w', 'd', 'S', 'W', 'D']:
                    pattern = f"'\\\\\\\\{char}" 
                    if pattern in line and f"'\\\\\\\\\\\\\\\\{char}" not in line:
                        # Check if it's in a RegExp string (not a regex literal)
                        if re.search(rf"RegExp\(['\"].*\\\\{char}", line):
                            issues.append((i, f"RegExp escape \\{char}",
                                f"'\\\\{char}' in RegExp string becomes escape char. Use '\\\\\\\\{char}'", "warning"))
            
            # Check for problematic newlines in strings
            # \\n in Python triple-quoted -> \n in JS (actual newline - breaks string)
            if re.search(r"'[^']*\\\\n[^']*'|\"[^\"]*\\\\n[^\"]*\"", line):
                # This is OK for things like alert() messages
                if 'alert(' not in line and 'console.log' not in line:
                    log(f"   Debug line {i}: Has \\\\n in string", 'debug')
            
            # Check for unescaped quotes that could break strings
            if re.search(r"'[^']*(?<!\\)'[^']*'", line):
                # This could be a nested quote issue
                pass
    
    return issues

def check_undefined_references(js_code):
    """Check for potentially undefined function/variable references"""
    issues = []
    lines = js_code.split('\n')
    
    # Extract all function definitions
    func_defs = set()
    for line in lines:
        # function name() or async function name()
        match = re.search(r'(?:async\s+)?function\s+(\w+)\s*\(', line)
        if match:
            func_defs.add(match.group(1))
        # const name = () => or const name = function
        match = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)\s*=>|function)', line)
        if match:
            func_defs.add(match.group(1))
    
    # Built-in globals that are OK
    builtins = {
        'console', 'document', 'window', 'fetch', 'alert', 'confirm', 'prompt',
        'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        'JSON', 'Math', 'Date', 'Array', 'Object', 'String', 'Number', 'Boolean',
        'Promise', 'async', 'await', 'localStorage', 'sessionStorage',
        'navigator', 'location', 'history', 'performance', 'crypto',
        'WebSocket', 'EventSource', 'FormData', 'URLSearchParams', 'URL',
        'Blob', 'File', 'FileReader', 'Image', 'Audio', 'MediaRecorder',
        'AudioContext', 'webkitAudioContext', 'SpeechRecognition', 'webkitSpeechRecognition',
        'Notification', 'Error', 'TypeError', 'ReferenceError', 'SyntaxError',
        'Map', 'Set', 'WeakMap', 'WeakSet', 'Symbol', 'Proxy', 'Reflect',
        'Intl', 'RegExp', 'encodeURIComponent', 'decodeURIComponent',
        'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'undefined', 'null',
        'true', 'false', 'this', 'super', 'class', 'new', 'delete', 'typeof',
        'void', 'yield', 'import', 'export', 'default', 'extends',
        'io', 'socket',  # Socket.IO
        'electronAPI',   # Electron
    }
    
    # Check for onclick handlers that reference undefined functions
    for i, line in enumerate(lines, 1):
        match = re.search(r'onclick\s*=\s*["\'](\w+)\s*\(', line)
        if match:
            func_name = match.group(1)
            if func_name not in func_defs and func_name not in builtins:
                issues.append((i, f"onclick references '{func_name}'", 
                    f"Function '{func_name}' may not be defined", "warning"))
    
    return issues

def check_html_structure(html):
    """Check for HTML structure issues"""
    issues = []
    
    # Check for unclosed tags (basic check)
    open_tags = []
    tag_pattern = re.compile(r'<(/?)(\w+)[^>]*(/?)>')
    
    for match in tag_pattern.finditer(html):
        is_close = match.group(1) == '/'
        tag_name = match.group(2).lower()
        is_self_close = match.group(3) == '/'
        
        # Skip self-closing and void elements
        void_elements = {'br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 
                        'col', 'embed', 'param', 'source', 'track', 'wbr'}
        if is_self_close or tag_name in void_elements:
            continue
        
        if is_close:
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
            elif tag_name in open_tags:
                issues.append((0, f"Tag mismatch", f"</{tag_name}> closes but last open was <{open_tags[-1] if open_tags else 'none'}>", "warning"))
        else:
            open_tags.append(tag_name)
    
    if open_tags:
        issues.append((0, "Unclosed tags", f"These tags may be unclosed: {', '.join(open_tags[-5:])}", "warning"))
    
    return issues

def check_api_endpoints(content):
    """Check that API endpoints in JS match Flask routes"""
    issues = []
    
    # Extract Flask routes
    flask_routes = set()
    for match in re.finditer(r"@app\.route\(['\"]([^'\"]+)['\"]", content):
        route = match.group(1)
        flask_routes.add(route)
    
    # Extract JS fetch calls
    js_match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
    if js_match:
        js_html = js_match.group(1)
        for match in re.finditer(r"fetch\(['\"]([^'\"]+)['\"]", js_html):
            endpoint = match.group(1)
            if endpoint.startswith('/') and not endpoint.startswith('//'):
                # Check if it exists
                if endpoint not in flask_routes:
                    # Check with regex for dynamic routes
                    found = False
                    for route in flask_routes:
                        if '<' in route:
                            pattern = route.replace('<', '(?P<').replace('>', '>[^/]+)')
                            if re.match(pattern, endpoint):
                                found = True
                                break
                        elif route == endpoint:
                            found = True
                            break
                    if not found:
                        issues.append((0, f"API endpoint '{endpoint}'", 
                            f"fetch('{endpoint}') but no matching Flask route found", "warning"))
    
    return issues

def check_socket_events(content):
    """Check that socket.emit matches socket.on handlers"""
    issues = []
    
    # Extract server-side socket handlers
    server_handlers = set()
    for match in re.finditer(r"@socketio\.on\(['\"]([^'\"]+)['\"]", content):
        server_handlers.add(match.group(1))
    
    # Extract client-side emits
    js_match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
    if js_match:
        js_html = js_match.group(1)
        for match in re.finditer(r"socket\.emit\(['\"]([^'\"]+)['\"]", js_html):
            event = match.group(1)
            if event not in server_handlers:
                log(f"   Debug: Client emits '{event}' but no server handler found", 'debug')
    
    return issues

def check_css_issues(html):
    """Check for CSS issues"""
    issues = []
    
    # Extract CSS
    css_match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    if not css_match:
        return issues
    
    css = css_match.group(1)
    
    # Check for unclosed braces
    open_braces = css.count('{')
    close_braces = css.count('}')
    if open_braces != close_braces:
        issues.append((0, "CSS braces", f"Mismatched braces: {open_braces} open, {close_braces} close", "error"))
    
    # Check for invalid property values
    # (basic check for common typos)
    typos = {
        'absolue': 'absolute',
        'relatvie': 'relative',
        'trasparent': 'transparent',
        'inheret': 'inherit',
    }
    for typo, correct in typos.items():
        if typo in css.lower():
            issues.append((0, "CSS typo", f"Found '{typo}', did you mean '{correct}'?", "warning"))
    
    return issues

def check_common_js_bugs(js_code):
    """Check for common JavaScript bugs"""
    issues = []
    lines = js_code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for = instead of == in conditions
        if re.search(r'if\s*\([^=]*[^!=<>]=[^=][^)]*\)', line):
            if '===' not in line and '!==' not in line and '>=' not in line and '<=' not in line:
                log(f"   Debug line {i}: Possible assignment in if condition", 'debug')
        
        # Check for missing await on async calls
        if 'fetch(' in line and 'await' not in line and 'then(' not in line:
            if not re.search(r'(const|let|var)\s+\w+\s*=\s*fetch', line):
                log(f"   Debug line {i}: fetch() without await or .then()", 'debug')
        
        # Check for console.log left in (just warn)
        if 'console.log(' in line:
            log(f"   Debug line {i}: console.log found (OK for debugging)", 'debug')
        
        # Check for TODO/FIXME comments
        if 'TODO' in line.upper() or 'FIXME' in line.upper():
            issues.append((i, "TODO/FIXME", line.strip()[:60], "info"))
    
    return issues

def check_json_in_js(js_code):
    """Check for JSON parsing issues"""
    issues = []
    lines = js_code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for unquoted keys in objects that should be quoted
        if re.search(r'\{[^}]*\w+\s*:', line):
            # This is OK in JS, just logging
            pass
    
    return issues

def check_template_literals(content):
    """Check for issues with template literals in Python strings"""
    issues = []
    lines = content.split('\n')
    in_dashboard = False
    
    for i, line in enumerate(lines, 1):
        if "DASHBOARD_PAGE = '''" in line:
            in_dashboard = True
            continue
        if in_dashboard and line.strip() == "'''":
            in_dashboard = False
            continue
        
        if in_dashboard:
            # Check for ${} in Python string that might conflict
            if '${' in line:
                # This is fine - it's JS template literal
                pass
            
            # Check for f-string syntax accidentally in JS
            if re.search(r'f["\'][^"\']*\{[^}]+\}', line):
                issues.append((i, "f-string in JS?", "Possible Python f-string syntax in JavaScript", "warning"))
    
    return issues

def run_all_checks():
    """Run all checks and report results"""
    print("🔍 Cortona Comprehensive Bug Checker")
    print("=" * 60)
    
    all_issues = []
    errors = 0
    warnings = 0
    
    # Read app.py
    with open('app.py', 'r') as f:
        content = f.read()
    
    # 1. Python syntax
    print("\n1️⃣  Python Syntax Check...")
    py_ok, py_result = check_python_syntax()
    if not py_ok:
        print(f"   ❌ Python syntax error: {py_result}")
        return 1
    print("   ✅ Python syntax OK")
    if py_result:
        for issue in py_result:
            print(f"   ⚠️  {issue}")
    
    # 2. Extract JS
    print("\n2️⃣  Extracting JavaScript...")
    js_code, js_err = extract_js_from_app()
    if js_err:
        print(f"   ❌ {js_err}")
        return 1
    print(f"   ✅ Extracted {len(js_code):,} characters")
    
    # 3. JS syntax
    print("\n3️⃣  JavaScript Syntax Check (Node.js)...")
    js_ok, js_err = check_js_syntax(js_code)
    if js_ok is None:
        print(f"   ⚠️  {js_err}")
    elif not js_ok:
        print(f"   ❌ JavaScript syntax error:")
        print(f"      {js_err}")
        errors += 1
    else:
        print("   ✅ JavaScript syntax OK")
    
    # 4. Escape sequences
    print("\n4️⃣  Escape Sequence Check...")
    escape_issues = check_escape_sequences(content)
    if escape_issues:
        for line_num, title, desc, level in escape_issues:
            print(f"   {'❌' if level == 'error' else '⚠️'} Line {line_num}: {title}")
            print(f"      {desc}")
            if level == 'error':
                errors += 1
            else:
                warnings += 1
    else:
        print("   ✅ No escape sequence issues")
    
    # 5. Undefined references
    print("\n5️⃣  Undefined Reference Check...")
    undef_issues = check_undefined_references(js_code)
    if undef_issues:
        for line_num, title, desc, level in undef_issues[:5]:  # Limit output
            print(f"   ⚠️  Line {line_num}: {title}")
            log(f"      {desc}", 'debug')
            warnings += 1
        if len(undef_issues) > 5:
            print(f"   ... and {len(undef_issues) - 5} more")
    else:
        print("   ✅ No obvious undefined references")
    
    # 6. API endpoints
    print("\n6️⃣  API Endpoint Check...")
    api_issues = check_api_endpoints(content)
    if api_issues:
        for _, title, desc, level in api_issues:
            print(f"   ⚠️  {title}")
            log(f"      {desc}", 'debug')
            warnings += 1
    else:
        print("   ✅ API endpoints look OK")
    
    # 7. HTML structure
    print("\n7️⃣  HTML Structure Check...")
    html_match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
    if html_match:
        html_issues = check_html_structure(html_match.group(1))
        if html_issues:
            for _, title, desc, level in html_issues:
                print(f"   ⚠️  {title}: {desc}")
                warnings += 1
        else:
            print("   ✅ HTML structure OK")
    
    # 8. CSS check
    print("\n8️⃣  CSS Check...")
    if html_match:
        css_issues = check_css_issues(html_match.group(1))
        if css_issues:
            for _, title, desc, level in css_issues:
                print(f"   {'❌' if level == 'error' else '⚠️'} {title}: {desc}")
                if level == 'error':
                    errors += 1
                else:
                    warnings += 1
        else:
            print("   ✅ CSS looks OK")
    
    # 9. Common JS bugs
    print("\n9️⃣  Common Bug Patterns...")
    js_bugs = check_common_js_bugs(js_code)
    todo_count = sum(1 for b in js_bugs if b[1] == 'TODO/FIXME')
    if js_bugs:
        for line_num, title, desc, level in js_bugs[:3]:
            if title != 'TODO/FIXME':
                print(f"   ⚠️  Line {line_num}: {title}")
        if todo_count:
            print(f"   ℹ️  Found {todo_count} TODO/FIXME comments")
    else:
        print("   ✅ No common bug patterns found")
    
    # 10. Template literals
    print("\n🔟  Template Literal Check...")
    tpl_issues = check_template_literals(content)
    if tpl_issues:
        for line_num, title, desc, level in tpl_issues:
            print(f"   ⚠️  Line {line_num}: {desc}")
            warnings += 1
    else:
        print("   ✅ Template literals OK")
    
    # Summary
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"❌ {errors} error(s) found - DO NOT DEPLOY")
        return 1
    elif warnings > 0:
        print(f"⚠️  {warnings} warning(s) found - Review before deploying")
        print("\n✅ No critical errors. OK to deploy (review warnings).")
    else:
        print("✅ All checks passed! Safe to deploy.")
    
    print("\nTo deploy:")
    print("  git add -A && git commit -m 'Your message' && git push origin main")
    return 0

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    sys.exit(run_all_checks())
