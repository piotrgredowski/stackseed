from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepresentativeSample:
    sample_id: str
    answers: dict[str, str]
    validators: tuple[tuple[str, ...], ...]
    cli_help: tuple[tuple[str, ...], ...] = ()

    @property
    def backend(self) -> str:
        return self.answers["backend"]

    @property
    def frontend(self) -> str:
        return self.answers["frontend"]

    @property
    def is_cli(self) -> bool:
        return self.answers["backend_mode"] == "cli" and self.backend in {"python", "go"}

    @property
    def has_config(self) -> bool:
        return self.is_cli and self.answers["config_enabled"] == "true"


BASE_ANSWERS = {
    "author_name": "Template Tester",
    "license": "MIT",
    "backend": "none",
    "backend_mode": "library",
    "python_cli_framework": "argparse",
    "frontend": "none",
    "config_enabled": "false",
    "ci_provider": "github",
}

PYTHON_VALIDATORS = (
    ("uv", "sync", "--dev"),
    ("uv", "run", "pytest"),
    ("uv", "run", "ruff", "check", "."),
    ("uv", "run", "ruff", "format", "--check", "."),
    ("uv", "run", "pyright"),
)
GO_VALIDATORS = (
    ("go", "mod", "download"),
    ("go", "test", "./..."),
    ("go", "vet", "./..."),
    ("gofmt", "-l", "."),
)
FRONTEND_VALIDATORS = (
    ("pnpm", "install"),
    ("pnpm", "typecheck"),
    ("pnpm", "test"),
    ("pnpm", "lint"),
    ("pnpm", "build"),
)


def _sample(
    sample_id: str,
    *,
    validators: tuple[tuple[str, ...], ...] = (),
    cli_help: tuple[tuple[str, ...], ...] = (),
    **answers: str,
) -> RepresentativeSample:
    resolved = {
        **BASE_ANSWERS,
        "project_name": sample_id.replace("-", " ").title(),
        "project_slug": sample_id,
        "description": f"Representative generated sample for {sample_id}",
        **answers,
    }
    return RepresentativeSample(sample_id, resolved, validators, cli_help)


REPRESENTATIVE_SAMPLES = (
    _sample("minimal"),
    _sample("python-library", backend="python", validators=PYTHON_VALIDATORS),
    _sample(
        "python-argparse-cli",
        backend="python",
        backend_mode="cli",
        python_cli_framework="argparse",
        validators=PYTHON_VALIDATORS,
        cli_help=(("uv", "run", "python-argparse-cli", "--help"),),
    ),
    _sample(
        "python-click-cli",
        backend="python",
        backend_mode="cli",
        python_cli_framework="click",
        validators=PYTHON_VALIDATORS,
        cli_help=(("uv", "run", "python-click-cli", "--help"),),
    ),
    _sample("go-library", backend="go", validators=GO_VALIDATORS),
    _sample(
        "go-cobra-cli",
        backend="go",
        backend_mode="cli",
        validators=GO_VALIDATORS,
        cli_help=(("go", "run", "./cmd/go-cobra-cli", "--help"),),
    ),
    _sample("frontend-only", frontend="solid_tailwind_shadcn", validators=FRONTEND_VALIDATORS),
    _sample(
        "python-frontend",
        backend="python",
        frontend="solid_tailwind_shadcn",
        validators=PYTHON_VALIDATORS + FRONTEND_VALIDATORS,
    ),
    _sample(
        "go-frontend",
        backend="go",
        frontend="solid_tailwind_shadcn",
        validators=GO_VALIDATORS + FRONTEND_VALIDATORS,
    ),
    _sample(
        "python-click-config-frontend",
        backend="python",
        backend_mode="cli",
        python_cli_framework="click",
        frontend="solid_tailwind_shadcn",
        config_enabled="true",
        validators=PYTHON_VALIDATORS + FRONTEND_VALIDATORS,
        cli_help=(
            ("uv", "run", "python-click-config-frontend", "--help"),
            ("uv", "run", "python-click-config-frontend", "show-config-path", "--help"),
        ),
    ),
    _sample(
        "go-cobra-config-frontend",
        backend="go",
        backend_mode="cli",
        frontend="solid_tailwind_shadcn",
        config_enabled="true",
        validators=GO_VALIDATORS + FRONTEND_VALIDATORS,
        cli_help=(
            ("go", "run", "./cmd/go-cobra-config-frontend", "--help"),
            ("go", "run", "./cmd/go-cobra-config-frontend", "show-config-path", "--help"),
        ),
    ),
)

SAMPLES_BY_ID = {sample.sample_id: sample for sample in REPRESENTATIVE_SAMPLES}
