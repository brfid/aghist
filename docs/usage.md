# Run historical research

This guide assumes you have completed the [engine setup](../README.md#setup) and initialized a library. The examples use the README's `~/src/aghist-example` library. Run coordinator commands from `~/src/aghist`; substitute your own library path when needed.

## Start OpenCode

Research runs require [OpenCode](https://opencode.ai/docs/) and an active [OpenCode Go subscription](https://opencode.ai/docs/go/). Install OpenCode and connect your Go account through its interface. The supplied profile uses the DeepSeek Flash route recorded in the [integration notes](../DESIGN.md#opencode-integration). Other providers are not fallback routes.

Start the dedicated backend in a terminal:

```sh
~/src/aghist/scripts/opencode-web
```

Keep this terminal running. The launcher starts a local server at `http://127.0.0.1:4096` with a separate configuration and working directory. It uses OpenCode's existing credential store.

In another terminal, check the connection:

```sh
cd ~/src/aghist
uv run aghist doctor
```

`doctor` checks configuration without a model call. Success does not confirm subscription eligibility; only a live request can do that.

Use the browser opened by the launcher to inspect sessions. To attach OpenCode's terminal interface to the same server, run:

```sh
opencode attach http://127.0.0.1:4096
```

If you configure a different port with `AGHIST_PORT`, pass its URL to `doctor`, `run`, and `resume` with `--server` and use that URL for attachment. If the backend has a password, provide `OPENCODE_SERVER_PASSWORD` to the coordinator environment as well. Provide `OPENCODE_SERVER_USERNAME` too if you changed the default username.

## Run one small batch

With the backend running and Go active, start a one-case pilot:

```sh
uv run aghist run --library ~/src/aghist-example \
  --brief 'Investigate one bounded historical case and seek contrary evidence.' \
  --max-cases 1 --minutes 30
```

The brief directs this batch. The question supplies its definitions, scope, component claims, and assessment criteria. Use `--brief-file /absolute/path/brief.md` instead of `--brief` for a longer objective.

One invocation runs one bounded batch. Increasing its time allowance does not repeat batches or convert an entire corpus. Discovery can return no suitable candidates. Supporting, invalidating, mixed, irrelevant, and unresolved conclusions can all complete normally.

### Use an existing corpus

Supply each read-only source directory or text file with `--source`:

```sh
uv run aghist run --library ~/src/aghist-example \
  --source /absolute/path/corpus \
  --brief 'Use the supplied corpus to investigate one case, checking its sources and contrary evidence.' \
  --max-cases 1 --minutes 30
```

Replace the corpus placeholder with an existing path; repeat `--source` for additional inputs. Inputs and output must be separate. The engine rejects ancestor/descendant overlaps. Each new run needs its source paths explicitly; resumption uses the recorded paths.

Earlier dossiers supply leads and provenance. The researcher can reuse checked historical extracts while preserving their original attribution and inspection limits. Review packets omit earlier case verdicts. Several old files can inform one case, and one file can supply several episodes.

Put topic-specific source rules in the question or brief. A library's guidance files are not automatically loaded into agent instructions. Local text and OpenCode's supported web retrieval are available; inaccessible PDFs and missing scans remain gaps. This version has no OCR pipeline.

## Inspect the results

The coordinator reports progress and prints the run directory on success. Inspect these records before increasing the batch size:

- The case account, source evidence, retrieval failures, and inspection limits.
- Both reviews and the reconciled assessment, including unresolved disagreement.
- The question and evidence revisions named by the assessment.
- The batch summary and any proposed working question versions.

See [saved records](../DESIGN.md#saved-records) for their locations. Retain the run's job records; completion checks depend on the accepted outputs saved there.

Read local status without contacting OpenCode:

```sh
uv run aghist status --library ~/src/aghist-example
```

| Case status | Meaning |
| --- | --- |
| `reviewed` | A valid completed assessment covers the principal question version and latest evidence revision. |
| `outdated` | A valid completed assessment exists, but none covers that current combination. |
| `unfinished` | No valid completed assessment is available. |

These labels describe saved workflow records. Completion does not establish historical validity. Offline status also cannot detect later input in remote OpenCode sessions.

## Revise a question

Runs use the principal question by default. Agents can save working proposals at the end of a batch, based on that batch's reconciled summaries. Synthesis does not yet review the accumulated library.

To add your own revision, write a new Markdown file outside the library's frozen version files. Include its wording, definitions, scope, components, criteria, and reason for the change. Then save it as a working version:

```sh
uv run aghist question --library ~/src/aghist-example \
  --question-id technology-and-work --parent v001 \
  --file /absolute/path/revised-question.md
```

The command prints the next version ID. In the following examples, replace `v002` with that ID if it differs. To test the working version, name it explicitly in a new run:

```sh
uv run aghist run --library ~/src/aghist-example \
  --question-id technology-and-work --version v002 \
  --brief 'Investigate a case that could challenge the revised definitions.' \
  --max-cases 1 --minutes 30
```

To make it the principal version, adopt it:

```sh
uv run aghist adopt --library ~/src/aghist-example \
  --question-id technology-and-work --version v002
```

Saving a proposal alone does not change principal-version status. Adoption can make earlier assessments outdated. It does not automatically reassess cases.

### Reassess an existing case

Use `--case` to assess a known case against a selected question version:

```sh
uv run aghist run --library ~/src/aghist-example \
  --question-id technology-and-work --version v002 \
  --case descriptive-case-id \
  --brief 'Assess this case under the revised definitions.'
```

Replace `descriptive-case-id` with its case folder name. Reassessment reuses the saved evidence revision and retains earlier assessments. Add `--refresh` and the needed `--source` paths to retrieve evidence and append a revision instead.

Append question and evidence versions rather than editing frozen records in place. Changed records fail validation or lose reviewed status. Discovery records known duplicates without automatically merging cases by title or URL.

## Limits

One case is processed at a time. Only its two reviewers run concurrently; other stages run singly. A coordinator lock applies across libraries, and startup checks for surviving aghist jobs on the backend. Workers cannot spawn agents.

| Setting | Default or limit |
| --- | --- |
| Candidates per batch | Default 3; `--max-cases` accepts 1–3. Zero discovered candidates is valid. |
| Run allowance | `--minutes 30` |
| Task allowance | `--task-seconds 600` |
| Observed tool-call limit | `--max-tools 16` |
| Review packet | At most 256,000 bytes |

Time and tool bounds are checked during execution. A task in flight can briefly exceed a bound while the next status check or HTTP request finishes. Source selection must fit the packet limit; reviewers receive no file or web tools.

This version has no continuous campaign, scheduler, or process supervisor. Inspect a live pilot before attempting longer unattended work.

## Recover unfinished work

To interrupt a run, press Ctrl+C in the coordinator terminal. Saved work remains available for resumption. Keep the backend running when inspecting a submitted job.

Run `status` to find the unfinished run ID, then resume it. Replace the example ID below with the folder name shown in your library:

```sh
uv run aghist resume --library ~/src/aghist-example run-20261012-120000-abcdef
```

Resumption reuses the recorded brief, source paths, question, and valid completed stages. Each invocation gets another allowance of the run's saved number of minutes. Per-task deadlines include time spent interrupted; completed remote results are collected before rejecting an expired task.

The selected model must match the recorded model. If you started a run with a non-default Go route using `--model`, supply that same route on resume.

| Situation | Action |
| --- | --- |
| Backend unavailable or profile rejected | Start the supplied launcher and run `doctor` again. Check the [integration notes](../DESIGN.md#opencode-integration) for the version tested. |
| Active current aghist job from another run | Resume its owning run or stop the job in OpenCode before starting other work. |
| Active superseded attempt | Stop that attempt in OpenCode. Resumption admits only the latest attempt for each job. |
| Confirmed failed, stopped job | Fix the cause, then use `resume ... --retry-failed` for one additional attempt. |
| Submission outcome uncertain | Inspect its saved session. Resume inspects recorded activity before submitting; if it cannot establish the outcome, it stops. |
| Subscription, permission, output-validation, or runtime failure | Read the stopping reason and saved messages. Resolve the cause before retrying. There is no provider or billing fallback. |

An uncertain attempt is never silently repeated. If its outcome cannot be resolved, preserve it and deliberately start a new run only after confirming its old session has stopped. See [recovery contracts](../DESIGN.md#recovery-contracts) for the checkpoint rules.

Inspect engine-owned sessions in OpenCode without sending input. Use separate sessions for manual exploration. Interrupt the coordinator before steering one of its sessions; outside input still invalidates that attempt, including a completed result reused during resumption.
