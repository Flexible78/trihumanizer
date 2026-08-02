# Troubleshooting

## Model test: Provider error 401: Unauthorized after restarting the app

Fixed in 1.6.1. The cause was that the API key lived only in the browser input:
the interface deliberately never restored it, no environment variable was set,
and the server therefore sent an empty credential to the provider, which replied
401. Keys are now stored server-side in data/settings.json and reused on start.

If you still see it:

1. Open the compact AI model block. A saved key badge means a key is on file.
2. Type the key again and press Save. The field clears itself once stored.
3. Check that data/settings.json exists and contains an entry for the provider.
4. If the file cannot be created (read-only or hosted install), set the matching
   environment variable instead, for example MISTRAL_API_KEY.
5. Press Re-check all. A green result means the credential works end to end.

A 401 that appears immediately after entering a key means the key itself is
rejected: wrong provider, revoked key, or no billing on the account.

## The provider answers 404 or endpoint not found

The client already tries alternative paths for each provider. A remaining 404
usually means a custom base URL is missing its /v1 suffix, or the selected model
does not exist on that endpoint. Press Refresh models to see what the endpoint
really offers.

## Connection refused for a local gateway

Ollama, Freeway and OmniRoute must be running first. Verify the port, then
re-check. Ollama needs no key.

## The port is already in use

Another instance is probably still running. Run STOP_TRANSLATOR.bat, or set
TRIHUMANIZER_PORT to a free port. The active port is recorded in data/app.port.

## The login prompt appears on every restart

Set FLASK_SECRET_KEY. Without it a random signing key is generated at startup
and all sessions become invalid.

## Hebrew looks reversed in the PDF

Install the dependencies from requirements.txt, python-bidi included; shaping is
done at export time.

## Tests

```bash
python tests/run_all.py
```

There is no pytest dependency and unittest discovery does not apply, because the
tests directory is a plain script collection rather than a package. run_all.py is
the supported entry point and also runs the two Node test modules.

## CI fails with secrets found in git-tracked files

The scan greps tracked files for key-shaped strings. The intentional redaction
fixture is now assembled from two literals in tests/self_test.py so that no
tracked file contains anything that looks like a real key. Never commit a real
key: keep it in .env or in data/settings.json, both of which are git-ignored.