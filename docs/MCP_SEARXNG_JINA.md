# MCP setup: SearXNG + Jina Reader in VS Code

Saved on 2026-08-02. This note is only documentation: the TriHumanizer app,
its templates, styles and deployment are NOT affected by anything described here.

## Idea

Two-step research chain that keeps the context window small:

1. `searxng` searches the web and returns titles, URLs and short snippets only (cheap).
2. `jina` (Jina Reader) is called for the 1-3 selected URLs and converts the page into
   clean Markdown without menus, ads, cookie banners or scripts (token efficient).

## Files touched

- Created: `C:\Users\Alexander\AppData\Roaming\Code\User\mcp.json`
  (VS Code global MCP config, applies to every workspace).
  No previous file existed, nothing was overwritten. Rollback = delete the file.
- Nothing inside this repository was modified for the MCP setup.

## Current mcp.json content

```json
{
  "inputs": [
    { "id": "jina_api_key", "type": "promptString", "description": "Jina AI API key from jina.ai (free tier is enough)", "password": true }
  ],
  "servers": {
    "searxng": {
      "type": "stdio",
      "command": "npx.cmd",
      "args": ["-y", "mcp-searxng"],
      "env": { "SEARXNG_URL": "https://searx.be" }
    },
    "jina": {
      "type": "stdio",
      "command": "npx.cmd",
      "args": ["-y", "jina-mcp-tools"],
      "env": { "JINA_API_KEY": "${input:jina_api_key}" }
    },
    "fetch": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

Verified package versions at setup time: `mcp-searxng` 1.14.0, `jina-mcp-tools` 1.2.5.
On Windows use `npx.cmd` (plain `npx` may not resolve from the VS Code process).
`fetch` (`uvx mcp-server-fetch`) is a key-free fallback reader.

## Enable in VS Code

1. Restart VS Code, or run `Ctrl+Shift+P` -> `MCP: List Servers`.
2. Select a server -> `Start`. On the first start of `jina` VS Code asks for the API key
   and stores it in its own Secret Storage (never written to disk in plain text).
3. Open Copilot Chat -> `Agent` mode -> `Tools` button -> enable the searxng / jina / fetch tools.

Useful tools: `searxng_web_search`, `web_url_read` (searxng), `read_url`, `search_web` (jina).

## Where to get the Jina API key

1. Open https://jina.ai and click `API Key` in the top right,
   or go directly to https://jina.ai/api-dashboard/key-manager
2. Sign in with Google / GitHub / email (no separate registration flow).
3. The key is shown immediately in the form `jina_xxxxxxxxxxxxxxxxxxxx`, together with
   the remaining free token balance (new accounts get roughly 10M free tokens shared
   across Reader, Search, Embeddings and Reranker). A new key can be generated there.
4. Paste it into the VS Code prompt for `Jina AI API key`.

Quick check from a terminal:

```bash
curl "https://r.jina.ai/https://example.com" -H "Authorization: Bearer jina_YOUR_KEY"
```

Clean Markdown in the response means the key works.

## Optional: local SearXNG instead of the public instance

Public instances rate-limit and can answer 429. A local one is unlimited and private.
Docker Desktop must be running.

```bash
docker run -d --name searxng -p 8080:8080 \
  -v D:/tmp/searxng:/etc/searxng \
  -e SEARXNG_SETTINGS_PATH=/etc/searxng \
  searxng/searxng
```

Then in `D:/tmp/searxng/settings.yml` make sure the JSON output format is enabled:

```yaml
search:
  formats:
    - html
    - json
```

Restart the container and change `SEARXNG_URL` in `mcp.json` to `http://localhost:8080`.

## Troubleshooting

- Wrong key entered: `Ctrl+Shift+P` -> `MCP: Clear Saved Inputs`, then start `jina` again.
- HTTP 429 from search: the public SearXNG instance is throttling; switch instance or go local.
- Server does not start: check `Output` panel -> `MCP` channel; confirm `node`, `npx.cmd` and `uvx` are on PATH.
- Reader works without a key at a low rate limit; `fetch` needs no key at all.

## Notes

- No API keys are stored in this repository or in `mcp.json`; the Jina key lives in VS Code Secret Storage.
- Keep this file in sync if the MCP config changes.
