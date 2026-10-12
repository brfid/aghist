import json
import time
from copy import deepcopy

import pytest

from aghist.contracts import ResearchError
from aghist.opencode import OpenCode
from aghist.store import load, save
from conftest import receipt, review


class FakeAPI(OpenCode):
    """Simulate the observed OpenCode HTTP contract, not historical reasoning."""

    def __init__(self, **kwargs):
        super().__init__(poll_seconds=0, **kwargs)
        self.idle_grace = 0
        self.submissions = []
        self.sessions = {}
        self.aborted = []
        self.remote_complete = True
        self.ambiguous = False
        self.provider_retry = False
        self.pending_permission = False
        self.extra_user = False
        self.tools = []
        self.value = review()

    def request(self, method, path, data=None):
        if path == "/session" and method == "POST":
            sid = "ses_" + str(len(self.sessions) + 1)
            self.sessions[sid] = {"body": None, "permission": data["permission"], "title": data["title"]}
            return {"id": sid}
        if path == "/experimental/tool/ids":
            return ["read", "glob", "grep", "websearch", "webfetch", "bash", "edit", "task", "question", "skill"]
        if path == "/session/status":
            return {sid: {"type": "retry", "message": "An active Go subscription is required."}
                    if self.provider_retry else {"type": "idle" if self.remote_complete or self.ambiguous else "busy"}
                    for sid in self.sessions}
        if path in {"/permission", "/question"}:
            return [{"sessionID": "ses_1"}] if self.pending_permission else []
        sid = path.split("/")[2]
        if path == f"/session/{sid}":
            return {"id": sid, "title": self.sessions[sid]["title"]}
        if path.endswith("/abort"):
            self.aborted.append(sid)
            return True
        if path.endswith("/prompt_async"):
            self.submissions.append(deepcopy(data))
            if self.ambiguous:
                raise ResearchError("Connection lost after submission")
            self.sessions[sid]["body"] = deepcopy(data)
            self.sessions[sid]["value"] = deepcopy(self.value)
            return None
        if "/message" in path:
            body = self.sessions[sid]["body"]
            if body is None:
                return []
            messages = [{"info": {"role": "user", "id": body["messageID"]}, "parts": body["parts"]}]
            if self.extra_user:
                messages.append({"info": {"role": "user", "id": "msg_outside"}, "parts": []})
            parts = [{"type": "tool", "callID": str(i), "tool": r["tool"], "state": r["state"]}
                     for i, r in enumerate(self.tools)]
            if self.remote_complete:
                parts.append({"type": "text", "text": json.dumps(self.sessions[sid]["value"])})
            messages.append({"info": {"id": "msg_answer", "role": "assistant", "parentID": body["messageID"],
                                      "providerID": "opencode-go", "modelID": "deepseek-v4.1-flash",
                                      "agent": body["agent"], "time": {"completed": 2000} if self.remote_complete else {},
                                      "finish": "stop" if self.remote_complete else None, "tokens": {}}, "parts": parts})
            return messages
        raise AssertionError((method, path, data))


def attempt_path(tmp_path):
    return tmp_path / "job" / "attempt-001"


def test_review_request_denies_tools_and_uses_explicit_subscription(tmp_path):
    api = FakeAPI()
    result = api.call(tmp_path / "job", "review", "Frozen packet")
    body = api.submissions[0]
    assert body["agent"] == "aghist-analysis"
    assert body["model"] == {"providerID": "opencode-go", "modelID": "deepseek-v4.1-flash"}
    assert "tools" not in body  # This field would replace scoped session permissions.
    assert "format" not in body  # Local schema validation avoids the observed response-codec error.
    assert api.sessions["ses_1"]["permission"] == [{"permission": "*", "pattern": "*", "action": "deny"}]
    assert result["value"] == review()


def test_researcher_read_permissions_stay_scoped_to_input(tmp_path):
    api = FakeAPI()
    api.value = {"candidates": [], "search_summary": "No new candidate."}
    api.call(tmp_path / "job", "discover", "Inspect the input corpus", sources=[tmp_path / "corpus"])
    rules = api.sessions["ses_1"]["permission"]
    assert rules[0] == {"permission": "*", "pattern": "*", "action": "deny"}
    assert {r["pattern"] for r in rules if r["permission"] == "read"} == {str(tmp_path / "corpus"), str(tmp_path / "corpus") + "/**"}
    assert "tools" not in api.submissions[0]


def test_resume_after_remote_completion_before_local_checkpoint_does_not_resubmit(tmp_path):
    api = FakeAPI()
    first = api.call(tmp_path / "job", "review", "Frozen packet")
    attempt = attempt_path(tmp_path)
    state = load(attempt / "state.json")
    state["status"] = "submitted"
    save(attempt / "state.json", state)
    (attempt / "result.json").unlink()
    recovered = api.call(tmp_path / "job", "review", "Frozen packet")
    assert recovered == first
    assert len(api.submissions) == 1


def test_recover_local_checkpoint_failure_before_retrying(tmp_path):
    api = FakeAPI()
    first = api.call(tmp_path / "job", "review", "Frozen packet")
    attempt = attempt_path(tmp_path)
    state = load(attempt / "state.json")
    state["status"] = "failed"
    save(attempt / "state.json", state)
    assert api.call(tmp_path / "job", "review", "Frozen packet") == first
    assert len(api.submissions) == 1


def test_ambiguous_submission_is_never_blindly_repeated(tmp_path):
    api = FakeAPI()
    api.ambiguous = True
    with pytest.raises(ResearchError, match="Connection lost"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert load(attempt_path(tmp_path) / "state.json")["status"] == "uncertain"
    with pytest.raises(ResearchError, match="Submission outcome is unknown"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert len(api.submissions) == 1


def test_subscription_retry_stops_and_aborts_without_fallback(tmp_path):
    api = FakeAPI()
    api.provider_retry = True
    with pytest.raises(ResearchError, match="active Go subscription"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert api.aborted == ["ses_1"]
    assert len(api.submissions) == 1
    assert api.submissions[0]["model"]["providerID"] == "opencode-go"


@pytest.mark.parametrize("reason", ["timeout", "permission", "tools", "outside-input"])
def test_execution_limits_cancel_sessions(tmp_path, reason):
    api = FakeAPI(task_seconds=0.01, max_tools=1)
    api.remote_complete = False
    if reason == "permission":
        api.pending_permission = True
    elif reason == "tools":
        api.tools = [receipt(), receipt()]
    elif reason == "outside-input":
        api.extra_user = True
    with pytest.raises(ResearchError):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert api.aborted == ["ses_1"]
    assert load(attempt_path(tmp_path) / "state.json")["status"] == "failed"


def test_malformed_output_is_retained_and_requires_explicit_bounded_retry(tmp_path):
    api = FakeAPI()
    api.value = {"conclusion": "supports"}
    with pytest.raises(ResearchError, match="Invalid review"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert (attempt_path(tmp_path) / "messages.json").exists()
    with pytest.raises(ResearchError, match="Job failed"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert len(api.submissions) == 1
    api.retry_failed = True
    api.value = review()
    assert api.call(tmp_path / "job", "review", "Frozen packet")["value"] == review()
    assert len(api.submissions) == 2
    assert (tmp_path / "job/attempt-001/messages.json").exists()


def test_manual_change_to_a_completed_result_is_rejected(tmp_path):
    api = FakeAPI()
    api.call(tmp_path / "job", "review", "Frozen packet")
    path = attempt_path(tmp_path) / "result.json"
    result = load(path)
    result["value"]["mechanism"] = "A manually substituted mechanism."
    save(path, result)
    with pytest.raises(ResearchError, match="completed job output changed"):
        api.call(tmp_path / "job", "review", "Frozen packet")


def test_retry_flag_still_cannot_exceed_two_attempts(tmp_path):
    api = FakeAPI(retry_failed=True)
    api.value = {"conclusion": "supports"}
    for _ in range(2):
        with pytest.raises(ResearchError, match="Invalid review"):
            api.call(tmp_path / "job", "review", "Frozen packet")
    with pytest.raises(ResearchError, match="Job failed"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert len(api.submissions) == 2


def test_first_state_write_failure_recovers_without_duplicate_submission(tmp_path, monkeypatch):
    from aghist import opencode
    api = FakeAPI()
    original = opencode.save
    def fail_initial_state(path, value, **kwargs):
        if path.name == "state.json" and not path.exists():
            raise OSError("Interrupted initial state checkpoint")
        return original(path, value, **kwargs)
    monkeypatch.setattr(opencode, "save", fail_initial_state)
    with pytest.raises(OSError, match="initial state"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert (attempt_path(tmp_path) / "request.json").exists()
    assert api.submissions == []
    monkeypatch.setattr(opencode, "save", original)
    assert api.call(tmp_path / "job", "review", "Frozen packet")["value"] == review()
    assert len(api.submissions) == len(api.sessions) == 1


def test_missing_state_collects_an_existing_remote_result_without_resubmitting(tmp_path):
    api = FakeAPI()
    first = api.call(tmp_path / "job", "review", "Frozen packet")
    (attempt_path(tmp_path) / "state.json").unlink()
    assert api.call(tmp_path / "job", "review", "Frozen packet") == first
    assert len(api.submissions) == 1


def test_cached_completion_rejects_later_outside_input(tmp_path):
    api = FakeAPI()
    api.call(tmp_path / "job", "review", "Frozen packet")
    api.extra_user = True
    with pytest.raises(ResearchError, match="outside input"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert len(api.submissions) == 1


def test_startup_blocks_surviving_owned_jobs_and_allows_their_resume():
    api = FakeAPI()
    api.remote_complete = False
    sessions = [api.request("POST", "/session", {"title": "aghist old-run: review", "permission": []})["id"]
                for _ in range(2)]
    with pytest.raises(ResearchError, match="still active"):
        api.check_active_sessions()
    api.check_active_sessions(sessions)
    assert api.submissions == []


def test_failed_abort_does_not_allow_a_new_run(monkeypatch):
    api = FakeAPI()
    api.remote_complete = False
    session = api.request("POST", "/session", {"title": "aghist old-run: review", "permission": []})["id"]
    api.active.add(session)
    original = api.request
    def unavailable_abort(method, path, data=None):
        if path.endswith("/abort"):
            raise ResearchError("Backend unavailable during cancellation")
        return original(method, path, data)
    monkeypatch.setattr(api, "request", unavailable_abort)
    api.cancel_active()
    with pytest.raises(ResearchError, match="still active"):
        api.check_active_sessions()
    assert api.submissions == []


def test_startup_ignores_separate_manual_sessions_and_rejects_more_than_two_owned():
    api = FakeAPI()
    api.remote_complete = False
    api.request("POST", "/session", {"title": "Manual exploration", "permission": []})
    api.check_active_sessions()
    sessions = [api.request("POST", "/session", {"title": "aghist old-run: review", "permission": []})["id"]
                for _ in range(3)]
    with pytest.raises(ResearchError, match="two-agent"):
        api.check_active_sessions(sessions)


@pytest.mark.parametrize("temporary_left", [False, True])
def test_interrupted_request_write_can_recover_unsubmitted_preparation(tmp_path, monkeypatch, temporary_left):
    from aghist import store
    api = FakeAPI()
    original = store.os.replace
    def fail_request(source, destination):
        if destination.name == "request.json":
            raise OSError("Interrupted request checkpoint")
        return original(source, destination)
    monkeypatch.setattr(store.os, "replace", fail_request)
    with pytest.raises(OSError, match="request checkpoint"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert list(attempt_path(tmp_path).iterdir()) == []
    assert api.submissions == []
    if temporary_left:
        (attempt_path(tmp_path) / ".writing-interrupted").write_text("Partial, uncommitted request bytes")
    monkeypatch.setattr(store.os, "replace", original)
    assert api.call(tmp_path / "job", "review", "Frozen packet")["value"] == review()
    assert len(api.submissions) == 1
    assert load(attempt_path(tmp_path) / "state.json")["status"] == "complete"
    if temporary_left:
        assert (attempt_path(tmp_path) / ".writing-interrupted").exists()


def test_missing_request_with_other_attempt_records_is_not_silently_retried(tmp_path):
    api = FakeAPI()
    api.call(tmp_path / "job", "review", "Frozen packet")
    (attempt_path(tmp_path) / "request.json").unlink()
    with pytest.raises(ResearchError, match="metadata is incomplete"):
        api.call(tmp_path / "job", "review", "Frozen packet")
    assert len(api.submissions) == 1
