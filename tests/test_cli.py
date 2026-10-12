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
