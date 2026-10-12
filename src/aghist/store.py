"""Atomic records, immutable research inputs, and a single library writer."""

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .contracts import ResearchError


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ResearchError(f"Invalid identifier: {value!r}")
    return value


def version_id(value):
    if not re.fullmatch(r"v[0-9]{3,}", value):
        raise ResearchError(f"Invalid question version: {value!r}")
    return value


def slug(value):
    return identifier(re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:100].rstrip("-") or "case")


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ResearchError(f"Cannot read record {path}: {exc}") from exc


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def atomic_write(path, data, *, immutable=False):
    """Replace a record atomically, or preserve a previously frozen record.

    Args:
        path: Destination owned by this library.
        data: Text or bytes to save.
        immutable: Accept an existing file only when its bytes are identical.

    Raises:
        ResearchError: A destination is a symlink or an immutable record differs.
        OSError: The filesystem cannot save the record.
    """
    path = Path(path)
    data = data.encode() if isinstance(data, str) else data
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ResearchError(f"Refusing symlink destination: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_bytes() != data:
            raise ResearchError(f"Frozen record changed: {path}")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(path, value, *, immutable=False):
    atomic_write(path, encode(value), immutable=immutable)


@contextmanager
def library_lock(root):
    """Hold the library's advisory writer lock until the operation finishes.

    Args:
        root: Library directory containing the lock file.

    Raises:
        ResearchError: Another coordinator already owns the library.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".aghist.lock"
    if lock.is_symlink():
        raise ResearchError("The library lock must not be a symlink.")
    with lock.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ResearchError("Another coordinator is writing this library.") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def disjoint_sources(library, sources):
    """Resolve inputs and keep all output writes outside their directory trees.

    Args:
        library: Destination research library.
        sources: Explicit read-only files or directories supplied to a run.

    Returns:
        Canonical existing input paths.

    Raises:
        ResearchError: An input and the output overlap in either direction.
        OSError: An input cannot be resolved to an existing path.
    """
    root = Path(library).resolve()
    paths = [Path(source).expanduser().resolve(strict=True) for source in sources]
    for path in paths:
        if path == root or path in root.parents or root in path.parents:
            raise ResearchError(f"Input and output must be separate: {path} and {root}")
    return paths


def question_path(root, question, version):
    return Path(root) / "questions" / identifier(question) / "versions" / f"{version_id(version)}.md"


def init_library(root, question, question_text, purpose):
    """Create an empty topic library without overwriting existing research.

    Args:
        root: New, empty output directory.
        question: Stable question identifier.
        question_text: Initial question, definitions, scope, and rubric in Markdown.
        purpose: Stable purpose used to assess proposed question refinements.

    Returns:
        The resolved, initialized library path.

    Raises:
        ResearchError: The directory is already initialized or contains other data.
    """
    root = Path(root).expanduser().resolve()
    identifier(question)
    if not question_text.strip() or not purpose.strip():
        raise ResearchError("Question text and purpose must be nonempty.")
    if root.exists() and any(p.name != ".aghist.lock" for p in root.iterdir()):
        raise ResearchError("Initialize an empty output directory; existing files are preserved.")
    with library_lock(root):
        if any(p.name != ".aghist.lock" for p in root.iterdir()):
            raise ResearchError("Initialize an empty output directory; existing files are preserved.")
        save(root / "library.json", {"schema_version": 1, "purpose": purpose,
             "principal": {"question_id": question, "version": "v001"}})
        atomic_write(question_path(root, question, "v001"), question_text, immutable=True)
        for folder in ("cases", "runs"):
            (root / folder).mkdir()
        atomic_write(root / "README.md", "# Research library\n\n"
                     "`library.json` identifies the purpose and author-selected principal question.\n"
                     "Browse `questions/`, `cases/` and `runs/`. Runs retain retrieval receipts and agent sessions; "
                     "case assessments identify their exact question and evidence revision.\n")
        atomic_write(root / ".gitignore", ".aghist.lock\n.writing-*\n.DS_Store\n")
    return root


def add_version(root, question, text, parent, *, origin="author", reserved=None):
    """Save a new working version; never change the principal automatically.

    Args:
        root: Library root; the caller holds its writer lock.
        question: Existing question identifier.
        text: Full proposed question, definitions, scope, and assessment rubric.
        parent: Version from which this proposal was developed.
        origin: Author or run identifier responsible for the proposal.
        reserved: Previously checkpointed version number for interruption recovery.

    Returns:
        The new working version identifier.
    """
    question_path(root, question, parent).read_text()
    directory = question_path(root, question, parent).parent
    numbers = [int(p.stem[1:]) for p in directory.glob("v[0-9]*.md")]
    version = reserved or f"v{max(numbers, default=0) + 1:03d}"
    content = (f"# Question {question} — {version}\n\n**Status:** working\n"
               f"**Parent:** {parent}\n**Proposed by:** {origin}\n\n{text.strip()}\n")
    atomic_write(question_path(root, question, version), content, immutable=True)
    return version


def packet_checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
