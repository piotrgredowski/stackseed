from __future__ import annotations

import json
import shutil
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
    assert "2 passed" in tests.stdout


def test_frontend_metadata_with_jsx_sensitive_characters_validates(tmp_path: Path) -> None:
    project = render_project(
        tmp_path,
        "frontend-jsx-sensitive",
        project_name='Acme <Portal> "UI"',
        description='Ship <safe> "interfaces"',
    )

    app = (project / "src" / "App.tsx").read_text()
    app_test = (project / "src" / "App.test.tsx").read_text()
    assert '{"Acme \\u003cPortal\\u003e \\"UI\\""}' in app
    assert '{"Ship \\u003csafe\\u003e \\"interfaces\\""}' in app
    assert 'toContain("Acme \\u003cPortal\\u003e \\"UI\\"")' in app_test

    for command in [
        ["pnpm", "install"],
        ["pnpm", "typecheck"],
        ["pnpm", "test"],
        ["pnpm", "lint"],
        ["pnpm", "build"],
    ]:
        result = run_command(command, cwd=project)
        assert result.returncode == 0, f"failed {' '.join(command)}\n{result.stdout}"


def test_python_and_go_backends_compose_with_frontend(tmp_path: Path) -> None:
    samples = [
        ("python-frontend", {"backend": "python"}),
        ("go-frontend", {"backend": "go"}),
    ]
    for name, answers in samples:
        project = render_project(tmp_path, name, **answers)
        assert (project / "frontend" / "package.json").is_file()
        assert (project / "frontend" / "src" / "main.tsx").is_file()
        assert (project / "frontend" / "src" / "api.ts").is_file()
        frontend_api = (project / "frontend" / "src" / "api.ts").read_text()
        assert "/api/calculate" in frontend_api
        assert "CalculatorRequest" in frontend_api
        assert "CalculatorResponse" in frontend_api
        assert "/api" in (project / "frontend" / "vite.config.ts").read_text()
        if answers["backend"] == "python":
            assert (project / "backend" / "pyproject.toml").is_file()
            assert (project / "backend" / "src" / "python_frontend" / "api.py").is_file()
            assert not (project / "backend" / "go.mod").exists()
        else:
            assert (project / "backend" / "go.mod").is_file()
            assert not (project / "backend" / "pyproject.toml").exists()
        assert not (project / "package.json").exists()


def test_python_and_go_full_stack_render_secure_minimal_container_scaffold(
    tmp_path: Path,
) -> None:
    project = render_project(tmp_path, "python-docker", backend="python")

    compose = (project / "docker-compose.yml").read_text()
    backend_dockerfile = (project / "backend" / "Dockerfile").read_text()
    frontend_dockerfile = (project / "frontend" / "Dockerfile").read_text()
    nginx = (project / "frontend" / "nginx.conf").read_text()
    api = (project / "backend" / "src" / "python_docker" / "api.py").read_text()
    api_tests = (project / "backend" / "tests" / "test_python_docker.py").read_text()

    assert "read_only: true" in compose
    assert compose.count("cap_drop:") == 2
    assert compose.count("no-new-privileges:true") == 2
    assert 'ports:\n      - "8080:8080"' in compose
    assert 'expose:\n      - "8000"' in compose
    assert "/healthz" in compose
    assert "USER app" in backend_dockerfile
    assert "uv sync --no-dev --no-editable" in backend_dockerfile
    assert "tests" in (project / "backend" / ".dockerignore").read_text()
    assert "nginxinc/nginx-unprivileged" in frontend_dockerfile
    assert "node:22-alpine AS builder" in frontend_dockerfile
    assert "proxy_pass http://backend:8000/api/" in nginx
    assert 'add_header X-Content-Type-Options "nosniff" always;' in nginx
    assert '@app.get("/healthz")' in api
    assert "test_api_healthz_returns_ok" in api_tests

    if shutil.which("docker") is not None:
        compose_config = run_command(
            ["docker", "compose", "-f", "docker-compose.yml", "config"], cwd=project
        )
        assert compose_config.returncode == 0, compose_config.stdout

    go_project = render_project(tmp_path, "go-docker", backend="go")
    go_compose = (go_project / "docker-compose.yml").read_text()
    go_backend_dockerfile = (go_project / "backend" / "Dockerfile").read_text()
    go_service = (go_project / "backend" / "internal" / "go_docker" / "service.go").read_text()
    go_main = (go_project / "backend" / "cmd" / "go-docker" / "main.go").read_text()

    assert "read_only: true" in go_compose
    assert go_compose.count("cap_drop:") == 2
    assert go_compose.count("no-new-privileges:true") == 2
    assert 'ports:\n      - "8080:8080"' in go_compose
    assert 'expose:\n      - "8000"' in go_compose
    assert "/healthz" in go_compose
    assert "USER app" in go_backend_dockerfile
    assert "golang:1.22-bookworm AS builder" in go_backend_dockerfile
    assert "CGO_ENABLED=0 GOOS=linux go build" in go_backend_dockerfile
    assert "ENV API_ADDRESS=0.0.0.0:8000" in go_backend_dockerfile
    assert "APP_LOG_DIR=/tmp/logs" in go_backend_dockerfile
    assert 'CMD ["/app/go-docker"]' in go_backend_dockerfile
    assert "coverage.out" in (go_project / "backend" / ".dockerignore").read_text()
    assert "nginxinc/nginx-unprivileged" in (go_project / "frontend" / "Dockerfile").read_text()
    assert (
        "proxy_pass http://backend:8000/api/"
        in (go_project / "frontend" / "nginx.conf").read_text()
    )
    assert "func HealthHandler" in go_service
    assert 'os.Getenv("API_ADDRESS")' in go_main

    if shutil.which("docker") is not None:
        go_compose_config = run_command(
            ["docker", "compose", "-f", "docker-compose.yml", "config"], cwd=go_project
        )
        assert go_compose_config.returncode == 0, go_compose_config.stdout


def test_container_scaffold_is_python_full_stack_only(tmp_path: Path) -> None:
    samples = [
        ("frontend-docker-absent", {"backend": "none"}),
        ("python-library-docker-absent", {"backend": "python", "frontend": "none"}),
        ("go-library-docker-absent", {"backend": "go", "frontend": "none"}),
    ]

    for name, answers in samples:
        project = render_project(tmp_path, name, **answers)
        assert not (project / "docker-compose.yml").exists()
        assert not (project / "Dockerfile").exists()
        assert not (project / "backend" / "Dockerfile").exists()
        assert not (project / "frontend" / "Dockerfile").exists()
