"use strict";

/* Node tests for static/layout-corrector.js */
const assert = require("assert");
const path = require("path");

const Layout = require(path.join(__dirname, "..", "static", "layout-corrector.js"));

function correct(text, sourceLanguage = "auto") {
  return Layout.correctText(text, { sourceLanguage });
}

function testShortWords() {
  // ghbdtn -> привет
  const r1 = correct("ghbdtn", "ru");
  assert.strictEqual(r1.text, "привет", `expected привет, got ${r1.text}`);
  assert.strictEqual(r1.level, "high", `expected high confidence, got ${r1.level}`);

  // руддщ -> hello
  const r2 = correct("руддщ");
  assert.strictEqual(r2.text, "hello", `expected hello, got ${r2.text}`);
}

function testSentence() {
  const r = correct("ghbdtn rfr ndjb ltkf", "ru");
  assert.strictEqual(r.text, "привет как твои дела", `got ${r.text}`);
  assert.strictEqual(r.level, "high", `expected high, got ${r.level}`);
}

function testCorrectTextUntouched() {
  // Correct English must not be converted.
  const r = correct("hello world this is fine", "en");
  assert.strictEqual(r.text, "hello world this is fine", `got ${r.text}`);
  assert.strictEqual(r.changed, false);

  // Correct Russian must not be converted.
  const r2 = correct("привет как дела", "ru");
  assert.strictEqual(r2.changed, false, `got ${r2.text}`);
}

function testMixedIntentional() {
  const r = correct("Напиши email to optical store support");
  assert.strictEqual(r.text, "Напиши email to optical store support", `got ${r.text}`);
  assert.strictEqual(r.changed, false);
}

function testHebrew() {
  // "hello" typed with a Hebrew layout active -> י-ק-ך-ך-ם (final mem on 'o') -> "hello"
  const typedWithHebrewLayout = "\u05D9\u05E7\u05DA\u05DA\u05DD"; // יקךכם
  const r = correct(typedWithHebrewLayout);
  assert.strictEqual(r.text, "hello", `expected hello, got ${r.text}`);
  // "שלום" typed with an English layout active -> "akuo" -> "שלום"
  // (Hebrew: ש=a, ל=k, ו=u, ם=o on the standard Israeli layout)
  const r2 = correct("akuo", "he");
  assert.strictEqual(r2.text, "\u05E9\u05DC\u05D5\u05DD", `expected שלום, got ${r2.text}`);
}

function testUrlsEmailsPaths() {
  const input =
    "Visit https://example.com/ghbdtn or www.site.org and mail a@b.com " +
    "path C:\\Users\\ghbdtn\\file.txt and v1.5.1 works";
  const r = correct(input);
  assert.strictEqual(r.text, input, `protected tokens changed: ${r.text}`);
  assert.strictEqual(r.changed, false);
}

function testNumbersAndCode() {
  const input = "count 12345 items and api_key=ghbdtn";
  const r = correct(input);
  assert.strictEqual(r.changed, false, `got ${r.text}`);
}

function testPunctuationPreserved() {
  const input = "ghbdtn! rfr ndjb ltkf?";
  const r = correct(input, "ru");
  assert.strictEqual(r.text, "привет! как твои дела?", `got ${r.text}`);
}

function testMediumConfidenceSuggestion() {
  // A single ambiguous word should not be auto-applied with high confidence.
  const r = correct("privet", "auto");
  assert.ok(r.level === "none" || r.level === "medium", `unexpected level ${r.level} (${r.text})`);
}

function testCasePreservation() {
  const r = correct("Ghbdtn", "ru");
  assert.strictEqual(r.text, "Привет", `expected Привет, got ${r.text}`);
}

function testUndoFlow() {
  // The UI keeps an undo stack; here we verify conversions are reversible.
  const r = correct("ghbdtn rfr", "ru");
  assert.strictEqual(r.text, "привет как", `got ${r.text}`);
  assert.ok(r.conversions.length >= 2);
}

function run() {
  testShortWords();
  testSentence();
  testCorrectTextUntouched();
  testMixedIntentional();
  testHebrew();
  testUrlsEmailsPaths();
  testNumbersAndCode();
  testPunctuationPreserved();
  testMediumConfidenceSuggestion();
  testCasePreservation();
  testUndoFlow();
  console.log("LAYOUT CORRECTOR JS TESTS OK");
}

run();
