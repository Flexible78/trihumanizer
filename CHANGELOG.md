# Changelog

## Version 1.7.0 - Three languages at once, Hebrew reading aids and cost control

### Result pane
- RU / EN / HE switcher in the final translation block: one click shows the same message in another language, already-loaded languages switch instantly without a new request.
- Multi-language mode fills Russian, English and Hebrew in a single model call, so switching costs nothing.
- Show changes view for the improved original: a word-level diff marks in green what the editor added and in red what it dropped, with a removed/added counter. Runs in the browser, no extra request.
- Transcription panel: Latin and Russian-letter transcription of the Hebrew result, so the text can be read aloud without knowing the alphabet. Cached per text.
- Nikud panel: the same Hebrew words with full vowel points, in a large right-to-left view with its own copy button.
- Compare models: pick a second model and both answer the same request in parallel, side by side, with word, character and latency counts plus Copy and Use this per column.

### Input and control
- Protected terms field: comma-separated names, brands and ticket numbers that are never translated, transliterated or inflected in any output language.
- Reply context field: paste the incoming message and the answer addresses its actual questions, names and dates without ever translating or quoting it.
- Scenario presets for HR and interviews, support, landlord and rent, clinic, bank and official authorities: one click fills the situation and the tone instructions.
- Extra hotkeys: Ctrl/Cmd+1/2/3 for Russian, English and Hebrew, Ctrl/Cmd+Shift+S for a smart swap based on the script actually typed, Ctrl/Cmd+Shift+C to copy the result.

### Cost, history and performance
- Usage meter under the result: requests, characters, estimated tokens and estimated cost for today, plus an optional daily request limit that blocks further calls.
- History search and export: live filtering of the list and one-click export as JSON or as CSV with a BOM, so Excel opens Hebrew and Cyrillic correctly.
- Server-side result cache: identical text with identical settings is answered from memory within the TTL, with no model call. Configurable via TRIHUMANIZER_CACHE_TTL and TRIHUMANIZER_CACHE_MAX.

### Compatibility
- Every addition is opt-in and additive: without the new flags the prompts are byte-identical to 1.6.3, existing endpoints keep their response shape (a `cached` flag was added), and no existing control, style or handler was replaced.

## Version 1.6.3 - Compact chrome and mobile layout

- The oversized AI model block is now a single low row: model, auto switch, Save and Re-check on one line. The long privacy paragraph and duplicate hints were removed.
- The top information ribbon was slimmed to one short line with three small chips and is hidden entirely on phones.
- All auxiliary, non-functional blocks (mode tabs, section headers, advanced settings, speech settings, empty result state, footer) got smaller heights and paddings.
- Mobile layout reworked: tighter paddings under 760px and 430px, icon-free full-width mode tabs, wrapping action rows, smaller empty state, readable input height, sticky Process button kept.

## Version 1.6.2 - Failover and language defaults

- History entries and the whole history are deleted immediately, without a confirmation dialog.
- Every mode now defaults the output language to "Same as original", the language of the input text. The selector stays visible and can be changed at any time.
- Tone control (Business / Friendly / Short reply) is available in every mode, including Write and Research, and is passed to the writing prompt.
- Automatic model failover: when a model errors, is rate limited or returns invalid JSON, the request is retried on the next best model (other models of the same provider first, then other configured providers). The status line reports which model answered.


## 1.6.1

### Fixed
- Provider error 401: Unauthorized after restarting the application. The API key
  existed only in the browser input, so a restart left the server with an empty
  credential. Provider, model, endpoint and key are now stored server-side in
  data/settings.json and reused automatically on start.
- resolve_api_key now also honours the built-in default key of local gateways,
  which was previously defined but never used.
- The CI secret scan is clean again: the intentional redaction fixture is
  assembled from two literals, so no tracked file contains a key-shaped string.

### Added
- settings_store.py: atomic, user-private storage of the provider selection with
  a secret-free public view (hasKey booleans only).
- GET, POST and DELETE /api/settings for reading, saving and forgetting the
  stored selection. /api/config now reports saved, savedKey and envKey.
- Successful /api/models, /api/test/key, /api/test/model and /api/process calls
  remember the configuration that worked.
- Compact AI model block in the interface: current engine, automatic mode, Save
  and Re-check all, with a saved key badge instead of a re-typed key.
- Documentation set: README rewritten for GitHub plus docs/ARCHITECTURE.md,
  docs/CONFIGURATION.md, docs/API.md, docs/TROUBLESHOOTING.md and
  docs/INTERVIEW_DEFENCE.md.

### Security
- data/settings.json and its temporary file are git-ignored, written atomically
  and chmod 0600 where the platform supports it. The key is never sent to the
  browser.
## Version 1.6.1 - Write mode language fix

- Fixed: Write mode no longer forces a previously selected translation language
  (for example Hebrew) onto generated letters. The hidden target language value was
  still sent to the model on every request.
- The output language selector is now visible and editable in every mode. It is
  labelled "Output language" in Write and Research modes and "Translate to" in
  translation mode.
- New "Same as request" (auto) option, applied by default in Write and Research
  modes: the answer keeps the language of the request unless the user picks another
  language or names one inside the request.
- Backend: "auto" is accepted in ALLOWED_TARGETS, and build_write_messages resolves
  the output language from the detected request language and instructs the model not
  to switch languages.

## Version 1.6.0 — Smart modes, keyboard layout correction, and hosted deployment

### Smart request modes

- Added the compact mode selector: **Auto / Translate / Write / Improve / Research** (default: Auto).
- Auto mode detects the user's intent from natural language in Russian, English, or Hebrew.
- Structured intent contract (`mode`, `input_language`, `output_language`,
  `needs_live_research`, `missing_information`, `cleaned_request`,
  `requested_format`, `requested_tone`), resolved by fast local heuristics and
  an optional model pass (`/api/intent`).
- New writing assistant prompts produce complete, ready-to-send text: emails
  render Subject, Greeting, Body, Closing, missing details, and verified
  findings. Opening hours, stock, and prices are never fabricated.

### Keyboard layout correction

- New `static/layout-corrector.js`: detects text typed with the wrong physical
  layout across English QWERTY, Russian JCUKEN, and Israeli Hebrew.
- Example conversions: `ghbdtn` → `привет`, `ghbdtn rfr ndjb ltkf` →
  `привет как твои дела`, `руддщ` → `hello`.
- High-confidence corrections apply automatically; medium confidence shows the
  "Wrong keyboard layout detected" bar with **Apply correction / Keep
  original / Undo**.
- URLs, emails, file paths, version numbers, code fragments, API names,
  hashtags, @mentions, numbers, and keyboard shortcuts are never modified.
- Intentional mixed-language text stays mixed.
- New user setting **Auto-correct keyboard layout** (default: On).
- Correction runs before translation, smart processing, improvement, and
  Ctrl+Enter execution.

### Keyboard shortcuts

- `Ctrl+Enter` (Windows/Linux) and `Cmd+Enter` (macOS) execute the selected
  primary action once; duplicates and IME composition are guarded, and the
  shortcut is disabled while a request is running.
- `Enter` / `Shift+Enter` remain available for multiline input.
- A visible `Ctrl + Enter` / `Cmd + Enter` hint sits next to the action button,
  with a loading state and cancellable fetch.

### Live research adapter

- Provider-independent research via `RESEARCH_ENABLED`, `RESEARCH_PROVIDER`,
  `RESEARCH_MODEL`, `RESEARCH_API_KEY`, `RESEARCH_BASE_URL`.
- Returns answers, verified findings, source titles/links, and a retrieval
  timestamp; distinguishes search results from AI inference and respects
  timeouts. When disabled, the app asks for the store URL and never fabricates
  current facts.

### English-only interface

- All public UI copy is now English (navigation, buttons, labels, statuses,
  errors, dialogs, tooltips, history, PDF, accessibility labels).
- Language names shown in English: Russian, English, Hebrew, Auto Detect.
- Documentation renamed and rewritten in English:
  `README_RU.md → README.md`, `CHANGELOG_RU.md → CHANGELOG.md`,
  `SECURITY_RU.md → SECURITY.md`, `QUALITY_ALGORITHM_RU.md → QUALITY_ALGORITHM.md`,
  `VALIDATION_RU.md → VALIDATION.md`, `BROWSER_VOICE_RU.md → BROWSER_VOICE.md`.

### Mobile and PWA

- Responsive layout tested at 390 px / 768 px / 1440 px, safe-area spacing,
  sticky action button on small screens, no horizontal scrolling.
- Web app manifest, generated 192/512 icons, theme color, and an installable
  PWA shell.
- Service worker caches static assets only; API responses with private text
  are never cached.
- Web Share API with a Copy fallback.

### Security

- Keys are read only from server-side environment variables
  (`MISTRAL_API_KEY`, `GROQ_API_KEY`, `GOOGLE_STUDIO_API_KEY`,
  `OPENROUTER_API_KEY`, `OMNIROUTE_API_KEY`, `FREEWAY_API_KEY`, `OPENAI_API_KEY`).
- Optional single-user protection: `APP_PASSWORD` + `FLASK_SECRET_KEY` with a
  signed, HttpOnly, SameSite session cookie. AI endpoints require login while
  the public shell stays visible.
- Provider/model allowlist validation, request length limits, secure HTTP
  headers (CSP, X-Frame-Options, Permissions-Policy, HSTS), same-origin CORS.
- Provider errors redacted before reaching the browser; full user text and API
  keys are never logged.
- `.env.example` added; `.gitignore` extended; secrets removed from the repo.

### Hosted deployment (Vercel)

- `vercel.json` wires the Flask app for Vercel.
- Hosted mode disables SQLite; history lives in the browser's localStorage.
- PDF export falls back to client-side TXT when the server PDF is unavailable.
- Local Windows operation (`START_TRANSLATOR.bat`) is unchanged.

### Testing

- New test coverage: layout correction (short words, sentences, mixed text,
  URLs/emails, Hebrew, undo), keyboard shortcut behavior, smart intent,
  English-only UI scan, security assertions, hosted-mode behavior, and
  regression tests. Run everything with `python tests/run_all.py`.

## Version 1.5.1 — compact panel, AI diagnostics, and voice fix

- Compact information ribbon replaced the oversized hero block.
- Separate "Test API key" and "Test model" diagnostics in the model panel.
- Continuous dictation auto-restarts after short browser sessions; duplicate
  fragments are deduplicated; transient errors no longer stop dictation.
- Two JavaScript errors in the speech module fixed; long texts are read in
  short chunks for stability.

## Version 1.5 — Mistral production and new interface

- Mistral became the default provider; `mistral-large-latest` the default model.
- Multi-provider catalog with server-side key resolution.
- Keys no longer serialized into HTML/JavaScript; only a "configured" flag is
  sent to the browser.

## Version 1.3 — stronger editing and quality control

- Rewritten system prompts; business mode performs a real register
  transformation.
- Local quality gate detects weak results and runs one strengthened retry pass.

## Version 1.4 — free speech input and output

- Browser dictation (Russian, English, Hebrew) with append/replace modes.
- Speech synthesis with voice selection, rate, pause, resume, and stop.
