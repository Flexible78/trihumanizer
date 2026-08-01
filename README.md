# TriHumanizer — AI Translator & Writing Assistant

**Version 1.6.0**

Translate, rewrite, dictate, and create polished multilingual text between
**Russian**, **English**, and **Hebrew** — powered by Mistral (default) and
other OpenAI-compatible providers.

![TriHumanizer](static/icon-512.png)

## Features

- **Translate** — humanized, natural translations plus an optional literal pass.
- **Improve** — rewrite any text into Business, Friendly, or Short-reply style.
- **Write** — compose emails, messages, letters, and posts from plain instructions.
- **Research** — optional live research adapter for current factual questions.
- **Auto mode** — detects what you need from natural language.
- **Wrong keyboard layout correction** — QWERTY ⇄ JCUKEN ⇄ Hebrew, with
  automatic application, suggestion bar, and undo.
- **Continuous speech recognition** (dictation) and **speech synthesis** in
  Russian, English, and Hebrew, using the browser's Web Speech API.
- **History** — local (SQLite) on your machine, per-device (localStorage) when hosted.
- **Export** — TXT and PDF with full RU / EN / HE support.
- **Multi-provider** — Mistral, Groq, Google AI Studio, OpenRouter, OmniRoute,
  Freeway, OpenAI, Ollama, and any OpenAI-compatible custom endpoint.
- **Light and dark themes**, responsive mobile layout, installable PWA shell.
- **Keyboard shortcuts** — `Ctrl+Enter` (Windows/Linux) or `Cmd+Enter` (macOS)
  runs the current action; `Enter` / `Shift+Enter` keep working for multiline input.

## Architecture

```
templates/index.html   English-only UI shell (mode selector, PWA, auth gate)
static/app.js          Client logic: modes, shortcuts, layout correction, history
static/layout-corrector.js  Keyboard layout detection and correction (EN/RU/HE)
static/speech.js       Continuous dictation and speech synthesis
static/styles.css      Responsive production styling
app.py                 Flask application (auth, headers, API routes)
provider_config.py     Provider catalog, environment-only keys
llm_client.py          OpenAI-compatible chat/models client with secret redaction
intent.py              Smart natural-language request classification
prompts.py             Translator, writing assistant, intent, improve prompts
research.py            Provider-independent live research adapter
quality.py             Local quality gate with one retry pass
storage.py             SQLite history (local) / null store (hosted)
pdf_export.py          ReportLab PDF with RTL Hebrew support
```

Server-side API keys are read **only** from environment variables. The browser
never receives a key — only a boolean "configured" flag.

## Quick start (Windows)

1. Unpack the archive into a new folder, e.g. `C:\Apps\TriHumanizer_v1.6.0`.
2. (Optional) Create a `.env` file from `.env.example` and add your API keys.
3. Run **`START_TRANSLATOR.bat`**.
4. The browser opens automatically. The first run creates `.venv` and installs
   `requirements.txt` automatically.
5. Run **`SELF_TEST.bat`** any time to verify the installation.

## Local development (any OS)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  |  source .venv/bin/activate (macOS/Linux)
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys
python app.py                 # http://127.0.0.1:8868
```

## Environment variables

| Variable | Purpose |
|---|---|
| `MISTRAL_API_KEY` | Default provider key (Mistral) |
| `GROQ_API_KEY` | Groq provider key |
| `GOOGLE_STUDIO_API_KEY` | Google AI Studio key |
| `OPENROUTER_API_KEY` | OpenRouter key |
| `OMNIROUTE_API_KEY` | Local OmniRoute gateway key |
| `FREEWAY_API_KEY` | Local Freeway gateway key |
| `OPENAI_API_KEY` | OpenAI key |
| `TRIHUMANIZER_PORT` | Local port (default `8868`) |
| `APP_PASSWORD` | Optional: password to protect AI features |
| `FLASK_SECRET_KEY` | Signs the login session cookie |
| `RESEARCH_ENABLED` | `1` to enable the live research adapter |
| `RESEARCH_PROVIDER` | Provider id used for research |
| `RESEARCH_MODEL` | Model used for research |
| `RESEARCH_API_KEY` | Key for the research provider |
| `RESEARCH_BASE_URL` | Optional base URL for research |
| `TRIHUMANIZER_HOSTED` | `1` to force hosted mode (no SQLite) |

## Deploying to Vercel

1. Push this repository to GitHub.
2. Import the repository in Vercel (framework: **Other**, build command: none,
   output: `app.py` — the included `vercel.json` wires Flask correctly).
3. Add the environment variables from the table above (only the ones you use).
4. Deploy. Hosted mode is detected automatically:
   - history is kept in the browser's `localStorage`;
   - PDF export falls back to a client-side TXT export if the server cannot
     generate a PDF;
   - nothing is written to the server filesystem.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` / `Cmd+Enter` | Run the current action |
| `Ctrl+V` | Paste (also via the Paste button) |
| `Ctrl+C` | Copy (also via Copy buttons) |

`Enter` and `Shift+Enter` continue to work normally in the text area. The
shortcut is ignored during IME composition and while a request is running.

## Privacy & security

- API keys live only in server-side environment variables; they are never
  serialized into HTML, JavaScript, or `/api/config`.
- Provider/model values are validated against an allowlist; request size is
  limited; secure HTTP headers are applied.
- Provider errors are redacted before being returned to the browser.
- If `APP_PASSWORD` is set, AI endpoints require a password login using a
  signed, HttpOnly, SameSite session cookie. The public shell stays visible.
- On hosted deployments no server-side database is used; your text never
  touches a persistent server disk.
- See [SECURITY.md](SECURITY.md) for details.

## Tests

Run the full suite locally:

```bash
python tests/run_all.py
```

The suite covers keyboard layout correction, smart intent, the shortcut
handler, English-only UI checks, security assertions, hosted-mode behavior,
and regression tests for speech, providers, PDF, and history. See
[VALIDATION.md](VALIDATION.md) for the build validation report.

### Live deployment smoke test

`tools/live_smoke_test.py` verifies a deployed instance end to end: config
flags, the optional `APP_PASSWORD` login, the provider key test, a real model
generation, and a full translation through `/api/process`.

```bash
# Without a password gate:
python tools/live_smoke_test.py https://trihumanizer.vercel.app

# With the password gate enabled:
python tools/live_smoke_test.py https://trihumanizer.vercel.app mistral mistral-large-latest --password YOUR_PASSWORD
# or set TRIHUMANIZER_TEST_PASSWORD instead of --password

# Any configured provider:
python tools/live_smoke_test.py https://trihumanizer.vercel.app groq openai/gpt-oss-120b --password YOUR_PASSWORD
```

The script never prints secrets — errors are redacted server-side and only
boolean `configuredKey` flags plus redacted responses are shown.

## Screenshots

Screenshots of the deployed interface are generated manually after deployment:

1. Open the deployed site (or `http://127.0.0.1:8868` locally).
2. Capture the desktop layout at 1440 px width and the mobile layout at 390 px width.
3. Save them as `docs/screenshots/desktop.png` and `docs/screenshots/mobile.png` and
   reference them here.

## License

[MIT](LICENSE)
