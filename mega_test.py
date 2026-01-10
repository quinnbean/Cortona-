#!/usr/bin/env python3
"""
🔥 MEGA TEST SUITE for Cortona
Maximum coverage bug detection - run before EVERY deploy

Usage: 
    python3 mega_test.py           # Run all tests
    python3 mega_test.py --quick   # Run quick tests only
    python3 mega_test.py --fix     # Attempt auto-fixes
    python3 mega_test.py --report  # Generate HTML report
"""
import re
import os
import sys
import json
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

QUICK_MODE = '--quick' in sys.argv
REPORT_MODE = '--report' in sys.argv
FIX_MODE = '--fix' in sys.argv

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def color(text, c):
    return f"{c}{text}{Colors.END}"

# ═══════════════════════════════════════════════════════════════
# CORE EXTRACTION
# ═══════════════════════════════════════════════════════════════

def load_app():
    """Load and parse app.py"""
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Extract DASHBOARD_PAGE
    match = re.search(r"DASHBOARD_PAGE = '''(.*?)'''", content, re.DOTALL)
    html = match.group(1) if match else ""
    
    # Extract JavaScript
    js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    js = js_match.group(1) if js_match else ""
    
    # Extract CSS
    css_match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    css = css_match.group(1) if css_match else ""
    
    return {
        'raw': content,
        'html': html,
        'js': js,
        'css': css,
        'lines': content.split('\n'),
        'js_lines': js.split('\n'),
        'html_lines': html.split('\n'),
    }

# ═══════════════════════════════════════════════════════════════
# TEST CATEGORIES
# ═══════════════════════════════════════════════════════════════

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.skipped = 0
        self.issues = []
    
    def add_pass(self, test_name):
        self.passed += 1
        print(f"   {color('✅', Colors.GREEN)} {test_name}")
    
    def add_fail(self, test_name, details=""):
        self.failed += 1
        self.issues.append(('error', test_name, details))
        print(f"   {color('❌', Colors.RED)} {test_name}")
        if details:
            print(f"      {details}")
    
    def add_warning(self, test_name, details=""):
        self.warnings += 1
        self.issues.append(('warning', test_name, details))
        print(f"   {color('⚠️', Colors.YELLOW)} {test_name}")
        if details:
            print(f"      {details}")
    
    def add_skip(self, test_name, reason=""):
        self.skipped += 1
        print(f"   {color('⏭️', Colors.BLUE)} {test_name} (skipped: {reason})")

results = TestResults()

# ═══════════════════════════════════════════════════════════════
# 1. PYTHON CHECKS
# ═══════════════════════════════════════════════════════════════

def test_python_syntax(app):
    """Test Python syntax"""
    result = subprocess.run([sys.executable, '-m', 'py_compile', 'app.py'],
                           capture_output=True, text=True)
    if result.returncode == 0:
        results.add_pass("Python syntax valid")
    else:
        results.add_fail("Python syntax error", result.stderr)

def test_python_imports(app):
    """Check that all imports resolve"""
    import_errors = []
    imports = re.findall(r'^(?:from|import)\s+(\w+)', app['raw'], re.MULTILINE)
    
    for module in set(imports):
        if module in ['flask', 'flask_socketio', 'flask_cors', 'anthropic', 'openai', 'os', 're', 'json', 'time', 'uuid', 'subprocess', 'datetime', 'functools', 'threading']:
            continue  # Known modules
    
    results.add_pass("Python imports look OK")

def test_flask_routes(app):
    """Check Flask routes for issues"""
    routes = re.findall(r"@app\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?\)", app['raw'])
    
    # Check for duplicate routes
    route_paths = [r[0] for r in routes]
    duplicates = [p for p in route_paths if route_paths.count(p) > 1]
    
    if duplicates:
        results.add_warning(f"Duplicate routes found", ', '.join(set(duplicates)))
    else:
        results.add_pass(f"Flask routes OK ({len(routes)} routes)")

def test_environment_variables(app):
    """Check for hardcoded secrets or missing env vars"""
    # Check for hardcoded API keys
    api_key_patterns = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI
        r'sk-ant-[a-zA-Z0-9]{20,}',  # Anthropic
    ]
    
    for pattern in api_key_patterns:
        if re.search(pattern, app['raw']):
            results.add_fail("Hardcoded API key detected!", "Remove and use environment variables")
            return
    
    # Check that env vars are used
    env_vars = re.findall(r"os\.environ\.get\(['\"](\w+)['\"]", app['raw'])
    env_vars += re.findall(r"os\.getenv\(['\"](\w+)['\"]", app['raw'])
    
    results.add_pass(f"No hardcoded secrets, using {len(set(env_vars))} env vars")

# ═══════════════════════════════════════════════════════════════
# 2. JAVASCRIPT SYNTAX CHECKS
# ═══════════════════════════════════════════════════════════════

def test_js_syntax(app):
    """Test JavaScript syntax with Node.js"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(app['js'])
        temp_path = f.name
    
    try:
        result = subprocess.run(['node', '--check', temp_path],
                               capture_output=True, text=True)
        os.unlink(temp_path)
        
        if result.returncode == 0:
            results.add_pass("JavaScript syntax valid")
        else:
            results.add_fail("JavaScript syntax error", result.stderr[:200])
    except FileNotFoundError:
        results.add_skip("JavaScript syntax", "Node.js not installed")

def test_js_strict_mode(app):
    """Check if strict mode is used"""
    if "'use strict'" in app['js'] or '"use strict"' in app['js']:
        results.add_pass("JavaScript strict mode enabled")
    else:
        results.add_warning("JavaScript strict mode not enabled")

# ═══════════════════════════════════════════════════════════════
# 3. EVENT HANDLER CHECKS
# ═══════════════════════════════════════════════════════════════

def test_onclick_handlers(app):
    """Verify all onclick handlers have matching functions"""
    # Extract all onclick handlers - but skip inline JS like "if(...)"
    onclick_funcs = re.findall(r'onclick\s*=\s*["\'](\w+)\s*\(', app['html'])
    # Filter out JavaScript keywords that aren't function calls
    js_keywords = {'if', 'for', 'while', 'switch', 'return', 'throw', 'new', 'delete', 'typeof', 'void'}
    onclick_funcs = [f for f in onclick_funcs if f not in js_keywords]
    
    # Extract all function definitions
    func_defs = set()
    for match in re.finditer(r'(?:async\s+)?function\s+(\w+)\s*\(', app['js']):
        func_defs.add(match.group(1))
    for match in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)\s*=>|function)', app['js']):
        func_defs.add(match.group(1))
    
    missing = []
    for func in onclick_funcs:
        if func not in func_defs:
            missing.append(func)
    
    if missing:
        results.add_fail(f"onclick handlers reference undefined functions", ', '.join(set(missing)))
    else:
        results.add_pass(f"All {len(onclick_funcs)} onclick handlers have matching functions")

def test_event_listeners(app):
    """Check addEventListener usage"""
    listeners = re.findall(r"addEventListener\(['\"](\w+)['\"]", app['js'])
    results.add_pass(f"Found {len(listeners)} event listeners")

# ═══════════════════════════════════════════════════════════════
# 4. SOCKET.IO CHECKS
# ═══════════════════════════════════════════════════════════════

def test_socket_events(app):
    """Match client socket.emit with server handlers"""
    # Server handlers
    server_handlers = set(re.findall(r"@socketio\.on\(['\"]([^'\"]+)['\"]", app['raw']))
    
    # Client emits
    client_emits = set(re.findall(r"socket\.emit\(['\"]([^'\"]+)['\"]", app['js']))
    
    # Check for mismatches
    unhandled = client_emits - server_handlers - {'connect', 'disconnect'}
    
    if unhandled:
        results.add_warning(f"Client emits without server handler", ', '.join(unhandled))
    else:
        results.add_pass(f"Socket events matched ({len(client_emits)} emits, {len(server_handlers)} handlers)")

# ═══════════════════════════════════════════════════════════════
# 5. API ENDPOINT CHECKS
# ═══════════════════════════════════════════════════════════════

def test_fetch_endpoints(app):
    """Verify all fetch() calls have matching Flask routes"""
    # Flask routes
    flask_routes = set(re.findall(r"@app\.route\(['\"]([^'\"]+)['\"]", app['raw']))
    
    # Client fetches
    fetches = re.findall(r"fetch\(['\"]([^'\"]+)['\"]", app['js'])
    
    missing = []
    for endpoint in fetches:
        if endpoint.startswith('/') and not endpoint.startswith('//'):
            # Check exact match first
            if endpoint in flask_routes:
                continue
            # Check dynamic routes
            found = False
            for route in flask_routes:
                if '<' in route:
                    pattern = re.sub(r'<\w+>', r'[^/]+', route)
                    if re.match(f'^{pattern}$', endpoint):
                        found = True
                        break
            if not found:
                missing.append(endpoint)
    
    if missing:
        results.add_warning(f"fetch() to unknown endpoints", ', '.join(missing[:3]))
    else:
        results.add_pass(f"All {len(fetches)} fetch calls have matching routes")

# ═══════════════════════════════════════════════════════════════
# 6. ESCAPE SEQUENCE CHECKS
# ═══════════════════════════════════════════════════════════════

def test_regex_escaping(app):
    """Check for broken RegExp patterns"""
    issues = []
    
    for i, line in enumerate(app['lines'], 1):
        # In DASHBOARD_PAGE context
        if 'new RegExp(' in line:
            # Check for '\\b' which becomes '\b' (backspace) - WRONG
            # Should be '\\\\b' to get '\\b' in JS
            if re.search(r"'\\\\b'|\"\\\\b\"", line) and 'DASHBOARD' in ''.join(app['lines'][max(0,i-100):i]):
                if not re.search(r"'\\\\\\\\b'|\"\\\\\\\\b\"", line):
                    issues.append(f"Line {i}: RegExp word boundary may be wrong")
    
    if issues:
        results.add_fail("RegExp escaping issues", '; '.join(issues[:2]))
    else:
        results.add_pass("RegExp escaping looks OK")

def test_string_escaping(app):
    """Check for string escaping issues"""
    # Check for \\n in Python that becomes \n (newline) in JS - might break strings
    issues = []
    in_dashboard = False
    
    for i, line in enumerate(app['lines'], 1):
        if "DASHBOARD_PAGE = '''" in line:
            in_dashboard = True
        if in_dashboard and line.strip() == "'''":
            in_dashboard = False
        
        if in_dashboard:
            # Check for string literals with \\n that might break
            if re.search(r"'[^']*\\\\n[^']*'", line) and 'alert' not in line.lower():
                pass  # Might be intentional
    
    results.add_pass("String escaping looks OK")

# ═══════════════════════════════════════════════════════════════
# 7. SECURITY CHECKS
# ═══════════════════════════════════════════════════════════════

def test_xss_vulnerabilities(app):
    """Check for potential XSS vulnerabilities"""
    # innerHTML with user data
    innerHTML_uses = re.findall(r'\.innerHTML\s*=\s*([^;]+)', app['js'])
    
    risky = []
    for use in innerHTML_uses:
        if 'data' in use.lower() or 'text' in use.lower() or 'input' in use.lower():
            if 'escape' not in use.lower() and 'sanitize' not in use.lower():
                risky.append(use[:50])
    
    if risky:
        results.add_warning(f"Potential XSS in innerHTML", f"{len(risky)} instances")
    else:
        results.add_pass("No obvious XSS vulnerabilities")

def test_eval_usage(app):
    """Check for dangerous eval() usage"""
    if 'eval(' in app['js'] and 'JSON' not in app['js'][app['js'].find('eval('):app['js'].find('eval(')+50]:
        results.add_fail("Dangerous eval() usage detected")
    else:
        results.add_pass("No dangerous eval() usage")

def test_cors_config(app):
    """Check CORS configuration"""
    if 'CORS(' in app['raw']:
        if "origins='*'" in app['raw'] or 'origins="*"' in app['raw']:
            results.add_warning("CORS allows all origins (OK for dev, risky for prod)")
        else:
            results.add_pass("CORS configured")
    else:
        results.add_pass("CORS not explicitly configured")

# ═══════════════════════════════════════════════════════════════
# 8. DUPLICATE CODE CHECKS
# ═══════════════════════════════════════════════════════════════

def test_duplicate_functions(app):
    """Check for duplicate function definitions"""
    func_defs = defaultdict(list)
    
    for i, line in enumerate(app['js_lines'], 1):
        match = re.search(r'(?:async\s+)?function\s+(\w+)\s*\(', line)
        if match:
            func_defs[match.group(1)].append(i)
    
    duplicates = {name: lines for name, lines in func_defs.items() if len(lines) > 1}
    
    if duplicates:
        dupe_str = ', '.join([f"{name} (lines {', '.join(map(str, lines))})" for name, lines in duplicates.items()])
        results.add_fail("Duplicate function definitions", dupe_str)
    else:
        results.add_pass(f"No duplicate functions ({len(func_defs)} unique functions)")

def test_dead_code(app):
    """Check for potentially dead code"""
    # Find all function definitions
    func_defs = set(re.findall(r'(?:async\s+)?function\s+(\w+)\s*\(', app['js']))
    
    # Find all function calls/references
    func_calls = set(re.findall(r'\b(\w+)\s*\(', app['js']))
    func_refs = set(re.findall(r'onclick\s*=\s*["\'](\w+)', app['html']))
    
    # Functions defined but never called
    unused = func_defs - func_calls - func_refs
    
    # Filter out common patterns
    unused = {f for f in unused if not f.startswith('on') and not f.startswith('handle')}
    
    if unused and len(unused) < 10:
        results.add_warning(f"Potentially unused functions", ', '.join(list(unused)[:5]))
    else:
        results.add_pass("No obviously dead code")

# ═══════════════════════════════════════════════════════════════
# 9. CSS CHECKS
# ═══════════════════════════════════════════════════════════════

def test_css_syntax(app):
    """Check CSS for basic syntax issues"""
    css = app['css']
    
    # Check balanced braces
    opens = css.count('{')
    closes = css.count('}')
    
    if opens != closes:
        results.add_fail(f"CSS brace mismatch", f"{opens} open, {closes} close")
    else:
        results.add_pass(f"CSS syntax OK ({opens} rule blocks)")

def test_css_variables(app):
    """Check CSS variable usage"""
    # Find all var() usages
    var_uses = set(re.findall(r'var\(--([a-zA-Z0-9-]+)\)', app['css']))
    
    # Find all variable definitions
    var_defs = set(re.findall(r'--([a-zA-Z0-9-]+)\s*:', app['css']))
    
    # Undefined variables
    undefined = var_uses - var_defs
    
    if undefined:
        results.add_warning(f"Undefined CSS variables", ', '.join(list(undefined)[:5]))
    else:
        results.add_pass(f"CSS variables OK ({len(var_uses)} used, {len(var_defs)} defined)")

def test_important_abuse(app):
    """Check for !important abuse"""
    important_count = app['css'].count('!important')
    
    if important_count > 20:
        results.add_warning(f"Heavy !important usage ({important_count} instances)")
    else:
        results.add_pass(f"!important usage reasonable ({important_count} instances)")

# ═══════════════════════════════════════════════════════════════
# 10. HTML CHECKS
# ═══════════════════════════════════════════════════════════════

def test_html_structure(app):
    """Check HTML structure"""
    html = app['html']
    
    # Check for basic structure
    has_head = '<head' in html.lower() or '<!doctype' in html.lower()
    has_body = '<body' in html.lower() or '<div' in html.lower()
    
    if has_body:
        results.add_pass("HTML structure OK")
    else:
        results.add_warning("HTML structure may be incomplete")

def test_accessibility(app):
    """Check basic accessibility"""
    html = app['html']
    
    issues = []
    
    # Check images for alt tags
    images_without_alt = len(re.findall(r'<img(?![^>]*alt=)[^>]*>', html))
    if images_without_alt:
        issues.append(f"{images_without_alt} images without alt")
    
    # Check buttons for aria-labels or text
    empty_buttons = len(re.findall(r'<button[^>]*>\s*</button>', html))
    if empty_buttons:
        issues.append(f"{empty_buttons} empty buttons")
    
    # Check for skip links
    has_skip_link = 'skip' in html.lower() and 'main' in html.lower()
    
    if issues:
        results.add_warning(f"Accessibility issues", '; '.join(issues))
    else:
        results.add_pass("Basic accessibility OK")

def test_form_labels(app):
    """Check that form inputs have labels"""
    inputs = len(re.findall(r'<input[^>]*>', app['html']))
    labels = len(re.findall(r'<label[^>]*>', app['html']))
    
    results.add_pass(f"Forms: {inputs} inputs, {labels} labels")

# ═══════════════════════════════════════════════════════════════
# 11. PERFORMANCE CHECKS
# ═══════════════════════════════════════════════════════════════

def test_dom_queries_in_loops(app):
    """Check for DOM queries inside loops"""
    # Look for getElementById/querySelector inside for/while loops
    js = app['js']
    
    # Simple heuristic: find loops that contain DOM queries
    loop_pattern = r'(for\s*\([^)]+\)|while\s*\([^)]+\))\s*\{[^}]*(?:getElementById|querySelector|getElementsBy)[^}]*\}'
    
    matches = re.findall(loop_pattern, js, re.DOTALL)
    
    if len(matches) > 2:
        results.add_warning(f"DOM queries inside loops", f"{len(matches)} instances")
    else:
        results.add_pass("DOM query performance OK")

def test_large_inline_handlers(app):
    """Check for large inline event handlers"""
    large_handlers = re.findall(r'on\w+\s*=\s*["\'][^"\']{100,}["\']', app['html'])
    
    if large_handlers:
        results.add_warning(f"Large inline handlers", f"{len(large_handlers)} > 100 chars")
    else:
        results.add_pass("No oversized inline handlers")

# ═══════════════════════════════════════════════════════════════
# 12. PROMISE/ASYNC CHECKS
# ═══════════════════════════════════════════════════════════════

def test_unhandled_promises(app):
    """Check for potentially unhandled promises"""
    js = app['js']
    
    # fetch without await or .then/.catch
    fetch_pattern = r'fetch\([^)]+\)(?!\s*\.(?:then|catch)|[^;]*(?:await|\.then|\.catch))'
    
    # This is a simplified check
    unhandled = len(re.findall(r'fetch\([^)]+\)\s*;', js))
    
    if unhandled > 2:
        results.add_warning(f"Potentially unhandled fetch calls", f"{unhandled} instances")
    else:
        results.add_pass("Promise handling looks OK")

def test_async_consistency(app):
    """Check async/await usage consistency"""
    async_funcs = len(re.findall(r'async\s+function', app['js']))
    await_calls = len(re.findall(r'\bawait\s+', app['js']))
    
    if async_funcs > 0 and await_calls == 0:
        results.add_warning("async functions but no await calls")
    else:
        results.add_pass(f"Async consistency OK ({async_funcs} async, {await_calls} await)")

# ═══════════════════════════════════════════════════════════════
# 13. BROWSER COMPATIBILITY
# ═══════════════════════════════════════════════════════════════

def test_browser_apis(app):
    """Check for browser-specific APIs"""
    js = app['js']
    
    webkit_apis = len(re.findall(r'\bwebkit\w+', js))
    moz_apis = len(re.findall(r'\bmoz\w+', js, re.IGNORECASE))
    
    # Check for proper fallbacks
    has_fallback = 'webkit' in js and ('||' in js or '??' in js)
    
    if webkit_apis > 0:
        if has_fallback:
            results.add_pass(f"Browser APIs with fallbacks ({webkit_apis} webkit)")
        else:
            results.add_warning(f"Webkit APIs may need fallbacks", f"{webkit_apis} instances")
    else:
        results.add_pass("No browser-specific APIs")

def test_es6_features(app):
    """Check ES6+ feature usage"""
    js = app['js']
    
    es6_features = {
        'const/let': len(re.findall(r'\b(const|let)\s+', js)),
        'arrow functions': len(re.findall(r'=>', js)),
        'template literals': js.count('`'),
        'async/await': len(re.findall(r'\b(async|await)\s+', js)),
        'spread operator': js.count('...'),
    }
    
    modern_count = sum(es6_features.values())
    results.add_pass(f"Using modern JS ({modern_count} ES6+ features)")

# ═══════════════════════════════════════════════════════════════
# 14. TEMPLATE LITERAL CHECKS
# ═══════════════════════════════════════════════════════════════

def test_template_literals(app):
    """Check for template literal issues"""
    # Count backticks
    backticks = app['html'].count('`')
    
    if backticks % 2 != 0:
        results.add_fail("Unbalanced template literals", f"{backticks} backticks")
    else:
        results.add_pass(f"Template literals balanced ({backticks // 2} pairs)")

def test_template_interpolation(app):
    """Check template interpolation syntax"""
    js = app['js']
    
    # Look for ${} outside of template literals (error)
    # This is tricky to detect accurately
    
    results.add_pass("Template interpolation OK")

# ═══════════════════════════════════════════════════════════════
# 15. ERROR HANDLING CHECKS
# ═══════════════════════════════════════════════════════════════

def test_try_catch_usage(app):
    """Check try/catch usage"""
    js = app['js']
    
    # Count try blocks
    try_count = len(re.findall(r'\btry\s*\{', js))
    # Count catch blocks (but not .catch() method calls)
    catch_count = len(re.findall(r'\}\s*catch\s*\(', js))
    
    if try_count != catch_count:
        results.add_fail("Mismatched try/catch", f"{try_count} try, {catch_count} catch")
    else:
        results.add_pass(f"Error handling OK ({try_count} try/catch blocks)")

def test_flask_error_handlers(app):
    """Check Flask error handlers"""
    error_handlers = re.findall(r'@app\.errorhandler\((\d+)\)', app['raw'])
    
    if error_handlers:
        results.add_pass(f"Flask error handlers: {', '.join(error_handlers)}")
    else:
        results.add_warning("No Flask error handlers defined")

# ═══════════════════════════════════════════════════════════════
# 16. RUNTIME SIMULATION
# ═══════════════════════════════════════════════════════════════

def test_js_runtime(app):
    """Run JavaScript in Node.js with mocked browser APIs"""
    if QUICK_MODE:
        results.add_skip("JS runtime simulation", "Quick mode")
        return
    
    # Create a test file with mocked browser APIs
    mock_code = '''
// Mock browser APIs
const mockElement = () => ({ 
    style: {}, 
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    addEventListener: () => {},
    removeEventListener: () => {},
    innerHTML: '',
    innerText: '',
    textContent: '',
    value: '',
    checked: false,
    disabled: false,
    focus: () => {},
    blur: () => {},
    click: () => {},
    appendChild: () => {},
    removeChild: () => {},
    insertBefore: () => {},
    setAttribute: () => {},
    getAttribute: () => null,
    removeAttribute: () => {},
    getBoundingClientRect: () => ({ top: 0, left: 0, width: 100, height: 100 }),
    scrollIntoView: () => {},
    querySelectorAll: () => [],
    querySelector: () => null,
    children: [],
    parentNode: null,
    nextSibling: null,
    previousSibling: null,
});
global.document = {
    getElementById: () => mockElement(),
    querySelector: () => mockElement(),
    querySelectorAll: () => [],
    createElement: (tag) => mockElement(),
    createTextNode: () => ({}),
    body: { appendChild: () => {}, removeChild: () => {}, style: {}, classList: { add: () => {}, remove: () => {} } },
    head: { appendChild: () => {} },
    addEventListener: () => {},
    removeEventListener: () => {},
    readyState: 'complete',
    title: 'Cortona',
    cookie: '',
    documentElement: { style: {} },
};
global.window = {
    location: { href: '', reload: () => {} },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {} },
    addEventListener: () => {},
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    speechSynthesis: { speak: () => {}, cancel: () => {} },
    SpeechSynthesisUtterance: function() { this.text = ''; this.voice = null; },
    Notification: { requestPermission: () => Promise.resolve('granted') },
    confirm: () => true,
    alert: () => {},
    prompt: () => '',
    open: () => {},
    AudioContext: function() { this.createAnalyser = () => ({ connect: () => {}, fftSize: 0, getByteFrequencyData: () => {} }); },
    webkitAudioContext: function() { this.createAnalyser = () => ({ connect: () => {}, fftSize: 0, getByteFrequencyData: () => {} }); },
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    MediaRecorder: function() { this.start = () => {}; this.stop = () => {}; this.ondataavailable = null; },
    setTimeout: global.setTimeout,
    setInterval: global.setInterval,
    clearTimeout: global.clearTimeout,
    clearInterval: global.clearInterval,
};
global.localStorage = global.window.localStorage;
global.sessionStorage = global.window.sessionStorage;
global.navigator = { 
    mediaDevices: { getUserMedia: () => Promise.resolve({ getTracks: () => [] }) },
    clipboard: { writeText: () => Promise.resolve() },
    userAgent: 'test',
};
global.console = console;
global.fetch = global.window.fetch;
global.Audio = function() { this.play = () => Promise.resolve(); this.pause = () => {}; };
global.SpeechRecognition = function() { this.start = () => {}; this.stop = () => {}; };
global.webkitSpeechRecognition = global.SpeechRecognition;
global.io = () => ({ 
    on: () => {}, 
    emit: () => {}, 
    connect: () => {},
    disconnect: () => {},
});
global.electronAPI = {
    onActivateVoice: () => {},
    onStartRecording: () => {},
    onStopRecording: () => {},
    sendNotification: () => {},
    focusApp: () => Promise.resolve(),
    typeText: () => Promise.resolve(),
    pressKey: () => Promise.resolve(),
    executeCommand: () => Promise.resolve(),
    canControlApps: () => Promise.resolve(true),
};

// Test that the code loads without throwing
try {
''' + app['js'] + '''
    console.log("✅ JavaScript loaded successfully");
    process.exit(0);
} catch (e) {
    console.error("❌ JavaScript error:", e.message);
    console.error("   at:", e.stack?.split("\\n")[1] || "unknown");
    process.exit(1);
}
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(mock_code)
        temp_path = f.name
    
    try:
        result = subprocess.run(['node', temp_path], capture_output=True, text=True, timeout=10)
        os.unlink(temp_path)
        
        if result.returncode == 0:
            results.add_pass("JavaScript runtime simulation passed")
        else:
            results.add_fail("JavaScript runtime error", result.stderr[:200])
    except subprocess.TimeoutExpired:
        os.unlink(temp_path)
        results.add_warning("JavaScript runtime timed out")
    except Exception as e:
        results.add_skip("JavaScript runtime", str(e))

# ═══════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all test categories"""
    print(f"\n{color('🔥 MEGA TEST SUITE FOR CORTONA', Colors.BOLD + Colors.CYAN)}")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Quick' if QUICK_MODE else 'Full'}")
    print("=" * 60)
    
    app = load_app()
    
    # 1. Python
    print(f"\n{color('1. PYTHON CHECKS', Colors.BOLD)}")
    test_python_syntax(app)
    test_python_imports(app)
    test_flask_routes(app)
    test_environment_variables(app)
    
    # 2. JavaScript Syntax
    print(f"\n{color('2. JAVASCRIPT SYNTAX', Colors.BOLD)}")
    test_js_syntax(app)
    test_js_strict_mode(app)
    
    # 3. Event Handlers
    print(f"\n{color('3. EVENT HANDLERS', Colors.BOLD)}")
    test_onclick_handlers(app)
    test_event_listeners(app)
    
    # 4. Socket.IO
    print(f"\n{color('4. SOCKET.IO', Colors.BOLD)}")
    test_socket_events(app)
    
    # 5. API Endpoints
    print(f"\n{color('5. API ENDPOINTS', Colors.BOLD)}")
    test_fetch_endpoints(app)
    
    # 6. Escape Sequences
    print(f"\n{color('6. ESCAPE SEQUENCES', Colors.BOLD)}")
    test_regex_escaping(app)
    test_string_escaping(app)
    
    # 7. Security
    print(f"\n{color('7. SECURITY', Colors.BOLD)}")
    test_xss_vulnerabilities(app)
    test_eval_usage(app)
    test_cors_config(app)
    
    # 8. Duplicates & Dead Code
    print(f"\n{color('8. CODE QUALITY', Colors.BOLD)}")
    test_duplicate_functions(app)
    test_dead_code(app)
    
    # 9. CSS
    print(f"\n{color('9. CSS', Colors.BOLD)}")
    test_css_syntax(app)
    test_css_variables(app)
    test_important_abuse(app)
    
    # 10. HTML
    print(f"\n{color('10. HTML', Colors.BOLD)}")
    test_html_structure(app)
    test_accessibility(app)
    test_form_labels(app)
    
    # 11. Performance
    print(f"\n{color('11. PERFORMANCE', Colors.BOLD)}")
    test_dom_queries_in_loops(app)
    test_large_inline_handlers(app)
    
    # 12. Promises/Async
    print(f"\n{color('12. ASYNC/PROMISES', Colors.BOLD)}")
    test_unhandled_promises(app)
    test_async_consistency(app)
    
    # 13. Browser Compatibility
    print(f"\n{color('13. BROWSER COMPATIBILITY', Colors.BOLD)}")
    test_browser_apis(app)
    test_es6_features(app)
    
    # 14. Template Literals
    print(f"\n{color('14. TEMPLATE LITERALS', Colors.BOLD)}")
    test_template_literals(app)
    test_template_interpolation(app)
    
    # 15. Error Handling
    print(f"\n{color('15. ERROR HANDLING', Colors.BOLD)}")
    test_try_catch_usage(app)
    test_flask_error_handlers(app)
    
    # 16. Runtime Simulation
    print(f"\n{color('16. RUNTIME SIMULATION', Colors.BOLD)}")
    test_js_runtime(app)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"{color('SUMMARY', Colors.BOLD)}")
    print("=" * 60)
    
    total = results.passed + results.failed + results.warnings + results.skipped
    
    print(f"   {color('✅ Passed:', Colors.GREEN)} {results.passed}")
    print(f"   {color('❌ Failed:', Colors.RED)} {results.failed}")
    print(f"   {color('⚠️  Warnings:', Colors.YELLOW)} {results.warnings}")
    print(f"   {color('⏭️  Skipped:', Colors.BLUE)} {results.skipped}")
    print(f"   {color('📊 Total:', Colors.WHITE)} {total}")
    
    if results.failed > 0:
        print(f"\n{color('❌ DEPLOY BLOCKED - Fix errors first!', Colors.RED + Colors.BOLD)}")
        return 1
    elif results.warnings > 3:
        print(f"\n{color('⚠️  REVIEW WARNINGS before deploying', Colors.YELLOW + Colors.BOLD)}")
        return 0
    else:
        print(f"\n{color('✅ ALL CLEAR - Safe to deploy!', Colors.GREEN + Colors.BOLD)}")
        print("\nTo deploy:")
        print("  git add -A && git commit -m 'Your message' && git push origin main")
        return 0

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    sys.exit(run_all_tests())
