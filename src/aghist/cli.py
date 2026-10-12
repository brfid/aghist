"""Command-line entry points; research runs never start implicitly."""

import argparse
import json
import os
import sys
from pathlib import Path

from .contracts import ResearchError
from .opencode import DEFAULT_MODEL, OpenCode
from .store import (add_version, identifier, init_library, library_lock, load,
                    question_path, save)
from .workflow import Workflow, case_states


def parser():
    """Define the deliberately small author-facing command surface."""
    root = argparse.ArgumentParser(prog="aghist", description="Bounded historical research teams through OpenCode.")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create an empty output library.")
    init.add_argument("--library", type=Path, required=True)
    init.add_argument("--question-id", required=True)
    init.add_argument("--question-file", type=Path, required=True)
    init.add_argument("--purpose", required=True)
    for name in ("run", "resume", "doctor"):
        command = commands.add_parser(name)
        command.add_argument("--server", default="http://127.0.0.1:4096")
        command.add_argument("--model", default=DEFAULT_MODEL)
        command.add_argument("--task-seconds", type=float, default=600)
        command.add_argument("--max-tools", type=int, default=16)
        if name != "doctor":
            command.add_argument("--library", type=Path, required=True)
            command.add_argument("--retry-failed", action="store_true")
        if name == "run":
            brief = command.add_mutually_exclusive_group(required=True)
            brief.add_argument("--brief")
            brief.add_argument("--brief-file", type=Path)
            command.add_argument("--source", type=Path, action="append", default=[])
            command.add_argument("--question-id")
            command.add_argument("--version")
            command.add_argument("--max-cases", type=int, default=3)
            command.add_argument("--minutes", type=float, default=30)
            command.add_argument("--case", dest="case_id")
            command.add_argument("--refresh", action="store_true")
        if name == "resume":
            command.add_argument("run_id")
    for name in ("question", "adopt"):
        command = commands.add_parser(name)
        command.add_argument("--library", type=Path, required=True)
        command.add_argument("--question-id", required=True)
        if name == "question":
            command.add_argument("--file", type=Path, required=True)
            command.add_argument("--parent", required=True)
        else:
            command.add_argument("--version", required=True)
    status = commands.add_parser("status", help="Read saved run state without model calls.")
    status.add_argument("--library", type=Path, required=True)
    return root


def main(argv=None):
    """Execute an explicit author command and report recoverable failures.

    Args:
        argv: Optional argument list, primarily for offline tests.

    Returns:
        Zero on success, two for unfinished or invalid work, 130 on interruption.
    """
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            print(init_library(args.library, args.question_id, args.question_file.read_text(), args.purpose))
        elif args.command == "status":
            config = load(args.library / "library.json")
            print("Principal:", config["principal"]["question_id"], config["principal"]["version"])
            for case in case_states(args.library):
                print(case["case_id"], case["revision"], case["status"])
            for path in sorted((args.library / "runs").glob("*/run.json")):
                state = load(path)
                print(state["run_id"], state["status"], state.get("stopping_reason", ""))
        elif args.command in {"question", "adopt"}:
            load(args.library / "library.json")
            with library_lock(args.library):
                if args.command == "question":
                    print(add_version(args.library, args.question_id, args.file.read_text(), args.parent))
                else:
                    question_path(args.library, args.question_id, args.version).read_text()
                    config = load(args.library / "library.json")
                    config["principal"] = {"question_id": args.question_id, "version": args.version}
                    save(args.library / "library.json", config)
                    print("Principal set to", args.question_id, args.version)
        else:
            worker = OpenCode(args.server, args.model, args.task_seconds, args.max_tools,
                              retry_failed=getattr(args, "retry_failed", False))
            if args.command == "doctor":
                print(json.dumps(worker.preflight(), indent=2))
                print("Configuration verified; subscription eligibility is established only by a live request.")
            else:
                # One coordinator across libraries; the two-agent cap applies globally.
                state_home = Path(os.environ.get("AGHIST_STATE_DIR", Path.home() / ".local/state/aghist"))
                with library_lock(state_home / "coordinator"):
                    worker.preflight()
                    allowed = set()
                    if args.command == "resume":
                        recorded_run = args.library / "runs" / identifier(args.run_id)
                        load(recorded_run / "run.json")
                        for job in recorded_run.glob("jobs/*"):
                            requests = sorted(job.glob("attempt-*/request.json"))
                            if requests:
                                allowed.add(load(requests[-1])["session_id"])
                    worker.check_active_sessions(allowed)
                    workflow = Workflow(args.library, worker, progress=lambda text: print(text, flush=True))
                    if args.command == "resume":
                        directory = workflow.run(resume=args.run_id)
                    else:
                        brief = args.brief_file.read_text() if args.brief_file else args.brief
                        if args.refresh and not args.case_id:
                            raise ResearchError("--refresh requires an existing --case identifier.")
                        directory = workflow.run(brief, args.source, question=args.question_id,
                                                 version=args.version, max_cases=args.max_cases,
                                                 minutes=args.minutes, case_id=args.case_id, refresh=args.refresh)
                    print(directory)
    except KeyboardInterrupt:
        print("Interrupted. Saved work remains resumable.", file=sys.stderr)
        return 130
    except (ResearchError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0
