import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def now():
    return int(time.time())


def resolve_codex_path():
    configured = os.environ.get("CODEX_BIN")
    if configured:
        return configured
    found = shutil.which("codex")
    if found:
        return found
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidate = Path(local_appdata) / "OpenAI" / "Codex" / "bin" / "codex.exe"
        if candidate.exists():
            return str(candidate)
    return "codex"


DEFAULT_CODEX = resolve_codex_path()
STATE_ROOT = Path(os.environ.get("CODEX_BRIDGE_STATE_DIR", str(Path.home() / ".codex-local-api"))).resolve()
JOBS_DIR = STATE_ROOT / "jobs"


def add_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    add_headers(handler)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_sse(handler, events):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    add_headers(handler)
    handler.end_headers()
    for event in events:
        handler.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8"))
        handler.wfile.flush()
    handler.wfile.write(b"data: [DONE]\n\n")
    handler.wfile.flush()


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def messages_to_prompt(messages):
    parts = []
    for message in messages or []:
        role = message.get("role", "user") if isinstance(message, dict) else "user"
        content = message.get("content", "") if isinstance(message, dict) else str(message)
        if isinstance(content, list):
            text = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in ("text", "input_text", "output_text"):
                    text.append(str(item.get("text", "")))
                elif isinstance(item, dict) and item.get("type") in ("image_url", "input_image"):
                    text.append(f"[image omitted by bridge: {item}]")
                else:
                    text.append(str(item))
            content = "\n".join(text)
        parts.append(f"{role}:\n{content}")
    return "\n\n".join(parts).strip()


def responses_input_to_prompt(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return messages_to_prompt(value)
    return str(value or "").strip()


def approx_tokens(text):
    return 0 if not text else max(1, len(text) // 4)


def build_codex_cmd(payload, output_file, json_events=False):
    codex_path = payload.get("codex_path") or DEFAULT_CODEX
    model = payload.get("model")
    cwd = payload.get("cwd") or os.environ.get("CODEX_BRIDGE_CWD") or os.getcwd()
    sandbox = payload.get("sandbox", "workspace-write")
    approval = payload.get("approval", "never")
    profile = payload.get("profile")
    search = bool(payload.get("search", False))
    extra_args = payload.get("extra_args") or []

    cmd = [codex_path, "-a", approval]
    if model and model not in ("codex", "codex-local"):
        cmd.extend(["-m", model])
    if profile:
        cmd.extend(["-p", profile])
    if search:
        cmd.append("--search")
    cmd.extend(["exec", "--skip-git-repo-check", "--sandbox", sandbox])
    if json_events:
        cmd.append("--json")
    cmd.extend(["--output-last-message", str(output_file)])
    cmd.extend([str(x) for x in extra_args])
    cmd.append("-")
    return cmd, cwd


def run_codex_exec(payload):
    prompt = payload.get("prompt") or ""
    if not prompt and "messages" in payload:
        prompt = messages_to_prompt(payload.get("messages"))
    if not prompt and "input" in payload:
        prompt = responses_input_to_prompt(payload.get("input"))
    if not prompt:
        raise ValueError("prompt/messages/input is required")

    timeout = int(payload.get("timeout") or 600)
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    output_file.close()
    cmd, cwd = build_codex_cmd(payload, output_file.name, json_events=bool(payload.get("json_events")))
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=cwd,
            timeout=timeout,
        )
        final = ""
        if os.path.exists(output_file.name):
            final = Path(output_file.name).read_text(encoding="utf-8", errors="replace").strip()
        return {
            "id": "codexrun_" + uuid.uuid4().hex,
            "object": "codex.exec",
            "created": now(),
            "status": "completed" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "cwd": cwd,
            "command": [str(x) for x in cmd],
            "output_text": final or (proc.stdout or "").strip(),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    finally:
        try:
            os.unlink(output_file.name)
        except OSError:
            pass


class JobStore:
    def __init__(self, codex_path, default_cwd):
        self.codex_path = codex_path
        self.default_cwd = default_cwd
        self.processes = {}
        JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def start(self, payload):
        prompt = payload.get("prompt") or messages_to_prompt(payload.get("messages"))
        if not prompt:
            raise ValueError("prompt/messages is required")

        job_id = "codexjob_" + uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        output_path = job_dir / "last_message.txt"
        stdout_path = job_dir / "stdout.jsonl"
        stderr_path = job_dir / "stderr.log"
        meta_path = job_dir / "meta.json"

        payload = dict(payload)
        payload.setdefault("codex_path", self.codex_path)
        payload.setdefault("cwd", self.default_cwd)
        cmd, cwd = build_codex_cmd(payload, output_path, json_events=True)
        meta = {
            "id": job_id,
            "object": "codex.job",
            "created": now(),
            "status": "running",
            "cwd": cwd,
            "command": [str(x) for x in cmd],
            "output_path": str(output_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        stdout_f = open(stdout_path, "w", encoding="utf-8", errors="replace")
        stderr_f = open(stderr_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )
        proc.stdin.write(prompt)
        proc.stdin.close()
        self.processes[job_id] = (proc, stdout_f, stderr_f, meta_path)
        threading.Thread(target=self._waiter, args=(job_id,), daemon=True).start()
        return meta

    def _waiter(self, job_id):
        proc, stdout_f, stderr_f, meta_path = self.processes[job_id]
        code = proc.wait()
        stdout_f.close()
        stderr_f.close()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["status"] = "completed" if code == 0 else "failed"
        meta["exit_code"] = code
        meta["completed_at"] = now()
        output_path = Path(meta["output_path"])
        meta["output_text"] = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.exists() else ""
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, job_id):
        meta_path = JOBS_DIR / job_id / "meta.json"
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        proc_tuple = self.processes.get(job_id)
        if proc_tuple and proc_tuple[0].poll() is None:
            meta["status"] = "running"
        return meta

    def list(self):
        if not JOBS_DIR.exists():
            return []
        jobs = []
        for meta_path in sorted(JOBS_DIR.glob("*/meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                jobs.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return jobs

    def events(self, job_id, limit=200):
        stdout_path = JOBS_DIR / job_id / "stdout.jsonl"
        if not stdout_path.exists():
            return None
        lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except Exception:
                events.append({"raw": line})
        return events


class Handler(BaseHTTPRequestHandler):
    server_version = "codex-agent-bridge/0.4"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def authorized(self):
        if self.path == "/health":
            return True
        expected = self.server.api_key
        return True if not expected else self.headers.get("Authorization", "") == f"Bearer {expected}"

    def do_OPTIONS(self):
        self.send_response(204)
        add_headers(self)
        self.end_headers()

    def do_GET(self):
        if not self.authorized():
            return send_json(self, 401, {"error": {"message": "invalid API key", "type": "authentication_error"}})
        path = urlparse(self.path).path
        if path == "/health":
            return send_json(self, 200, {"ok": True, "backend": "codex exec", "bridge": self.server_version})
        if path == "/v1/models":
            return send_json(self, 200, {"object": "list", "data": self.models()})
        if path == "/v1/codex/jobs":
            return send_json(self, 200, {"object": "list", "data": self.server.jobs.list()})
        if path.startswith("/v1/codex/jobs/"):
            parts = path.strip("/").split("/")
            job_id = parts[3] if len(parts) >= 4 else ""
            if len(parts) >= 5 and parts[4] == "events":
                events = self.server.jobs.events(job_id)
                return send_json(self, 404 if events is None else 200, {"error": {"message": "job not found", "type": "not_found"}} if events is None else {"object": "list", "data": events})
            meta = self.server.jobs.get(job_id)
            return send_json(self, 404 if meta is None else 200, {"error": {"message": "job not found", "type": "not_found"}} if meta is None else meta)
        return send_json(self, 404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self):
        if not self.authorized():
            return send_json(self, 401, {"error": {"message": "invalid API key", "type": "authentication_error"}})
        path = urlparse(self.path).path
        try:
            if path == "/v1/codex/exec":
                payload = read_json(self)
                payload.setdefault("codex_path", self.server.codex_path)
                payload.setdefault("cwd", self.server.cwd)
                return send_json(self, 200, run_codex_exec(payload))
            if path == "/v1/codex/jobs":
                return send_json(self, 202, self.server.jobs.start(read_json(self)))
            if path == "/v1/chat/completions":
                return self.chat_completions(read_json(self))
            if path == "/v1/responses":
                return self.responses(read_json(self))
            return send_json(self, 404, {"error": {"message": "not found", "type": "invalid_request_error"}})
        except subprocess.TimeoutExpired:
            return send_json(self, 504, {"error": {"message": "codex exec timed out; increase request timeout", "type": "timeout_error"}})
        except Exception as exc:
            return send_json(self, 500, {"error": {"message": str(exc), "type": "server_error"}})

    def models(self):
        return [
            {"id": "codex", "object": "model", "created": now(), "owned_by": "local"},
            {"id": "codex-local", "object": "model", "created": now(), "owned_by": "local"},
            {"id": "gpt-5.5", "object": "model", "created": now(), "owned_by": "local"},
        ]

    def complete(self, payload):
        agent_payload = {
            "model": payload.get("model") or "codex",
            "messages": payload.get("messages"),
            "input": payload.get("input"),
            "timeout": payload.get("timeout") or self.server.codex_timeout,
            "sandbox": payload.get("codex_sandbox") or payload.get("sandbox") or "workspace-write",
            "approval": payload.get("codex_approval") or payload.get("approval") or "never",
            "cwd": payload.get("cwd") or self.server.cwd,
            "codex_path": self.server.codex_path,
            "search": payload.get("search", False),
        }
        result = run_codex_exec(agent_payload)
        if result["status"] != "completed":
            raise RuntimeError(result.get("stderr") or result.get("stdout") or "codex exec failed")
        return result["output_text"]

    def chat_completions(self, payload):
        model = payload.get("model") or "codex"
        prompt = messages_to_prompt(payload.get("messages"))
        content = self.complete(payload)
        completion_id = "chatcmpl-" + uuid.uuid4().hex
        if payload.get("stream"):
            return send_sse(self, [
                {"id": completion_id, "object": "chat.completion.chunk", "created": now(), "model": model, "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]},
                {"id": completion_id, "object": "chat.completion.chunk", "created": now(), "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ])
        return send_json(self, 200, {
            "id": completion_id,
            "object": "chat.completion",
            "created": now(),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": approx_tokens(prompt), "completion_tokens": approx_tokens(content), "total_tokens": approx_tokens(prompt) + approx_tokens(content)},
            "system_fingerprint": "codex-agent-bridge",
        })

    def responses(self, payload):
        model = payload.get("model") or "codex"
        content = self.complete(payload)
        response_id = "resp_" + uuid.uuid4().hex
        response_obj = {
            "id": response_id,
            "object": "response",
            "created_at": now(),
            "status": "completed",
            "model": model,
            "output": [{"id": "msg_" + uuid.uuid4().hex, "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": content, "annotations": []}]}],
            "output_text": content,
            "usage": {"input_tokens": 0, "output_tokens": approx_tokens(content), "total_tokens": approx_tokens(content)},
        }
        if payload.get("stream"):
            return send_sse(self, [{"type": "response.output_text.delta", "response_id": response_id, "delta": content}, {"type": "response.completed", "response": response_obj}])
        return send_json(self, 200, response_obj)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("CODEX_BRIDGE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CODEX_BRIDGE_PORT", "8787")))
    parser.add_argument("--api-key", default=os.environ.get("CODEX_BRIDGE_API_KEY", ""))
    parser.add_argument("--codex", default=os.environ.get("CODEX_BIN", DEFAULT_CODEX))
    parser.add_argument("--cwd", default=os.environ.get("CODEX_BRIDGE_CWD", os.getcwd()))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("CODEX_BRIDGE_TIMEOUT", "600")))
    parser.add_argument("--log", default=os.environ.get("CODEX_BRIDGE_LOG", ""))
    parser.add_argument("--err-log", default=os.environ.get("CODEX_BRIDGE_ERR_LOG", ""))
    args = parser.parse_args()

    if args.log:
        sys.stdout = open(args.log, "a", encoding="utf-8", errors="replace", buffering=1)
    if args.err_log:
        sys.stderr = open(args.err_log, "a", encoding="utf-8", errors="replace", buffering=1)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.api_key = args.api_key
    httpd.codex_path = args.codex
    httpd.cwd = args.cwd
    httpd.codex_timeout = args.timeout
    httpd.jobs = JobStore(args.codex, args.cwd)
    print(f"codex-agent-bridge listening on http://{args.host}:{args.port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
