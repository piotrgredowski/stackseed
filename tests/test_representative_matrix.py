from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from representative_matrix import REPRESENTATIVE_SAMPLES, RepresentativeSample

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_command(
    args: list[str] | tuple[str, ...],
    cwd: Path | None = None,
    timeout: float = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )


def render_project(tmp_path: Path, sample: RepresentativeSample) -> Path:
    output_dir = tmp_path / sample.sample_id
    command = ["uvx", "copier", "copy", "--trust", "--defaults"]
    for key, value in sample.answers.items():
        command.extend(["--data", f"{key}={value}"])
    command.extend([str(REPO_ROOT), str(output_dir)])

    result = run_command(command, timeout=240)
    assert result.returncode == 0, result.stdout
    return output_dir


def workflow_commands(project: Path) -> list[str]:
    workflow = (project / ".github" / "workflows" / "ci.yml").read_text()
    return [match.strip() for match in re.findall(r"^\s+run: (.+)$", workflow, re.MULTILINE)]


def documented_commands(project: Path) -> set[str]:
    docs = (project / "README.md").read_text() + "\n" + (project / "AGENTS.md").read_text()
    return set(re.findall(r"`([^`]+)`", docs))


def expected_validation_commands(sample: RepresentativeSample) -> set[str]:
    commands: set[str] = set()
    if sample.backend == "python":
        commands.update(
            {
                "uv sync --dev",
                "uv run pytest",
                "uv run ruff check .",
                "uv run ruff format --check .",
                "uv run pyright",
            }
        )
    if sample.backend == "go":
        commands.update(
            {
                "go mod download",
                "go test ./...",
                "go vet ./...",
                'test -z "$(gofmt -l .)"',
            }
        )
    if sample.frontend == "solid_tailwind_shadcn":
        commands.update(
            {
                "pnpm install",
                "pnpm typecheck",
                "pnpm test",
                "pnpm lint",
                "pnpm build",
            }
        )
    return commands


def test_representative_matrix_names_all_required_samples() -> None:
    assert [sample.sample_id for sample in REPRESENTATIVE_SAMPLES] == [
        "minimal",
        "python-library",
        "python-argparse-cli",
        "python-click-cli",
        "go-library",
        "go-cobra-cli",
        "frontend-only",
        "python-frontend",
        "go-frontend",
        "python-click-config-frontend",
        "go-cobra-config-frontend",
    ]


@pytest.mark.parametrize("sample", REPRESENTATIVE_SAMPLES, ids=lambda sample: sample.sample_id)
def test_representative_combinations_generate_and_include_only_selected_stacks(
    tmp_path: Path, sample: RepresentativeSample
) -> None:
    project = render_project(tmp_path, sample)

    for required in [
        "README.md",
        "AGENTS.md",
        ".agents/project-context.md",
        ".scratchpad/.gitkeep",
        ".gitignore",
        ".editorconfig",
        ".github/workflows/ci.yml",
    ]:
        assert (project / required).is_file(), f"{sample.sample_id} missing {required}"

    assert (project / "pyproject.toml").exists() is (sample.backend == "python")
    assert (project / "go.mod").exists() is (sample.backend == "go")
    assert (project / "package.json").exists() is (sample.frontend == "solid_tailwind_shadcn")
    assert (project / "config" / f"{sample.sample_id}.toml").exists() is sample.has_config

    all_text = "\n".join(
        path.read_text(errors="ignore")
        for path in project.rglob("*")
        if path.is_file() and "node_modules" not in path.parts and ".git" not in path.parts
    )
    for forbidden in ["{{", "{%", ".jinja", str(REPO_ROOT), ".factory", "Factory", "Droid"]:
        assert forbidden not in all_text


@pytest.mark.parametrize("sample", REPRESENTATIVE_SAMPLES, ids=lambda sample: sample.sample_id)
def test_representative_command_sources_are_synchronized(
    tmp_path: Path, sample: RepresentativeSample
) -> None:
    project = render_project(tmp_path, sample)
    expected_commands = expected_validation_commands(sample)
    ci_commands = set(workflow_commands(project))
    docs_commands = documented_commands(project)

    if not expected_commands:
        assert workflow_commands(project) == ['echo "No stack-specific validators configured yet."']
        assert not any(command.startswith(("uv ", "go ", "pnpm ")) for command in docs_commands)
        return

    normalized_ci = {
        "pnpm install" if command == "pnpm install --frozen-lockfile=false" else command
        for command in ci_commands
    }
    assert expected_commands.issubset(normalized_ci)
    assert expected_commands.issubset(docs_commands)

    if sample.backend != "python":
        assert not any(command.startswith("uv ") for command in docs_commands | normalized_ci)
    if sample.backend != "go":
        assert not any(command.startswith("go ") for command in docs_commands | normalized_ci)
    if sample.frontend != "solid_tailwind_shadcn":
        assert not any(command.startswith("pnpm ") for command in docs_commands | normalized_ci)


@pytest.mark.parametrize(
    "sample",
    [sample for sample in REPRESENTATIVE_SAMPLES if sample.validators],
    ids=lambda sample: sample.sample_id,
)
def test_representative_generated_validators_pass(
    tmp_path: Path, sample: RepresentativeSample
) -> None:
    project = render_project(tmp_path, sample)

    for command in sample.validators:
        result = run_command(command, cwd=project, timeout=240)
        assert result.returncode == 0, (
            f"{sample.sample_id} failed {' '.join(command)}\n{result.stdout}"
        )
        if command == ("gofmt", "-l", "."):
            assert result.stdout.strip() == ""

    for command in sample.cli_help:
        result = run_command(command, cwd=project, timeout=120)
        assert result.returncode == 0, (
            f"{sample.sample_id} failed {' '.join(command)}\n{result.stdout}"
        )
        assert "show-logs" in result.stdout or "show-config-path" in result.stdout
