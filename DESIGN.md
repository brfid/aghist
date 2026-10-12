# Agentic historical research engine

Design discussion, 11 October 2026. This is the authoritative design for `aghist`. Requirements are recorded below; proposed operating choices remain labeled. The first topic is maintained independently in [aghist-tech-adoption](../aghist-tech-adoption/README.md).

## Purpose and repository boundaries

Build a reusable agentic tool for investigating general historical causal claims, initially by explaining **when and how** they hold. The basic research unit is a historical case. Each evaluation applies a specific version of a research question to a particular revision of that case and its evidence.

- **aghist** owns Python software, pytest tests, agent instructions and this design. It accepts a library path rather than containing a particular topic's cases or source rules.
- **A topic library** owns its research purpose, question versions, case folders, source records, assessments, synthesis and any associated manuscript. The first library is `~/src/aghist-tech-adoption`.
- The existing public site continues to own approved publication copies and site implementation. Large archival originals may remain at the exact external paths recorded by a library.

The engine and library are separate local Git repositories. The engine must be usable with another topic by supplying that topic's question and source guidance, without changing its workflow code. Topic-specific definitions belong in the library rather than the engine's prompts or schemas.

## Settled requirements

1. Use a team of agents for ongoing discovery, source inspection, evaluation and refinement.
2. Treat a historical case as the basic unit; save each case in its own descriptive folder.
3. Record exactly which research-question versions each case has been assessed against. Preserve useful iterations and variants of the question.
4. Have more than one agent evaluate each case. The proposed minimum is two independent evaluations, beyond preparing the case.
5. Use empirical cases collectively to improve definitions, identify recurring outcomes and mechanisms, and propose more precise questions.
6. Collect and investigate invalidating cases as seriously as supporting ones. Preserve mixed and unresolved evidence.
7. Reassess cases after substantive changes to a question or its definitions, and after relevant evidence changes.
8. Use files and folders as durable research memory wherever this avoids a separate maintained index.
9. Implement in Python, use **pytest**, and use **Google-style docstrings for non-trivial functions, classes and other objects**.
10. Keep the first implementation minimal and robust. Build one working research loop before adding optional infrastructure or conveniences.

## Methodological approach

The agreed initial target is **contingent generalization**: causal explanations whose mechanisms and applicability depend on historical circumstances. This is a kind of inference to pursue, not a complete research method by itself.

The author's earlier inspiration from Brenner's Center for Social Theory and Comparative History suggests a broader comparative-historical orientation. UCLA describes the center as connecting historically rooted social theory with theoretically informed comparative history. That institutional aim supports the orientation; it does not prescribe a single method or commit this project to a particular substantive theory. [UCLA's description](https://socialsciences.ucla.edu/research-centers/).

Several approaches can work together:

| Approach | Use in this program |
| --- | --- |
| Comparative-historical analysis | Compare similar and contrasting historical settings, practices and sequences to develop and challenge explanations. The comparative sequential method explicitly connects comparison across cases with analysis within them. |
| Process tracing | Examine the sequence and diagnostic evidence within a case to assess a proposed mechanism and alternatives. |
| Abductive refinement | Use surprising cases and mismatches between expectations and evidence to propose better concepts, questions or explanations. |
| Typological theorizing | Group cases by combinations of conditions and mechanisms, developing bounded explanations rather than forcing one generalization across all settings. |
| Qualitative Comparative Analysis (QCA) | A possible later method for comparing combinations of conditions once the case set and coding rules warrant it. Formal set membership and calibration would be additional research decisions; QCA is outside the first implementation. |

Recommended starting practice: comparative historical cases, within-case mechanism assessment and explicit proposals for empirical refinement. These are intellectual practices supported by the same simple case-review workflow, not separate software modes.

Sources inspected: Falleti and Mahoney, [“The comparative sequential method”](https://www.cambridge.org/core/books/abs/advances-in-comparativehistorical-analysis/comparative-sequential-method/4EA22A74E138226321803CDBDE27618E), *Advances in Comparative-Historical Analysis* (2015), publisher summary; Collier, [“Understanding Process Tracing”](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1), *PS* 44(4) (2011), online abstract and opening discussion; Bennett, [“Drawing Contingent Generalizations from Case Studies”](https://www.cambridge.org/core/books/case-for-case-studies/drawing-contingent-generalizations-from-case-studies/58F73BA16250FECBE4D7EE8F5F02943E), *The Case for Case Studies* (2022), online chapter; Tavory and Timmermans, [*Abductive Analysis*](https://press.uchicago.edu/ucp/books/book/chicago/A/bo18785947.html) (2014), publisher description, not the full book; Ragin's [QCA introduction](https://sites.socsci.uci.edu/~cragin/fsQCA/), inspected in full. These inform the proposed method, not evidence that the machine has been validated.

## Versioning the research question

A library keeps a stable research purpose, then one or more named questions. Each question has immutable numbered versions such as `v001`, `v002`. A version preserves the exact wording, definitions, scope, component claims or variants, assessment criteria, parent version and reason for revision. Any changed substantive text receives a new version. Git preserves ordinary editing history; a Git commit alone is insufficient as the question identifier in a case assessment.

An assessment identifies `question_id`, `question_version`, `case_id`, the case/evidence revision and the component claims it addresses. One case can be evaluated against several question versions and several components within a version. The cases assessed under a version can be found by scanning their assessment folders and fields.

A question's current record points to its adopted version and identifies any working variants. Agents should maintain useful working iterations. **Which working versions agents may test or adopt without human selection remains open.** The recommendation is that agents may propose and test working versions while the author selects the principal question.

For example, “new technologies often require organizational change to utilize them well” contains separate issues: new to whom, which work changes, what benefit, whether a change is necessary or contributory, through which mechanism, and frequent among which cases. Keep those components explicit rather than silently replacing necessity with helpfulness or a particular outcome with a broader one.

## Cases, evidence and assessment

A case account describes a bounded historical episode or coherent comparison: actors, setting, sequence, practices or interventions, outcomes and uncertainties. It is separate from evaluations against particular questions. Multiple retellings of the same episode are linked rather than treated as independent observations.

Assessments explain source fidelity, relevance to the question's scope, the mechanism steps supported or unobserved, alternative explanations, invalidating evidence, and the limits of the account. A case can support one component, qualify another and remain inconclusive on a third. Favorable outcomes, causal support and source quality are separate judgments. A credible attributed account can contribute without a numerical measure or a complete causal test.

Evaluators must assess the question's actual wording. Benefits without a new work change can challenge a necessity claim, but may reveal an already suitable arrangement. Failure despite a work change bears on sufficiency and scope; it does not alone disprove necessity. Missing evidence or failed retrieval is not evidence that an event did not occur.

The library's existing research criteria govern its case inclusion. The engine should not impose universal demands for controlled comparisons, large effects or independent corroboration. The strength of a case's contribution to a particular generalization is a separate assessment.

## Minimal team workflow

Use a coordinator, researchers, two independent evaluators and a curator/reconciler. The coordinator may also curate and synthesize; roles need not be permanently running processes.

1. Select a bounded investigation addressing a useful uncertainty or comparison.
2. Gather sources and prepare a case account plus an evidence packet with exact provenance and locators.
3. Give two fresh evaluators the same question version and evidence revision, with prior verdicts omitted from the review packet. Neither sees the other's verdict before submitting. Both examine the full rubric, including rival explanations and invalidation.
4. Reconcile the reviews into an assessment, preserving unresolved disagreements and naming any useful follow-up. Agreement among agents is not independent historical corroboration.
5. Periodically compare reviewed cases and propose informative next investigations or question refinements.

Separate input packets and access controls should enforce review independence. A researcher summary alone does not replace accessible original evidence. Concurrent workers write separate outputs; one curator writes the accepted account and assessment. A case becomes reviewed for a version only after the required valid evaluations and reconciled assessment exist.

Collection proceeds in bounded, resumable batches with explicit call/spending limits, retrieval limits and stopping rules. Invalidating, adverse and mixed cases receive the same seriousness and source standards as supporting cases. Discovery routes should seek meaningful contrasts rather than only sources already endorsing the proposition. The goal is informative evidence, including evidence that weakens an explanation.

## Empirical refinement and protection against drift

Refining the question is part of the agents' research work. In the technology example, the cases may reveal recurring senses of “utilize well”: lower downtime, improved quality, reduced material use, or easier coordination. Agents should propose distinctions grounded in identifiable cases rather than require all outcomes to fit a fixed vocabulary in advance.

Aggregate descriptions may identify a more specific and more frequent variant **within the collected, reviewed cases**. Record the category definition, missing information and the cases it includes. Frequencies in a selectively assembled collection do not establish prevalence across all historical adoptions. The initial priority remains when and how; population frequency estimation is deferred.

Each refinement proposal gives old and new wording, motivating cases, changed definitions or scope, effects on previous judgments, contrary cases and the next inquiry that could challenge it. Preserve useful alternative versions rather than forcing one formulation prematurely. A narrower scope requires a substantive explanation; a higher proportion of supportive cases is insufficient justification.

The author's purpose anchors the inquiry. A different outcome, population or purpose should be identified as a different branch. Cases used to develop a version are identified as development evidence; additional comparisons can then examine it. Reassess affected cases, including formerly excluded cases, when a substantive version changes. Keep old assessments and distinguish current, outdated and unreviewed work in synthesis.

## Library layout

```text
README.md
notes.md
questions/
  technology-and-work/
    question.md
    versions/v001.md
cases/
  electric-motors-and-factory-layout/
    case.md
    sources/
    assessments/
      technology-and-work/
        v001/
          review-a.md
          review-b.md
          assessment.md
supporting/
article/
```

This illustrates the first library, not mandatory technology-specific engine fields. A question version can also be marked as a working proposal. Exact record serialization is an implementation choice; stable identifiers, version references and evidence revisions are required. A new assessment of changed evidence goes in a distinct assessment revision or run folder; it never overwrites earlier reviews.

Folders retain descriptive names regardless of classification. A folder scan finds cases, assessments and pending reassessment; a separate maintained case index is unnecessary. Any later search index must be rebuildable from authoritative files. Shared source originals can stay outside case folders with precise references. A small amount of operational state records attempts, expenditure and running work; it must not become a second catalogue of research knowledge.

The initial library preserves earlier case verdicts and their original scope. Moving a record into a case folder or creating the first question version does not turn those verdicts into completed evaluations under the new engine.

## First implementation and verification

Python is selected. Recommend a thin runner that takes a library path, reads a question version, obtains two independent evaluations, saves an assessment and resumes interrupted work. Whether the first live slice also discovers new sources remains open. Start with one model provider and only the tools required for that slice. OpenCode can be considered as a worker environment if it simplifies the chosen tasks; it is not a requirement.

Use pytest for meaningful checks of version immutability, references to the intended case/question/evidence revision, completion requiring two evaluations, preservation of earlier assessments, stale-review detection, and resumption after interruption. Model failures and invalid outputs must leave work explicitly unfinished. Use temporary libraries and a deterministic fake worker for offline tests; separately inspect a few real outputs before trusting a live run. Python correctness tests do not establish historical validity.

Use Google-style docstrings for non-trivial objects, explaining behavior, arguments, returns and exceptions where useful. Prefer straightforward functions and a small number of modules. No dashboard, database, search index, plugin framework or multi-provider framework is needed for the first working loop. Add capabilities only when the basic workflow exposes a concrete need.

## Clarifications before implementation

1. **Question authority:** may agents create and test working versions while the author chooses the principal version, may they adopt revisions within a defined scope, or should all changes wait for author selection?
2. **First live slice:** review selected existing cases first, or include discovery and retrieval from the beginning?
3. **Live model and budget:** which provider/model and total spending cap should the first paid pilot use? MiniMax and a $25–50 ceiling were discussed but not selected.

These are the remaining decisions with immediate implementation consequences. The next step is to settle them, then implement and verify one complete loop in this repository against the separate library.
