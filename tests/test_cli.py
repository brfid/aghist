from aghist.cli import main
from aghist.store import load


def test_initialization_and_explicit_adoption_need_no_backend(tmp_path):
    question = tmp_path / "question.md"
    question.write_text("How and when does this mechanism work? Scope and evidence criteria.\n")
    root = tmp_path / "library"
    assert main(["init", "--library", str(root), "--question-id", "causal-question",
                 "--question-file", str(question), "--purpose", "Understand mechanisms."]) == 0
    question.write_text("An alternative question with definitions, scope and evidence criteria.\n")
    assert main(["question", "--library", str(root), "--question-id", "causal-question",
                 "--file", str(question), "--parent", "v001"]) == 0
    assert load(root / "library.json")["principal"]["version"] == "v001"
    assert main(["adopt", "--library", str(root), "--question-id", "causal-question", "--version", "v002"]) == 0
    assert load(root / "library.json")["principal"]["version"] == "v002"
    assert main(["status", "--library", str(root)]) == 0


def test_run_checks_for_surviving_jobs_before_starting_work(library, tmp_path, monkeypatch):
    from aghist import cli
    from aghist.contracts import ResearchError
    checks = []
    class GuardedWorker:
        def __init__(self, *args, **kwargs):
            pass
        def preflight(self):
            return {}
        def check_active_sessions(self, allowed=()):
            checks.append(set(allowed))
            raise ResearchError("Earlier owned job is still active")
    monkeypatch.setattr(cli, "OpenCode", GuardedWorker)
    monkeypatch.setenv("AGHIST_STATE_DIR", str(tmp_path / "state"))
    assert main(["run", "--library", str(library), "--brief", "A contrast."]) == 2
    assert checks == [set()]
    assert not list((library / "runs").iterdir())


def test_resume_admits_only_sessions_recorded_in_that_run(library, worker, tmp_path, monkeypatch):
    from aghist import cli
    from aghist.contracts import ResearchError
    from aghist.workflow import Workflow
    directory = Workflow(library, worker, progress=lambda _: None).run("A contrast.")
    request_path = next(directory.glob("jobs/*/attempt-*/request.json"))
    request_path.parent.rename(request_path.parent.with_name("attempt-002"))
    from aghist.store import save
    save(request_path, {"session_id": "old-failed-attempt"})
    recorded = {load(sorted(job.glob("attempt-*/request.json"))[-1])["session_id"]
                for job in directory.glob("jobs/*")}
    assert len(recorded) == 6 and "old-failed-attempt" not in recorded
    checks = []
    class GuardedWorker:
        def __init__(self, *args, **kwargs):
            pass
        def preflight(self):
            return {}
        def check_active_sessions(self, allowed=()):
            checks.append(set(allowed))
            raise ResearchError("Stop before execution")
    monkeypatch.setattr(cli, "OpenCode", GuardedWorker)
    monkeypatch.setenv("AGHIST_STATE_DIR", str(tmp_path / "state"))
    assert main(["resume", "--library", str(library), directory.name]) == 2
    assert checks == [recorded]
