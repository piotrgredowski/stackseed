from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def render_project(tmp_path: Path, name: str, **answers: str) -> Path:
    output_dir = tmp_path / name
    data = {
        "project_name": name.replace("-", " ").title(),
        "project_slug": name,
        "description": f"Generated CI sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "none",
        "backend_mode": "library",
        "python_cli_framework": "argparse",
        "frontend": "none",
        "config_enabled": "false",
    }
    data.update(answers)

    command = ["uvx", "copier", "copy", "--trust", "--defaults"]
    for key, value in data.items():
        command.extend(["--data", f"{key}={value}"])
    command.extend([str(REPO_ROOT), str(output_dir)])

    result = run_command(command)
    assert result.returncode == 0, result.stdout
    return output_dir


def workflow(project: Path) -> str:
    workflows = sorted((project / ".github" / "workflows").glob("*.yml"))
    assert [path.name for path in workflows] == ["ci.yml"]
    return workflows[0].read_text()


def run_commands(ci_text: str) -> list[str]:
    return [match.strip() for match in re.findall(r"^\s+run: (.+)$", ci_text, re.MULTILINE)]


def assert_valid_github_actions_shape(ci_text: str) -> None:
    assert ci_text.startswith("name: CI\n")
    assert re.search(r"^on:\n", ci_text, re.MULTILINE)
    assert re.search(r"^jobs:\n", ci_text, re.MULTILINE)
    assert re.search(r"^\s+[a-z][a-z-]*:\n\s+name: ", ci_text, re.MULTILINE)
    assert "runs-on: ubuntu-latest" in ci_text
    assert "uses: actions/checkout@v4" in ci_text
    assert "\t" not in ci_text


def assert_absent(ci_text: str, forbidden: list[str]) -> None:
    for needle in forbidden:
        assert needle not in ci_text, needle


def test_ci_is_generated_by_default_and_only_github_is_supported(tmp_path: Path) -> None:
    default_project = render_project(tmp_path, "default-ci")
    explicit_project = render_project(tmp_path, "explicit-ci", ci_provider="github")

    for project in [default_project, explicit_project]:
        ci_text = workflow(project)
        assert_valid_github_actions_shape(ci_text)
        assert "CI provider: GitHub Actions" in (project / "README.md").read_text()

    invalid = run_command(
        [
            "uvx",
            "copier",
            "copy",
            "--trust",
            "--defaults",
            "--data",
            "project_name=No CI",
            "--data",
            "project_slug=no-ci",
            "--data",
            "description=Invalid CI",
            "--data",
            "author_name=Template Tester",
            "--data",
            "license=MIT",
            "--data",
            "backend=none",
            "--data",
            "frontend=none",
            "--data",
            "ci_provider=none",
            str(REPO_ROOT),
            str(tmp_path / "no-ci"),
        ]
    )
    assert invalid.returncode != 0
    assert "ci_provider" in invalid.stdout or "Invalid choice" in invalid.stdout


def test_minimal_ci_is_valid_stack_neutral_github_actions_only(tmp_path: Path) -> None:
    project = render_project(tmp_path, "minimal-ci")
    ci_text = workflow(project)

    assert_valid_github_actions_shape(ci_text)
    assert run_commands(ci_text) == ['echo "No stack-specific validators configured yet."']
    assert_absent(
        ci_text,
        [
            "actions/setup-python",
            "astral-sh/setup-uv",
            "actions/setup-go",
            "actions/setup-node",
            "pnpm/action-setup",
            "uv run",
            "pytest",
            "ruff",
            "pyright",
            "go test",
            "go vet",
            "gofmt",
            "pnpm",
            "npm",
            "vite",
            "vitest",
        ],
    )
    for forbidden in [
        ".gitlab-ci.yml",
        ".circleci",
        "azure-pipelines.yml",
        ".buildkite",
        ".drone.yml",
        "Jenkinsfile",
        "woodpecker.yml",
    ]:
        assert not (project / forbidden).exists()


def test_ci_runs_only_selected_stack_validators_and_setup(tmp_path: Path) -> None:
    samples = {
        "python-ci": (
            {"backend": "python"},
            [
                "uv sync --dev",
                "uv run pytest",
                "uv run ruff check .",
                "uv run ruff format --check .",
                "uv run pyright",
            ],
            ["actions/setup-python", "astral-sh/setup-uv"],
            ["actions/setup-go", "actions/setup-node", "pnpm/action-setup", "go test", "pnpm"],
        ),
        "go-ci": (
            {"backend": "go"},
            ["go mod download", "go test ./...", "go vet ./...", 'test -z "$(gofmt -l .)"'],
            ["actions/setup-go"],
            ["actions/setup-python", "astral-sh/setup-uv", "actions/setup-node", "pnpm", "uv run"],
        ),
        "frontend-ci": (
            {"frontend": "solid_tailwind_shadcn"},
            [
                "pnpm install --frozen-lockfile=false",
                "pnpm typecheck",
                "pnpm test",
                "pnpm lint",
                "pnpm build",
            ],
            ["actions/setup-node", "pnpm/action-setup"],
            [
                "actions/setup-python",
                "astral-sh/setup-uv",
                "actions/setup-go",
                "uv run",
                "go test",
                "run: npm",
                "run: yarn",
                "run: bun",
            ],
        ),
    }

    for name, (answers, expected_commands, expected_setup, forbidden) in samples.items():
        ci_text = workflow(render_project(tmp_path, name, **answers))
        assert_valid_github_actions_shape(ci_text)
        for command in expected_commands:
            assert command in run_commands(ci_text)
        for setup in expected_setup:
            assert setup in ci_text
        assert_absent(ci_text, forbidden)


def test_frontend_ci_does_not_cache_pnpm_without_generated_lockfile(tmp_path: Path) -> None:
    samples = [
        ("frontend-cache-ci", {"frontend": "solid_tailwind_shadcn"}, Path(".")),
        (
            "python-frontend-cache-ci",
            {"backend": "python", "frontend": "solid_tailwind_shadcn"},
            Path("frontend"),
        ),
    ]

    for name, answers, frontend_dir in samples:
        project = render_project(tmp_path, name, **answers)
        ci_text = workflow(project)
        commands = run_commands(ci_text)

        assert not (project / frontend_dir / "pnpm-lock.yaml").exists()
        assert 'cache: "pnpm"' not in ci_text
        assert "cache: pnpm" not in ci_text
        assert "cache-dependency-path" not in ci_text
        assert "actions/setup-node@v4" in ci_text
        assert "pnpm/action-setup@v4" in ci_text
        assert "pnpm install --frozen-lockfile=false" in commands
        for command in ["pnpm typecheck", "pnpm test", "pnpm lint", "pnpm build"]:
            assert command in commands

        if frontend_dir != Path("."):
            assert len(re.findall(r"working-directory: frontend", ci_text)) >= 5
        else:
            assert "working-directory: frontend" not in ci_text


def test_combined_ci_composes_validators_once_and_matches_docs(tmp_path: Path) -> None:
    samples = [
        ("python-frontend-ci", {"backend": "python", "frontend": "solid_tailwind_shadcn"}),
        (
            "python-click-config-frontend-ci",
            {
                "backend": "python",
                "backend_mode": "cli",
                "python_cli_framework": "click",
                "config_enabled": "true",
                "frontend": "solid_tailwind_shadcn",
            },
        ),
        ("go-frontend-ci", {"backend": "go", "frontend": "solid_tailwind_shadcn"}),
        (
            "go-cli-config-frontend-ci",
            {
                "backend": "go",
                "backend_mode": "cli",
                "config_enabled": "true",
                "frontend": "solid_tailwind_shadcn",
            },
        ),
    ]
    expected_frontend = ["pnpm typecheck", "pnpm test", "pnpm lint", "pnpm build"]

    for name, answers in samples:
        project = render_project(tmp_path, name, **answers)
        ci_text = workflow(project)
        commands = run_commands(ci_text)
        readme = (project / "README.md").read_text()
        agents = (project / "AGENTS.md").read_text()

        assert_valid_github_actions_shape(ci_text)
        for command in expected_frontend:
            assert commands.count(command) == 1
            assert f"`{command}`" in readme
        if answers["backend"] == "python":
            for command in [
                "uv run pytest",
                "uv run ruff check .",
                "uv run ruff format --check .",
                "uv run pyright",
            ]:
                assert commands.count(command) == 1
                assert f"`{command}`" in readme
            assert "go test" not in ci_text
            assert "actions/setup-go" not in ci_text
        else:
            for command in ["go test ./...", "go vet ./...", 'test -z "$(gofmt -l .)"']:
                assert commands.count(command) == 1
                assert f"`{command}`" in readme
            assert "uv run" not in ci_text
            assert "actions/setup-python" not in ci_text
        assert "Run the stack-specific commands documented in `README.md`" in agents
