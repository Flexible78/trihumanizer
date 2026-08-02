# HTTP API

All endpoints accept and return JSON, are same-origin only, and answer with
{"ok": false, "error": "..."} plus a 4xx or 502 status on failure. When
APP_PASSWORD is set, every path below except /, /api/health, /api/config and
/api/auth/* requires an authenticated session cookie.

## GET /api/health

```json
{ "ok": true, "version": "1.6.2", "hosted": false, "auth_required": false }
```

## GET /api/config

Public, secret-free description of the server: version, default provider and
model, whether research is enabled, the provider catalogue, and the saved
selection. Per provider it reports configuredKey (a key is available from any
source), savedKey (a key is stored on this machine) and envKey (a key comes from
the environment). No key value is ever included.

## GET /api/settings

```json
{
  "ok": true,
  "settings": {
    "provider": "mistral",
    "model": "mistral-large-latest",
    "customUrl": "",
    "persisted": true,
    "providers": { "mistral": { "model": "mistral-large-latest", "customUrl": "", "hasKey": true } }
  }
}
```

## POST /api/settings

Stores the selection for the next application start. Empty fields keep their
previous value, so the interface can keep sending an empty key field while a key
is already on file.

```json
{ "provider": "mistral", "model": "mistral-large-latest", "custom_url": "", "api_key": "...", "clear_key": false }
```

The response repeats the secret-free settings view and adds "stored": true when
the file was written. Hosted deployments answer 400 because the filesystem is
read-only.

## DELETE /api/settings

Forgets one provider, including its key: {"provider": "mistral"}.

## POST /api/models

Lists models from the provider endpoint. Body: provider, optional custom_url,
optional api_key override. Returns models and the endpoint that answered.

## POST /api/test/key

Diagnostic for endpoint and credential. Returns endpoint_reachable,
key_accepted, models_count, sample_models, elapsed_ms and error_category.

## POST /api/test/model

Sends a minimal completion to the selected model. Returns reply, endpoint and
elapsed_ms, or an error with a category such as auth or model_unavailable.

## POST /api/intent

Classifies a request. Returns the heuristic contract, upgraded by the model when
a model is selected and the heuristic is confident enough to be checked.

## POST /api/process

The main endpoint. Body fields: text (max 20000 characters), source_language
(auto, ru, en, he), target_language (ru, en, he), mode (business, friendly,
short_reply), action (auto, translate, write, improve, research), provider,
model, api_key, custom_url, context, custom_instruction, writer_gender,
recipient_gender, humanize_original, humanize_translation, include_literal,
preserve_length.

Returns history_id, result, provider, model, endpoint, intent, action and
quality_retry. The result object carries detected_language, humanized_original,
literal_translation, humanized_translation, subject, greeting, body, closing,
answer, missing_information, verified_findings, sources and notes, depending on
the action.

## POST /api/export/pdf

Returns application/pdf built from the current result, with correct
bidirectional shaping for Hebrew.

## GET, DELETE /api/history and DELETE /api/history/<id>

Local SQLite history. In hosted mode these behave as an empty store.

## POST /api/control/restart and /api/control/exit

Restart asks the process to exit with code 75, which the launcher interprets as
restart. Exit stops the application with code 0. Both are protected by the
password gate when it is enabled.

## Side effect worth knowing

A successful /api/models, /api/test/key, /api/test/model or /api/process call
remembers the provider, model, endpoint and key that worked. Only credentials
that a provider has just accepted are ever written to disk.