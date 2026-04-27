from __future__ import annotations

import json
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
        "description": f"Generated frontend sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "none",
        "backend_mode": "library",
        "python_cli_framework": "argparse",
        "frontend": "solid_tailwind_shadcn",
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


def test_solid_frontend_renders_required_pnpm_tailwind_shadcn_files(tmp_path: Path) -> None:
    project = render_project(tmp_path, "frontend-only")

    required_files = [
        "package.json",
        "index.html",
        "src/main.tsx",
        "src/App.tsx",
        "src/App.test.tsx",
        "src/index.css",
        "src/lib/utils.ts",
        "src/components/ui/.gitkeep",
        "vite.config.ts",
        "tsconfig.json",
        "tsconfig.node.json",
        "tailwind.config.ts",
        "postcss.config.cjs",
        "components.json",
    ]
    for relative in required_files:
        assert (project / relative).is_file(), relative

    package_json = json.loads((project / "package.json").read_text())
    assert package_json["packageManager"].startswith("pnpm@")
    assert set(["dev", "preview", "typecheck", "test", "lint", "build"]).issubset(
        package_json["scripts"]
    )
    assert "solid-js" in package_json["dependencies"]
    assert "vite-plugin-solid" in package_json["devDependencies"]
    assert "@vitejs/plugin-solid" not in package_json["dependencies"]
    assert package_json["devDependencies"]["tailwindcss"].startswith("^3.")
    assert "autoprefixer" in package_json["devDependencies"]
    assert "postcss" in package_json["devDependencies"]
    assert "class-variance-authority" in package_json["dependencies"]
    assert "tailwindcss-animate" in package_json["dependencies"]

    components = json.loads((project / "components.json").read_text())
    assert components["tailwind"]["config"] == "tailwind.config.ts"
    assert components["tailwind"]["css"]["path"] == "src/index.css"
    assert components["alias"]["cn"] == "@/lib/utils"
    assert components["alias"]["ui"] == "@/components/ui"

    all_text = "\n".join(
        path.read_text(errors="ignore")
        for path in project.rglob("*")
        if path.is_file() and "node_modules" not in path.parts
    )
    for forbidden in ["react", "React", "@vitejs/plugin-solid", "@tailwindcss/vite"]:
        assert forbidden not in all_text
    assert "{{" not in all_text
    assert "{%" not in all_text
    assert "@tailwind base;" in (project / "src/index.css").read_text()
    assert "tailwindcss" in (project / "postcss.config.cjs").read_text()


def test_frontend_none_excludes_all_frontend_artifacts(tmp_path: Path) -> None:
    project = render_project(tmp_path, "no-frontend", frontend="none")

    for relative in [
        "package.json",
        "index.html",
        "vite.config.ts",
        "tailwind.config.ts",
        "postcss.config.cjs",
        "components.json",
        "src/main.tsx",
        "src/App.tsx",
        "src/index.css",
    ]:
        assert not (project / relative).exists(), relative

    readme = (project / "README.md").read_text()
    assert "pnpm" not in readme
    assert "Vite" not in readme


def test_generated_frontend_validators_pass_and_build_outputs_assets(tmp_path: Path) -> None:
    project = render_project(tmp_path, "frontend-validators")

    for command in [
        ["pnpm", "install"],
        ["pnpm", "typecheck"],
        ["pnpm", "test"],
        ["pnpm", "lint"],
        ["pnpm", "build"],
    ]:
        result = run_command(command, cwd=project)
        assert result.returncode == 0, f"failed {' '.join(command)}\n{result.stdout}"

    assert (project / "dist" / "index.html").is_file()
    assert any((project / "dist" / "assets").iterdir())
    tests = run_command(["pnpm", "test", "--", "--reporter=verbose"], cwd=project)
    assert tests.returncode == 0, tests.stdout
    assert "src/App.test.tsx" in tests.stdout
    assert "1 passed" in tests.stdout


def test_python_and_go_backends_compose_with_frontend(tmp_path: Path) -> None:
    samples = [
        ("python-frontend", {"backend": "python"}),
        ("go-frontend", {"backend": "go"}),
    ]
    for name, answers in samples:
        project = render_project(tmp_path, name, **answers)
        assert (project / "package.json").is_file()
        assert (project / "src" / "main.tsx").is_file()
        if answers["backend"] == "python":
            assert (project / "pyproject.toml").is_file()
            assert not (project / "go.mod").exists()
        else:
            assert (project / "go.mod").is_file()
            assert not (project / "pyproject.toml").exists()
