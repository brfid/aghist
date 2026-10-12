# aghist development

- Read README.md and DESIGN.md first. DESIGN.md owns requirements and architecture decisions; docs/usage.md owns operating procedures. Update the authoritative document when behavior or a decision changes, and link to it rather than duplicating details.
- Build the reusable engine here. Topic questions, cases, source evidence and manuscripts belong in independent library repositories supplied by path.
- Use Python and pytest. Use Google-style docstrings for non-trivial functions, classes and other objects.
- Run research agents through OpenCode and the author's subscription. DESIGN.md owns the selected model route. Include discovery and source retrieval in the first working loop.
- Agents may create and test working question versions; the author chooses the principal version.
- Keep the implementation minimal and robust. Make the basic workflow work before adding optional features or frameworks.
- Keep tests meaningful: question-version references, independent reviews, evidence revisions, interruption recovery and preservation of existing records. Use temporary libraries and fake workers for offline tests.
- Preserve research-question versions and identify them in every assessment. Treat invalidating cases as seriously as supporting cases. Do not turn agent agreement into source corroboration.
- Preserve uncommitted and untracked work. Make coherent local checkpoint commits after appropriate verification. Push only when explicitly requested.
- Keep documentation task-focused and plain. Follow the [Google developer documentation style guide](https://developers.google.com/style/) where it helps clarity; introduce basic tasks before recovery details or implementation rationale.
