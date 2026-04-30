# Stackseed

A local [Copier](https://copier.readthedocs.io/) template for generating small
projects with stack-aware documentation, validation commands, and GitHub Actions
CI. The template can create backend-only, frontend-only, full-stack, CLI, and
minimal starter projects without running post-generation scaffold fetchers.

## What this template generates

Every generated project includes:

- `README.md` with project-local setup and validation commands
- `AGENTS.md` and `.agents/project-context.md` with generic contributor
  guidance, including Conventional Commits message format
- `.scratchpad/.gitkeep` for ignored temporary work
- `.gitignore` and `.editorconfig`
- `.github/workflows/ci.yml` for GitHub Actions

Optional stack choices add only the files and commands for the selected stacks:

| Area | Supported choices |
| --- | --- |
| Backend | Python, Go, or none |
| Backend mode | Library/service or CLI |
| Python CLI framework | `argparse` or `click` when Python CLI mode is selected |
| Frontend | Solid + Vite + TypeScript + Tailwind v3 + shadcn-solid, or none |
| CLI config scaffold | Enabled or disabled for generated CLI projects |
| CI provider | GitHub Actions |

## Generated project layout

Generated projects keep shared files such as `README.md`, `AGENTS.md`,
`.agents/`, `.scratchpad/`, `.gitignore`, `.editorconfig`, and
`.github/workflows/ci.yml` at the project root.

Single-stack projects keep the selected stack at the project root:

- Python-only projects place `pyproject.toml`, `src/`, and `tests/` at the
  root.
- Go-only projects place `go.mod`, `cmd/`, and `internal/` at the root.
- Frontend-only projects place `package.json`, Vite/TypeScript/Tailwind
  configuration, `index.html`, and `src/` at the root.

Full-stack projects use stack directories while keeping shared files at the
root:

- Backend assets are generated under `backend/`.
- Frontend assets are generated under `frontend/`.
- Backend validators run from `backend/`.
- Frontend validators run from `frontend/`.

## Requirements

To work on this template repository:

- `uv` for Python dependency management and test execution
- Python 3.11 or newer
- Copier, usually through `uvx copier`
- Ruff and pytest, installed by `uv sync --dev`

To validate generated projects, install the tools for the stacks you select:

- Python projects: `uv`
- Go projects: Go 1.22 or newer
- Frontend projects: Node.js and `pnpm`

## Template repository setup and validation

Install the template repository's development dependencies:

```sh
uv sync --dev
```

Run the template test suite:

```sh
uv run pytest
```

Run lint and format checks:

```sh
uv run ruff check .
uv run ruff format --check .
```

## Generate a project

From this repository, render a new project into a directory outside the template
checkout:

```sh
uvx copier copy --trust /path/to/stackseed ./my-project
```

If Copier is already installed, this also works:

```sh
copier copy --trust /path/to/stackseed ./my-project
```

For noninteractive generation, pass answers with `--data`:

```sh
uvx copier copy --trust --defaults \
  --data project_name="Python CLI App" \
  --data project_slug="python-cli-app" \
  --data description="Generated Python CLI sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="python" \
  --data backend_mode="cli" \
  --data python_cli_framework="argparse" \
  --data frontend="none" \
  --data config_enabled="true" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./python-cli-app
```

## Supported answers

- `project_name`: human-readable project name
- `project_slug`: lowercase slug using letters, digits, and single hyphens
- `description`: short project description
- `author_name`: project author or owning team
- `license`: license identifier, defaulting to `MIT`
- `backend`: `python`, `go`, or `none`
- `backend_mode`: `library` or `cli`
- `python_cli_framework`: `argparse` or `click`; prompted only for Python CLI
  projects
- `frontend`: `solid_tailwind_shadcn` or `none`
- `config_enabled`: `true` or `false`
- `ci_provider`: `github`

## Generated project examples

### Minimal project

```sh
uvx copier copy --trust --defaults \
  --data project_name="Minimal App" \
  --data project_slug="minimal-app" \
  --data description="Minimal generated sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="none" \
  --data backend_mode="library" \
  --data frontend="none" \
  --data config_enabled="false" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./minimal-app
```

### Python library

Generated Python projects use a `src/` layout, `uv`, pytest, Ruff, and basedpyright.

```sh
uvx copier copy --trust --defaults \
  --data project_name="Python Library" \
  --data project_slug="python-library" \
  --data description="Python generated sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="python" \
  --data backend_mode="library" \
  --data frontend="none" \
  --data config_enabled="false" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./python-library
```

Validate the generated Python project:

```sh
cd ./python-library
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

### Go CLI

Generated Go projects include `go.mod`, `cmd/`, `internal/`, tests, and Cobra
when CLI mode is selected.

```sh
uvx copier copy --trust --defaults \
  --data project_name="Go CLI" \
  --data project_slug="go-cli" \
  --data description="Go CLI generated sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="go" \
  --data backend_mode="cli" \
  --data frontend="none" \
  --data config_enabled="true" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./go-cli
```

Validate the generated Go project:

```sh
cd ./go-cli
go mod download
go test ./...
go vet ./...
test -z "$(gofmt -l .)"
```

Run the generated CLI:

```sh
go run ./cmd/go-cli --help
go run ./cmd/go-cli show-logs --help
go run ./cmd/go-cli show-logs-path
go run ./cmd/go-cli show-config-path
```

### Solid frontend

Generated frontend projects use pnpm with Solid, Vite, TypeScript, Tailwind v3,
PostCSS, Vitest, and shadcn-solid-compatible aliases.

```sh
uvx copier copy --trust --defaults \
  --data project_name="Frontend App" \
  --data project_slug="frontend-app" \
  --data description="Solid frontend generated sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="none" \
  --data backend_mode="library" \
  --data frontend="solid_tailwind_shadcn" \
  --data config_enabled="false" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./frontend-app
```

Validate the generated frontend project:

```sh
cd ./frontend-app
pnpm install
pnpm typecheck
pnpm test
pnpm lint
pnpm build
```

Run the frontend locally:

```sh
pnpm dev
```

Preview a production build:

```sh
pnpm build
pnpm preview
```

### Full-stack project

Select a backend and the Solid frontend together to generate both stacks. For
example, Python CLI with Click, config, and frontend:

```sh
uvx copier copy --trust --defaults \
  --data project_name="Full Stack App" \
  --data project_slug="full-stack-app" \
  --data description="Full-stack generated sample" \
  --data author_name="Example Team" \
  --data license="MIT" \
  --data backend="python" \
  --data backend_mode="cli" \
  --data python_cli_framework="click" \
  --data frontend="solid_tailwind_shadcn" \
  --data config_enabled="true" \
  --data ci_provider="github" \
  /path/to/stackseed \
  ./full-stack-app
```

Run the Python and frontend validation commands from the generated project's
`README.md`. In full-stack generated projects, run Python or Go backend
validators from `backend/` and frontend validators from `frontend/`:

```sh
cd ./full-stack-app/backend
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright

cd ../frontend
pnpm install
pnpm typecheck
pnpm test
pnpm lint
pnpm build
```

## Generated CLI behavior

Python and Go CLI projects expose these commands:

- `show-logs`
- `show-logs-path`
- `show-config-path` when `config_enabled=true`

`show-logs` supports `--lines` and `--follow`. `show-logs-path` and
`show-config-path` print only the resolved path, making them suitable for scripts.

## Notes

- Generate sample projects outside this template repository.
- Copier rendering is local and deterministic; dependency installation happens
  only when you run the generated project's setup commands.
- Frontend generated projects use `pnpm` as the package-manager contract.
