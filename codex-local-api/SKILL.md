---
name: codex-local-api
description: Start, stop, inspect, and document a local OpenAI-compatible HTTP API bridge backed by the Codex CLI, plus the native Codex app-server WebSocket bridge. Use when a user wants to expose Codex as a local API endpoint, configure OpenAI-compatible tools such as AI Scientist v2 or game generators, manage local bridge environment variables, or install this Codex API bridge skill on another computer.
---

# Codex Local API

## Core Workflow

1. Verify prerequisites:
   - Codex CLI is installed, authenticated, and available as `codex`, or the user provides `CODEX_BIN`.
   - Python 3.10+ is available as `python`, or the user provides `-Python`.
   - The target project directory is the intended working directory for Codex file edits.
2. Start the OpenAI-compatible HTTP bridge from the target project:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\start-codex-openai-bridge.ps1" -Cwd (Get-Location)
   ```
3. Report the printed `base_url` and `api_key`. The default base URL is `http://127.0.0.1:8787/v1`.
4. For tools needing the official Codex app-server protocol, start the WebSocket bridge:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codex-local-api\scripts\start-codex-native-app-server.ps1" -Cwd (Get-Location)
   ```
5. Read `references/api.md` when the user asks about endpoint coverage, client configuration, shutdown, persistence, or limitations.

## Script Map

- `scripts/start-codex-openai-bridge.ps1`: start the HTTP bridge and persist `.env` style settings.
- `scripts/status-codex-openai-bridge.ps1`: show PID, health, logs, and saved key/base URL.
- `scripts/stop-codex-openai-bridge.ps1`: stop the HTTP bridge by PID file.
- `scripts/codex_openai_bridge.py`: the Python HTTP bridge implementation.
- `scripts/start-codex-native-app-server.ps1`: start `codex app-server` on `ws://127.0.0.1:8791`.
- `scripts/status-codex-native-app-server.ps1`: inspect native app-server status.
- `scripts/stop-codex-native-app-server.ps1`: stop native app-server.
- `scripts/generate-codex-app-server-schema.ps1`: export official app-server JSON schemas for integration work.

## Compatibility Notes

The HTTP bridge is OpenAI-compatible enough for many clients that call `/v1/models`, `/v1/chat/completions`, or `/v1/responses`. It also exposes native job endpoints under `/v1/codex/*` for asynchronous agent-style runs.

It is not a full OpenAI Platform clone. It does not provide embeddings, image/video/audio generation, fine-tuning, file/vector-store APIs, true OpenAI-hosted tool execution, or billing/project management APIs.
