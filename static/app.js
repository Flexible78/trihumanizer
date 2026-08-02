"use strict";

const $ = (id) => document.getElementById(id);

const APP_CONFIG = window.TRIHUMANIZER_CONFIG || {};
const DEFAULT_PROVIDER = APP_CONFIG.defaultProvider || "mistral";
const DEFAULT_MODEL = APP_CONFIG.defaultModel || "mistral-large-latest";
const AUTH_REQUIRED = window.TRIHUMANIZER_AUTH_REQUIRED === true;
const HOSTED = Boolean(APP_CONFIG.hosted);

// Server-side remembered settings: provider, model, endpoint and a boolean
// flag telling whether an API key is stored. The key itself is never sent to
// the browser, it stays in data/settings.json on the machine that runs the app.
let SAVED_SETTINGS = APP_CONFIG.saved || {
  provider: "",
  model: "",
  customUrl: "",
  persisted: false,
  providers: {},
};
let settingsSaveTimer = null;

function savedEntry(provider) {
  return (SAVED_SETTINGS.providers || {})[provider] || {};
}

function savedHasKey(provider) {
  return Boolean(savedEntry(provider).hasKey);
}

// Keep the provider table injected at page load in sync with what is stored,
// so every "is a key configured" check keeps working without a page reload.
function syncSavedKeyFlags() {
  const providers = SAVED_SETTINGS.providers || {};
  Object.keys(providers).forEach((name) => {
    if (providerDefaults[name] && providers[name].hasKey) {
      providerDefaults[name].configuredKey = true;
      providerDefaults[name].savedKey = true;
    }
  });
}

// Autosave of provider, model, endpoint and API key. Debounced by default so
// typing a key does not produce a request per keystroke.
async function persistSettings(options) {
  const settings = options || {};
  if (HOSTED) return;
  const remember = $("rememberSettings");
  if (remember && !remember.checked) return;

  const send = async () => {
    const body = {
      provider: $("provider").value,
      model: selectedModel(),
      custom_url: $("customUrl").value.trim(),
      api_key: $("apiKey").value.trim(),
      clear_key: Boolean(settings.clearKey),
    };
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => null);
      if (!data || !data.settings) return;
      SAVED_SETTINGS = data.settings;
      syncSavedKeyFlags();
      // The key is on the server now; keep the input empty so it is never
      // stored in the browser and never shown again.
      if (data.stored && body.api_key) $("apiKey").value = "";
      updateProviderUI();
      updateCompactBlock();
    } catch (_) {
      // Autosave is a convenience: never interrupt the user on failure.
    }
  };

  if (settingsSaveTimer) clearTimeout(settingsSaveTimer);
  if (settings.immediate) {
    await send();
    return;
  }
  settingsSaveTimer = setTimeout(send, 600);
}

const STORAGE = {
  general: "triHumanizerGeneralV16",
  providers: "triHumanizerProvidersV16",
  lastSuccess: "triHumanizerLastSuccessV16",
  modelCache: "triHumanizerModelCacheV16",
  theme: "triHumanizerThemeV16",
  layout: "triHumanizerLayoutV16",
  history: "triHumanizerHistoryV16",
};

const LEGACY = {
  general: "triHumanizerGeneralV15",
  providers: "triHumanizerProvidersV15",
  lastSuccess: "triHumanizerLastSuccessV15",
  modelCache: "triHumanizerModelCacheV15",
  theme: "triHumanizerThemeV15",
};

const fallbackProviders = {
  mistral: {
    label: "Mistral · primary",
    shortLabel: "Mistral",
    endpoint: "https://api.mistral.ai/v1",
    model: DEFAULT_MODEL,
    requiresKey: true,
    configuredKey: false,
    help: "Mistral Large is the primary model.",
  },
  custom: {
    label: "Other OpenAI-compatible API",
    shortLabel: "Custom API",
    endpoint: "",
    model: "",
    requiresKey: false,
    configuredKey: false,
    help: "Enter your own endpoint.",
  },
};

const providerDefaults = APP_CONFIG.providers || fallbackProviders;
let activeProvider = DEFAULT_PROVIDER;
let allModels = [];
let currentResult = null;
let currentAction = "auto";
let requestInFlight = false;
let requestController = null;
let layoutUndoStack = [];
// True once the user explicitly picks an output language in this session.
let targetLanguageTouched = false;

const ACTION_LABELS = {
  auto: "Process",
  translate: "Translate & humanize",
  write: "Write",
  improve: "Improve text",
  research: "Run research",
};

const ACTION_HINTS = {
  auto: "Message, email, post, recruiter reply, or technical description. Describe what you need in plain words.",
  translate: "Message, email, post, recruiter reply, or technical description.",
  write: "Describe the text you need: topic, format, tone, recipient.",
  improve: "Paste the text you want polished or rewritten.",
  research: "Ask a current factual question. Live research must be enabled on the server.",
};

function readJSON(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value ?? fallback;
  } catch (_) {
    return fallback;
  }
}

function writeJSON(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function migrateLegacySettings() {
  if (!localStorage.getItem(STORAGE.theme) && localStorage.getItem(LEGACY.theme)) {
    localStorage.setItem(STORAGE.theme, localStorage.getItem(LEGACY.theme));
  }
  if (!localStorage.getItem(STORAGE.general) && localStorage.getItem(LEGACY.general)) {
    const legacy = readJSON(LEGACY.general, {});
    legacy.provider = DEFAULT_PROVIDER;
    legacy.remember = true;
    writeJSON(STORAGE.general, legacy);
  }
}

function isHebrew(text) {
  return /[\u0590-\u05FF]/.test(text || "");
}

function setDirection(el, text) {
  if (!el) return;
  el.dir = isHebrew(text) ? "rtl" : "ltr";
}

function selectedMode() {
  return document.querySelector('input[name="mode"]:checked')?.value || "business";
}

function selectedAction() {
  return currentAction;
}

function selectedModel() {
  return $("modelSelect").value.trim();
}

function updateModeCards() {
  document.querySelectorAll(".mode").forEach((card) => {
    card.classList.toggle("active", card.querySelector("input").checked);
  });
}

function currentEndpoint(provider = $("provider").value) {
  return provider === "custom"
    ? $("customUrl").value.trim()
    : providerDefaults[provider]?.endpoint || "";
}

function providerStateMap() {
  return readJSON(STORAGE.providers, {});
}

function lastSuccessMap() {
  return readJSON(STORAGE.lastSuccess, {});
}

function modelCacheKey(provider = $("provider").value, endpoint = currentEndpoint()) {
  return `${provider}|${endpoint}`;
}

function captureProviderState(provider = activeProvider) {
  if (!$("rememberSettings").checked || !provider) return;
  const states = providerStateMap();
  states[provider] = { model: selectedModel(), customUrl: $("customUrl").value.trim() };
  writeJSON(STORAGE.providers, states);
  persistSettings();
}

function preferredProviderState(provider) {
  const server = savedEntry(provider);
  const successful = lastSuccessMap()[provider];
  const saved = providerStateMap()[provider];
  const defaults = providerDefaults[provider] || {};
  return {
    // Server-side memory wins: it is the last combination that actually worked
    // and it survives a restart of the application and a cleared browser.
    model: server.model || successful?.model || saved?.model || defaults.model || "",
    apiKey: "",
    customUrl:
      server.customUrl ||
      successful?.customUrl ||
      saved?.customUrl ||
      (provider === "custom" ? defaults.endpoint : ""),
  };
}

function cachedModels(provider = $("provider").value, endpoint = currentEndpoint()) {
  const cache = readJSON(STORAGE.modelCache, {});
  return cache[modelCacheKey(provider, endpoint)]?.models || [];
}

function cacheModels(models, endpoint) {
  const cache = readJSON(STORAGE.modelCache, {});
  cache[modelCacheKey($("provider").value, currentEndpoint())] = {
    models,
    endpoint,
    savedAt: new Date().toISOString(),
  };
  writeJSON(STORAGE.modelCache, cache);
}

function populateModels(models, preferred = selectedModel(), filter = $("modelFilter").value.trim()) {
  allModels = Array.from(new Set((models || []).filter(Boolean))).sort((a, b) => a.localeCompare(b));
  if (preferred && !allModels.includes(preferred)) allModels.unshift(preferred);

  const normalized = filter.toLocaleLowerCase();
  const visible = normalized
    ? allModels.filter((model) => model.toLocaleLowerCase().includes(normalized))
    : allModels;

  const select = $("modelSelect");
  select.innerHTML = "";
  if (!visible.length) {
    const option = document.createElement("option");
    option.value = preferred || "";
    option.textContent = preferred || "No models match this filter";
    select.appendChild(option);
  } else {
    visible.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      select.appendChild(option);
    });
  }

  if (preferred && visible.includes(preferred)) select.value = preferred;
  else if (visible.length) select.value = visible[0];
  updateModelSummary();
}

function applyProviderState(provider) {
  const state = preferredProviderState(provider);
  $("apiKey").value = state.apiKey;
  $("customUrl").value = state.customUrl;
  $("modelFilter").value = "";
  populateModels(
    cachedModels(provider, provider === "custom" ? state.customUrl : providerDefaults[provider].endpoint),
    state.model
  );
}

function updateModelSummary() {
  const provider = $("provider").value;
  const defaults = providerDefaults[provider] || {};
  const providerText = defaults.shortLabel || $("provider").selectedOptions[0]?.textContent || provider;
  const model = selectedModel();
  $("modelSummary").textContent = model
    ? `${providerText} · ${model}`
    : `${providerText} · no model selected`;
}

function updateProviderUI() {
  const provider = $("provider").value;
  const defaults = providerDefaults[provider] || {};
  const needsKey = Boolean(defaults.requiresKey);
  const storedKey = savedHasKey(provider) || Boolean(defaults.savedKey);
  const configured = Boolean(defaults.configuredKey) || storedKey;
  const isLocal = /^http:\/\/(localhost|127\.0\.0\.1)/i.test(currentEndpoint(provider));

  $("providerHelp").textContent = defaults.help || "";
  $("customUrlLabel").classList.toggle("hidden", provider !== "custom");
  $("apiKeyLabel").classList.toggle("hidden", !needsKey && provider !== "custom");
  $("endpointPreview").textContent = currentEndpoint(provider) || "Enter an endpoint below";

  const credentialBadge = $("credentialBadge");
  if (credentialBadge) {
    credentialBadge.textContent = storedKey
      ? "saved key"
      : configured
        ? "server key"
        : needsKey
          ? "key required"
          : "no key";
    credentialBadge.className = `credential-badge ${configured || !needsKey ? "configured" : "missing"}`;
  }
  $("apiKey").placeholder = storedKey
    ? "Saved key in use; type a new key to replace it"
    : configured
    ? "Leave empty — uses the server-side key"
    : needsKey
      ? "Enter an API key for this provider"
      : "Optional key";

  const providerStatus = $("providerStatus");
  if (providerStatus) {
    providerStatus.textContent = isLocal ? "local" : configured || !needsKey ? "ready" : "key required";
    providerStatus.className = `status-pill ${isLocal ? "local" : configured || !needsKey ? "ready" : "needs-key"}`;
  }
  if ($("configSourceBadge")) {
    $("configSourceBadge").textContent = "configured";
  }
  updateModelSummary();
}

function saveGeneralSettings() {
  if (!$("rememberSettings").checked) {
    localStorage.removeItem(STORAGE.general);
    localStorage.removeItem(STORAGE.providers);
    localStorage.removeItem(STORAGE.lastSuccess);
    return;
  }
  captureProviderState();
  writeJSON(STORAGE.general, {
    provider: $("provider").value,
    sourceLanguage: $("sourceLanguage").value,
    targetLanguage: $("targetLanguage").value,
    context: $("context").value,
    customInstruction: $("customInstruction").value,
    writerGender: $("writerGender").value,
    recipientGender: $("recipientGender").value,
    humanizeOriginal: $("humanizeOriginal").checked,
    humanizeTranslation: $("humanizeTranslation").checked,
    includeLiteral: $("includeLiteral").checked,
    preserveLength: $("preserveLength").checked,
    autoCorrectLayout: $("autoCorrectLayout").checked,
    mode: selectedMode(),
    action: currentAction,
    remember: true,
  });
}

function loadGeneralSettings() {
  const data = readJSON(STORAGE.general, null);
  $("rememberSettings").checked = true;
  $("provider").value = providerDefaults[data?.provider] ? data.provider : DEFAULT_PROVIDER;
  activeProvider = $("provider").value;
  $("sourceLanguage").value = data?.sourceLanguage || "auto";
  $("targetLanguage").value = data?.targetLanguage || "en";
  $("context").value = data?.context || "general communication";
  $("customInstruction").value = data?.customInstruction || "";
  $("writerGender").value = data?.writerGender || "male";
  $("recipientGender").value = data?.recipientGender || "neutral";
  $("humanizeOriginal").checked = data?.humanizeOriginal !== false;
  $("humanizeTranslation").checked = data?.humanizeTranslation !== false;
  $("includeLiteral").checked = Boolean(data?.includeLiteral);
  $("preserveLength").checked = data?.preserveLength !== false;
  $("autoCorrectLayout").checked = data?.autoCorrectLayout !== false;
  $("rememberSettings").checked = data?.remember !== false;
  const radio = document.querySelector(`input[name="mode"][value="${data?.mode || "business"}"]`);
  if (radio) radio.checked = true;
  if (data?.action && ["auto", "translate", "write", "improve", "research"].includes(data.action)) {
    setAction(data.action);
  }
  applyProviderState(activeProvider);

  const defaults = providerDefaults[activeProvider] || {};
  const keyReady = !defaults.requiresKey || defaults.configuredKey || Boolean($("apiKey").value.trim());
  $("modelPanel").open = !selectedModel() || !keyReady;
  updateLayoutBadge();
}

function saveSuccessfulSettings(payload) {
  if (!$("rememberSettings").checked) return;
  const successful = lastSuccessMap();
  successful[payload.provider] = {
    model: payload.model,
    customUrl: payload.custom_url || "",
    savedAt: new Date().toISOString(),
  };
  writeJSON(STORAGE.lastSuccess, successful);
  captureProviderState(payload.provider);
  saveGeneralSettings();
}

function setStatus(message, error = false, ok = false) {
  $("status").textContent = message;
  $("status").className = `status${error ? " error" : ok ? " ok" : ""}`;
}

function setModelStatus(message, error = false, ok = false) {
  $("modelStatus").textContent = message;
  $("modelStatus").className = `model-status${error ? " error" : ok ? " ok" : ""}`;
}

function autoCollapseModelPanel(delay = 550) {
  if (!selectedModel()) return;
  window.setTimeout(() => {
    $("modelPanel").open = false;
  }, delay);
}

async function loadModels({ silent = false, collapse = true } = {}) {
  const provider = $("provider").value;
  const payload = {
    provider,
    api_key: $("apiKey").value,
    custom_url: provider === "custom" ? $("customUrl").value.trim() : "",
  };

  const defaults = providerDefaults[provider] || {};
  if (defaults.requiresKey && !defaults.configuredKey && !payload.api_key.trim()) {
    if (!silent) setModelStatus("This provider requires an API key. Enter it above.", true);
    $("modelPanel").open = true;
    return;
  }
  if (provider === "custom" && !payload.custom_url) {
    if (!silent) setModelStatus("Enter an endpoint and press Refresh models.", true);
    $("modelPanel").open = true;
    return;
  }

  const oldModel = selectedModel() || preferredProviderState(provider).model;
  $("loadModelsBtn").disabled = true;
  setModelStatus("Loading the model list…");
  try {
    const response = await fetch("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Could not load models.");
    cacheModels(data.models, data.endpoint);
    populateModels(
      data.models,
      oldModel && data.models.includes(oldModel) ? oldModel : data.models[0] || oldModel
    );
    setModelStatus(`Loaded ${data.models.length} models.`, false, true);
    captureProviderState();
    saveGeneralSettings();
    if (collapse) autoCollapseModelPanel();
  } catch (error) {
    setModelStatus(error.message, true);
    $("modelPanel").open = true;
  } finally {
    $("loadModelsBtn").disabled = false;
  }
}

function diagnosticPayload(includeModel = false) {
  const provider = $("provider").value;
  const payload = {
    provider,
    api_key: $("apiKey").value,
    custom_url: provider === "custom" ? $("customUrl").value.trim() : "",
  };
  if (includeModel) payload.model = selectedModel();
  return payload;
}

function validateDiagnosticPayload(payload, requireModel = false) {
  const defaults = providerDefaults[payload.provider] || {};
  if (defaults.requiresKey && !defaults.configuredKey && !payload.api_key.trim()) {
    setModelStatus("An API key is required. Enter it above.", true);
    $("modelPanel").open = true;
    return false;
  }
  if (payload.provider === "custom" && !payload.custom_url) {
    setModelStatus("Enter an API endpoint to test.", true);
    $("modelPanel").open = true;
    return false;
  }
  if (requireModel && !payload.model) {
    setModelStatus("Select a model first.", true);
    $("modelPanel").open = true;
    return false;
  }
  return true;
}

function setDiagnosticButtons(disabled) {
  ["testKeyBtn", "testModelBtn", "loadModelsBtn"].forEach((id) => {
    if ($(id)) $(id).disabled = disabled;
  });
}

async function testApiKey() {
  const payload = diagnosticPayload(false);
  if (!validateDiagnosticPayload(payload, false)) return;
  setDiagnosticButtons(true);
  setModelStatus("Testing API key, endpoint and model catalog access…");
  try {
    const response = await fetch("/api/test/key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const category = data.error_category ? ` (${data.error_category})` : "";
      throw new Error(`${data.error || "API key test failed."}${category}`);
    }
    const providerName = providerDefaults[payload.provider]?.shortLabel || payload.provider;
    setModelStatus(
      `Key and endpoint OK: ${providerName}. Models available: ${data.models_count}. Response ${data.elapsed_ms} ms.`,
      false,
      true
    );
    const badge = $("providerStatus");
    if (badge) {
      badge.textContent = "verified";
      badge.className = "status-pill ready";
    }
  } catch (error) {
    setModelStatus(`Key/endpoint: ${error.message}`, true);
  } finally {
    setDiagnosticButtons(false);
  }
}

async function testSelectedModel() {
  const payload = diagnosticPayload(true);
  if (!validateDiagnosticPayload(payload, true)) return;
  setDiagnosticButtons(true);
  setModelStatus(`Sending a short real request to ${payload.model}…`);
  try {
    const response = await fetch("/api/test/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "The model did not respond.");
    const seconds = (Number(data.elapsed_ms || 0) / 1000).toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
    const reply = String(data.reply || "OK").replace(/\s+/g, " ").slice(0, 90);
    setModelStatus(`Model works. Response in ${seconds} s: ${reply}`, false, true);
    saveSuccessfulSettings({ ...selectedPayload(), text: "" });
    updateModelSummary();
  } catch (error) {
    setModelStatus(`Model test: ${error.message}`, true);
  } finally {
    setDiagnosticButtons(false);
  }
}

function addManualModel() {
  const model = $("manualModel").value.trim();
  if (!model) {
    setModelStatus("Enter the exact model name.", true);
    return;
  }
  const combined = [model, ...allModels];
  $("modelFilter").value = "";
  populateModels(combined, model);
  $("manualModel").value = "";
  setModelStatus(`Model added manually: ${model}`, false, true);
  captureProviderState();
  saveGeneralSettings();
}

function selectedPayload() {
  const provider = $("provider").value;
  return {
    text: $("sourceText").value.trim(),
    source_language: $("sourceLanguage").value,
    target_language: $("targetLanguage").value,
    mode: selectedMode(),
    action: selectedAction(),
    context: $("context").value,
    custom_instruction: $("customInstruction").value,
    writer_gender: $("writerGender").value,
    recipient_gender: $("recipientGender").value,
    humanize_original: $("humanizeOriginal").checked,
    humanize_translation: $("humanizeTranslation").checked,
    include_literal: $("includeLiteral").checked,
    preserve_length: $("preserveLength").checked,
    provider,
    model: selectedModel(),
    api_key: $("apiKey").value,
    custom_url: provider === "custom" ? $("customUrl").value.trim() : "",
  };
}

/* ---------------- layout correction ---------------- */

function layoutSettings() {
  const settings = readJSON(STORAGE.layout, {});
  return { enabled: settings.enabled !== false };
}

function saveLayoutSettings(settings) {
  writeJSON(STORAGE.layout, settings);
}

function updateLayoutBadge() {
  const badge = $("autoCorrectBadge");
  if (!badge) return;
  badge.textContent = layoutSettings().enabled ? "⌨ auto-correct: on" : "⌨ auto-correct: off";
}

function showLayoutSuggestion(correction) {
  const bar = $("layoutSuggestion");
  if (!bar) return;
  $("layoutSuggestionPreview").textContent = `${correction.conversions.length} word(s) affected`;
  bar.classList.remove("hidden");
  $("layoutKeepBtn").classList.remove("hidden");
  $("layoutUndoBtn").classList.add("hidden");
}

function hideLayoutSuggestion() {
  const bar = $("layoutSuggestion");
  if (bar) bar.classList.add("hidden");
}

function applyLayoutCorrection(auto) {
  if (!layoutSettings().enabled) return null;
  if (!$("sourceText").value.trim()) return null;
  const correction = window.TriHumanizerLayout?.correctText($("sourceText").value, {
    sourceLanguage: $("sourceLanguage").value,
  });
  if (!correction || !correction.changed) {
    hideLayoutSuggestion();
    return null;
  }

  if (auto && correction.level === "high") {
    layoutUndoStack.push($("sourceText").value);
    $("sourceText").value = correction.text;
    $("sourceText").dispatchEvent(new Event("input", { bubbles: true }));
    setStatus(
      `Keyboard layout corrected: ${correction.conversions.map((c) => `“${c.from}” → “${c.to}”`).join(", ")}`,
      false,
      true
    );
    hideLayoutSuggestion();
    return correction;
  }

  // Medium confidence or manual mode: show the suggestion bar.
  layoutUndoStack.push($("sourceText").value);
  $("layoutSuggestionPreview").textContent =
    `${correction.conversions.map((c) => `“${c.from}” → “${c.to}”`).join(", ")}`;
  showLayoutSuggestion(correction);
  return correction;
}

function applyLayoutSuggestion() {
  const correction = window.TriHumanizerLayout?.correctText($("sourceText").value, {
    sourceLanguage: $("sourceLanguage").value,
  });
  if (correction?.changed) {
    $("sourceText").value = correction.text;
    $("sourceText").dispatchEvent(new Event("input", { bubbles: true }));
    setStatus("Correction applied.", false, true);
  }
  $("layoutUndoBtn").classList.remove("hidden");
  $("layoutApplyBtn").disabled = true;
  $("layoutKeepBtn").disabled = true;
}

function keepLayoutSuggestion() {
  hideLayoutSuggestion();
  layoutUndoStack.pop();
  setStatus("Original text kept.");
}

function undoLayoutSuggestion() {
  const previous = layoutUndoStack.pop();
  if (previous !== undefined) {
    $("sourceText").value = previous;
    $("sourceText").dispatchEvent(new Event("input", { bubbles: true }));
    setStatus("Correction undone.", false, true);
  }
  hideLayoutSuggestion();
}

/* ---------------- processing ---------------- */

function setProcessButton(busy) {
  $("processBtn").disabled = busy;
  $("processBtn").querySelector("span").textContent = busy ? "Working…" : ACTION_LABELS[selectedAction()] || "Process";
  if (busy) {
    $("processBtnArrow").textContent = "…";
  } else {
    $("processBtnArrow").textContent = "→";
  }
}

async function apiFetch(url, payload) {
  const controller = new AbortController();
  requestController = controller;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: controller.signal,
  });
  return response;
}

async function processText() {
  if (requestInFlight) return;
  const payload = selectedPayload();
  if (!payload.text) {
    setStatus("Enter or paste text.", true);
    return;
  }
  if (!payload.model) {
    setStatus("Open model settings and choose a model.", true);
    $("modelPanel").open = true;
    return;
  }

  // Layout correction runs before every smart request.
  applyLayoutCorrection(true);

  saveGeneralSettings();
  requestInFlight = true;
  setProcessButton(true);
  setStatus(
    `Request sent: ${providerDefaults[payload.provider]?.shortLabel || payload.provider} · ${payload.model} · ${ACTION_LABELS[selectedAction()]}`
  );

  try {
    const response = await apiFetch("/api/process", payload);
    const data = await response.json();
    if (response.status === 401) {
      showAuthOverlay();
      setStatus("Authentication required.", true);
      return;
    }
    if (!response.ok || !data.ok) throw new Error(data.error || "Unknown error.");
    currentResult = data.result;
    showResult(data.result, data.action || payload.action);
    saveSuccessfulSettings(payload);
    const retryNote = data.quality_retry ? "Quality check ran twice. " : "";
    setStatus(
      `${retryNote}Done. Model: ${data.model}.`,
      false,
      true
    );
    updateModelSummary();
    $("modelPanel").open = false;
    if ((data.action || payload.action) !== "clarify") {
      saveLocalHistory(payload, data.result, data.action || payload.action);
    }
    await loadHistory();
  } catch (error) {
    if (error.name === "AbortError") {
      setStatus("Request cancelled.");
    } else {
      setStatus(error.message, true);
      $("modelPanel").open = true;
    }
  } finally {
    requestInFlight = false;
    requestController = null;
    setProcessButton(false);
  }
}

function cancelRequest() {
  if (requestController) {
    requestController.abort();
    requestController = null;
  }
}

/* ---------------- result rendering ---------------- */

function renderEmail(result) {
  const subject = result.subject || "";
  const body = [result.greeting, result.body, result.closing].filter(Boolean).join("\n\n");
  const html = [];
  if (subject) html.push(`<p class="email-subject"><strong>Subject:</strong> ${escapeHtml(subject)}</p>`);
  html.push(`<div class="email-body">${escapeHtml(body).replace(/\n/g, "<br>")}</div>`);
  const composed = $("emailComposed");
  composed.innerHTML = html.join("");
  $("emailBodyText").value = [subject ? `Subject: ${subject}` : "", body].filter(Boolean).join("\n\n");

  const findings = $("emailFindings");
  findings.classList.toggle("hidden", !result.verified_findings?.length && !result.sources?.length);
  if (!findings.classList.contains("hidden")) {
    const parts = [];
    if (result.verified_findings?.length) {
      parts.push(`<div class="findings-block"><strong>Verified findings</strong><ul>${result.verified_findings.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul></div>`);
    }
    if (result.sources?.length) {
      parts.push(`<div class="findings-block"><strong>Sources</strong><ul>${result.sources.map((s) => `<li>${escapeHtml(s.title || "")}${s.url ? ` — <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.url)}</a>` : ""}</li>`).join("")}</ul></div>`);
    }
    findings.innerHTML = parts.join("");
  }
}

function renderResearch(result) {
  $("researchAnswer").innerHTML = escapeHtml(result.answer || "").replace(/\n/g, "<br>");
  const sources = $("researchSources");
  if (result.sources?.length) {
    sources.innerHTML = `<strong>Sources (retrieved ${escapeHtml(result.retrieved_at || "now")})</strong><ul>${result.sources.map((s) => `<li>${escapeHtml(s.title || "")}${s.url ? ` — <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.url)}</a>` : ""}</li>`).join("")}</ul>`;
    sources.classList.remove("hidden");
  } else {
    sources.classList.add("hidden");
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showResult(result, action = selectedAction()) {
  currentResult = result;
  $("emptyResult").classList.add("hidden");
  $("resultContent").classList.remove("hidden");

  const isEmail = action === "write" || Boolean(result.subject);
  const isResearch = action === "research" || Boolean(result.retrieved_at && !result.subject);
  $("emailBlock").classList.toggle("hidden", !isEmail);
  $("researchBlock").classList.toggle("hidden", !isResearch);
  $("originalBlock").classList.toggle("hidden", !result.humanized_original && !isEmail && !isResearch);
  $("literalBlock").classList.toggle("hidden", !result.literal_translation);
  $("translationBlock").classList.toggle("hidden", !result.humanized_translation);

  if (isEmail) renderEmail(result);
  if (isResearch) renderResearch(result);

  $("humanizedOriginal").value = result.humanized_original || "";
  $("literalTranslation").value = result.literal_translation || "";
  $("humanizedTranslation").value = result.humanized_translation || "";

  setDirection($("humanizedOriginal"), result.humanized_original);
  setDirection($("literalTranslation"), result.literal_translation);
  setDirection($("humanizedTranslation"), result.humanized_translation);
  setDirection($("emailBodyText"), result.body || result.greeting || result.subject);

  const notesParts = [];
  if (result.notes) notesParts.push(result.notes);
  if (result.missing_information?.length) {
    notesParts.push(`Missing details: ${result.missing_information.join(", ")}`);
  }
  $("notes").textContent = notesParts.join(" · ");
  $("notes").classList.toggle("hidden", !notesParts.length);

  const language = result.detected_language ? `Detected language: ${result.detected_language}` : "";
  const actionLabel = ACTION_LABELS[action] || "";
  $("detectedLanguage").textContent = [language, actionLabel].filter(Boolean).join(" · ") || "Result ready.";

  if (window.innerWidth < 1050) {
    $("resultsCard").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/* ---------------- clipboard / share ---------------- */

async function readClipboardText() {
  if (navigator.clipboard?.readText) return navigator.clipboard.readText();
  throw new Error("Clipboard API unavailable. Use Ctrl+V.");
}

async function writeClipboardText(text) {
  if (!text) throw new Error("No text to copy.");
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const temp = document.createElement("textarea");
  temp.value = text;
  temp.style.position = "fixed";
  temp.style.opacity = "0";
  document.body.appendChild(temp);
  temp.select();
  const ok = document.execCommand("copy");
  temp.remove();
  if (!ok) throw new Error("Could not copy. Use Ctrl+C.");
}

async function shareResult() {
  const text = primaryResultText();
  if (!text) {
    setStatus("No result to share yet.", true);
    return;
  }
  if (navigator.share) {
    try {
      await navigator.share({ title: "TriHumanizer result", text });
      return;
    } catch (_) {
      return; // user cancelled
    }
  }
  try {
    await writeClipboardText(text);
    setStatus("Result copied (share unavailable on this browser).", false, true);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function flashButton(button, action, success = "Copied") {
  const old = button.textContent;
  try {
    await action();
    button.textContent = success;
  } catch (error) {
    setStatus(error.message, true);
    button.textContent = "Error";
  }
  setTimeout(() => (button.textContent = old), 1300);
}

function primaryResultText() {
  return (
    $("humanizedTranslation").value.trim() ||
    $("humanizedOriginal").value.trim() ||
    $("emailBodyText").value.trim() ||
    $("researchAnswer").textContent.trim() ||
    $("literalTranslation").value.trim()
  );
}

function useAsSource(text) {
  if (!text) return;
  const oldSource = $("sourceLanguage").value;
  const oldTarget = $("targetLanguage").value;
  $("sourceText").value = text;
  $("sourceLanguage").value = oldTarget;
  if (oldSource !== "auto") $("targetLanguage").value = oldSource;
  updateCount();
  $("sourceText").focus();
  saveGeneralSettings();
}

function collectAllResults(includeSource = false) {
  const parts = [];
  if (includeSource && $("sourceText").value.trim()) {
    parts.push(`Source text\n${$("sourceText").value.trim()}`);
  }
  if ($("emailBodyText").value.trim()) parts.push(`Written text\n${$("emailBodyText").value.trim()}`);
  if ($("researchAnswer").textContent.trim()) parts.push(`Research answer\n${$("researchAnswer").textContent.trim()}`);
  const entries = [
    ["Improved original", $("humanizedOriginal").value],
    ["Literal translation", $("literalTranslation").value],
    ["Natural translation", $("humanizedTranslation").value],
    ["Notes", $("notes").textContent],
  ];
  entries.forEach(([title, value]) => {
    if ((value || "").trim()) parts.push(`${title}\n${value.trim()}`);
  });
  return parts.join("\n\n");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function exportTxt() {
  const text = collectAllResults(true);
  if (!text) {
    setStatus("Get a result first.", true);
    return;
  }
  downloadBlob(new Blob(["\ufeff", text], { type: "text/plain;charset=utf-8" }), "TriHumanizer_result.txt");
  setStatus("TXT file saved.", false, true);
}

async function exportPdf() {
  if (!currentResult && !$("sourceText").value.trim()) {
    setStatus("Get a result first.", true);
    return;
  }
  const payload = {
    source_text: $("sourceText").value,
    humanized_original: $("humanizedOriginal").value,
    literal_translation: $("literalTranslation").value,
    humanized_translation: $("humanizedTranslation").value,
    notes: $("notes").textContent,
    meta: {
      source_language: $("sourceLanguage").value,
      target_language: $("targetLanguage").value,
      mode: selectedMode(),
      action: selectedAction(),
      provider: $("provider").value,
      model: selectedModel(),
    },
  };
  $("exportPdfBtn").disabled = true;
  try {
    const response = await fetch("/api/export/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "Could not create the PDF.");
    }
    downloadBlob(await response.blob(), "TriHumanizer_result.pdf");
    setStatus("PDF saved.", false, true);
  } catch (error) {
    // Fallback: client-side PDF-free export as TXT.
    try {
      exportTxt();
      setStatus(`${error.message} — exported as TXT instead.`, false, true);
    } catch (_) {
      setStatus(error.message, true);
    }
  } finally {
    $("exportPdfBtn").disabled = false;
  }
}

/* ---------------- history ---------------- */

function saveLocalHistory(payload, result, action) {
  if (!HOSTED) return; // server-side SQLite history on local installs
  const items = readJSON(STORAGE.history, []);
  items.unshift({
    id: Date.now(),
    created_at: new Date().toISOString(),
    source_language: payload.source_language,
    target_language: payload.target_language,
    mode: payload.mode,
    action: action || payload.action,
    source_text: payload.text,
    result,
  });
  writeJSON(STORAGE.history, items.slice(0, 100));
}

function historyItems() {
  if (HOSTED) return readJSON(STORAGE.history, []);
  return null; // server-backed
}

async function loadHistory() {
  const items = historyItems();
  if (items !== null) {
    renderHistoryList(items, true);
    return;
  }
  try {
    const response = await fetch("/api/history");
    const data = await response.json();
    renderHistoryList(data.items || [], false);
  } catch (error) {
    setStatus(`Could not load history: ${error.message}`, true);
  }
}

function renderHistoryList(items, hosted) {
  const list = $("historyList");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<div class="help">History is empty for now.</div>';
    return;
  }

  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "history-item";

    const open = document.createElement("div");
    open.className = "history-open";
    open.innerHTML = `
        <div class="history-meta">${new Date(item.created_at).toLocaleString()} · ${item.source_language} → ${item.target_language} · ${item.action || item.mode}</div>
        <div class="history-preview"></div>
        <div class="history-result-preview"></div>`;
    open.querySelector(".history-preview").textContent = item.source_text;
    open.querySelector(".history-result-preview").textContent =
      item.result?.humanized_translation || item.result?.humanized_original || item.result?.body || item.result?.answer || "";
    open.addEventListener("click", () => {
      $("sourceText").value = item.source_text;
      $("sourceLanguage").value = item.source_language;
      $("targetLanguage").value = item.target_language;
      const radio = document.querySelector(`input[name="mode"][value="${item.mode}"]`);
      if (radio) radio.checked = true;
      updateModeCards();
      updateCount();
      showResult(item.result, item.action);
    });

    const actions = document.createElement("div");
    actions.className = "history-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "ghost";
    copy.textContent = "Copy";
    copy.addEventListener("click", () =>
      flashButton(
        copy,
        () =>
          writeClipboardText(
            item.result?.humanized_translation || item.result?.humanized_original || item.result?.body || item.source_text
          )
      )
    );

    const del = document.createElement("button");
    del.type = "button";
    del.className = "ghost danger";
    del.textContent = "Delete";
    del.addEventListener("click", async () => {
      if (!confirm("Delete only this history entry?")) return;
      if (hosted) {
        const items = readJSON(STORAGE.history, []);
        writeJSON(
          STORAGE.history,
          items.filter((entry) => entry.id !== item.id)
        );
        await loadHistory();
      } else {
        await fetch(`/api/history/${item.id}`, { method: "DELETE" });
        await loadHistory();
      }
    });

    actions.append(copy, del);
    div.append(open, actions);
    list.appendChild(div);
  });
}

async function clearHistory() {
  if (!confirm("Delete the entire local history?")) return;
  if (HOSTED) {
    localStorage.removeItem(STORAGE.history);
  } else {
    await fetch("/api/history", { method: "DELETE" });
  }
  await loadHistory();
}

/* ---------------- misc UI ---------------- */

function updateCount() {
  const text = $("sourceText").value;
  $("charCount").textContent = `${text.length.toLocaleString("en-US")} / 20 000`;
  setDirection($("sourceText"), text);
}

function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("themeToggle").textContent = dark ? "☀️ Light" : "🌙 Dark";
  localStorage.setItem(STORAGE.theme, dark ? "dark" : "light");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = dark ? "#0d111b" : "#6956e8";
}

function initTheme() {
  const saved = localStorage.getItem(STORAGE.theme) || localStorage.getItem(LEGACY.theme);
  const preferred = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  applyTheme(saved || preferred);
}

function setAction(action) {
  currentAction = action;
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.action === action);
  });
  const label = ACTION_LABELS[action] || "Process";
  const labelEl = $("processBtnLabel");
  if (labelEl) labelEl.textContent = requestInFlight ? "Working…" : label;
  $("inputHint").textContent = ACTION_HINTS[action] || "";
  const isWriteOrResearch = action === "write" || action === "research";
  $("toneHeading").classList.toggle("hidden", isWriteOrResearch);
  $("toneGrid").classList.toggle("hidden", isWriteOrResearch);
  // The output language stays visible and editable in every mode. In Write and
  // Research modes it defaults to "Same as request", so nothing is translated
  // unless the user explicitly selects another language.
  const targetSelect = $("targetLanguage");
  const targetLabel = targetSelect ? targetSelect.closest("label") : null;
  if (targetLabel) targetLabel.classList.remove("hidden");
  const targetLabelText = $("targetLanguageLabelText");
  if (targetLabelText) {
    targetLabelText.textContent = isWriteOrResearch ? "Output language" : "Translate to";
  }
  if (targetSelect && !targetLanguageTouched) {
    if (isWriteOrResearch) {
      targetSelect.value = "auto";
    } else if (targetSelect.value === "auto") {
      targetSelect.value = "en";
    }
  }
  const placeholder = action === "write"
    ? "Describe the text you need, e.g. “Compose an email to optical store support asking to exchange my glasses…”"
    : action === "research"
      ? "Ask a current factual question, e.g. “What are the opening hours of the optical store?”"
      : action === "improve"
        ? "Paste the text you want improved…"
        : "Enter or paste text, or start dictation…";
  $("sourceText").placeholder = placeholder;
}

function showControlOverlay(title, message) {
  $("controlTitle").textContent = title;
  $("controlMessage").textContent = message;
  $("controlOverlay").classList.remove("hidden");
}

async function restartApplication() {
  if (!confirm("Restart the local application? Unsaved text stays only in this browser tab.")) return;
  showControlOverlay("Restarting", "Please wait a few seconds…");
  try {
    await fetch("/api/control/restart", { method: "POST" });
  } catch (_) {}

  await new Promise((resolve) => setTimeout(resolve, 900));
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`/api/health?t=${Date.now()}`, { cache: "no-store" });
      if (response.ok) {
        window.location.reload();
        return;
      }
    } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 550));
  }
  $("controlMessage").textContent = "The server did not restart within 30 seconds. Run START_TRANSLATOR.bat and check data/launcher.log.";
}

async function exitApplication() {
  if (!confirm("Stop TriHumanizer Translator?")) return;
  showControlOverlay("Stopped", "You can close this tab.");
  try {
    await fetch("/api/control/exit", { method: "POST" });
  } catch (_) {}
  setTimeout(() => window.close(), 800);
}

/* ---------------- auth gate ---------------- */

function showAuthOverlay() {
  $("authOverlay").classList.remove("hidden");
  $("authPassword").focus();
}

function hideAuthOverlay() {
  $("authOverlay").classList.add("hidden");
}

async function submitAuth(event) {
  event.preventDefault();
  const password = $("authPassword").value;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Login failed.");
    hideAuthOverlay();
    $("authPassword").value = "";
    setStatus("Unlocked. AI features are available.", false, true);
    await loadHistory();
  } catch (error) {
    $("authError").textContent = error.message;
    $("authError").className = "status error";
  }
}

/* ---------------- keyboard shortcut ---------------- */

function shortcutLabel() {
  const isMac = /Mac|iPhone|iPad|iPod/i.test(navigator.platform || "");
  return isMac ? "Cmd" : "Ctrl";
}

function handleShortcut(event) {
  if (event.isComposing || event.keyCode === 229) return; // IME composition
  const modifier = event.ctrlKey || event.metaKey;
  if (!modifier || event.key !== "Enter") return;
  if (event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLInputElement) {
    // Still allow Ctrl+Enter to run the action.
  }
  event.preventDefault();
  if (requestInFlight) return; // never trigger twice while a request runs
  processText();
}

function initShortcutHint() {
  const key = $("shortcutKey");
  if (key) key.textContent = shortcutLabel();
}

/* ---------------- events ---------------- */

function bindEvents() {
  $("sourceText").addEventListener("input", updateCount);
  $("provider").addEventListener("change", async () => {
    captureProviderState(activeProvider);
    activeProvider = $("provider").value;
    applyProviderState(activeProvider);
    updateProviderUI();
    saveGeneralSettings();
    $("modelPanel").open = true;
    const activeModel = selectedModel();
    setModelStatus(
      activeModel
        ? `Starting model: ${activeModel}. Refresh the catalog if needed.`
        : "Select a model or add one manually."
    );
  });
  $("customUrl").addEventListener("input", () => {
    $("endpointPreview").textContent = currentEndpoint() || "Enter an endpoint below";
    populateModels(cachedModels(), preferredProviderState($("provider").value).model);
    saveGeneralSettings();
  });
  $("apiKey").addEventListener("change", () => {
    captureProviderState();
    saveGeneralSettings();
  });
  $("modelSelect").addEventListener("change", () => {
    captureProviderState();
    saveGeneralSettings();
    updateModelSummary();
    autoCollapseModelPanel(350);
  });
  $("modelFilter").addEventListener("input", () => populateModels(allModels, selectedModel(), $("modelFilter").value));
  $("addManualModelBtn").addEventListener("click", addManualModel);
  $("manualModel").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addManualModel();
    }
  });
  $("testKeyBtn").addEventListener("click", testApiKey);
  $("testModelBtn").addEventListener("click", testSelectedModel);
  $("loadModelsBtn").addEventListener("click", () => loadModels({ silent: false, collapse: true }));
  $("collapseModelPanelBtn").addEventListener("click", () => {
    $("modelPanel").open = false;
  });
  $("processBtn").addEventListener("click", processText);
  $("clearTextBtn").addEventListener("click", () => {
    $("sourceText").value = "";
    updateCount();
    hideLayoutSuggestion();
    $("sourceText").focus();
  });
  $("pasteBtn").addEventListener("click", async () => {
    try {
      $("sourceText").value = await readClipboardText();
      updateCount();
      $("sourceText").focus();
    } catch (error) {
      setStatus(`${error.message} You can paste with Ctrl+V.`, true);
    }
  });
  $("copySourceBtn").addEventListener("click", (event) =>
    flashButton(event.currentTarget, () => writeClipboardText($("sourceText").value))
  );
  $("swapBtn").addEventListener("click", () => {
    const source = $("sourceLanguage").value;
    const target = $("targetLanguage").value;
    if (source === "auto") {
      $("sourceLanguage").value = target;
      $("targetLanguage").value = target === "en" ? "ru" : "en";
    } else {
      $("sourceLanguage").value = target;
      $("targetLanguage").value = source;
    }
    saveGeneralSettings();
  });
  document.querySelectorAll('input[name="mode"]').forEach((input) =>
    input.addEventListener("change", () => {
      updateModeCards();
      saveGeneralSettings();
    })
  );
  document.querySelectorAll(".mode-tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      setAction(tab.dataset.action);
      saveGeneralSettings();
    })
  );
  document.querySelectorAll(".copyBtn").forEach((btn) =>
    btn.addEventListener("click", () => flashButton(btn, () => writeClipboardText($(btn.dataset.target).value)))
  );
  document.querySelectorAll(".toSourceBtn").forEach((btn) =>
    btn.addEventListener("click", () => useAsSource($(btn.dataset.target).value))
  );
  $("copyTranslationBtn").addEventListener("click", (event) =>
    flashButton(event.currentTarget, () => writeClipboardText(primaryResultText()))
  );
  $("copyAllBtn").addEventListener("click", (event) =>
    flashButton(event.currentTarget, () => writeClipboardText(collectAllResults()))
  );
  $("shareResultBtn").addEventListener("click", shareResult);
  $("translationToSourceBtn").addEventListener("click", () => useAsSource(primaryResultText()));
  $("exportTxtBtn").addEventListener("click", exportTxt);
  $("exportPdfBtn").addEventListener("click", exportPdf);
  $("clearHistoryBtn").addEventListener("click", clearHistory);
  $("rememberSettings").addEventListener("change", saveGeneralSettings);
  $("autoCorrectLayout").addEventListener("change", () => {
    saveLayoutSettings({ enabled: $("autoCorrectLayout").checked });
    updateLayoutBadge();
    saveGeneralSettings();
  });
  $("toggleKeyBtn").addEventListener("click", () => {
    const input = $("apiKey");
    input.type = input.type === "password" ? "text" : "password";
  });
  $("themeToggle").addEventListener("click", () =>
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark")
  );
  $("restartBtn").addEventListener("click", restartApplication);
  $("exitBtn").addEventListener("click", exitApplication);
  $("layoutApplyBtn").addEventListener("click", applyLayoutSuggestion);
  $("layoutKeepBtn").addEventListener("click", keepLayoutSuggestion);
  $("layoutUndoBtn").addEventListener("click", undoLayoutSuggestion);
  $("authForm").addEventListener("submit", submitAuth);
  document.addEventListener("keydown", handleShortcut);

  [
    "sourceLanguage", "targetLanguage", "context", "customInstruction", "writerGender",
    "recipientGender", "humanizeOriginal", "humanizeTranslation", "includeLiteral", "preserveLength",
  ].forEach((id) => $(id).addEventListener("change", saveGeneralSettings));
  $("targetLanguage").addEventListener("change", () => {
    targetLanguageTouched = true;
  });

  // Debounced layout check while typing.
  let layoutTimer = null;
  $("sourceText").addEventListener("input", () => {
    if (!layoutSettings().enabled) return;
    window.clearTimeout(layoutTimer);
    layoutTimer = window.setTimeout(() => applyLayoutCorrection(true), 700);
  });
}

/* ---------------- service worker ---------------- */

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  });
}

/* ---------------- init ---------------- */

migrateLegacySettings();
initTheme();
bindEvents();
loadGeneralSettings();
updateProviderUI();
updateModeCards();
updateCount();
initShortcutHint();
loadHistory();
if (AUTH_REQUIRED) showAuthOverlay();
registerServiceWorker();
setModelStatus(
  selectedModel() ? `Ready: ${selectedModel()}.` : "Select a model in settings.",
  false,
  Boolean(selectedModel())
);

// ---------------------------------------------------------------------------
// Autosave wiring.
//
// Before this, the API key lived only in the DOM: after a restart of the
// application the field was empty, no key was sent, and the provider answered
// "Provider error 401: Unauthorized". Provider, model, endpoint and key are
// now saved on the server as soon as they change and re-applied on start.
// ---------------------------------------------------------------------------
(function initSettingsAutosave() {
  if (HOSTED) return;

  const keyField = $("apiKey");
  const providerField = $("provider");
  const modelField = $("modelSelect");
  const urlField = $("customUrl");

  if (keyField) {
    keyField.addEventListener("change", () => persistSettings({ immediate: true }));
    keyField.addEventListener("blur", () => persistSettings({ immediate: true }));
  }
  if (providerField) providerField.addEventListener("change", () => persistSettings());
  if (modelField) modelField.addEventListener("change", () => persistSettings());
  if (urlField) urlField.addEventListener("change", () => persistSettings());

  syncSavedKeyFlags();

  // Re-read the stored selection on start: this is what makes the saved model
  // and key survive a restart of the application.
  fetch("/api/settings")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data || !data.settings) return;
      SAVED_SETTINGS = data.settings;
      syncSavedKeyFlags();
      const provider = SAVED_SETTINGS.provider && providerDefaults[SAVED_SETTINGS.provider]
        ? SAVED_SETTINGS.provider
        : $("provider").value;
      $("provider").value = provider;
      activeProvider = provider;
      applyProviderState(provider);
      updateProviderUI();
      updateCompactBlock();
    })
    .catch(() => {});
})();
// ---------------------------------------------------------------------------
// Compact AI model block.
//
// Shows the engine actually in use, saves provider/model/key with one click and
// re-checks the endpoint and the model without opening the full settings panel.
// ---------------------------------------------------------------------------
const AUTO_ENGINE_KEY = "triHumanizerAutoEngineV16";

function compactStatus(message, ok) {
  const node = $("aiCompactStatus");
  if (!node) return;
  node.textContent = message || "";
  node.style.color = ok === false ? "#c0392b" : "";
}

function updateCompactBlock() {
  const engine = $("aiCompactEngine");
  if (!engine) return;
  const provider = $("provider").value;
  const model = selectedModel();
  engine.textContent = provider + "/" + (model || "no model selected");
  const flag = $("aiCompactVerified");
  if (flag) {
    const defaults = providerDefaults[provider] || {};
    const ready = savedHasKey(provider) || Boolean(defaults.configuredKey) || !defaults.requiresKey;
    flag.textContent = ready ? "(auto-verified)" : "(key not saved yet)";
  }
}

(function initCompactBlock() {
  if (!$("aiCompact")) return;

  const auto = $("aiCompactAuto");
  if (auto) {
    auto.checked = readJSON(AUTO_ENGINE_KEY, true) !== false;
    auto.addEventListener("change", () => {
      writeJSON(AUTO_ENGINE_KEY, auto.checked);
      compactStatus(
        auto.checked
          ? "Automatic engine selection is on: the best available model is checked for you."
          : "Automatic engine selection is off: the model stays exactly as chosen.",
        true
      );
    });
  }

  const save = $("aiCompactSave");
  if (save) {
    save.addEventListener("click", async () => {
      await persistSettings({ immediate: true });
      updateCompactBlock();
      compactStatus("Saved on the server: provider, model, endpoint and key.", true);
    });
  }

  const recheck = $("aiCompactRecheck");
  if (recheck) {
    recheck.addEventListener("click", async () => {
      compactStatus("Re-checking the endpoint and the selected model...", true);
      try {
        if (typeof loadModels === "function") await loadModels();
        if (typeof testSelectedModel === "function") await testSelectedModel();
        updateCompactBlock();
        compactStatus("Re-check finished. Details are in the settings panel.", true);
      } catch (_) {
        compactStatus("Re-check did not finish. Open the settings panel for details.", false);
      }
    });
  }

  ["provider", "modelSelect", "customUrl", "apiKey"].forEach((id) => {
    const field = $(id);
    if (field) field.addEventListener("change", updateCompactBlock);
  });

  updateCompactBlock();
})();