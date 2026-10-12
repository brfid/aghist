import json
from copy import deepcopy

import pytest

from aghist.contracts import ResearchError
from aghist.store import (add_version, atomic_write, init_library, library_lock,
                          load, question_path, save)
from aghist.workflow import Workflow, case_states, check_assessment, evidence_for
from conftest import HISTORICAL_TEXT, prepared_case, receipt


def run(library, worker, **kwargs):
    return Workflow(library, worker, progress=lambda _: None).run("Test a useful contrast.", **kwargs)


def assessment_dir(library):
    return next((library / "cases").glob("*/assessments/*/*/*"))


def test_complete_batch_has_two_isolated_reviews_and_preserves_input(library, worker, tmp_path):
    source = tmp_path / "corpus"
    source.mkdir()
    original = source / "earlier-case.md"
    original.write_text("Earlier research and original qualifications.\n")
    before = original.read_bytes()
    directory = run(library, worker, sources=[source])
    assert original.read_bytes() == before
    assert sorted(p.name for p in source.iterdir()) == ["earlier-case.md"]
    assert worker.maximum_active == 2
    reviews = [p for p in worker.prompts if p[1] == "review"]
    assert len(reviews) == 2 and reviews[0][2] == reviews[1][2]
    assert all(not p[3] for p in reviews)
    assert all("session-case" not in p[2] for p in reviews)
    receipt_path = assessment_dir(library) / "complete.json"
    complete = load(receipt_path)
    assert len(set(complete["sessions"])) == 2
    assert complete["question_version"] == "v001" and complete["evidence_revision"] == "r001"
    assert load(directory / "run.json")["status"] == "complete"


def test_failed_second_review_is_unfinished_and_resume_reuses_good_work(library, worker):
    worker.fail_b = True
    with pytest.raises(RuntimeError, match="second review"):
        run(library, worker)
    directory = next((library / "runs").iterdir())
    assert load(directory / "run.json")["status"] == "unfinished"
    assert not (assessment_dir(library) / "complete.json").exists()
    first_calls = deepcopy(worker.calls)
    worker.fail_b = False
    Workflow(library, worker, progress=lambda _: None).run(resume=directory.name)
    assert worker.calls.count(("prepare-001", "prepare")) == 1
    assert worker.calls.count(("case-001-review-a", "review")) == 1
    assert worker.calls.count(("case-001-review-b", "review")) == 2
    assert len(worker.calls) > len(first_calls)
    assert (assessment_dir(library) / "complete.json").exists()


def test_changed_numbered_question_cannot_resume(library, worker):
    directory = run(library, worker)
    question_path(library, "work-and-change", "v001").write_text("Changed question.")
    count = len(worker.calls)
    with pytest.raises(ResearchError, match="numbered question"):
        Workflow(library, worker).run(resume=directory.name)
    assert len(worker.calls) == count


def test_changed_packet_blocks_reuse_of_saved_reviews(library, worker):
    worker.fail_b = True
    with pytest.raises(RuntimeError):
        run(library, worker)
    packet = assessment_dir(library) / "packet.json"
    data = load(packet)
    data["case"]["account"] = "Changed evidence under the same revision."
    save(packet, data)
    worker.fail_b = False
    with pytest.raises(ResearchError, match="Frozen record changed"):
        Workflow(library, worker).run(resume=next((library / "runs").iterdir()).name)
    assert not (packet.parent / "complete.json").exists()


def test_invalidating_case_completes_normally(library, worker):
    worker.conclusion = "challenges"
    run(library, worker)
    assert load(assessment_dir(library) / "assessment.json")["result"]["value"]["conclusion"] == "challenges"
    assert (assessment_dir(library) / "complete.json").exists()


def test_new_working_version_does_not_promote_it_and_can_reassess(library, worker):
    worker.propose = True
    first = run(library, worker)
    assert load(library / "library.json")["principal"]["version"] == "v001"
    proposal = question_path(library, "work-and-change", "v002")
    assert "**Status:** working" in proposal.read_text()
    worker.propose = False
    second = run(library, worker, version="v002", case_id="factory-layout-change")
    folders = list((library / "cases/factory-layout-change/assessments/work-and-change").glob("*/*/complete.json"))
    assert len(folders) == 2
    assert len(list((library / "cases/factory-layout-change/revisions").iterdir())) == 1
    assert load(first / "run.json")["question_version"] == "v001"
    assert load(second / "run.json")["question_version"] == "v002"


def test_refresh_appends_evidence_revision(library, worker):
    run(library, worker)
    worker.case["uncertainties"].append("New evidence remains incomplete.")
    run(library, worker, case_id="factory-layout-change", refresh=True)
    revisions = library / "cases/factory-layout-change/revisions"
    assert sorted(p.name for p in revisions.iterdir()) == ["r001", "r002"]
    assert "New evidence" not in (revisions / "r001/case.md").read_text()


def test_prior_ai_verdicts_are_kept_out_of_review_packet(library, worker):
    worker.case["sources"].append({"origin": "/old/case.md", "citation": "Earlier AI dossier",
                                   "locator": "Earlier assessment", "excerpt": "LEGACY_VERDICT_NO_COPY",
                                   "limitations": "Prior interpretation, not independent source evidence.",
                                   "kind": "prior_research"})
    worker.receipts.append(receipt("read", "/old/case.md", "LEGACY_VERDICT_NO_COPY"))
    run(library, worker)
    assert "LEGACY_VERDICT_NO_COPY" not in (assessment_dir(library) / "packet.json").read_text()
    assert "LEGACY_VERDICT_NO_COPY" in (library / "cases/factory-layout-change/revisions/r001/retrieval.json").read_text()


def test_invented_source_extract_is_rejected(library, worker):
    worker.case["sources"][0]["excerpt"] = "No one changed the work arrangement."
    with pytest.raises(ResearchError, match="No retrieval receipt"):
        run(library, worker)
    assert not list((library / "cases").glob("*/assessments/*/*/*/complete.json"))


def test_duplicate_candidate_is_recorded_without_merging(library, worker):
    run(library, worker)
    worker.discovery[0]["existing_case"] = "factory-layout-change"
    directory = run(library, worker)
    state = load(directory / "run.json")
    assert state["status"] == "complete" and len(state["skipped"]) == 1
    assert state["cases"] == []
    assert len(list((library / "cases").iterdir())) == 1


def test_zero_candidates_is_valid(library, worker):
    worker.discovery = []
    directory = run(library, worker)
    assert load(directory / "run.json")["status"] == "complete"
    assert not list((library / "cases").iterdir())


@pytest.mark.parametrize("source_kind", ["same", "parent", "child"])
def test_input_output_overlap_is_rejected(library, worker, source_kind):
    source = {"same": library, "parent": library.parent, "child": library / "cases"}[source_kind]
    with pytest.raises(ResearchError, match="Input and output must be separate"):
        run(library, worker, sources=[source])
    assert worker.calls == []


def test_second_writer_is_rejected(library):
    with library_lock(library):
        with pytest.raises(ResearchError, match="Another coordinator"):
            with library_lock(library):
                pytest.fail("Acquired conflicting writer lock")


def test_atomic_write_failure_preserves_previous_record(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("original")
    def fail_replace(*args):
        raise OSError("Simulated interruption before rename")
    monkeypatch.setattr("aghist.store.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write(path, "replacement")
    assert path.read_text() == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_initialization_preserves_nonempty_directory(tmp_path):
    original = tmp_path / "original.md"
    original.write_text("Keep this research.")
    with pytest.raises(ResearchError, match="empty output"):
        init_library(tmp_path, "question", "Question?", "Purpose")
    assert original.read_text() == "Keep this research."
    assert sorted(p.name for p in tmp_path.iterdir()) == ["original.md"]


def test_frozen_version_cannot_be_overwritten(library):
    with library_lock(library):
        add_version(library, "work-and-change", "Working question", "v001", reserved="v002")
        with pytest.raises(ResearchError, match="Frozen record changed"):
            add_version(library, "work-and-change", "Changed working question", "v001", reserved="v002")


def test_completion_receipt_cannot_replace_a_missing_review(library, worker):
    run(library, worker)
    directory = assessment_dir(library)
    (directory / "review-b.json").unlink()
    with pytest.raises(ResearchError, match="Cannot read record"):
        check_assessment(directory)
    assert case_states(library)[0]["status"] == "unfinished"


def test_principal_change_marks_old_assessment_outdated(library, worker):
    run(library, worker)
    assert case_states(library)[0]["status"] == "reviewed"
    with library_lock(library):
        add_version(library, "work-and-change", "A working alternative question and rubric.", "v001")
        config = load(library / "library.json")
        config["principal"]["version"] = "v002"
        save(library / "library.json", config)
    assert case_states(library)[0]["status"] == "outdated"
    run(library, worker, version="v002", case_id="factory-layout-change")
    assert case_states(library)[0]["status"] == "reviewed"


def test_partial_revision_write_recovers_without_repeating_research(library, worker, monkeypatch):
    from aghist import workflow
    original = workflow.atomic_write
    def interrupted(path, *args, **kwargs):
        if str(path).endswith("revisions/r001/case.md"):
            raise OSError("Simulated interruption saving case account")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(workflow, "atomic_write", interrupted)
    with pytest.raises(OSError, match="Simulated interruption"):
        run(library, worker)
    monkeypatch.setattr(workflow, "atomic_write", original)
    directory = next((library / "runs").iterdir())
    Workflow(library, worker, progress=lambda _: None).run(resume=directory.name)
    assert worker.calls.count(("prepare-001", "prepare")) == 1
    assert case_states(library)[0]["status"] == "reviewed"


def test_oversized_packet_stops_before_model_reviews(library, worker):
    worker.receipts[0]["state"]["output"] += "x" * 260_000
    with pytest.raises(ResearchError, match="exceeds 256 KB"):
        run(library, worker)
    assert not [call for call in worker.calls if call[1] == "review"]


def test_editing_a_frozen_revision_invalidates_current_review_status(library, worker):
    run(library, worker)
    path = library / "cases/factory-layout-change/revisions/r001/case.json"
    case = load(path)
    case["account"] = "A changed account under the old evidence revision."
    save(path, case)
    assert case_states(library)[0]["status"] == "unfinished"


def test_fresh_clone_without_empty_directories_can_run(library, worker):
    (library / "cases").rmdir()
    (library / "runs").rmdir()
    run(library, worker)
    assert case_states(library)[0]["status"] == "reviewed"


def test_accidental_source_as_output_is_rejected_before_any_write(tmp_path, worker):
    source = tmp_path / "existing-corpus"
    source.mkdir()
    (source / "research.md").write_text("Preserve the original corpus.")
    with pytest.raises(ResearchError, match="Cannot read record"):
        Workflow(source, worker).run("A run", sources=[source])
    assert sorted(p.name for p in source.iterdir()) == ["research.md"]


def test_retained_historical_extract_can_be_reused_without_prior_verdict(library, worker):
    source = worker.case["sources"][0]
    source.update(origin="/old/checked-extract.md", kind="retained_extract",
                  limitations="Quotation checked in earlier research; the original is not newly inspected.")
    worker.receipts = [receipt("read", source["origin"], HISTORICAL_TEXT + "\nLEGACY_VERDICT_NO_COPY")]
    run(library, worker)
    packet = (assessment_dir(library) / "packet.json").read_text()
    assert source["excerpt"] in packet
    assert "LEGACY_VERDICT_NO_COPY" not in packet
    assert "not newly inspected" in packet


def test_editing_a_numbered_question_invalidates_review_status(library, worker):
    run(library, worker)
    question_path(library, "work-and-change", "v001").write_text("A different question and rubric.")
    with pytest.raises(ResearchError, match="numbered question"):
        check_assessment(assessment_dir(library))
    assert case_states(library)[0]["status"] == "unfinished"


def test_question_change_during_execution_prevents_completion(library, worker, monkeypatch):
    original = worker.call
    def change_question(directory, kind, prompt, **kwargs):
        result = original(directory, kind, prompt, **kwargs)
        if kind == "reconcile":
            question_path(library, "work-and-change", "v001").write_text("Changed during execution.")
        return result
    monkeypatch.setattr(worker, "call", change_question)
    with pytest.raises(ResearchError, match="numbered question"):
        run(library, worker)
    assert case_states(library)[0]["status"] == "unfinished"


@pytest.mark.parametrize("artifact", ["review-a.json", "assessment.json"])
def test_editing_a_saved_judgment_invalidates_review_status(library, worker, artifact):
    run(library, worker)
    path = assessment_dir(library) / artifact
    record = load(path)
    record["result"]["value"]["conclusion"] = "supports"
    save(path, record)
    with pytest.raises(ResearchError, match="accepted job output"):
        check_assessment(path.parent)
    assert case_states(library)[0]["status"] == "unfinished"


def test_whitespace_extract_cannot_count_as_retrieved_evidence(library, worker):
    worker.case["sources"][0]["excerpt"] = " \n\t "
    with pytest.raises(ResearchError, match="Invalid prepare"):
        run(library, worker)
    assert not [call for call in worker.calls if call[1] == "review"]
