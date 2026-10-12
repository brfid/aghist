# aghist

A minimal Python engine for agent teams investigating historical causal claims, using OpenCode for agent execution and the author's subscription for model access.

The [design](DESIGN.md) owns requirements, proposed behavior and open decisions. Read [AGENTS.md](AGENTS.md) before implementation. Use pytest and Google-style docstrings for non-trivial objects.

Research data belongs in separate topic libraries. The first is [aghist-tech-adoption](../aghist-tech-adoption/README.md), which owns its questions, cases, source records, assessments and manuscript.

The current checkpoint establishes the project and design. The first implementation will include web discovery, source retrieval and two independent case evaluations, starting with DeepSeek V4.1 Flash through OpenCode Go. Agents may test working question versions; the author chooses the principal version.
