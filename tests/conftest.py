import json
import threading
import time
from copy import deepcopy

import pytest

from aghist.opencode import DEFAULT_MODEL
from aghist.store import init_library, load, save

HISTORICAL_TEXT = "The factory changed its layout. Downtime fell after the change. Other investments also occurred."


def receipt(tool="webfetch", origin="https://example.org/history", text=HISTORICAL_TEXT):
    return {"tool": tool, "call_id": "call-" + tool,
            "state": {"status": "completed", "input": {"url" if tool == "webfetch" else "filePath": origin},
                      "output": text, "metadata": {}, "time": {"start": 1, "end": 2}}}


def prepared_case():
    return {"title": "Factory layout change", "boundary": "One factory's adoption episode, 1900–1910.",
            "account": "The source reports a layout change and lower downtime, alongside other investments.",
            "sources": [{"origin": "https://example.org/history", "citation": "Factory history, author and edition identified in source.",
                         "locator": "Paragraph 1", "excerpt": "Downtime fell after the change.",
                         "limitations": "An attributed account; competing investments are not isolated.",
                         "kind": "historical_source"}],
            "uncertainties": ["The separate effect of the work change is unknown."]}


def review(conclusion="qualifies"):
    return {"conclusion": conclusion,
            "components": [{"component": "Contribution of work change", "judgment": conclusion,
                            "explanation": "Chronology is consistent; competing investments remain."}],
            "source_fidelity": "The account matches the supplied extract.",
            "mechanism": "A plausible sequence with missing intermediate evidence.",
            "alternatives": "Other investment may explain the outcome.",
            "contrary_evidence": "The improvement does not establish necessity.",
            "limitations": "One attributed retrospective account.",
            "follow_up": "Find evidence of the workflow before and after the change."}


class FakeWorker:
    """Persist deterministic outputs and expose concurrency and failure behavior."""

    model = DEFAULT_MODEL

    def __init__(self):
        self.calls = []
        self.prompts = []
        self.mutex = threading.Lock()
        self.active = self.maximum_active = 0
        self.fail_b = False
        self.conclusion = "qualifies"
        self.propose = False
        self.discovery = [{"title": "Factory layout change", "focus": "An informative contrast.",
                           "leads": ["https://example.org/history"], "existing_case": ""}]
        self.case = prepared_case()
        self.receipts = [receipt()]
        self.cancelled = False

    def cancel_active(self):
        self.cancelled = True

    def call(self, directory, kind, prompt, *, sources=()):
        attempt = directory / "attempt-001"
        path = attempt / "result.json"
        request = {"kind": kind, "prompt": prompt, "sources": list(map(str, sources))}
        if path.exists():
            assert load(attempt / "request.json")["spec"] == request
            return load(path)
        with self.mutex:
            self.calls.append((directory.name, kind))
            self.prompts.append((directory.name, kind, prompt, list(sources)))
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            if kind == "review":
                time.sleep(0.04)
                if self.fail_b and directory.name.endswith("review-b"):
                    raise RuntimeError("Simulated second review failure")
                value = review(self.conclusion)
            elif kind == "discover":
                value = {"candidates": self.discovery, "search_summary": "Found a bounded candidate."}
            elif kind == "prepare":
                value = self.case
            elif kind == "reconcile":
                value = {"conclusion": self.conclusion, "account": "The case qualifies the explanation.",
                         "disagreements": "The independent reviewers retain different emphases.",
                         "follow_up": "Check the alternative explanation."}
            else:
                proposals = []
                if self.propose:
                    proposals = [{"text": "How does work change affect downtime? Definitions, scope and rubric remain explicit.",
                                  "reason": "One observed outcome warrants testing a narrower variant.",
                                  "changed_scope": "A working outcome-specific branch.",
                                  "motivating_cases": ["factory-layout-change"], "contrary_cases": [],
                                  "next_test": "Find adoption with unchanged work and lower downtime."}]
                value = {"summary": "Evidence remains bounded.", "next_inquiry": "Seek an invalidating contrast.",
                         "refinements": proposals}
            result = {"value": deepcopy(value), "receipts": deepcopy(self.receipts) if kind == "prepare" else [],
                      "session_id": "session-" + directory.parent.parent.name + "-" + directory.name,
                      "message_id": "message-" + directory.name,
                      "runtime": {"model": self.model}, "completed_at": "fixture-time", "usage": []}
            save(attempt / "request.json", {"spec": request, "session_id": result["session_id"]}, immutable=True)
            save(path, result, immutable=True)
            save(attempt / "state.json", {"status": "complete"})
            return result
        finally:
            with self.mutex:
                self.active -= 1


@pytest.fixture
def library(tmp_path):
    return init_library(tmp_path / "output", "work-and-change",
                        "How and when does changed work contribute to adoption outcomes?\nDefinitions and rubric.\n",
                        "Explain historical mechanisms and scope, including invalidating cases.")


@pytest.fixture
def worker():
    return FakeWorker()
