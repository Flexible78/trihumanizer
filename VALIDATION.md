# Build validation — 1.6.1

The following checks are performed without requests to paid AI models (a local
mock OpenAI-compatible server is used for provider tests):

- Python files pass `py_compile`.
- `static/app.js`, `static/speech.js`, `static/layout-corrector.js`, and
  `static/sw.js` pass `node --check`.
- All element IDs used by JavaScript exist in the HTML; there are no duplicate IDs.
- Flask health/config, history, PDF, model-list, and chat-completion endpoints
  pass the built-in self-test.
- API key/endpoint and selected-model diagnostics run against the local mock server.
- Keyboard layout correction tests cover:
  - `ghbdtn` → `привет`
  - `ghbdtn rfr ndjb ltkf` → `привет как твои дела`
  - `руддщ` → `hello`
  - mixed Russian/English preservation
  - Hebrew layout conversion
  - URL, email, and code preservation
  - low-confidence suggestion instead of destructive replacement
  - undo behavior
- Smart intent tests cover literal translation, rewrite requests, email
  creation, research requests, missing store details, and the no-fabrication rule.
- Security tests confirm no keys in HTML, JavaScript, `/api/config`, or
  Git-tracked files, and that the password gate works when enabled and stays
  optional when not.
- English-portfolio tests confirm no unintended Russian UI labels and intact
  language functionality.
- Deployment tests confirm the Flask app imports, the app starts, the Vercel
  entrypoint imports, static assets load, API routes work, and hosted mode
  never writes to SQLite.

Real keys remain only in local environment variables. The "Test model" button
in the running app performs a short real request to the selected provider.
