# aghist design

This file owns the engine's requirements, research approach, and architecture decisions. It describes the first implementation as of 12 October 2026. Proposed extensions appear under [Later work](#later-work). For commands and operating limits, use [Run historical research](docs/usage.md).

## Purpose and boundaries

The engine investigates general historical causal claims, initially by explaining **when and how** they hold. A historical case is the basic unit. Every assessment applies an exact question version to a particular revision of the case and its evidence.

The engine repository owns software, tests, agent instructions, and documentation. Independent topic libraries own their purpose, question versions, cases, evidence, assessments, and manuscripts. Existing research is an explicitly supplied read-only input to an ordinary run; new records go to a separate library. Input and output paths must not overlap. Shared archival originals can remain at external locations with precise provenance.

Topic-specific definitions and source rules belong in the question or brief. The reusable workflow does not inherit an earlier corpus's layout or eligibility template. Reorganizing files does not itself validate a case or authorize publication.

## Research approach

The initial target is **contingent generalization**: an explanation whose mechanisms and applicability depend on historical circumstances. This is an aim of inference, not a complete method. The first version supports case comparison and within-case inquiry; it does not estimate prevalence in a historical population.

The author's inspiration from Brenner's Center for Social Theory and Comparative History informs a comparative-historical orientation. [UCLA's description](https://socialsciences.ucla.edu/research-centers/) connects historically rooted social theory with theoretically informed comparative history. It does not prescribe a single method or commit the project to a substantive theory.

| Approach | Contribution |
| --- | --- |
| Comparative-historical analysis | Compare similar and contrasting settings, practices, and sequences to develop and challenge explanations. |
| Process tracing | Examine a case's sequence and diagnostic evidence to assess a mechanism and alternatives. |
| Abductive refinement | Use surprising cases and mismatches to propose better concepts or explanations. |
| Typological theorizing | Develop bounded explanations for combinations of conditions and mechanisms. |
| Qualitative Comparative Analysis (QCA) | A possible later method once case selection and coding warrant it; calibration requires additional research decisions. |

These approaches inform the research practice. They are not separate software modes or mechanically enforced methods.

Methodological sources previously inspected: Falleti and Mahoney, [“The comparative sequential method”](https://www.cambridge.org/core/books/abs/advances-in-comparativehistorical-analysis/comparative-sequential-method/4EA22A74E138226321803CDBDE27618E) (2015), publisher summary; Collier, [“Understanding Process Tracing”](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1) (2011), online abstract and opening discussion; Bennett, [“Drawing Contingent Generalizations from Case Studies”](https://www.cambridge.org/core/books/case-for-case-studies/drawing-contingent-generalizations-from-case-studies/58F73BA16250FECBE4D7EE8F5F02943E) (2022), online chapter; Tavory and Timmermans, [*Abductive Analysis*](https://press.uchicago.edu/ucp/books/book/chicago/A/bo18785947.html) (2014), publisher description, not the full book; Ragin's [QCA introduction](https://sites.socsci.uci.edu/~cragin/fsQCA/), inspected in full. This coverage informs the approach; it does not validate the machine.

### Questions and refinement

A library has a stable research purpose and named questions with immutable numbered versions, such as `v001` and `v002`. Each version preserves its wording, definitions, scope, component claims, assessment criteria, parent, and reason for change. Git history supplements these identifiers; a commit alone does not identify the question in an assessment.

For example, “new technologies often require organizational change to utilize them well” contains several issues: new to whom, which changes, what benefit, necessity versus contribution, the mechanism, and frequency among which cases. Keep them explicit. A narrower outcome or a weaker causal claim requires a visible revision.

Agents can propose and test working versions. Only author adoption changes the principal pointer in `library.json`. Testing uses an explicitly selected version and preserves earlier assessments. Creating a proposal alone does not change principal-version review status. Adoption or a new evidence revision can leave cases without a current assessment.

Empirical cases can suggest more specific meanings of an outcome, recurring mechanisms, or useful contrasts. A refinement proposal records changed wording and scope, motivating cases, contrary evidence, effects on judgments, and a next inquiry that could challenge it. Identify cases used to develop a version. A higher proportion of supportive cases is insufficient reason to narrow the question.

The stable purpose anchors refinement. A different outcome, population, or purpose needs an explicit branch and rationale. Frequencies describe the collected cases; a selectively assembled collection cannot establish general prevalence. Reassess affected and formerly excluded cases deliberately, preserving current and earlier conclusions.

### Cases and evidence

A case account describes a bounded episode or coherent comparison: actors, setting, sequence, practices, outcomes, and uncertainties. It remains separate from question-specific judgments. Link retellings of the same episode rather than counting them as independent observations.

Assess source fidelity, relevance, supported and unobserved mechanism steps, alternatives, invalidating evidence, and limits. A case can support one component and qualify another. Favorable outcomes, causal support, and source quality are separate judgments. A credible attributed account can contribute without a numerical measure or a complete causal test. The engine imposes no universal requirement for controlled comparisons, large effects, or independent corroboration.

Benefits without a new work change can challenge necessity, or reveal an already suitable arrangement. Failure despite a change bears on sufficiency and scope; it does not alone disprove necessity. Missing evidence and failed retrieval do not establish absence. Distinguish source observations, testimony, source explanations, and agent inferences.

Invalidating, adverse, mixed, and unresolved cases receive the same seriousness and source standards as supporting cases. Agent agreement is not independent historical corroboration.

## Workflow and responsibilities

Python coordinates and accepts records. OpenCode executes the agent jobs.

1. A discovery session selects candidates under the fixed brief and question version, seeking informative contrasts.
2. A researcher retrieves sources and prepares each bounded case with provenance and inspection limits.
3. Two fresh evaluators independently assess the same frozen packet. Neither sees the other's review or prior case verdicts.
4. A reconciler considers the packet and both reviews, preserving unresolved disagreement and useful follow-up.
5. A synthesis session considers this batch's reconciled summaries and can propose grounded working question versions.

There are four agent sessions per case, plus discovery and synthesis sessions per batch. Cases proceed one at a time; only the reviewers run concurrently. Workers cannot delegate. A global coordinator lock and a backend check for surviving jobs bound engine-managed concurrency.

Agents return proposals and structured results. Python validates them, supplies authoritative identifiers and references, and writes accepted files. Schema validity establishes structure, not historical truth. Valid supporting, invalidating, mixed, irrelevant, and unresolved judgments can all satisfy workflow completion.

### Architecture decisions

| Decision | Reason and consequence |
| --- | --- |
| Thin Python workflow, OpenCode adapter, file store, and CLI | Separate execution, persistence, and coordination without a general agent framework or plugin interface. |
| Connect to a separately started OpenCode HTTP server | Shared session IDs support inspection, cancellation, and recovery through the same browser or terminal UI. The engine does not own backend startup or restarts. |
| Keep reconciliation for each case | Preserve both raw reviews and disagreement under a clear completion contract. Conditional or batch-only reconciliation would couple completion to additional decisions. |
| Use files and folders as research memory | Keep records browsable and reconstruct state by scanning them. A maintained case index or database adds a second source of truth. |
| Enforce explicit bounds and retries | Deadlines, tool limits, and recorded outcomes give concrete stopping rules. A model-driven stagnation controller can wait. |
| Hash only the frozen review packet | One checksum detects changed inputs without a content-addressed store or per-file hashing system. |

## Saved records

```text
library.json                         # stable purpose and principal question
questions/<question>/versions/v001.md
cases/<case>/case.md                  # navigation to the latest account
cases/<case>/revisions/r001/
  case.json / case.md
  evidence.json
  retrieval.json
cases/<case>/assessments/<question>/<version>/<run>/
  packet.json
  review-a.json / review-a.md
  review-b.json / review-b.md
  assessment.json / assessment.md
  complete.json
runs/<run>/run.json                   # operational state
runs/<run>/jobs/<stage>/attempt-001/
  request.json
  state.json
  messages.json
  result.json
runs/<run>/synthesis.json
runs/<run>/summary.md
```

JSON owns structured results and metadata; Markdown renders support browsing. Assessments identify the case, question version, evidence revision, and components addressed. Descriptive case folder names remain stable across classifications. Original attempt outputs, numbered questions, and evidence revisions are preserved; changed evidence receives a new revision and assessment.

OpenCode sessions support inspection and recovery. The library files are the durable research record. Job records remain necessary for validating accepted judgments; do not discard them while retaining completion receipts.

### Evidence and completion contracts

Save actual retrieval outputs, including failures and truncation metadata. A generated bibliography or paraphrase alone is insufficient. Selected excerpts must match returned text at the reported origin. A fetched page demonstrates retrieval, not the truth of a causal interpretation or preservation of an original PDF.

Earlier dossiers are ordinary research inputs. Review packets retain substantive source evidence, contradictions, and qualifications while omitting inherited verdicts. Previously checked quotations can be retained extracts, labeled as prior inspection with attribution and limits. They must not be described as a fresh reading of the original. No migration adapter or automatic wholesale conversion is needed.

Both reviewers receive identical saved packet bytes: the exact question, neutral account, selected retrieved evidence, provenance, and known limits. They have no file or web tools, peer verdicts, or inherited project instructions. More evidence requires a new packet and fresh reviews. Source text is evidence rather than operational instruction.

One SHA-256 checksum detects packet changes. Completion also checks exact numbered question text, frozen case/evidence data, distinct review sessions, required judgments, and their accepted job outputs. Python writes an explicit completion receipt atomically. File existence or schema validity alone cannot establish completion.

### Recovery contracts

Persist session and message identifiers before submission. After an ambiguous network failure, inspect recorded remote activity before submitting again. A client-supplied message ID is not assumed to establish provider idempotency.

Empty attempt folders or interrupted atomic-write temporary files precede submission and can be reused. Other missing request records stop for inspection. When the initial state checkpoint is missing, only an empty idle recorded session is eligible for initial submission; existing activity is collected without resubmission.

Startup checks active aghist jobs on the dedicated backend. Jobs from another run or a superseded attempt block new work; only current attempts of the resumed run are admitted. A local lock alone cannot bound jobs that survive a coordinator crash or failed cancellation.

Completed stages are reusable only while their inputs and outputs remain valid. Resumption checks remote messages even for cached completed jobs, detecting outside UI input. Offline status validates local records only. Unknown submission outcomes remain explicit and unfinished; only a confirmed failed, stopped job is eligible for the bounded extra attempt.

## OpenCode integration

The selected default is **`opencode-go/deepseek-v4.1-flash`**. The model list and Go configuration were checked with OpenCode **1.18.35** on 11 October 2026. This pins a checked route; it does not establish current subscription eligibility or claim that it is still the newest release. Check a newer route deliberately before changing the default. Resumption requires the same model route.

The supplied launcher separates backend configuration and working context from research inputs and ambient project instructions. Session permissions allow scoped local reads and web search/retrieval for researchers. Analysis roles have no tools; workers cannot edit files, use a shell, or spawn agents.

The adapter validates generated JSON locally. It omits the deprecated prompt `tools` field because [OpenCode 1.18.35's implementation](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/session/prompt.ts) replaces session permissions when that field is present. Scoped session permissions preserve the role boundary.

OpenCode's [server](https://opencode.ai/docs/server/), [permissions](https://opencode.ai/docs/permissions/), [tools](https://opencode.ai/docs/tools/), and [Go documentation](https://opencode.ai/docs/go/) describe the available mechanisms. Check installed behavior when changing OpenCode versions; documentation alone does not validate this workflow.

## Verification and limits

As of 12 October 2026, **56 pytest tests pass without model calls**. Temporary libraries and deterministic workers or API fixtures exercise version and evidence references, independent reviews, invalidating conclusions, source preservation, partial writes, concurrent writers, uncertain submissions, remote completion, UI input, and permission/time/tool/subscription stops.

Installed-API checks with `noReply=true` verified message identifiers and permission preservation without generation. The initial live request was rejected for an inactive Go subscription and aborted. The pilot remains deferred until the author reactivates Go. Live source retrieval, model output quality, and historical validity remain unverified.

The current implementation runs one manually started batch per invocation. Synthesis uses that batch's reconciled summaries, not the accumulated collection or its full evidence. There is no OCR pipeline, automatic full-corpus conversion, or corpus-wide reassessment queue.

## Later work

Long-running collection would repeat the same small batches under a fixed campaign brief, question version, and outer deadline. It would need a persistent work queue, stopping rules for repeated empty or inaccessible leads, and deliberate reassessment selection. Longer time allowances alone do not provide this behavior.

A proposed first unattended trial was four hours, retaining the current concurrency and batch bounds and stopping after two batches with no informative progress. Tune these choices after an inspected live pilot. Scheduling, host/process supervision, accumulated-case synthesis, additional providers, and rebuildable search indexes remain later decisions tied to observed needs.
