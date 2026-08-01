# Security

## API keys

- API keys are read **only** from server-side environment variables:
  `MISTRAL_API_KEY`, `GROQ_API_KEY`, `GOOGLE_STUDIO_API_KEY`,
  `OPENROUTER_API_KEY`, `OMNIROUTE_API_KEY`, `FREEWAY_API_KEY`,
  `OPENAI_API_KEY`.
- The browser never receives a key. `/api/config` and the HTML template only
  expose a boolean "configured" flag.
- A manual key typed in the UI is sent to the local server as an override and
  is never stored in `localStorage`.
- `.env` is git-ignored; `.env.example` contains variable names only.
- `data/ai_endpoints.json` (legacy imported keys) is git-ignored and excluded
  from any repository and archive.

## Network

- The local server binds to `127.0.0.1` only.
- CORS stays same-origin.
- Secure headers are applied on every response: `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`,
  `Permissions-Policy`, and HSTS when served over HTTPS.
- A Content-Security-Policy is emitted with a per-request nonce for inline
  scripts; API responses are never cached by the service worker.

## Validation and limits

- Provider ids are validated against an allowlist.
- Model names are validated against a strict character allowlist (max 200 chars).
- Request bodies are limited to 1 MB; text is limited to 20 000 characters.
- Provider error messages are redacted (keys/tokens replaced) before being
  returned to the browser.

## Optional password protection

When `APP_PASSWORD` is set:

- AI endpoints (`/api/process`, `/api/models`, `/api/test/*`, `/api/export/*`,
  `/api/history*`, `/api/intent`, `/api/research`) return `401` until login.
- The public portfolio shell, `/api/health`, and `/api/config` remain visible.
- Login uses a signed session cookie (HttpOnly, SameSite) secured with
  `FLASK_SECRET_KEY`; the plain password is never stored client-side.
- Generate a secret key with:
  `python -c "import secrets; print(secrets.token_hex(32))"`

## Logging

- Full user text and API keys are never written to logs. Only technical errors
  (with redacted secrets) and launcher lifecycle events are logged.

## If a key leaks

1. Revoke the key in the provider dashboard.
2. Rotate it in your `.env` / Vercel environment variables.
3. Never commit `.env` or archives containing keys.
