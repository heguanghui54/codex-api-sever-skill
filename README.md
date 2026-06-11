# Codex Local API Skill

This repository packages a Codex skill that starts a local OpenAI-compatible API bridge backed by the Codex CLI. It is useful for tools that accept `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `model` settings.

It also includes scripts for the native Codex `app-server` WebSocket bridge when a client needs Codex-specific agent protocol features instead of plain OpenAI-compatible HTTP.

## Install On Another Computer

Prerequisites:

- Codex CLI installed and signed in.
- Python 3.10+ available on `PATH` as `python`, or pass `-Python`.
- PowerShell.

Install:

```powershell
git clone https://github.com/heguanghui54/codex-api-sever-skill.git codex-local-api-skill
cd codex-local-api-skill
powershell -ExecutionPolicy Bypass -File .\install-skill.ps1
```

If `CODEX_HOME` is unset, the installer copies the skill to:

```text
$HOME\.codex\skills\codex-local-api
```

## Start The OpenAI-Compatible Bridge

Run this from the project directory where Codex should work:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\start-codex-openai-bridge.ps1" -Cwd (Get-Location)
```

Default output:

```text
Started: http://127.0.0.1:8787/v1
API key: sk-codex-local-...
Env file: $HOME\.codex-local-api\codex-openai-bridge.env
```

The key is local to your machine. Do not commit the generated env file.

## Use From OpenAI-Compatible Clients

```powershell
$env:OPENAI_BASE_URL = "http://127.0.0.1:8787/v1"
$env:OPENAI_API_KEY = "sk-codex-local-..."
$env:OPENAI_MODEL = "codex"
```

Python example:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-codex-local-...",
)

result = client.chat.completions.create(
    model="codex",
    messages=[{"role": "user", "content": "Inspect this project and summarize it."}],
)
print(result.choices[0].message.content)
```

## AI Scientist v2 / OpenGame Integration

Use this bridge when the project supports a custom OpenAI-compatible base URL, API key, and model name:

```text
OPENAI_BASE_URL=http://127.0.0.1:8787/v1
OPENAI_API_KEY=<generated local key>
OPENAI_MODEL=codex
```

If the tool only needs normal text/chat generation, `/v1/chat/completions` or `/v1/responses` may be enough.

If the tool expects autonomous coding, shell execution, file edits, long-running jobs, event streaming, or Codex desktop-style agent state, adapt it to either:

- the bridge's native `/v1/codex/jobs` endpoints, or
- the official Codex app-server WebSocket protocol.

## Native Codex App Server

Start:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\start-codex-native-app-server.ps1" -Cwd (Get-Location)
```

Default URL:

```text
ws://127.0.0.1:8791
```

Generate official schemas:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\generate-codex-app-server-schema.ps1"
```

## Manage Services

Status:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\status-codex-openai-bridge.ps1"
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\status-codex-native-app-server.ps1"
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\stop-codex-openai-bridge.ps1"
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\stop-codex-native-app-server.ps1"
```

State is stored in:

```text
$HOME\.codex-local-api
```

## API Coverage

Implemented:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/codex/exec`
- `POST /v1/codex/jobs`
- `GET /v1/codex/jobs`
- `GET /v1/codex/jobs/{job_id}`
- `GET /v1/codex/jobs/{job_id}/events`

Not implemented:

- embeddings
- audio/image/video generation
- files, vector stores, fine tuning
- OpenAI account/project/billing APIs
- hosted OpenAI tools
- true token-by-token model streaming

The usage is billed against the Codex account/session used by your local Codex CLI, not an OpenAI Platform API key, unless you configure Codex itself to use another backend.
