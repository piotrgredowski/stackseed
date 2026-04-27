from __future__ import annotations

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
        "description": f"Generated Go sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "go",
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


def test_go_library_renders_buildable_module_without_other_stacks(tmp_path: Path) -> None:
    project = render_project(tmp_path, "go-library", backend_mode="library")

    assert (project / "go.mod").is_file()
    assert (project / "cmd" / "go-library" / "main.go").is_file()
    assert (project / "internal" / "go_library" / "service.go").is_file()
    assert (project / "internal" / "go_library" / "service_test.go").is_file()
    assert not (project / "pyproject.toml").exists()
    assert not (project / "package.json").exists()

    readme = (project / "README.md").read_text()
    assert "go test ./..." in readme
    assert "go vet ./..." in readme
    assert "gofmt -l ." in readme
    assert "Cobra" not in (project / "go.mod").read_text()


def test_go_generated_validators_pass_for_library_and_cli(tmp_path: Path) -> None:
    samples = [
        ("go-library", {"backend_mode": "library"}, False),
        ("go-cli", {"backend_mode": "cli"}, True),
    ]

    for name, answers, expects_cobra in samples:
        project = render_project(tmp_path, name, **answers)
        for command in [
            ["go", "mod", "download"],
            ["go", "test", "./..."],
            ["go", "vet", "./..."],
        ]:
            result = run_command(command, cwd=project)
            assert result.returncode == 0, f"{name} failed {' '.join(command)}\n{result.stdout}"

        gofmt = run_command(["gofmt", "-l", "."], cwd=project)
        assert gofmt.returncode == 0, gofmt.stdout
        assert gofmt.stdout.strip() == ""

        json_tests = run_command(["go", "test", "-json", "./..."], cwd=project)
        assert json_tests.returncode == 0, json_tests.stdout
        assert '"Action":"run"' in json_tests.stdout
        assert "TestGreeting" in json_tests.stdout

        cobra = run_command(["go", "list", "-m", "github.com/spf13/cobra"], cwd=project)
        assert (cobra.returncode == 0) is expects_cobra


def test_go_module_packages_and_cobra_cli_help(tmp_path: Path) -> None:
    project = render_project(tmp_path, "go-cli", backend_mode="cli")
    downloaded = run_command(["go", "mod", "download"], cwd=project)
    assert downloaded.returncode == 0, downloaded.stdout

    module = run_command(["go", "list", "-m"], cwd=project)
    assert module.returncode == 0, module.stdout
    assert module.stdout.strip() == "example.com/go-cli"

    packages = run_command(["go", "list", "./..."], cwd=project)
    assert packages.returncode == 0, packages.stdout
    assert "example.com/go-cli/cmd/go-cli" in packages.stdout
    assert "example.com/go-cli/internal/go_cli" in packages.stdout

    help_result = run_command(["go", "run", "./cmd/go-cli", "--help"], cwd=project)
    assert help_result.returncode == 0, help_result.stdout
    assert "show-logs" in help_result.stdout
    assert "show-logs-path" in help_result.stdout

    command_help = run_command(["go", "run", "./cmd/go-cli", "show-logs", "--help"], cwd=project)
    assert command_help.returncode == 0, command_help.stdout
    assert "--lines" in command_help.stdout
    assert "--follow" in command_help.stdout


def test_go_stack_absent_for_python_and_none_backends(tmp_path: Path) -> None:
    python_project = render_project(tmp_path, "python-without-go", backend="python")
    none_project = render_project(tmp_path, "none-without-go", backend="none")

    for project in [python_project, none_project]:
        assert not (project / "go.mod").exists()
        assert not (project / "cmd").exists()
        assert not (project / "internal").exists()
        readme = (project / "README.md").read_text()
        assert "go test" not in readme
        assert "go vet" not in readme
