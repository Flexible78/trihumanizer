# Secret Scan Report — TriHumanizer v1.6.0

Date: 2026-08-01
Scope: full working tree (excluding `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`)

## Patterns scanned

| Pattern | Description |
| --- | --- |
| `sk-[A-Za-z0-9_-]{16,}` | OpenAI-style secret keys |
| `(?:AIza\|ya29)\.[A-Za-z0-9_-]{20,}` | Google API keys |
| `ghp_[A-Za-z0-9]{30,}` | GitHub personal access tokens |
| `xox[baprs]-[A-Za-z0-9-]{10,}` | Slack tokens |
| `AKIA[0-9A-Z]{16}` | AWS access keys |
| `-----BEGIN (RSA\|EC\|OPENSSH\|PGP) PRIVATE KEY-----` | Private keys |
| `APP_PASSWORD\s*[=:]\s*\S{4,}` | Password assignments |
| `MISTRAL_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY = <value>` | Provider key assignments |
| `sk_[a-zA-Z0-9]{24,}` | Raw sk- tokens |

## Findings

### 1. `data/ai_endpoints.json` — REAL CREDENTIALS (critical)

The pre-existing local file contained live API keys:

- `groq`: `gsk_…` (real key)
- `omniroute`: `sk-…` (real key)

**Resolution:**
- The file is excluded from version control: `.gitignore` → `data/ai_endpoints.json`.
- The application no longer reads it — provider keys are resolved only from environment variables (`provider_config.py`, `resolve_api_key`).
- The file stays out of the repository and out of the release archive.

### 2. `app.py:59` — false positive

`APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()` — reads the password from the environment; no literal secret.

### 3. `tests/self_test.py:63-65` — test fixture

`sk-abcdefghijklmnopqrstuvwxyz123456` is a deliberately fake key used to verify the secret-redaction function. It is not a real credential.

## Conclusion

- **Real secrets found:** 2 (both inside `data/ai_endpoints.json`).
- **Real secrets exposed in code/docs:** 0.
- **Action taken:** the file is untracked, gitignored, and excluded from the archive; no real key appears in any committed file.
- Additional protection: `llm_client.redact_secrets` scrubs key-shaped strings from every error before it reaches the browser, and `/api/config` never serializes keys.
