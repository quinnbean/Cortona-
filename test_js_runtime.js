// Runtime test for JavaScript patterns in Cortona
// Run with: node test_js_runtime.js

console.log("🧪 Testing JavaScript Runtime Patterns...\n");

let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        console.log(`✅ ${name}`);
        passed++;
    } catch (e) {
        console.log(`❌ ${name}: ${e.message}`);
        failed++;
    }
}

// Test word boundary regex (the main issue we fixed)
test("Word boundary regex with dynamic content", () => {
    const word = "test";
    const regex = new RegExp('\\b' + word + '\\b', 'gi');
    if (!regex.test("this is a test string")) throw new Error("Pattern didn't match");
});

test("Spell check regex pattern", () => {
    const wrong = "teh";
    const regex = new RegExp('\\b' + wrong + '\\b', 'gi');
    const text = "teh quick brown fox";
    const result = text.replace(regex, "the");
    if (result !== "the quick brown fox") throw new Error("Replace failed");
});

test("Punctuation replacement regex", () => {
    const word = "period";
    const regex = new RegExp('\\b' + word + '\\b', 'gi');
    const text = "end of sentence period";
    const result = text.replace(regex, ".");
    if (!result.includes(".")) throw new Error("Replace failed");
});

test("escapeRegex function", () => {
    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
    const escaped = escapeRegex("hello.world");
    if (escaped !== "hello\\.world") throw new Error("Escape failed");
});

test("Filler word removal", () => {
    const filler = "um";
    const regex = new RegExp('\\b' + filler + '\\b[,]?\\s*', 'gi');
    const text = "so um I was thinking";
    const result = text.replace(regex, "");
    if (result !== "so I was thinking") throw new Error("Filler removal failed");
});

test("Wake word extraction", () => {
    const wakeWord = "hey jarvis";
    const assistantName = wakeWord.replace(/^(hey|ok|hi|hello)\s+/i, '').trim() || 'Jarvis';
    if (assistantName !== "jarvis") throw new Error(`Got: ${assistantName}`);
});

test("Newline in strings", () => {
    const text = "line1\nline2";
    if (!text.includes("\n")) throw new Error("Newline not present");
});

console.log(`\n${"=".repeat(40)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
