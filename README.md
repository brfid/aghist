# aghist

aghist coordinates small teams of agents to investigate historical causal claims. It gathers sources, prepares case accounts, obtains two independent reviews, and saves the results in a separate research library. Each assessment identifies the question version and evidence it used. Agents can propose question revisions; the researcher chooses the principal version.

This is an experimental first version. Offline tests and limited OpenCode protocol checks have passed. Live source retrieval and the quality of model-generated research still need an inspected pilot. See [verification and limits](DESIGN.md#verification-and-limits).

## Setup

Install Python 3.11 or later and [uv](https://docs.astral.sh/uv/), then get the engine:

```sh
git clone https://github.com/brfid/aghist.git ~/src/aghist
cd ~/src/aghist
uv sync --locked
```

The engine repository contains software and documentation. Questions, cases, evidence, and manuscripts belong in separate libraries.

## Create an example library

Library creation and inspection work without OpenCode or model calls. From the engine directory, use the [sample question](examples/question.md) to create a library:

```sh
uv run aghist init --library ~/src/aghist-example \
  --question-id technology-and-work \
  --question-file examples/question.md \
  --purpose 'Explain when and how changes in work contribute to technology adoption.'
uv run aghist status --library ~/src/aghist-example
```

The output directory must be empty or absent. These commands create question version `v001` and report `Principal: technology-and-work v001`. They create no historical cases.

To investigate a case, continue with [Run historical research](docs/usage.md). That guide covers OpenCode Go setup, read-only source corpora, inspecting results, question revisions, and recovery.

## Develop the engine

Read [AGENTS.md](AGENTS.md) for development rules and [DESIGN.md](DESIGN.md) for requirements, methodology, architecture, and record contracts.

```sh
uv sync --locked --dev
uv run pytest
```

Tests use temporary libraries and deterministic workers or API fixtures. They make no model calls.

For command options, run `uv run aghist --help` or `uv run aghist run --help`.
