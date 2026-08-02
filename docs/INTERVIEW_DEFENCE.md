# Defending this project as an infrastructure engineer

A translator is the visible part. What is worth defending in an interview is
everything around it: process supervision, credential handling, safe rollout of a
change, tests as a gate, and honest failure modes. Use the sections below as
ready answers, each backed by a file in this repository.

## 30-second summary

A self-hosted Flask service that talks to nine interchangeable OpenAI-compatible
backends. It ships its own supervisor, its own credential store, a CSP-hardened
front end, an eight-module test suite wired into CI, and a secret scanner that
fails the build if a key-shaped string ever reaches a tracked file. Roughly 5000
lines, no framework beyond Flask, four runtime dependencies.

## Why the design is defensible

**Single source of truth for credentials.** resolve_api_key in
provider_config.py is the only function that decides where a key comes from:
request, stored file, environment, or a local gateway default. When server-side
persistence was added, not a single request handler had to change. That is the
interface-narrowing argument an interviewer wants to hear.

**Secrets never cross the trust boundary outward.** The browser can send a key,
but it can never read one back. public_state() and public_config() return only a
hasKey boolean. Two tests assert that no key-shaped marker appears in the HTML,
in the JavaScript bundle or in /api/config.

**Atomic writes, least privilege.** data/settings.json is written to a temporary
file and moved with os.replace, so an interrupted write cannot corrupt it; the
file is chmod 0600 where the platform supports it and is git-ignored. Storage
failures are swallowed deliberately: persistence is a convenience and must never
break a request that already succeeded.

**Only known-good credentials are persisted.** The save path runs after a
provider accepted a request, so the stored state is by construction a working
configuration, not a guess.

**Environments are explicit, not accidental.** VERCEL or TRIHUMANIZER_HOSTED
switches the process to read-only behaviour: no settings file, a null history
store, credentials from the environment only. One code path, two declared
environments, no drift.

**Process lifecycle is owned, not hoped for.** launcher.py builds the virtual
environment, records pid and port under data/, and treats exit code 75 as
restart and 0 as stop. The Restart button in the interface is that contract,
exposed to the user; the client then polls /api/health until the service is back.

**Defence in depth in the delivery layer.** Per-request CSP nonce, no inline
handlers, nosniff, DENY framing, no-referrer, a narrow permissions policy, HSTS
when the request is secure, an optional password gate on every AI and control
endpoint, a 1 MB body cap and a 20000-character text cap.

**Failures are classified, not dumped.** Provider errors are mapped to auth,
connection, timeout, rate_limit, endpoint_not_found and model_unavailable, and
every message passes redact_secrets first. Users get advice; logs do not get
keys.

**Tests are the gate.** tests/run_all.py runs the endpoints against a mock HTTP
provider, intent detection, the layout corrector, deployment configuration, an
English-only interface check, the security tests and two Node modules. No paid
call is made, so the suite is free to run on every push.

## The incident story to tell

Interviewers respond to a concrete debugging narrative. This one is real and
documented in docs/TROUBLESHOOTING.md.

- **Symptom.** After every restart of the application, the first model test
  answered "Provider error 401: Unauthorized".
- **First hypothesis, rejected.** A bad key. Rejected because the same key worked
  immediately after being typed in.
- **Evidence gathering.** The 401 came from the provider, not from the app, so
  the request must have carried an empty credential. Reading the front end
  showed the API key field was intentionally never restored, and only model and
  endpoint were kept in browser storage. Reading the server showed keys were
  resolved from environment variables only, and no .env file existed.
- **Root cause.** The only copy of the key lived in a DOM input. Restarting the
  app reloaded the page, the field came back empty, and the server had nothing
  to fall back to.
- **Fix.** Move the credential to where it belongs: the server. A small module
  stores provider, model, endpoint and key atomically, resolve_api_key gained one
  new fallback step, every successful call remembers what worked, and the browser
  only ever learns whether a key exists.
- **Verification.** Save through the API, then read the value back in a fresh
  process to simulate a restart: the key resolved correctly, configuredKey and
  savedKey both reported true, and the whole suite stayed green.
- **Follow-up.** The stored file was added to .gitignore, and the CI secret scan
  was made clean by splitting the intentional test fixture into two literals so
  no tracked file can look like it holds a real key.

The lesson to state out loud: a credential kept in exactly one volatile place is
not configuration, it is an outage waiting for a restart.

## Questions you should expect, and short answers

**Why not just use environment variables?** They are supported and take
precedence over nothing but the built-in defaults. They are the right answer for
shared and hosted installs, and the wrong answer for a desktop user who should
not have to edit .env and restart to change a model.

**Is storing a key on disk not a downgrade?** It replaces a key retyped into a
browser field several times a day. The file is user-scoped, 0600, git-ignored,
never served, and can be cleared with one API call. The alternative in practice
was a key pasted into chat logs and screenshots.

**How would you scale this?** It is deliberately single-user and local. The
scaling path is to keep the same interface: swap settings_store for a secret
manager, swap SQLite for Postgres, put the process behind a reverse proxy, and
keep resolve_api_key as the only credential entry point.

**What would you do next?** Structured request logging with correlation ids, a
provider health cache so the interface can grey out unreachable backends, key
rotation reminders, and a container image so the launcher logic becomes the
container restart policy.

**What is still weak?** No rate limiting per client, no audit trail for settings
changes, and the front end is one large script rather than modules. All three are
known, none is hidden.

## Evidence map

| Claim | Look at |
| --- | --- |
| Credential precedence in one function | provider_config.py, resolve_api_key |
| Atomic, private, secret-free storage | settings_store.py |
| Keys never leave the server | provider_config.public_config, settings_store.public_state |
| Hardened delivery | app.py, secure_headers and _render |
| Only known-good state is stored | app.py, _remember and its call sites |
| Environment separation | HOSTED checks in app.py, storage.py, settings_store.py |
| Process lifecycle | launcher.py, /api/control/restart, exit codes 75 and 0 |
| Error classification and redaction | app.py _error_category, llm_client.redact_secrets |
| Tests as a gate | tests/run_all.py, .github/workflows/ci.yml |