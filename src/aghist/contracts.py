"""Small output contracts; identifiers and provenance are added by Python."""

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


class ResearchError(RuntimeError):
    """Work cannot safely proceed; existing outputs remain available for inspection."""


TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
STRINGS = {"type": "array", "items": TEXT}


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


CANDIDATE = obj(title=TEXT, focus=TEXT, leads=STRINGS,
                existing_case={"type": "string"})
DISCOVERY = obj(candidates={"type": "array", "items": CANDIDATE, "maxItems": 3},
                search_summary=TEXT)
SOURCE = obj(origin=TEXT, citation=TEXT, locator=TEXT, excerpt=TEXT, limitations=TEXT,
             kind={"enum": ["historical_source", "retained_extract", "prior_research"]})
CASE = obj(title=TEXT, boundary=TEXT, account=TEXT,
           sources={"type": "array", "items": SOURCE}, uncertainties=STRINGS)
COMPONENT = obj(component=TEXT, judgment={"enum": ["supports", "qualifies", "challenges", "unresolved", "irrelevant"]},
                explanation=TEXT)
REVIEW = obj(conclusion={"enum": ["supports", "qualifies", "challenges", "unresolved", "irrelevant"]},
             components={"type": "array", "items": COMPONENT, "minItems": 1},
             source_fidelity=TEXT, mechanism=TEXT, alternatives=TEXT,
             contrary_evidence=TEXT, limitations=TEXT, follow_up=TEXT)
ASSESSMENT = obj(conclusion=REVIEW["properties"]["conclusion"], account=TEXT,
                 disagreements=TEXT, follow_up=TEXT)
REFINEMENT = obj(text=TEXT, reason=TEXT, changed_scope=TEXT, motivating_cases=STRINGS,
                 contrary_cases=STRINGS, next_test=TEXT)
SYNTHESIS = obj(summary=TEXT, next_inquiry=TEXT,
                refinements={"type": "array", "items": REFINEMENT, "maxItems": 2})
SCHEMAS = {"discover": DISCOVERY, "prepare": CASE, "review": REVIEW,
           "reconcile": ASSESSMENT, "synthesize": SYNTHESIS}


def validate(kind, value):
    """Validate an agent output without interpreting its historical conclusion.

    Args:
        kind: Name of the workflow stage's output contract.
        value: Decoded JSON object supplied by the agent.

    Returns:
        The validated object.

    Raises:
        ResearchError: The object does not satisfy its stage's contract.
    """
    try:
        Draft202012Validator(SCHEMAS[kind]).validate(value)
    except ValidationError as exc:
        raise ResearchError(f"Invalid {kind} output at {list(exc.path)}: {exc.message}") from exc
    return value

