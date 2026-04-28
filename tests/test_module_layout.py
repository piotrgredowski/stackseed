from __future__ import annotations

import re
from pathlib import Path

import pytest
from representative_matrix import SAMPLES_BY_ID, RepresentativeSample
from test_representative_matrix import render_project

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_template_source_has_concern_markers_and_conditional_stack_paths() -> None:
    template = REPO_ROOT / "template"

    assert (template / "_source_shared" / ".gitkeep").is_file()
    assert (template / "_source_backend" / ".gitkeep").is_file()
    assert (template / "_source_frontend" / ".gitkeep").is_file()

    rendered_path_templates = {str(path.relative_to(template)) for path in template.rglob("*")}
    assert any("{{ backend_prefix }}" in path for path in rendered_path_templates)
    assert any("{{ frontend_prefix }}" in path for path in rendered_path_templates)


@pytest.mark.parametrize(
    "sample_id,root_files,absent_dirs",
    [
        ("python-library", {"pyproject.toml", "src", "tests"}, {"backend", "frontend"}),
        ("go-library", {"go.mod", "cmd", "internal"}, {"backend", "frontend"}),
        (
            "frontend-only",
            {"package.json", "index.html", "src", "vite.config.ts"},
            {"backend", "frontend"},
        ),
    ],
)
def test_single_stack_projects_keep_root_stack_layout(
    tmp_path: Path, sample_id: str, root_files: set[str], absent_dirs: set[str]
) -> None:
    project = render_project(tmp_path, SAMPLES_BY_ID[sample_id])

    for path in root_files:
        assert (project / path).exists(), f"{sample_id} should keep {path} at root"
    for path in absent_dirs:
        assert not (project / path).exists(), f"{sample_id} should not create {path}/"


@pytest.mark.parametrize("sample_id", ["python-frontend", "go-frontend"])
def test_full_stack_projects_split_backend_and_frontend_assets(
    tmp_path: Path, sample_id: str
) -> None:
    sample = SAMPLES_BY_ID[sample_id]
    project = render_project(tmp_path, sample)

    assert (project / "backend").is_dir()
    assert (project / "frontend").is_dir()
    assert not (project / "pyproject.toml").exists()
    assert not (project / "go.mod").exists()
    assert not (project / "package.json").exists()
    assert not (project / "src").exists()

    if sample.backend == "python":
        assert (project / "backend" / "pyproject.toml").is_file()
        assert (project / "backend" / "src").is_dir()
        assert not (project / "backend" / "package.json").exists()
    else:
        assert (project / "backend" / "go.mod").is_file()
        assert (project / "backend" / "cmd").is_dir()
        assert not (project / "backend" / "package.json").exists()

    assert (project / "frontend" / "package.json").is_file()
    assert (project / "frontend" / "src").is_dir()
    assert not (project / "frontend" / "pyproject.toml").exists()
    assert not (project / "frontend" / "go.mod").exists()


@pytest.mark.parametrize(
    "sample",
    [SAMPLES_BY_ID["python-click-config-frontend"], SAMPLES_BY_ID["go-cobra-config-frontend"]],
    ids=lambda sample: sample.sample_id,
)
def test_full_stack_docs_and_ci_use_stack_working_directories(
    tmp_path: Path, sample: RepresentativeSample
) -> None:
    project = render_project(tmp_path, sample)
    readme = (project / "README.md").read_text()
    agents = (project / "AGENTS.md").read_text()
    workflow = (project / ".github" / "workflows" / "ci.yml").read_text()

    assert "from `backend/`" in readme
    assert "from `frontend/`" in readme
    assert "Run backend commands from `backend/` and frontend commands from `frontend/`." in agents
    assert len(re.findall(r"working-directory: backend", workflow)) >= 4
    assert len(re.findall(r"working-directory: frontend", workflow)) >= 4
