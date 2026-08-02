# Architecture

## Runtime shape

One Flask process serves the interface and the JSON API on 127.0.0.1:8868.
launcher.py supervises it: it creates the virtual environment, installs
requirements, writes data/app.pid and data/app.port, and restarts the process
when it exits with code 75 (the Restart button) while treating code 0 as a
deliberate stop.

```
browser (static/app.js)
   |  JSON over fetch, same-origin only
   v
Flask app.py  --  validation, auth gate, security headers
   |                |                  |
   |                |                  +--> storage.py    (SQLite history)
   |                +---------------------> settings_store.py (provider/model/key)
   +--------------------------------------> llm_client.py  --> provider HTTP API
```

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| app.py | Routing, payload validation, allowlists, auth gate, CSP nonce, error mapping |
| provider_config.py | Provider catalogue, model-name allowlist, key resolution, public config |
| settings_store.py | Reads and atomically writes data/settings.json, exposes a secret-free view |
| llm_client.py | Endpoint candidates, headers, retries, JSON extraction, secret redaction |
| prompts.py | Prompt construction per mode and per tone |
| intent.py | Heuristic intent plus optional model-based classification |
| quality.py | Grades a result and decides whether one retry is worth it |
| research.py | Optional live-research path, disabled by default |
| pdf_export.py | ReportLab output with bidirectional shaping for Hebrew |
| storage.py | SQLite history store and a null store for read-only hosts |

## Request flow for /api/process

1. Validate size, language, tone, action, provider and model against allowlists.
2. Resolve the effective API key (see below).
3. For action auto, run heuristic intent detection and pick a concrete action.
4. Build prompts, call the provider, parse the JSON payload out of the reply.
5. Grade the result. If the grade fails, retry once with a revision prompt and
   keep whichever result scores better.
6. Remember the working provider, model, endpoint and key.
7. Store the exchange in SQLite history and return the result.

## Key resolution

resolve_api_key(provider, override) returns the first non-empty value of:

1. override sent with the request (a key typed in the interface right now),
2. settings_store.stored_api_key(provider) from data/settings.json,
3. environment_api_key(provider), including the legacy TRIHUMANIZER_ names,
4. the built-in default key of the provider, used by local gateways only.

This single function is the only place that knows where credentials come from,
which is why adding server-side persistence did not touch any request handler.

## Persistence of settings

data/settings.json holds the last selected provider, model and endpoint plus one
entry per provider with its key. Writes go to a temporary file first and are then
moved into place with os.replace, so a crash cannot leave a half-written file.
The file is never sent to the browser: public_state() strips every key and
replaces it with a hasKey boolean.

## Hosted mode

When VERCEL or TRIHUMANIZER_HOSTED is set, the filesystem is read-only:
settings persistence is disabled, history uses the null store, and credentials
come from environment variables only. The same code path runs locally and hosted;
only these two behaviours change.

## Failure handling

- Endpoint discovery tries the documented path first, then known alternatives,
  and retries only on 404 and 405 (plus 400 for the model probe).
- Provider errors are mapped to categories (auth, connection, timeout,
  rate_limit, endpoint_not_found, model_unavailable) so the interface can give
  advice instead of a raw status code.
- Every message is passed through redact_secrets before it reaches a response.
- Settings persistence failures are swallowed on purpose: a convenience feature
  must never break an otherwise successful request.