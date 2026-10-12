# aghist

A small Python coordinator for historical research teams, using DeepSeek Flash through OpenCode Go.

The engine takes a research brief, an explicit question version, optional read-only corpus paths, and a separate output library. It discovers candidates, retrieves sources, prepares bounded historical accounts, obtains two independent reviews, reconciles them, and proposes grounded working question versions. The researcher selects the principal question.

This is an experimental first version. Offline tests pass; live model inference, source retrieval and historical quality still need an inspected pilot. Research libraries and source collections are separate and are not included here.

Read [AGENTS.md](AGENTS.md) and [DESIGN.md](DESIGN.md) for the requirements. Python owns accepted files; agents never write them. There is no maintained case index, database, dashboard or scheduler in this version.

## Setup

Python 3.11 or later, [uv](https://docs.astral.sh/uv/), and OpenCode are required.

```sh
git clone https://github.com/brfid/aghist.git ~/src/aghist
cd ~/src/aghist
uv sync --dev
uv run pytest
```

Start the dedicated backend in another terminal:

```sh
~/src/aghist/scripts/opencode-web
```

This runs `opencode web` on `127.0.0.1:4096` with a separate configuration and neutral working directory, without external plugins or inherited project instructions. It uses the existing OpenCode credential store; credentials are never copied into aghist. Keep this process running while research executes. The browser UI shows the same sessions; the terminal UI can attach with `opencode attach http://127.0.0.1:4096`.

```sh
uv run aghist doctor
```

`doctor` checks the backend profile and model configuration without a model call. It cannot confirm subscription eligibility. The selected route is `opencode-go/deepseek-v4.1-flash`. No other provider or paid route is used as a fallback. If the backend has a password, supply `OPENCODE_SERVER_PASSWORD` to the coordinator environment too.

## First bounded run

Create a Markdown question file containing its wording, definitions, scope, component claims and assessment criteria. Keep it outside the new output directory, which must be empty or absent. Then initialize a library:

```sh
uv run aghist init --library ~/src/aghist-library \
  --question-id technology-and-work \
  --question-file /absolute/path/question.md \
  --purpose 'Explain when and how work changes contribute to technology adoption.'
```

With the dedicated backend running and an active OpenCode Go subscription, start one small batch:

```sh
uv run aghist run --library ~/src/aghist-library \
  --brief 'Investigate one bounded historical case and seek contrary evidence.' \
  --max-cases 1 --minutes 30
```

Add `--source /absolute/path/corpus` for each read-only corpus directory or text file. Inputs and output must be separate; ancestor/descendant overlaps are rejected. Sources are supplied explicitly rather than retained as a hidden default for every future run. Prior research supplies leads and provenance; prior verdicts are omitted from review packets. One old file can yield several episodes, and several files can inform one case.

Inspect the pilot's sources and judgments before increasing limits. An inactive subscription stops the run without a provider or billing fallback. The local development pilot remains deferred pending Go reactivation; publishing this code does not start it.

## Question versions and reassessment

Runs use the principal question unless `--question-id` and `--version` select a working version. Agent proposals are saved as numbered working versions, with their parent, motivating cases, changed scope and next test. They never update `library.json`'s principal pointer. The author can add or adopt a version explicitly:

```sh
uv run aghist question --library /absolute/path/library \
  --question-id technology-and-work --parent v001 --file /absolute/path/variant.md
uv run aghist adopt --library /absolute/path/library \
  --question-id technology-and-work --version v002
```

Reassess an existing case against a selected version, retaining its earlier assessment and evidence:

```sh
uv run aghist run --library /absolute/path/library \
  --brief 'Assess this case under the revised definitions.' \
  --case descriptive-case-id --version v002
```

Add `--refresh` and the needed `--source` paths to retrieve new evidence and append a case/evidence revision. Ordinary discovery records known duplicates without merging cases by a shared title or URL. Supporting, invalidating, mixed, irrelevant and unresolved assessments can all complete normally.

## Limits and recovery

- One case is prepared and assessed at a time. Two fresh reviewers run concurrently; all other stages run singly. A coordinator lock applies across libraries. Startup also checks surviving aghist sessions on the dedicated backend: resume their recorded run or stop them in OpenCode before starting other work. This covers remote jobs that outlive a crashed coordinator or failed cancellation. Worker agents cannot spawn agents.
- A batch considers at most three candidates, with zero a valid result. Default run allowance: 30 minutes; default per-task allowance: 600 seconds; default observed tool-call limit: 16. Use `--minutes`, `--task-seconds` and `--max-tools` deliberately. A task already in flight can briefly exceed a bound while its next status check or HTTP request finishes.
- Review packets are limited to 256 KB. They contain the actual selected retrieval text, exact question, neutral account, provenance and known limits. Both reviewers receive identical bytes and no file/web tools. A single SHA-256 checksum detects changed packets; readable IDs identify question and evidence versions.
- Provider retry/quota errors, unexpected permission requests, invalid outputs, deadlines and interruptions leave work unfinished. Already completed stages are reused. One explicit retry of a stopped failed job is available; no automatic provider change occurs.

```sh
uv run aghist status --library /absolute/path/library
uv run aghist resume --library /absolute/path/library run-YYYYMMDD-HHMMSS-abcdef
```

`status` reads files without contacting OpenCode and distinguishes principal-version reviews from outdated or unfinished cases. It checks exact numbered question text, frozen case/evidence data and saved judgments against their accepted job outputs.

`resume` uses the run's recorded brief, source paths, model and question; it gives the invocation another saved run allowance. It checks remote sessions even when reusing completed jobs, so later UI input is detected. Task deadlines still include interrupted time, but completed remote results are collected before an expired task is rejected. An interrupted initial state checkpoint is recovered by inspecting the recorded session before any submission. Empty, unsubmitted attempt folders can be reused; other incomplete request records stop for inspection.

After fixing a confirmed failed job's cause, use `resume ... --retry-failed` once. A submission with an unknown outcome is inspected rather than silently repeated. If it cannot be resolved from the saved session, it remains uncertain and requires manual inspection. To restart such work deliberately, create a new run after confirming the old session has stopped. Preserve the uncertain run as part of the record.

Inspect sessions in OpenCode at any time. Use separate sessions for manual exploration. Pause the coordinator before steering its sessions; outside input invalidates an engine-owned attempt. Editing frozen questions, evidence revisions or packets in place is rejected or invalidates review status. Append a version or refresh the evidence instead.

This first version runs one bounded batch per invocation. Larger wall-time allowances do not add automatic repeated batches. Continuous collection, scheduling and process supervision remain later work after a live pilot succeeds.

## Saved records

```text
library.json                         # purpose and author-selected principal
questions/<question>/versions/v001.md
cases/<case>/case.md                  # navigation to the latest account
cases/<case>/revisions/r001/          # case, evidence and retrieval receipts
cases/<case>/assessments/<question>/<version>/<run>/
  packet.json
  review-a.json / review-a.md
  review-b.json / review-b.md
  assessment.json / assessment.md
  complete.json
runs/<run>/run.json                   # operational progress and continuation
runs/<run>/jobs/<stage>/attempt-001/  # request, state, actual messages, result
runs/<run>/summary.md                 # synthesis and question-refinement rationale
```

JSON records own metadata and structured results; Markdown renders make accounts and judgments browsable. Each review and reconciliation names its original run/job record, which remains necessary for validating completion. Attempt outputs, numbered question versions and evidence revisions are preserved. Research memory is reconstructed from these folders; OpenCode sessions support inspection and recovery but are not the research record.

Actual retrieved text, tool failures and truncation metadata are retained. Source excerpts must match returned text at the reported origin. Previously checked historical quotations can be reused as retained extracts, preserving their original attribution and inspection limits without passing along the earlier dossier's verdicts. They are labeled as prior inspection rather than a fresh reading of the original. This checks quotation provenance, not historical truth. Local text and the backend's supported web retrieval work directly; inaccessible PDFs or missing scans remain explicit gaps. There is no OCR pipeline in this version.

## Verification

`uv run pytest` uses temporary libraries and deterministic workers/API fixtures. It covers independent review inputs, source preservation, packet changes, question/evidence revisions, invalidating conclusions, partial writes, writer conflicts, remote-completion recovery, uncertain submissions, permission/timeout/tool limits, subscription stops and bounded retries. Regression checks also cover surviving remote sessions, initial-checkpoint recovery, later UI input, and schema-valid edits to saved judgments or numbered questions. Tests make no model calls.

The installed OpenCode 1.18.35 API was checked without generation using `noReply=true`: supplied message IDs and scoped session permissions survived round trips. Model inference, source retrieval and end-to-end historical quality remain unverified pending an inspected live pilot.

Agent JSON is validated locally with JSON Schema. The adapter omits OpenCode's deprecated prompt `tools` field because [1.18.35's implementation](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/session/prompt.ts) replaces session permission rules when that field is present. The [server documentation](https://opencode.ai/docs/server/) describes the shared HTTP/UI backend. The provided isolated profile and runtime checks constrain its use here.
