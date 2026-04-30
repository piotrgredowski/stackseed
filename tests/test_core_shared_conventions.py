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
        "description": f"Generated sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "none",
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


def test_required_prompts_render_shared_files_and_python_cli_metadata(tmp_path: Path) -> None:
    project = render_project(
        tmp_path,
        "python-cli-app",
        backend="python",
        backend_mode="cli",
        python_cli_framework="click",
        config_enabled="true",
    )

    assert (project / "README.md").read_text().startswith("# Python Cli App")
    assert "Generated sample for python-cli-app" in (project / "README.md").read_text()
    assert "uv run pytest" in (project / "README.md").read_text()
    assert "Backend: Python" in (project / "README.md").read_text()
    assert "Backend mode: CLI" in (project / "README.md").read_text()
    assert "Python CLI framework: click" in (project / "README.md").read_text()
    assert "Config scaffold: enabled" in (project / "README.md").read_text()
    assert (project / "AGENTS.md").is_file()
    assert (project / ".agents" / "project-context.md").is_file()
    assert (project / ".scratchpad" / ".gitkeep").is_file()
    assert (project / ".editorconfig").is_file()
    assert (project / ".gitignore").is_file()
    assert (project / "pyproject.toml").is_file()


def test_backend_and_frontend_choices_are_mutually_exclusive(tmp_path: Path) -> None:
    python_project = render_project(tmp_path, "python-only", backend="python")
    go_project = render_project(tmp_path, "go-only", backend="go")
    frontend_project = render_project(
        tmp_path,
        "frontend-only",
        frontend="solid_tailwind_shadcn",
    )
    empty_project = render_project(tmp_path, "empty-project")

    assert (python_project / "pyproject.toml").exists()
    assert (python_project / "src").exists()
    assert not (python_project / "go.mod").exists()
    assert not (python_project / "cmd").exists()
    assert not (python_project / "internal").exists()
    assert not (python_project / "package.json").exists()

    assert (go_project / "go.mod").exists()
    assert (go_project / "cmd").exists()
    assert (go_project / "internal").exists()
    assert not (go_project / "pyproject.toml").exists()
    assert not (go_project / "src").exists()
    assert not (go_project / "package.json").exists()

    assert (frontend_project / "package.json").exists()
    assert (frontend_project / "vite.config.ts").exists()
    assert (frontend_project / "tailwind.config.ts").exists()
    assert (frontend_project / "src").exists()
    assert not (frontend_project / "pyproject.toml").exists()
    assert not (frontend_project / "go.mod").exists()

    assert not (empty_project / "pyproject.toml").exists()
    assert not (empty_project / "go.mod").exists()
    assert not (empty_project / "package.json").exists()


def test_agent_context_scratchpad_ignore_and_no_factory_specific_files(tmp_path: Path) -> None:
    project = render_project(tmp_path, "shared-files", backend="none", frontend="none")

    agent_text = (project / "AGENTS.md").read_text()
    assert ".scratchpad/" in agent_text
    assert "temporary scripts" in agent_text
    assert "experiments" in agent_text
    assert "throwaway work" in agent_text

    all_rendered_text = "\n".join(
        path.read_text(errors="ignore")
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    assert "Factory" not in all_rendered_text
    assert ".factory" not in all_rendered_text

    assert run_command(["git", "init"], cwd=project).returncode == 0
    assert run_command(["git", "check-ignore", ".scratchpad/.gitkeep"], cwd=project).returncode == 1
    scratch_file = project / ".scratchpad" / "example.tmp"
    scratch_file.write_text("temporary\n")
    ignored = run_command(["git", "check-ignore", ".scratchpad/example.tmp"], cwd=project)
    assert ignored.returncode == 0
    assert ignored.stdout.strip() == ".scratchpad/example.tmp"


def test_template_readme_documents_copier_and_rendering_has_no_network_hooks(
    tmp_path: Path,
) -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    assert "uvx copier copy" in readme
    assert "copier copy" in readme

    render_project(tmp_path, "no-network-hooks", backend="none", frontend="none")
    copier_config = (REPO_ROOT / "copier.yml").read_text()
    assert "_tasks" not in copier_config
    assert "curl" not in copier_config
    assert "wget" not in copier_config
    assert "npm create" not in copier_config
    assert "npx" not in copier_config


def test_shared_files_are_git_trackable_and_transients_ignored_for_stack_matrix(
    tmp_path: Path,
) -> None:
    samples = {
        "minimal": {},
        "python": {"backend": "python"},
        "go-shared": {"backend": "go"},
        "frontend": {"frontend": "solid_tailwind_shadcn"},
        "full": {"backend": "python", "frontend": "solid_tailwind_shadcn"},
    }

    for name, answers in samples.items():
        project = render_project(tmp_path, name, **answers)

        for required in [
            "README.md",
            "AGENTS.md",
            ".agents/project-context.md",
            ".scratchpad/.gitkeep",
            ".gitignore",
            ".editorconfig",
        ]:
            assert (project / required).is_file(), f"{name} missing {required}"

        assert run_command(["git", "init"], cwd=project).returncode == 0
        addable = run_command(
            [
                "git",
                "add",
                "--dry-run",
                "README.md",
                "AGENTS.md",
                ".agents/project-context.md",
                ".scratchpad/.gitkeep",
                ".gitignore",
                ".editorconfig",
            ],
            cwd=project,
        )
        assert addable.returncode == 0, addable.stdout

        for ignored in [
            ".env",
            ".DS_Store",
            "__pycache__/x.pyc",
            "node_modules/pkg/file.js",
            "dist/app.js",
            ".scratchpad/notes.md",
        ]:
            ignored_path = project / ignored
            ignored_path.parent.mkdir(parents=True, exist_ok=True)
            ignored_path.write_text("ignored\n")
            assert run_command(["git", "check-ignore", ignored], cwd=project).returncode == 0, (
                ignored
            )

        for tracked in [".scratchpad/.gitkeep", ".agents/project-context.md"]:
            assert run_command(["git", "check-ignore", tracked], cwd=project).returncode == 1, (
                tracked
            )


def test_generated_docs_are_stack_aware_and_have_no_template_or_runtime_leakage(
    tmp_path: Path,
) -> None:
    project = render_project(
        tmp_path, "minimal-docs", backend="none", frontend="none", config_enabled="true"
    )
    readme = (project / "README.md").read_text()
    agents = (project / "AGENTS.md").read_text() + (
        project / ".agents" / "project-context.md"
    ).read_text()

    assert "Backend: None" in readme
    assert "Frontend: None" in readme
    assert "Config scaffold: disabled" in readme
    assert "uv run pytest" not in readme
    assert "go test" not in readme
    assert "pnpm" not in readme
    assert "npm" not in readme

    rendered_text = "\n".join(
        path.read_text(errors="ignore")
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    forbidden = [
        "{{",
        "{%",
        ".jinja",
        str(REPO_ROOT),
        str(tmp_path),
        str(Path.home()),
        ".factory",
        "Factory",
        "Droid",
        "model-settings",
        "runtime-custom-models",
        "API_KEY",
    ]
    for needle in forbidden:
        assert needle not in rendered_text
    assert "temporary scripts" in agents
    assert "external secrets" in agents


def test_invalid_answers_fail_before_rendering_project(tmp_path: Path) -> None:
    invalid_cases = [
        ("bad-backend", "backend=rust", "backend"),
        ("bad-frontend", "frontend=react", "frontend"),
        ("bad-mode", "backend_mode=invalid", "backend_mode"),
        ("bad-framework", "python_cli_framework=typer", "python_cli_framework"),
        ("bad-ci", "ci_provider=none", "ci_provider"),
        ("bad-slug", "project_slug=Invalid Python Slug", "project_slug"),
    ]
    for name, data_arg, diagnostic in invalid_cases:
        output_dir = tmp_path / name
        command = [
            "uvx",
            "copier",
            "copy",
            "--trust",
            "--defaults",
            "--data",
            "project_name=Invalid Sample",
            "--data",
            "description=Invalid sample",
            "--data",
            "author_name=Template Tester",
            "--data",
            "license=MIT",
            "--data",
            "backend=python",
            "--data",
            "backend_mode=cli",
            "--data",
            "python_cli_framework=argparse",
            "--data",
            "frontend=none",
            "--data",
            "config_enabled=false",
            "--data",
            "ci_provider=github",
            "--data",
            data_arg,
            str(REPO_ROOT),
            str(output_dir),
        ]
        result = run_command(command)
        assert result.returncode != 0, result.stdout
        assert diagnostic in result.stdout or "Invalid choice" in result.stdout
        assert not (output_dir / "README.md").exists()


def test_api_backend_mode_requires_backend_stack(tmp_path: Path) -> None:
    output_dir = tmp_path / "bad-api-mode-without-backend"
    command = [
        "uvx",
        "copier",
        "copy",
        "--trust",
        "--defaults",
        "--data",
        "project_name=Invalid API Mode",
        "--data",
        "project_slug=invalid-api-mode",
        "--data",
        "description=Invalid API mode",
        "--data",
        "author_name=Template Tester",
        "--data",
        "license=MIT",
        "--data",
        "backend=none",
        "--data",
        "backend_mode=api",
        "--data",
        "frontend=none",
        "--data",
        "config_enabled=false",
        "--data",
        "ci_provider=github",
        str(REPO_ROOT),
        str(output_dir),
    ]

    result = run_command(command)

    assert result.returncode != 0, result.stdout
    assert "backend_mode api requires a backend stack" in result.stdout
    assert not (output_dir / "README.md").exists()


def test_language_keyword_project_slugs_fail_before_rendering_source(tmp_path: Path) -> None:
    invalid_cases = [
        (
            "python-keyword",
            {
                "project_slug": "class",
                "backend": "python",
            },
            [Path("src/class/__init__.py"), Path("tests/test_class.py")],
            ["import class as package", "from class.cli import"],
        ),
        (
            "go-keyword",
            {
                "project_slug": "type",
                "backend": "go",
            },
            [Path("internal/type/service.go"), Path("cmd/type/main.go")],
            ["package type", " type.Greeting"],
        ),
    ]
    for name, answers, invalid_paths, invalid_text in invalid_cases:
        output_dir = tmp_path / name
        data = {
            "project_name": name.replace("-", " ").title(),
            "project_slug": name,
            "description": f"Generated sample for {name}",
            "author_name": "Template Tester",
            "license": "MIT",
            "backend": "none",
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

        assert result.returncode != 0, result.stdout
        assert "project_slug" in result.stdout
        for invalid_path in invalid_paths:
            assert not (output_dir / invalid_path).exists()
        if output_dir.exists():
            rendered_text = "\n".join(
                path.read_text(errors="ignore") for path in output_dir.rglob("*") if path.is_file()
            )
            for needle in invalid_text:
                assert needle not in rendered_text


def test_rendering_is_deterministic_and_does_not_mutate_template_repo(tmp_path: Path) -> None:
    def manifest(root: Path) -> dict[str, tuple[int, str]]:
        import hashlib

        result = {}
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and ".git" not in path.parts
                and ".pytest_cache" not in path.parts
                and ".ruff_cache" not in path.parts
                and "__pycache__" not in path.parts
            ):
                relative = path.relative_to(root).as_posix()
                result[relative] = (
                    path.stat().st_mode & 0o777,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
        return result

    before = manifest(REPO_ROOT)
    first = render_project(
        tmp_path,
        "deterministic-a",
        project_name="Deterministic",
        project_slug="same-project",
        description="Same generated project",
        backend="python",
        frontend="solid_tailwind_shadcn",
    )
    second = render_project(
        tmp_path,
        "deterministic-b",
        project_name="Deterministic",
        project_slug="same-project",
        description="Same generated project",
        backend="python",
        frontend="solid_tailwind_shadcn",
    )
    after = manifest(REPO_ROOT)

    assert manifest(first) == manifest(second)
    assert before == after
