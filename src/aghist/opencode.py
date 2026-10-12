"""A thin, resumable OpenCode HTTP client. No provider keys are read here."""

import base64
import fnmatch
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .contracts import ResearchError, SCHEMAS, validate
from .store import load, now, save

DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"
READ_TOOLS = {"read", "glob", "grep"}
WEB_TOOLS = {"websearch", "webfetch"}


class OpenCode:
    """Execute bounded jobs and recover their already-submitted sessions.

    Args:
        url: Local backend started with the provided isolated profile.
        model: Explicit provider/model route; it is fixed for the worker's lifetime.
        task_seconds: Maximum wall time per attempt, including interrupted time.
        max_tools: Maximum observed tool calls before cancellation.
        retry_failed: Allow one explicit new attempt after a failed, stopped session.
        poll_seconds: Interval between bounded status checks.
    """

    def __init__(self, url="http://127.0.0.1:4096", model=DEFAULT_MODEL,
                 task_seconds=600, max_tools=16, retry_failed=False, poll_seconds=1):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.path not in {"", "/"} or parsed.username is not None or parsed.query or parsed.fragment:
            raise ResearchError("Use a local OpenCode HTTP backend, without credentials in its URL.")
        if not model.startswith("opencode-go/"):
            raise ResearchError("This version uses the selected OpenCode Go subscription route.")
        if task_seconds <= 0 or max_tools < 1 or poll_seconds < 0:
            raise ResearchError("Task time and tool limits must be positive.")
        self.url, self.model = url.rstrip("/"), model
        self.task_seconds, self.max_tools = task_seconds, max_tools
        self.retry_failed, self.poll_seconds = retry_failed, poll_seconds
        self.stop = threading.Event()
        self.active = set()
        self.mutex = threading.Lock()
        self.runtime = {}
        self.deadline = float("inf")
        self.idle_grace = 2

    def request(self, method, path, data=None):
        """Make one HTTP request; mutations are never automatically retried.

        Args:
            method: HTTP method.
            path: Backend-relative API path.
            data: Optional JSON request body.

        Returns:
            Decoded response data, or None for an empty response.

        Raises:
            ResearchError: The backend rejects or cannot complete the request.
        """
        headers = {"Content-Type": "application/json"}
        password = os.environ.get("OPENCODE_SERVER_PASSWORD")
        if password:
            user = os.environ.get("OPENCODE_SERVER_USERNAME", "opencode")
            token = base64.b64encode(f"{user}:{password}".encode()).decode()
            headers["Authorization"] = "Basic " + token
        request = Request(self.url + path, method=method, headers=headers,
                          data=None if data is None else json.dumps(data).encode())
        try:
            with urlopen(request, timeout=min(15, self.task_seconds)) as response:
                raw = response.read()
            return json.loads(raw) if raw else None
        except HTTPError as exc:
            detail = exc.read(3000).decode(errors="replace")
            raise ResearchError(f"OpenCode HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ResearchError(f"OpenCode request failed: {exc}") from exc

    def preflight(self):
        """Verify the selected model and restrictive profile without model calls.

        Returns:
            Runtime identifiers saved with each run.

        Raises:
            ResearchError: The backend, model, or profile is unsuitable.
        """
        health = self.request("GET", "/global/health")
        if not health.get("healthy"):
            raise ResearchError("The OpenCode backend is unhealthy.")
        providers = self.request("GET", "/provider")
        provider, model = self.model.split("/", 1)
        selected = next((p for p in providers["all"] if p["id"] == provider), {})
        if provider not in providers["connected"] or model not in selected.get("models", {}):
            raise ResearchError(f"Configured subscription model unavailable: {self.model}")
        config = self.request("GET", "/config")
        paths = self.request("GET", "/path")
        workspace = Path(paths["directory"])
        expected_config = workspace.parent / "xdg-config" / "opencode"
        if workspace.name != "workspace" or workspace.parent.name != ".runtime" or Path(paths["config"]) != expected_config:
            raise ResearchError("Use scripts/opencode-web: it isolates ambient project and global instructions.")
        if (expected_config / "AGENTS.md").exists():
            raise ResearchError("Remove extra instructions from the dedicated backend profile.")
        agents = {a["name"]: a for a in self.request("GET", "/agent")}
        if config.get("instructions") or config.get("plugin") or config.get("mcp"):
            raise ResearchError("Start the supplied isolated OpenCode profile, without extra instructions, plugins or MCP servers.")
        for name, allowed in [("aghist-research", READ_TOOLS | WEB_TOOLS), ("aghist-analysis", set())]:
            agent = agents.get(name)
            if not agent:
                raise ResearchError("Start the backend with aghist's supplied profile.")
            for tool in (READ_TOOLS | WEB_TOOLS | {"bash", "edit", "task", "question", "skill"}):
                action = "deny"
                for rule in agent.get("permission", []):
                    if fnmatch.fnmatchcase(tool, rule["permission"]) and rule["pattern"] == "*":
                        action = rule["action"]
                if action == "allow" and tool not in allowed:
                    raise ResearchError(f"Unexpected {tool} permission for {name}.")
        spec = self.request("GET", "/doc")
        for path in ("/session", "/session/{sessionID}/prompt_async", "/session/{sessionID}/abort"):
            if path not in spec.get("paths", {}):
                raise ResearchError("This OpenCode version exposes an unsupported session API.")
        self.runtime = {"opencode_version": health["version"], "model": self.model,
                        "model_info": {k: selected["models"][model].get(k) for k in ("id", "name", "release_date", "limit")},
                        "backend": self.url, "checked_at": now()}
        return self.runtime

    def check_active_sessions(self, allowed=()):
        """Admit a coordinator only when earlier owned remote jobs are accounted for.

        Args:
            allowed: Recorded session IDs from the one run being resumed. An active
                session from another run must be stopped or resumed first.

        Raises:
            ResearchError: A surviving aghist job would escape this coordinator,
                or more than two owned jobs are already active.
        """
        owned = []
        for session, status in self.request("GET", "/session/status").items():
            if status["type"] == "idle":
                continue
            info = self.request("GET", f"/session/{session}")
            if info.get("title", "").startswith("aghist "):
                owned.append(session)
        if len(owned) > 2:
            raise ResearchError("More than two owned sessions are active; stop them in OpenCode to restore the two-agent cap.")
        unknown = set(owned) - set(allowed)
        if unknown:
            raise ResearchError("An earlier aghist session is still active: " + ", ".join(sorted(unknown)) +
                                ". Resume its recorded run or stop it in OpenCode before starting new work.")

    def cancel_active(self):
        """Stop active jobs after a failure, deadline or user interruption."""
        self.stop.set()
        with self.mutex:
            sessions = list(self.active)
        for session in sessions:
            try:
                self.request("POST", f"/session/{session}/abort")
            except ResearchError:
                pass  # The next resume inspects the unresolved session before any retry.

    def call(self, directory, kind, prompt, *, sources=()):
        """Execute or recover one immutable job, retaining all attempt outputs.

        Args:
            directory: Durable directory unique to this workflow stage.
            kind: Output contract and role name.
            prompt: Exact task text; changing it requires a new job.
            sources: Read-only input paths for researcher jobs only.

        Returns:
            Validated value, retrieval receipts, session and execution metadata.

        Raises:
            ResearchError: Inputs changed, execution failed, or submission is ambiguous.
        """
        if self.stop.is_set():
            raise ResearchError("The run has been stopped.")
        directory = Path(directory)
        spec = {"kind": kind, "prompt": prompt, "sources": list(map(str, sources)),
                "model": self.model, "schema": SCHEMAS[kind]}
        attempts = []
        for folder in sorted(directory.glob("attempt-*")):
            if (folder / "request.json").exists():
                attempts.append(folder)
            elif any(not p.name.startswith(".writing-") or not p.is_file() or p.is_symlink()
                     for p in folder.iterdir()):
                raise ResearchError(f"Attempt metadata is incomplete; inspect {folder} before continuing.")
            # An empty directory or an interrupted atomic-write temporary file
            # precedes the request checkpoint, so no model call was submitted.
        attempt = attempts[-1] if attempts else None
        if attempt:
            request = load(attempt / "request.json")
            if request["spec"] != spec:
                raise ResearchError(f"Job inputs changed: {directory}")
            if not (attempt / "state.json").exists():
                # No submission can precede the initial state checkpoint. Inspect
                # the remote session anyway; existing activity is collected rather
                # than submitted again, including for older incomplete records.
                messages = self.request("GET", f"/session/{request['session_id']}/message?limit=1000")
                self._finished(messages, request)
                status = self.request("GET", "/session/status").get(request["session_id"], {"type": "idle"})
                state = {"status": "prepared" if not messages and status["type"] == "idle" else "uncertain",
                         "created_at": request.get("created_at", (attempt / "request.json").stat().st_mtime),
                         "updated_at": now()}
                save(attempt / "state.json", state)
            else:
                state = load(attempt / "state.json")
            if state["status"] == "complete":
                result = load(attempt / "result.json")
                original = self._finished(load(attempt / "messages.json"), request)
                if original is None or any(result.get(k) != original.get(k) for k in ("value", "receipts", "session_id", "message_id")):
                    raise ResearchError("A completed job output changed; create a new attempt.")
                # UI steering after one reviewer completed must still be
                # detected when its cached result is reused after interruption.
                messages = self.request("GET", f"/session/{request['session_id']}/message?limit=1000")
                current = self._finished(messages, request)
                if current is None or any(result.get(k) != current.get(k) for k in ("value", "receipts", "session_id", "message_id")):
                    raise ResearchError("The completed session no longer matches its accepted output.")
                return result
            if state["status"] == "failed":
                # Completion may have preceded a local write failure. Inspect it
                # before requiring a fresh attempt or spending another model call.
                messages = self.request("GET", f"/session/{request['session_id']}/message?limit=1000")
                try:
                    recovered = self._finished(messages, request)
                except ResearchError:
                    recovered = None
                if recovered:
                    save(attempt / "messages.json", messages)
                    save(attempt / "result.json", recovered, immutable=True)
                    state.update(status="complete", updated_at=now())
                    state.pop("error", None)
                    save(attempt / "state.json", state)
                    return recovered
                if not self.retry_failed or len(attempts) >= 2:
                    raise ResearchError(f"Job failed; inspect {attempt}. Use --retry-failed once after resolving its cause.")
                status = self.request("GET", "/session/status").get(request["session_id"], {"type": "idle"})
                if status["type"] != "idle":
                    raise ResearchError("The failed session is still active; retry is unsafe.")
                attempt = None
        if attempt is None:
            researcher = kind in {"discover", "prepare"}
            allowed = WEB_TOOLS | (READ_TOOLS if sources else set()) if researcher else set()
            permissions = [{"permission": "*", "pattern": "*", "action": "deny"}]
            permissions += [{"permission": t, "pattern": "*", "action": "allow"} for t in sorted(allowed - {"read"})]
            for source in sources if researcher else ():
                for pattern in [str(source), str(source) + "/**"]:
                    permissions += [{"permission": t, "pattern": pattern, "action": "allow"}
                                    for t in ("read", "external_directory")]
            session = self.request("POST", "/session", {"title": f"aghist {directory.parent.parent.name}: {directory.name}",
                                   "permission": permissions})
            request = {"session_id": session["id"], "message_id": "msg_" + uuid.uuid4().hex,
                       "spec": spec, "allowed_tools": sorted(allowed), "runtime": self.runtime,
                       "created_at": time.time()}
            attempt = directory / f"attempt-{len(attempts) + 1:03d}"
            save(attempt / "request.json", request, immutable=True)
            state = {"status": "prepared", "created_at": request["created_at"], "updated_at": now()}
            save(attempt / "state.json", state)
        session = request["session_id"]
        with self.mutex:
            self.active.add(session)
        try:
            if state["status"] == "prepared":
                if self.stop.is_set() or time.time() >= min(state["created_at"] + self.task_seconds, self.deadline):
                    raise ResearchError("The task was stopped before submission.")
                state.update(status="submitting", updated_at=now())
                save(attempt / "state.json", state)
                provider, model = self.model.split("/", 1)
                # In OpenCode 1.18.35, the deprecated tools field REPLACES
                # session permissions with wildcard rules. Preserve the scoped
                # permissions established at session creation instead.
                body = {"messageID": request["message_id"],
                        "model": {"providerID": provider, "modelID": model},
                        "agent": "aghist-research" if kind in {"discover", "prepare"} else "aghist-analysis",
                        "parts": [{"type": "text", "text": prompt + "\n\nReturn exactly one JSON object, no commentary or code fences, satisfying this contract:\n" + json.dumps(SCHEMAS[kind])}]}
                self.request("POST", f"/session/{session}/prompt_async", body)
                state.update(status="submitted", updated_at=now())
                save(attempt / "state.json", state)
            result = self._collect(attempt, request, state)
            save(attempt / "result.json", result, immutable=True)
            state.update(status="complete", updated_at=now())
            save(attempt / "state.json", state)
            return result
        except BaseException as exc:
            stopped = False
            try:
                stopped = self.request("POST", f"/session/{session}/abort") is True
            except ResearchError:
                pass
            # Never treat an ambiguous submission as a safely retryable failed job.
            status = "uncertain" if state["status"] in {"submitting", "uncertain"} or not stopped else "failed"
            state.update(status=status, error=str(exc), updated_at=now())
            save(attempt / "state.json", state)
            raise
        finally:
            with self.mutex:
                self.active.discard(session)

    def _collect(self, attempt, request, state):
        """Poll one recorded request until completion or a bounded stopping condition.

        Args:
            attempt: Current attempt's durable directory.
            request: Previously saved session, input and model identifiers.
            state: Current submission status and original task start time.

        Returns:
            The validated final result and source retrieval receipts.
        """
        session = request["session_id"]
        deadline = min(state["created_at"] + self.task_seconds, self.deadline)
        idle_since = None
        while True:
            status = self.request("GET", "/session/status").get(session, {"type": "idle"})
            if status["type"] == "retry":
                raise ResearchError("OpenCode stopped on a provider retry: " + status.get("message", "unknown error"))
            messages = self.request("GET", f"/session/{session}/message?limit=1000")
            save(attempt / "messages.json", messages)
            result = self._finished(messages, request)
            if result:
                return result
            users = [m["info"]["id"] for m in messages if m["info"]["role"] == "user"]
            for endpoint in ("/permission", "/question"):
                pending = self.request("GET", endpoint)
                if any(p.get("sessionID") == session for p in pending):
                    raise ResearchError("The unattended session needs permission or user input.")
            if self.stop.is_set() or time.time() >= deadline:
                raise ResearchError("Task deadline reached or run stopped; the session was cancelled.")
            if status["type"] == "idle":
                idle_since = idle_since if idle_since is not None else time.monotonic()
                if time.monotonic() - idle_since >= self.idle_grace:
                    if state["status"] in {"submitting", "uncertain"} and request["message_id"] not in users:
                        raise ResearchError("Submission outcome is unknown; inspect this session before any new submission.")
                    raise ResearchError("The session became idle without a valid final output.")
            else:
                idle_since = None
            self.stop.wait(self.poll_seconds)

    def _finished(self, messages, request):
        """Validate available messages and return their final JSON, if complete.

        Args:
            messages: Actual or previously saved OpenCode message objects.
            request: Immutable job description and role permissions.

        Returns:
            A validated result, or None while the task remains unfinished.

        Raises:
            ResearchError: Session contents violate the role or output contract.
        """
        if len(messages) >= 1000:
            raise ResearchError("Message history exceeds the bounded retrieval window.")
        users = [m["info"]["id"] for m in messages if m["info"]["role"] == "user"]
        if any(user != request["message_id"] for user in users):
            raise ResearchError("This engine-owned session received outside input; create a new assessment.")
        receipts = [{"tool": p["tool"], "call_id": p["callID"], "state": p["state"]}
                    for m in messages for p in m["parts"] if p["type"] == "tool"]
        if len(receipts) > self.max_tools:
            raise ResearchError("The task exceeded its observed tool-call limit.")
        if any(r["tool"] not in request["allowed_tools"] for r in receipts):
            raise ResearchError("The session attempted a tool outside its assigned role.")
        for message in messages:
            info = message["info"]
            if info.get("error"):
                raise ResearchError("OpenCode agent error: " + json.dumps(info["error"]))
            if info["role"] != "assistant" or info.get("parentID") != request["message_id"]:
                continue
            if not info.get("time", {}).get("completed") or info.get("finish") in {None, "tool-calls"}:
                continue
            if info["finish"] != "stop":
                raise ResearchError("The agent did not finish normally: " + info["finish"])
            provider, model = self.model.split("/", 1)
            expected_agent = "aghist-research" if request["spec"]["kind"] in {"discover", "prepare"} else "aghist-analysis"
            if (info.get("providerID"), info.get("modelID"), info.get("agent")) != (provider, model, expected_agent):
                raise ResearchError("The backend used a different provider, model or agent role.")
            if request["message_id"] not in users:
                raise ResearchError("The completed response has no matching user request.")
            raw = "\n".join(p["text"] for p in message["parts"] if p["type"] == "text").strip()
            fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", raw, re.S)
            try:
                value = json.loads(fenced.group(1) if fenced else raw)
            except ValueError as exc:
                raise ResearchError("The agent returned invalid JSON; inspect its saved messages.") from exc
            validate(request["spec"]["kind"], value)
            return {"value": value, "receipts": receipts, "session_id": request["session_id"],
                    "message_id": request["message_id"],
                    "completed_at": datetime.fromtimestamp(info["time"]["completed"] / 1000, timezone.utc).isoformat(),
                    "runtime": request["runtime"], "usage": [m["info"].get("tokens", {}) for m in messages
                                                            if m["info"]["role"] == "assistant"]}
        return None
