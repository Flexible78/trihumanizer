"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const SETTINGS_KEY = "triHumanizerSpeechV16";
  const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  const synth = window.speechSynthesis || null;

  const LANGUAGE_PREFIXES = {
    "ru-RU": "ru",
    "en-US": "en",
    "en-GB": "en",
    "he-IL": "he"
  };

  const FATAL_RECOGNITION_ERRORS = new Set([
    "not-allowed",
    "service-not-allowed",
    "audio-capture",
    "language-not-supported"
  ]);

  let recognition = null;
  let dictationRequested = false;
  let dictationStopping = false;
  let dictationBase = "";
  let dictationCommitted = "";
  let dictationInterim = "";
  let recognitionRestartTimer = null;
  let recognitionRestartCount = 0;
  let lastRecognitionError = "";

  let voices = [];
  let currentUtterance = null;
  let speechQueue = [];
  let speechQueueIndex = 0;
  let speechRunId = 0;
  let speechLanguage = "en-US";
  let speechVoice = null;
  let speechHeartbeat = null;

  function readSettings() {
    try {
      return JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}") || {};
    } catch (_) {
      return {};
    }
  }

  function saveSettings() {
    const settings = {
      dictationLanguage: byId("dictationLanguage")?.value || "ru-RU",
      dictationInsertMode: byId("dictationInsertMode")?.value || "append",
      speechLanguage: byId("speechLanguage")?.value || "auto",
      speechVoice: byId("speechVoice")?.value || "",
      speechRate: Number(byId("speechRate")?.value || 1)
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }

  function loadSettings() {
    const settings = readSettings();
    if (settings.dictationLanguage && byId("dictationLanguage")) byId("dictationLanguage").value = settings.dictationLanguage;
    if (settings.dictationInsertMode && byId("dictationInsertMode")) byId("dictationInsertMode").value = settings.dictationInsertMode;
    if (settings.speechLanguage && byId("speechLanguage")) byId("speechLanguage").value = settings.speechLanguage;
    if (settings.speechRate && byId("speechRate")) byId("speechRate").value = String(settings.speechRate);
    updateRateLabel();
  }

  function setVoiceStatus(message, error = false, ok = false) {
    const element = byId("speechStatus");
    if (!element) return;
    element.textContent = message;
    element.className = `voice-status${error ? " error" : ok ? " ok" : ""}`;
  }

  function setDictationStatus(message, error = false, ok = false) {
    const element = byId("dictationStatus");
    if (!element) return;
    element.textContent = message;
    element.className = `voice-status${error ? " error" : ok ? " ok" : ""}`;
  }

  function detectLanguage(text) {
    const value = String(text || "");
    if ([...value].some((char) => {
      const cp = char.codePointAt(0);
      return cp >= 0x0590 && cp <= 0x05ff;
    })) return "he-IL";
    if (/[А-Яа-яЁё]/.test(value)) return "ru-RU";
    return "en-US";
  }

  function normalizeLanguage(lang) {
    const lower = String(lang || "").toLowerCase();
    if (lower.startsWith("he") || lower.startsWith("iw")) return "he-IL";
    if (lower.startsWith("ru")) return "ru-RU";
    if (lower.startsWith("en-gb")) return "en-GB";
    if (lower.startsWith("en")) return "en-US";
    return lang || "en-US";
  }

  function matchingVoice(voice, language) {
    const normalized = normalizeLanguage(language);
    const wanted = LANGUAGE_PREFIXES[normalized] || normalized.slice(0, 2).toLowerCase();
    const actual = String(voice.lang || "").slice(0, 2).toLowerCase();
    if (wanted === "he") return actual === "he" || actual === "iw";
    return actual === wanted;
  }

  function loadVoices() {
    if (!synth || !byId("speechVoice")) return;
    const current = byId("speechVoice").value || readSettings().speechVoice || "";
    voices = synth.getVoices().slice().sort((a, b) => {
      const langCompare = String(a.lang).localeCompare(String(b.lang));
      return langCompare || String(a.name).localeCompare(String(b.name));
    });

    const select = byId("speechVoice");
    select.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "Automatic matching voice";
    select.appendChild(auto);

    voices.forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice.voiceURI;
      option.textContent = `${voice.name} — ${voice.lang}${voice.localService ? " — local" : ""}`;
      select.appendChild(option);
    });

    if (current && voices.some((voice) => voice.voiceURI === current)) select.value = current;
    else select.value = "";

    if (!voices.length) {
      setVoiceStatus("Voices are still loading. Press Read again in a second or check the Windows voices.");
    } else {
      const counts = ["ru-RU", "en-US", "he-IL"].map(
        (lang) => `${lang.slice(0, 2)}: ${voices.filter((voice) => matchingVoice(voice, lang)).length}`
      );
      setVoiceStatus(`Speech ready. Voices: ${voices.length} (${counts.join(", ")}).`, false, true);
    }
  }

  function updateRateLabel() {
    const rate = Number(byId("speechRate")?.value || 1);
    if (byId("speechRateValue")) byId("speechRateValue").textContent = `${rate.toFixed(1)}×`;
  }

  function selectedVoice(language) {
    const selectedURI = byId("speechVoice")?.value || "";
    if (selectedURI) return voices.find((voice) => voice.voiceURI === selectedURI) || null;
    return voices.find((voice) => matchingVoice(voice, language) && voice.localService)
      || voices.find((voice) => matchingVoice(voice, language))
      || voices.find((voice) => voice.default)
      || null;
  }

  function splitLongPart(part, maxLength) {
    const chunks = [];
    let rest = part.trim();
    while (rest.length > maxLength) {
      let cut = rest.lastIndexOf(" ", maxLength);
      if (cut < Math.floor(maxLength * 0.55)) cut = maxLength;
      chunks.push(rest.slice(0, cut).trim());
      rest = rest.slice(cut).trim();
    }
    if (rest) chunks.push(rest);
    return chunks;
  }

  function splitForSpeech(text, maxLength = 220) {
    const clean = String(text || "").replace(/\r/g, "").replace(/[ \t]+/g, " ").trim();
    if (!clean) return [];
    const sentenceParts = clean
      .split(/(?<=[.!?…։。！？])\s+|\n+/u)
      .map((part) => part.trim())
      .filter(Boolean);
    const chunks = [];
    sentenceParts.forEach((part) => {
      if (part.length <= maxLength) chunks.push(part);
      else chunks.push(...splitLongPart(part, maxLength));
    });
    return chunks;
  }

  function clearSpeechHeartbeat() {
    if (speechHeartbeat) window.clearInterval(speechHeartbeat);
    speechHeartbeat = null;
  }

  function startSpeechHeartbeat(runId) {
    clearSpeechHeartbeat();
    speechHeartbeat = window.setInterval(() => {
      if (runId !== speechRunId || !synth) return;
      if (synth.speaking && !synth.paused) {
        try { synth.resume(); } catch (_) {}
      }
    }, 8000);
  }

  function finishSpeech(message = "Reading finished.") {
    currentUtterance = null;
    speechQueue = [];
    speechQueueIndex = 0;
    clearSpeechHeartbeat();
    setVoiceStatus(message, false, true);
  }

  function speakNextChunk(runId) {
    if (!synth || runId !== speechRunId) return;
    if (speechQueueIndex >= speechQueue.length) {
      finishSpeech();
      return;
    }

    const chunk = speechQueue[speechQueueIndex];
    const utterance = new SpeechSynthesisUtterance(chunk);
    utterance.lang = speechVoice?.lang || speechLanguage;
    utterance.rate = Number(byId("speechRate")?.value || 1);
    if (speechVoice) utterance.voice = speechVoice;

    utterance.onstart = () => {
      if (runId !== speechRunId) return;
      const voiceName = speechVoice?.name || utterance.lang;
      setVoiceStatus(`Reading ${speechQueueIndex + 1}/${speechQueue.length}: ${voiceName}.`, false, true);
    };
    utterance.onpause = () => {
      if (runId === speechRunId) setVoiceStatus("Speech paused.");
    };
    utterance.onresume = () => {
      if (runId === speechRunId) setVoiceStatus("Speech resumed.", false, true);
    };
    utterance.onend = () => {
      if (runId !== speechRunId) return;
      currentUtterance = null;
      speechQueueIndex += 1;
      window.setTimeout(() => speakNextChunk(runId), 35);
    };
    utterance.onerror = (event) => {
      if (runId !== speechRunId) return;
      currentUtterance = null;
      if (event.error === "canceled" || event.error === "interrupted") return;
      clearSpeechHeartbeat();
      setVoiceStatus(`Speech error: ${event.error || "unknown error"}. Try a different voice.`, true);
    };

    currentUtterance = utterance;
    window.setTimeout(() => {
      if (runId !== speechRunId) return;
      try {
        synth.speak(utterance);
      } catch (error) {
        clearSpeechHeartbeat();
        setVoiceStatus(`Could not start reading: ${error.message}`, true);
      }
    }, 30);
  }

  function speak(text, languageHint = "auto") {
    const clean = String(text || "").trim();
    if (!clean) {
      setVoiceStatus("No text to read.", true);
      return;
    }
    if (!synth || typeof SpeechSynthesisUtterance === "undefined") {
      setVoiceStatus("This browser does not support built-in speech.", true);
      return;
    }

    loadVoices();
    speechRunId += 1;
    const runId = speechRunId;
    try { synth.cancel(); } catch (_) {}

    const requestedLanguage = byId("speechLanguage")?.value || "auto";
    speechLanguage = requestedLanguage === "auto"
      ? (languageHint === "auto" ? detectLanguage(clean) : normalizeLanguage(languageHint))
      : normalizeLanguage(requestedLanguage);
    speechVoice = selectedVoice(speechLanguage);
    speechQueue = splitForSpeech(clean);
    speechQueueIndex = 0;

    if (!speechQueue.length) {
      setVoiceStatus("No text to read.", true);
      return;
    }

    startSpeechHeartbeat(runId);
    setVoiceStatus(`Preparing to read: ${speechQueue.length} parts.`);
    window.setTimeout(() => speakNextChunk(runId), 80);
  }

  function primaryResult() {
    return byId("humanizedTranslation")?.value.trim()
      || byId("humanizedOriginal")?.value.trim()
      || byId("literalTranslation")?.value.trim()
      || "";
  }

  function languageForTarget(targetId, text) {
    if (targetId === "humanizedTranslation" || targetId === "literalTranslation") {
      const target = byId("targetLanguage")?.value;
      return target === "he" ? "he-IL" : target === "ru" ? "ru-RU" : "en-US";
    }
    if (targetId === "sourceText" || targetId === "humanizedOriginal") {
      const source = byId("sourceLanguage")?.value;
      if (source === "he") return "he-IL";
      if (source === "ru") return "ru-RU";
      if (source === "en") return "en-US";
    }
    return detectLanguage(text);
  }

  function stopSpeech(showStatus = true) {
    speechRunId += 1;
    clearSpeechHeartbeat();
    if (synth) {
      try { synth.cancel(); } catch (_) {}
    }
    currentUtterance = null;
    speechQueue = [];
    speechQueueIndex = 0;
    if (showStatus) setVoiceStatus("Speech stopped.");
  }

  function pauseSpeech() {
    if (!synth || (!synth.speaking && !currentUtterance)) {
      setVoiceStatus("Nothing is being read right now.", true);
      return;
    }
    try {
      synth.pause();
      setVoiceStatus("Speech paused.");
    } catch (error) {
      setVoiceStatus(`Could not pause: ${error.message}`, true);
    }
  }

  function resumeSpeech() {
    if (!synth || !synth.paused) {
      setVoiceStatus("Speech is not paused.", true);
      return;
    }
    try {
      synth.resume();
      setVoiceStatus("Speech resumed.", false, true);
    } catch (error) {
      setVoiceStatus(`Could not resume reading: ${error.message}`, true);
    }
  }

  function normalizeTranscript(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function appendUniqueText(existing, segment) {
    const left = normalizeTranscript(existing);
    const right = normalizeTranscript(segment);
    if (!right) return left;
    if (!left) return right;
    if (left.toLocaleLowerCase().endsWith(right.toLocaleLowerCase())) return left;

    const leftWords = left.split(" ");
    const rightWords = right.split(" ");
    const maxOverlap = Math.min(12, leftWords.length, rightWords.length);
    let overlap = 0;
    for (let size = maxOverlap; size >= 1; size -= 1) {
      const leftTail = leftWords.slice(-size).join(" ").toLocaleLowerCase();
      const rightHead = rightWords.slice(0, size).join(" ").toLocaleLowerCase();
      if (leftTail === rightHead) {
        overlap = size;
        break;
      }
    }
    return [...leftWords, ...rightWords.slice(overlap)].join(" ");
  }

  function composeDictationText(interim = "") {
    let value = normalizeTranscript(dictationBase);
    value = appendUniqueText(value, dictationCommitted);
    value = appendUniqueText(value, interim);
    return value;
  }

  function applyDictationText(interim = "") {
    const source = byId("sourceText");
    if (!source) return;
    source.value = composeDictationText(interim);
    source.dispatchEvent(new Event("input", {bubbles: true}));
  }

  function mapRecognitionError(code) {
    const messages = {
      "not-allowed": "Microphone access was denied. Allow the microphone for 127.0.0.1/localhost in the browser settings.",
      "service-not-allowed": "The browser blocked the speech recognition service.",
      "audio-capture": "Microphone not found or already in use by another application.",
      "no-speech": "No speech heard yet. Still listening…",
      "network": "The recognition service is temporarily unavailable. Trying to reconnect…",
      "language-not-supported": "The selected recognition language is not supported by this browser.",
      "aborted": "Dictation stopped."
    };
    return messages[code] || `Recognition error: ${code || "unknown error"}.`;
  }

  function setDictationButtons(active) {
    if (byId("startDictationBtn")) {
      byId("startDictationBtn").disabled = active;
      byId("startDictationBtn").textContent = active ? "🎙 Listening…" : "🎙 Start dictation";
    }
    if (byId("stopDictationBtn")) byId("stopDictationBtn").disabled = !active;
  }

  function clearRecognitionRestart() {
    if (recognitionRestartTimer) window.clearTimeout(recognitionRestartTimer);
    recognitionRestartTimer = null;
  }

  function finalizeDictation(message = "Dictation finished. You can edit the text or process it right away.") {
    clearRecognitionRestart();
    if (dictationInterim) {
      dictationCommitted = appendUniqueText(dictationCommitted, dictationInterim);
      dictationInterim = "";
    }
    applyDictationText();
    recognition = null;
    dictationStopping = false;
    setDictationButtons(false);
    if (!byId("sourceText")?.value.trim()) setDictationStatus("Dictation finished without recognized text.", true);
    else setDictationStatus(message, false, true);
  }

  function scheduleRecognitionRestart(delay = 250) {
    clearRecognitionRestart();
    if (!dictationRequested) return;
    recognitionRestartTimer = window.setTimeout(() => {
      recognitionRestartTimer = null;
      startRecognitionSession();
    }, delay);
  }

  function startRecognitionSession() {
    if (!dictationRequested || recognition) return;
    if (!RecognitionClass) {
      dictationRequested = false;
      setDictationButtons(false);
      setDictationStatus("This browser has no Web Speech Recognition.", true);
      return;
    }

    const session = new RecognitionClass();
    recognition = session;
    lastRecognitionError = "";
    session.lang = byId("dictationLanguage")?.value || "ru-RU";
    session.continuous = true;
    session.interimResults = true;
    session.maxAlternatives = 1;

    session.onstart = () => {
      if (recognition !== session) return;
      recognitionRestartCount = 0;
      setDictationButtons(true);
      setDictationStatus("Listening continuously. Pauses are fine — recognition restarts automatically.", false, true);
      const sourceLangMap = {"ru-RU": "ru", "en-US": "en", "en-GB": "en", "he-IL": "he"};
      if (byId("sourceLanguage")?.value === "auto") {
        byId("sourceLanguage").value = sourceLangMap[session.lang] || "auto";
        byId("sourceLanguage").dispatchEvent(new Event("change", {bubbles: true}));
      }
    };

    session.onresult = (event) => {
      if (recognition !== session) return;
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = normalizeTranscript(event.results[i][0]?.transcript || "");
        if (!transcript) continue;
        if (event.results[i].isFinal) {
          dictationCommitted = appendUniqueText(dictationCommitted, transcript);
          dictationInterim = "";
        } else {
          interim = appendUniqueText(interim, transcript);
        }
      }
      dictationInterim = interim;
      applyDictationText(interim);
      const wordCount = composeDictationText(interim).split(/\s+/).filter(Boolean).length;
      setDictationStatus(
        interim ? `Recognizing: ${interim} · words: ${wordCount}` : `Phrase added · words: ${wordCount}. Keep going…`,
        false,
        true
      );
    };

    session.onerror = (event) => {
      if (recognition !== session) return;
      lastRecognitionError = event.error || "";
      if (FATAL_RECOGNITION_ERRORS.has(lastRecognitionError)) {
        dictationRequested = false;
        setDictationStatus(mapRecognitionError(lastRecognitionError), true);
        return;
      }
      if (lastRecognitionError === "aborted" && dictationStopping) return;
      setDictationStatus(mapRecognitionError(lastRecognitionError), false, false);
    };

    session.onend = () => {
      if (recognition !== session) return;
      recognition = null;

      if (dictationInterim) {
        dictationCommitted = appendUniqueText(dictationCommitted, dictationInterim);
        dictationInterim = "";
        applyDictationText();
      }

      if (!dictationRequested || dictationStopping || FATAL_RECOGNITION_ERRORS.has(lastRecognitionError)) {
        finalizeDictation();
        return;
      }

      recognitionRestartCount += 1;
      const delay = lastRecognitionError === "network"
        ? Math.min(3500, 700 * recognitionRestartCount)
        : 220;
      setDictationStatus("The browser ended the session. Automatically continuing dictation…");
      scheduleRecognitionRestart(delay);
    };

    try {
      session.start();
    } catch (error) {
      recognition = null;
      recognitionRestartCount += 1;
      if (dictationRequested && recognitionRestartCount <= 5) {
        setDictationStatus("Restarting the microphone…");
        scheduleRecognitionRestart(Math.min(1800, 250 * recognitionRestartCount));
      } else {
        dictationRequested = false;
        setDictationButtons(false);
        setDictationStatus(`Could not start dictation: ${error.message}`, true);
      }
    }
  }

  function startDictation() {
    if (!RecognitionClass) {
      setDictationStatus("This browser has no Web Speech Recognition. Try a current Chrome/Edge or a local Whisper.", true);
      return;
    }
    if (dictationRequested) return;

    const source = byId("sourceText");
    const mode = byId("dictationInsertMode")?.value || "append";
    dictationBase = mode === "append" ? source.value.trim() : "";
    dictationCommitted = "";
    dictationInterim = "";
    recognitionRestartCount = 0;
    dictationStopping = false;
    dictationRequested = true;
    setDictationButtons(true);
    setDictationStatus("Requesting microphone access…");
    startRecognitionSession();
  }

  function stopDictation() {
    if (!dictationRequested && !recognition) return;
    dictationRequested = false;
    dictationStopping = true;
    clearRecognitionRestart();
    if (dictationInterim) {
      dictationCommitted = appendUniqueText(dictationCommitted, dictationInterim);
      dictationInterim = "";
      applyDictationText();
    }
    setDictationStatus("Stopping dictation…");
    if (!recognition) {
      finalizeDictation();
      return;
    }
    try {
      recognition.stop();
    } catch (_) {
      try { recognition.abort(); } catch (_) {}
      recognition = null;
      finalizeDictation();
    }
  }

  function bindClick(id, handler) {
    const element = byId(id);
    if (element) element.addEventListener("click", handler);
  }

  function initialize() {
    loadSettings();

    if (!RecognitionClass) {
      if (byId("startDictationBtn")) byId("startDictationBtn").disabled = true;
      setDictationStatus("This browser does not provide speech recognition. Speech output may still work.", true);
    } else {
      setDictationStatus("Dictation ready. After pauses it will automatically keep listening.", false, true);
    }

    if (!synth) {
      ["readSourceBtn", "readPrimaryBtn", "stopSpeechBtn", "pauseSpeechBtn", "resumeSpeechBtn"].forEach((id) => {
        if (byId(id)) byId(id).disabled = true;
      });
      document.querySelectorAll(".speakTargetBtn").forEach((button) => { button.disabled = true; });
      setVoiceStatus("This browser does not support built-in speech.", true);
    } else {
      loadVoices();
      if ("onvoiceschanged" in synth) synth.addEventListener("voiceschanged", loadVoices);
      [250, 800, 1800, 3500].forEach((delay) => window.setTimeout(loadVoices, delay));
    }

    bindClick("startDictationBtn", startDictation);
    bindClick("stopDictationBtn", stopDictation);
    bindClick("readSourceBtn", () => {
      const text = byId("sourceText")?.value || "";
      speak(text, languageForTarget("sourceText", text));
    });
    bindClick("readPrimaryBtn", () => {
      const text = primaryResult();
      const targetId = byId("humanizedTranslation")?.value.trim() ? "humanizedTranslation" : "humanizedOriginal";
      speak(text, languageForTarget(targetId, text));
    });
    bindClick("stopSpeechBtn", () => stopSpeech(true));
    bindClick("pauseSpeechBtn", pauseSpeech);
    bindClick("resumeSpeechBtn", resumeSpeech);

    document.querySelectorAll(".speakTargetBtn").forEach((button) => {
      button.addEventListener("click", () => {
        const targetId = button.dataset.target;
        const text = byId(targetId)?.value || "";
        speak(text, languageForTarget(targetId, text));
      });
    });

    ["dictationLanguage", "dictationInsertMode", "speechLanguage", "speechVoice"].forEach((id) => {
      if (byId(id)) byId(id).addEventListener("change", saveSettings);
    });
    if (byId("speechRate")) {
      byId("speechRate").addEventListener("input", () => {
        updateRateLabel();
        saveSettings();
      });
    }
    if (byId("speechLanguage")) byId("speechLanguage").addEventListener("change", loadVoices);

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && dictationRequested && !recognition) {
        scheduleRecognitionRestart(180);
      }
    });

    window.addEventListener("beforeunload", () => {
      dictationRequested = false;
      clearRecognitionRestart();
      if (recognition) {
        try { recognition.abort(); } catch (_) {}
      }
      stopSpeech(false);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize);
  else initialize();
})();
