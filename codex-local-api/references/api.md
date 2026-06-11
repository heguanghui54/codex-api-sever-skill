# Codex Local API Reference

## HTTP Bridge

Default endpoint:

```text
OPENAI_BASE_URL=http://127.0.0.1:8787/v1
OPENAI_API_KEY=<printed by start script>
OPENAI_MODEL=codex
```

Supported endpoints:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/codex/exec`
- `POST /v1/codex/jobs`
- `GET /v1/codex/jobs`
- `GET /v1/codex/jobs/{job_id}`
- `GET /v1/codex/jobs/{job_id}/events`

The OpenAI-compatible endpoints run `codex exec` underneath. Streaming is represented as a small SSE-compatible response, not token-by-token model streaming.

## Common Client Configuration

Python OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-codex-local-your-key",
)

response = client.chat.completions.create(
    model="codex",
    messages=[{"role": "user", "content": "Summarize this repo."}],
)
print(response.choices[0].message.content)
```

Environment variables used by most OpenAI-compatible projects:

```powershell
$env:OPENAI_BASE_URL = "http://127.0.0.1:8787/v1"
$env:OPENAI_API_KEY = "sk-codex-local-your-key"
$env:OPENAI_MODEL = "codex"
```

## AI Scientist v2 / OpenGame Style Tools

Use the bridge when the project can configure:

- custom OpenAI-compatible base URL
- API key
- model name
- standard chat completions or responses calls

For tools that need agentic repo editing, shell commands, long-running tasks, or event logs, prefer the native `/v1/codex/jobs` endpoints or the official `codex app-server` WebSocket bridge. Plain chat-completions clients may work for text generation but will not automatically get rich Codex desktop capabilities unless their workflow is adapted to the Codex job API or app-server protocol.

## Native Codex App Server

Default endpoint:

```text
CODEX_APP_SERVER_URL=ws://127.0.0.1:8791
```

Generate schemas:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\generate-codex-app-server-schema.ps1"
```

Use this when a client needs the official Codex protocol instead of OpenAI-compatible HTTP.

## State and Shutdown

By default, scripts store runtime state in:

```text
$HOME\.codex-local-api
```

Important files:

- `codex-openai-bridge.env`
- `codex_openai_bridge.pid`
- `codex_openai_bridge_info.json`
- `codex_native_app_server.pid`
- `codex_native_app_server_info.json`
- `jobs/`
- `logs/`

Stop services with the matching `stop-*.ps1` scripts. Delete the state directory only after stopping services.
