# TriHumanizer Translator

Local-first AI workspace for translating, rewriting, dictating and composing text
in Russian, English and Hebrew. It runs as a small Flask application on your own
machine, talks to any OpenAI-compatible provider, and keeps every credential on
the server side.

![CI](https://github.com/Flexible78/trihumanizer/actions/workflows/ci.yml/badge.svg)

Live demo: https://trihumanizer.vercel.app — the hosted instance is behind a
password gate, because every AI endpoint there costs real provider credits. Run
it locally with your own key to see the full workspace.

## Why it exists

Machine translation output usually reads like machine translation. TriHumanizer
splits the job into stages: it detects intent, translates, rewrites the result so
it sounds like a human wrote it, then grades its own output and retries once when
the result is too close to the noisy input or keeps profanity in a business tone.

## Features

- Five request modes: auto, translate, write, improve, research.
- Russian, English and Hebrew, including right-to-left rendering and PDF export
  with proper bidirectional shaping.
- RU / EN / HE switcher on the result: all three languages are filled in one
  model call and switch instantly afterwards.
- Hebrew reading aids: Latin and Cyrillic transcription, plus a nikud view with
  full vowel points.
- Show changes view with a word-level diff between your text and the rewritten
  version.
- Protected terms that are never translated, and an optional reply-context field
  so answers address the incoming message.
- Scenario presets for HR, support, landlord, clinic, bank and authorities.
- Side-by-side comparison of two models on the same text.
- Usage meter with token and cost estimates, an optional daily request limit, and
  a short-lived server cache for repeated requests.
- History search plus JSON and CSV export.
- Hotkeys: Ctrl+Enter to run, Ctrl+1/2/3 for the target language,
  Ctrl+Shift+S smart swap, Ctrl+Shift+C copy result.
- Any OpenAI-compatible backend: Mistral, Groq, Google AI Studio, OpenRouter,
  OmniRoute, a local Freeway gateway, OpenAI, Ollama, or a custom endpoint.
- Compact AI model block: current engine, one-click Save, and Re-check all.
- Autosave of provider, model, endpoint and API key on the server, so a restart
  of the application never asks for the key again.
- Keyboard-layout corrector for text typed in the wrong layout.
- Browser dictation and text-to-speech.
- Local history in SQLite, TXT and PDF export, optional password gate.
- Progressive web app assets and an offline-tolerant service worker.

## Quick start (Windows)

```bat
START_TRANSLATOR.bat
```

The launcher creates the virtual environment, installs dependencies, starts the
server on http://127.0.0.1:8868 and opens the browser. STOP_TRANSLATOR.bat stops
it, SELF_TEST.bat runs the test suite.

## Quick start (any platform)

```bash
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8868, pick a provider, paste an API key, press Save. The
key is stored server-side in data/settings.json and reused after every restart.

## Configuration

Credentials can come from three places, in this order of precedence:

1. the key typed in the interface for the current request,
2. the key saved on the server in data/settings.json (written by Save or by any
   successful request),
3. environment variables or a .env file, for example MISTRAL_API_KEY.

Copy .env.example to .env for a headless or shared install. See
[docs/CONFIGURATION.md](docs/CONFIGURATION.md) for every variable and for the
exact shape of the stored settings file.

## Documentation

| Document | Content |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, request flow, quality gate, key resolution |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables, saved settings, providers |
| [docs/API.md](docs/API.md) | HTTP endpoints with request and response shapes |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 401 after restart, endpoint errors, ports, tests |
| [docs/INTERVIEW_DEFENCE.md](docs/INTERVIEW_DEFENCE.md) | The project as infrastructure-engineering evidence |
| [SECURITY.md](SECURITY.md) | Threat model and reporting |
| [VALIDATION.md](VALIDATION.md) | Manual validation checklist |
| [QUALITY_ALGORITHM.md](QUALITY_ALGORITHM.md) | Self-grading and retry rules |

## Project layout

```
app.py               Flask routes, validation, auth gate, security headers
provider_config.py   Provider catalogue, allowlists, key resolution
settings_store.py    Atomic server-side storage of provider, model and keys
llm_client.py        OpenAI-compatible client, endpoint probing, redaction
prompts.py           System and task prompts per mode
intent.py            Heuristic and model-based intent detection
quality.py           Result grading and retry decision
research.py          Optional live-research path
pdf_export.py        PDF with RU/EN/HE shaping
storage.py           SQLite history, null store for hosted mode
launcher.py          Supervisor: venv, port, restart exit codes
static/              app.js, speech.js, layout-corrector.js, styles, PWA assets
templates/           index.html rendered with a per-request CSP nonce
tests/               run_all.py plus Python and Node test modules
```

## Security posture

- API keys never reach the browser. The interface only receives provider and
  model names plus a boolean flag telling whether a key is on file.
- data/settings.json is written atomically, chmod 0600 where the platform
  supports it, and is listed in .gitignore.
- Content-Security-Policy with a per-request nonce, no inline event handlers,
  plus nosniff, DENY framing, no-referrer and a strict permissions policy.
- Provider error messages pass through a redaction filter before display.
- Optional password gate (APP_PASSWORD) protects every AI and control endpoint.
- CI greps all tracked files for key-shaped strings on every push.

## Tests

```bash
python tests/run_all.py
```

The suite covers the Flask endpoints with a mock provider, intent detection, the
layout corrector, deployment configuration, English-only interface strings,
secret leakage, and the two Node test modules. No paid provider call is made.

## Deployment

Local use is the default. vercel.json describes a hosted deployment: in hosted
mode the filesystem is read-only, history uses a null store and settings come
from environment variables only.

## License

See [LICENSE](LICENSE).
