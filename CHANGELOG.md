# Changelog

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
