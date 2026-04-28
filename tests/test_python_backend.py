from __future__ import annotations

import subprocess
import tomllib
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
        "description": f"Generated Python sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "python",
        "backend_mode": "library",
        "python_cli_framework": "argparse",
        "frontend": "none",
        "config_enabled": "false",
        "ci_provider": "github",
    }
    data.update(answers)

    command = ["uvx", "copier", "copy", "--trust", "--defaults"]
    for key, value in data.items():
        command.extend(["--data", f"{key}={value}"])
    command.extend([str(REPO_ROOT), str(output_dir)])

    result = run_command(command)
    assert result.returncode == 0, result.stdout
    return output_dir


def test_python_library_renders_src_layout_and_meaningful_tests(tmp_path: Path) -> None:
    project = render_project(tmp_path, "python-library", backend_mode="library")
    package_dir = project / "src" / "python_library"

    assert (project / "pyproject.toml").is_file()
    assert (package_dir / "__init__.py").is_file()
    assert not (package_dir / "cli.py").exists()
    assert (project / "tests" / "test_python_library.py").is_file()
    assert "uv run ruff format --check ." in (project / "README.md").read_text()
    assert "uv run pyright" in (project / "README.md").read_text()
    assert not (project / "go.mod").exists()
    assert not (project / "package.json").exists()


def test_python_generated_validators_pass_for_library_argparse_and_click(
    tmp_path: Path,
) -> None:
    samples = [
        ("python-library", {"backend_mode": "library"}),
        ("python-argparse", {"backend_mode": "cli", "python_cli_framework": "argparse"}),
        ("python-click", {"backend_mode": "cli", "python_cli_framework": "click"}),
    ]

    for name, answers in samples:
        project = render_project(tmp_path, name, **answers)
        for command in [
            ["uv", "sync", "--dev"],
            ["uv", "run", "pytest"],
            ["uv", "run", "ruff", "check", "."],
            ["uv", "run", "ruff", "format", "--check", "."],
            ["uv", "run", "pyright"],
        ]:
            result = run_command(command, cwd=project)
            assert result.returncode == 0, f"{name} failed {' '.join(command)}\n{result.stdout}"

        pytest_result = run_command(["uv", "run", "pytest", "--collect-only", "-q"], cwd=project)
        assert "no tests collected" not in pytest_result.stdout
        assert "test_" in pytest_result.stdout


def test_python_package_importable_and_cli_variants_have_scoped_dependencies(
    tmp_path: Path,
) -> None:
    variants = [
        ("python-argparse", "argparse", False),
        ("python-click", "click", True),
    ]

    for name, framework, expects_click in variants:
        project = render_project(
            tmp_path,
            name,
            backend_mode="cli",
            python_cli_framework=framework,
        )
        assert run_command(["uv", "sync", "--dev"], cwd=project).returncode == 0

        package = name.replace("-", "_")
        imported = run_command(
            ["uv", "run", "python", "-c", f"import {package}; print({package}.__version__)"],
            cwd=project,
        )
        assert imported.returncode == 0, imported.stdout
        assert imported.stdout.strip().endswith("0.1.0")

        help_result = run_command(["uv", "run", name, "--help"], cwd=project)
        assert help_result.returncode == 0, help_result.stdout
        assert "show-logs" in help_result.stdout
        assert "show-logs-path" in help_result.stdout

        pyproject = (project / "pyproject.toml").read_text()
        assert ('"click>=' in pyproject) is expects_click


def test_python_description_with_quotes_renders_valid_toml_and_validators(
    tmp_path: Path,
) -> None:
    project = render_project(
        tmp_path,
        "python-quoted-description",
        description='She said "hello"',
    )

    pyproject = tomllib.loads((project / "pyproject.toml").read_text())
    assert pyproject["project"]["description"] == 'She said "hello"'

    for command in [
        ["uv", "sync", "--dev"],
        ["uv", "run", "pytest"],
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "pyright"],
    ]:
        result = run_command(command, cwd=project)
        assert result.returncode == 0, f"failed {' '.join(command)}\n{result.stdout}"


def test_python_stack_absent_for_go_and_none_backends(tmp_path: Path) -> None:
    go_project = render_project(tmp_path, "go-without-python", backend="go")
    none_project = render_project(tmp_path, "none-without-python", backend="none")

    for project in [go_project, none_project]:
        assert not (project / "pyproject.toml").exists()
        assert not (project / "tests").exists()
        assert "uv run pytest" not in (project / "README.md").read_text()
