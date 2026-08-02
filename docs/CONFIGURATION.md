# Configuration

## Where credentials can live

| Source | Scope | Survives restart | Recommended for |
| --- | --- | --- | --- |
| Interface field | Current request | Yes, once saved | Trying a key quickly |
| data/settings.json | This machine and user | Yes | Single-user desktop install |
| Environment or .env | Whole process | Yes | Shared, headless or hosted installs |

Resolution order: request field, then data/settings.json, then environment, then
the built-in default key of local gateways.

## Environment variables

| Variable | Purpose |
| --- | --- |
| MISTRAL_API_KEY | Mistral, the default provider |
| GROQ_API_KEY | Groq |
| GOOGLE_STUDIO_API_KEY | Google AI Studio, OpenAI-compatible endpoint |
| OPENROUTER_API_KEY | OpenRouter |
| OMNIROUTE_API_KEY | Local OmniRoute gateway |
| FREEWAY_API_KEY | Local Freeway gateway |
| OPENAI_API_KEY | OpenAI |
| TRIHUMANIZER_PORT | Listening port, default 8868 |
| APP_PASSWORD | Enables the password gate when set |
| FLASK_SECRET_KEY | Stable session signing key, random per start if unset |
| RESEARCH_ENABLED | Set to 1 to allow the live-research path |
| RESEARCH_PROVIDER, RESEARCH_MODEL, RESEARCH_API_KEY, RESEARCH_BASE_URL | Research backend |
| TRIHUMANIZER_HOSTED | Forces hosted, read-only behaviour |
| TRIHUMANIZER_HTTPS | Marks the deployment as HTTPS for secure cookies |

Legacy names TRIHUMANIZER_<PROVIDER>_API_KEY and TRIHUMANIZER_API_KEY are still
accepted as a fallback.

## Saved settings file

Path: data/settings.json, git-ignored, written atomically, chmod 0600 where the
platform supports it.

```json
{
  "provider": "mistral",
  "model": "mistral-large-latest",
  "custom_url": "",
  "providers": {
    "mistral": {
      "api_key": "<stored key>",
      "model": "mistral-large-latest",
      "custom_url": ""
    }
  }
}
```

What the browser receives instead:

```json
{
  "provider": "mistral",
  "model": "mistral-large-latest",
  "customUrl": "",
  "persisted": true,
  "providers": {
    "mistral": { "model": "mistral-large-latest", "customUrl": "", "hasKey": true }
  }
}
```

## Saving, replacing and clearing a key

- Saving: type the key and press Save in the compact AI model block, or simply
  run a successful Test API key, Test model or normal request. The input is
  cleared afterwards and the badge changes to saved key.
- Replacing: type a new key and save again.
- Clearing one provider: send DELETE /api/settings with {"provider": "mistral"}.
- Clearing everything: delete data/settings.json while the app is stopped.

## Providers and default models

| Provider | Base URL | Default model | Key required |
| --- | --- | --- | --- |
| mistral | https://api.mistral.ai/v1 | mistral-large-latest | yes |
| groq | https://api.groq.com/openai/v1 | openai/gpt-oss-120b | yes |
| google_studio | https://generativelanguage.googleapis.com/v1beta/openai | models/gemma-4-31b-it | yes |
| openrouter | https://openrouter.ai/api/v1 | openrouter/free | yes |
| omniroute | http://localhost:20128 | kilocode/openrouter/free | gateway dependent |
| freeway | http://127.0.0.1:8787/v1 | nemotron-3-ultra-550b-a55b | gateway dependent |
| openai | https://api.openai.com/v1 | gpt-4.1-mini | yes |
| ollama | http://127.0.0.1:11434/v1 | qwen3:8b | no |
| custom | your endpoint | your model | optional |

Model names are validated against a pattern and a 200-character limit before any
request is made.

## Password gate

Set APP_PASSWORD to require a login before any AI or control endpoint responds.
Set FLASK_SECRET_KEY as well, otherwise sessions are invalidated on every
restart because the signing key is regenerated.