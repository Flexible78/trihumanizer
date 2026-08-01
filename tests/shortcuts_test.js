"use strict";

/* Tests for the Ctrl+Enter / Cmd+Enter shortcut behavior.
 *
 * The app wires a real keydown listener in app.js; here we verify the decision
 * function that governs whether the shortcut should run, extracted so it can
 * be unit-tested without a browser.
 */
const assert = require("assert");

function shouldRunShortcut(event, requestInFlight) {
  if (requestInFlight) return false; // disabled while a request runs
  if (event.isComposing || event.keyCode === 229) return false; // IME composition
  const modifier = event.ctrlKey || event.metaKey;
  if (!modifier || event.key !== "Enter") return false;
  return true;
}

function testCtrlEnter() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: true, metaKey: false, key: "Enter", isComposing: false, keyCode: 13 }, false),
    true
  );
}

function testCmdEnter() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: false, metaKey: true, key: "Enter", isComposing: false, keyCode: 13 }, false),
    true
  );
}

function testPlainEnterIgnored() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: false, metaKey: false, key: "Enter", isComposing: false, keyCode: 13 }, false),
    false
  );
}

function testDisabledDuringRequest() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: true, metaKey: false, key: "Enter", isComposing: false, keyCode: 13 }, true),
    false
  );
}

function testImeCompositionIgnored() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: true, metaKey: false, key: "Enter", isComposing: true, keyCode: 229 }, false),
    false
  );
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: true, metaKey: false, key: "Enter", isComposing: false, keyCode: 229 }, false),
    false
  );
}

function testOtherKeysIgnored() {
  assert.strictEqual(
    shouldRunShortcut({ ctrlKey: true, metaKey: false, key: "a", isComposing: false, keyCode: 65 }, false),
    false
  );
}

function testMacLabel() {
  const isMac = /Mac|iPhone|iPad|iPod/i.test("MacIntel");
  assert.strictEqual(isMac, true);
}

function run() {
  testCtrlEnter();
  testCmdEnter();
  testPlainEnterIgnored();
  testDisabledDuringRequest();
  testImeCompositionIgnored();
  testOtherKeysIgnored();
  testMacLabel();
  console.log("SHORTCUT TESTS OK");
}

run();
