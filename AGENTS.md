# Agent Guidance

## Project context

This repository is a Copier template for generating minimal, Python, Go,
frontend, CLI, API, and full-stack starter projects.

The root `README.md` is the canonical documentation for this template
repository. Keep it up to date whenever supported answers, generated layouts,
commands, generated files, Docker/CI behavior, or validation expectations change.

## Documentation policy

- Update `README.md` in the same change as any template behavior change that
  affects users or maintainers.
- Keep command examples aligned with generated `README.md` output and CI.
- Do not add separate documentation files unless explicitly requested; prefer
  improving the root README.

## Scratchpad policy

Use `.scratchpad/` for temporary scripts, experiments, generated samples, and
throwaway work. Do not commit scratchpad contents unless explicitly requested.

## Validation

Before handing off changes, run:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

When validating rendered projects manually, render them outside this template
checkout.

## Safety

Do not put provider credentials, API keys, or external secrets in tracked files.
