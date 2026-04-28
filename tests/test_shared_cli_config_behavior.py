from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_command(
    args: list[str], cwd: Path | None = None, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def render_project(tmp_path: Path, name: str, **answers: str) -> Path:
    output_dir = tmp_path / name
    data = {
        "project_name": name.replace("-", " ").title(),
        "project_slug": name,
        "description": f"Generated CLI sample for {name}",
        "author_name": "Template Tester",
        "license": "MIT",
        "backend": "python",
        "backend_mode": "cli",
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

    result = run_command(command, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return output_dir


def cli_command(project: Path, slug: str, backend: str) -> list[str]:
    if backend == "go":
        return [str(project / ".bin" / slug)]
    return [str(project / ".venv" / "bin" / slug)]


def prepare(project: Path, slug: str, backend: str) -> None:
    command = ["go", "mod", "download"] if backend == "go" else ["uv", "sync", "--dev"]
    result = run_command(command, cwd=project, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    if backend == "go":
        (project / ".bin").mkdir()
        build = run_command(
            ["go", "build", "-o", str(project / ".bin" / slug), f"./cmd/{slug}"],
            cwd=project,
            timeout=90,
        )
        assert build.returncode == 0, build.stdout + build.stderr


def assert_no_live_process(pid: int) -> None:
    if sys.platform == "win32":
        return
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    raise AssertionError(f"process {pid} is still alive")


def wait_for_output(process: subprocess.Popen[str], needle: str, timeout: float = 5) -> str:
    deadline = time.monotonic() + timeout
    output = ""
    assert process.stdout is not None
    stdout_fd = process.stdout.fileno()
    os.set_blocking(stdout_fd, False)
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([stdout_fd], [], [], min(0.05, remaining))
        if not ready:
            if process.poll() is not None:
                break
            continue
        try:
            chunk = os.read(stdout_fd, 4096)
        except BlockingIOError:
            continue
        if chunk:
            output += chunk.decode()
            if needle in output:
                return output
        elif process.poll() is not None:
            break
        else:
            time.sleep(0.05)
    raise AssertionError(f"did not observe {needle!r}; saw {output!r}")


def test_wait_for_output_times_out_for_live_process_without_output() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    result: list[BaseException] = []

    def call_wait_for_output() -> None:
        try:
            wait_for_output(process, "never-emitted", timeout=0.2)
        except BaseException as error:
            result.append(error)

    thread = threading.Thread(target=call_wait_for_output)
    started = time.monotonic()
    thread.start()
    thread.join(timeout=1.0)
    elapsed = time.monotonic() - started
    try:
        assert not thread.is_alive(), "wait_for_output blocked past its timeout"
        assert elapsed < 1.0
        assert len(result) == 1
        assert isinstance(result[0], AssertionError)
        assert "never-emitted" in str(result[0])
    finally:
        pid = process.pid
        terminate(process)
        assert_no_live_process(pid)


def terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=5)


def test_cli_log_behavior_is_equivalent_across_argparse_click_and_cobra(tmp_path: Path) -> None:
    variants = [
        ("python-argparse-cli", "python", {"python_cli_framework": "argparse"}),
        ("python-click-cli", "python", {"python_cli_framework": "click"}),
        ("go-cobra-cli", "go", {"backend": "go"}),
    ]

    for slug, backend, answers in variants:
        project = render_project(tmp_path, slug, **answers)
        prepare(project, slug, backend)
        base = cli_command(project, slug, backend)

        help_result = run_command([*base, "--help"], cwd=project)
        assert help_result.returncode == 0, help_result.stdout + help_result.stderr
        assert "show-logs" in help_result.stdout
        assert "show-logs-path" in help_result.stdout

        command_help = run_command([*base, "show-logs", "--help"], cwd=project)
        assert command_help.returncode == 0, command_help.stdout + command_help.stderr
        assert "--follow" in command_help.stdout
        assert "--lines" in command_help.stdout

        path_from_root = run_command([*base, "show-logs-path"], cwd=project)
        path_from_tmp = run_command([*base, "show-logs-path"], cwd=tmp_path)
        assert path_from_root.returncode == 0
        assert path_from_tmp.returncode == 0
        assert path_from_root.stderr == ""
        assert path_from_tmp.stderr == ""
        assert path_from_root.stdout.count("\n") == 1
        assert path_from_root.stdout == path_from_tmp.stdout
        log_path = Path(path_from_root.stdout.strip())
        assert log_path.is_absolute()
        assert not log_path.exists()

        log_path.parent.mkdir(parents=True, exist_ok=True)
        fixture = [f"{slug}-line-{index:02d}" for index in range(1, 13)]
        log_path.write_text("\n".join(fixture) + "\n")
        before = log_path.read_text()
        assert run_command([*base, "show-logs-path"], cwd=project).stdout.strip() == str(log_path)
        assert log_path.read_text() == before

        default_logs = run_command([*base, "show-logs"], cwd=project)
        assert default_logs.returncode == 0, default_logs.stdout + default_logs.stderr
        assert default_logs.stderr == ""
        assert default_logs.stdout.splitlines() == fixture[-10:]

        two_logs = run_command([*base, "show-logs", "--lines", "2"], cwd=project)
        assert two_logs.returncode == 0
        assert two_logs.stdout.splitlines() == fixture[-2:]

        zero_logs = run_command([*base, "show-logs", "--lines", "0"], cwd=project)
        assert zero_logs.returncode == 0
        assert zero_logs.stdout == ""

        oversized = run_command([*base, "show-logs", "--lines", "99"], cwd=project)
        assert oversized.returncode == 0
        assert oversized.stdout.splitlines() == fixture

        for invalid in ["-1", "nope"]:
            result = run_command([*base, "show-logs", "--lines", invalid], cwd=project)
            assert result.returncode != 0

        process = subprocess.Popen(
            [*base, "show-logs", "--follow", "--lines", "2"],
            cwd=project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            wait_for_output(process, fixture[-1])
            appended = f"{slug}-appended"
            with log_path.open("a") as file:
                file.write(appended + "\n")
            observed = wait_for_output(process, appended)
            assert observed.count(appended) == 1
        finally:
            pid = process.pid
            terminate(process)
        assert_no_live_process(pid)

        log_path.unlink()
        missing = run_command([*base, "show-logs", "--lines", "3"], cwd=project)
        assert missing.returncode == 0
        assert missing.stdout == ""
        assert missing.stderr == ""


def test_follow_handles_missing_and_empty_logs_without_orphans(tmp_path: Path) -> None:
    variants = [
        ("missing-argparse", "python", {"python_cli_framework": "argparse"}),
        ("missing-click", "python", {"python_cli_framework": "click"}),
        ("missing-cobra", "go", {"backend": "go"}),
    ]

    for slug, backend, answers in variants:
        project = render_project(tmp_path, slug, **answers)
        prepare(project, slug, backend)
        base = cli_command(project, slug, backend)
        log_path = Path(run_command([*base, "show-logs-path"], cwd=project).stdout.strip())
        log_path.parent.mkdir(parents=True, exist_ok=True)

        for make_empty in [False, True]:
            if log_path.exists():
                log_path.unlink()
            if make_empty:
                log_path.touch()

            process = subprocess.Popen(
                [*base, "show-logs", "--follow"],
                cwd=project,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                time.sleep(0.3)
                assert process.poll() is None
                appended = f"{slug}-created-{make_empty}"
                with log_path.open("a") as file:
                    file.write(appended + "\n")
                observed = wait_for_output(process, appended)
                assert observed.strip() == appended
            finally:
                pid = process.pid
                terminate(process)
            assert_no_live_process(pid)


def test_config_scaffold_and_command_are_only_enabled_for_cli_projects(tmp_path: Path) -> None:
    enabled_variants = [
        ("config-argparse", "python", {"python_cli_framework": "argparse"}),
        ("config-click", "python", {"python_cli_framework": "click"}),
        ("config-cobra", "go", {"backend": "go"}),
    ]
    for slug, backend, answers in enabled_variants:
        project = render_project(tmp_path, slug, config_enabled="true", **answers)
        prepare(project, slug, backend)
        base = cli_command(project, slug, backend)
        assert (project / "config" / f"{slug}.toml").is_file()
        assert "Config scaffold: enabled" in (project / "README.md").read_text()
        assert "show-config-path" in run_command([*base, "--help"], cwd=project).stdout

        config_path = run_command([*base, "show-config-path"], cwd=project)
        assert config_path.returncode == 0, config_path.stdout + config_path.stderr
        assert config_path.stderr == ""
        assert config_path.stdout.count("\n") == 1
        path = Path(config_path.stdout.strip())
        assert path == (project / "config" / f"{slug}.toml").resolve()
        before = path.read_text()
        from_other_cwd = run_command([*base, "show-config-path"], cwd=tmp_path)
        assert from_other_cwd.stdout == config_path.stdout
        assert path.read_text() == before

    disabled = render_project(tmp_path, "config-disabled", config_enabled="false")
    prepare(disabled, "config-disabled", "python")
    assert not (disabled / "config").exists()
    base = cli_command(disabled, "config-disabled", "python")
    assert "show-config-path" not in run_command([*base, "--help"], cwd=disabled).stdout
    unknown = run_command([*base, "show-config-path"], cwd=disabled)
    assert unknown.returncode != 0
    assert not (disabled / "config").exists()

    for slug, answers in [
        ("none-config-leak", {"backend": "none", "backend_mode": "cli", "config_enabled": "true"}),
        (
            "python-library-config-leak",
            {"backend": "python", "backend_mode": "library", "config_enabled": "true"},
        ),
        (
            "go-library-config-leak",
            {"backend": "go", "backend_mode": "library", "config_enabled": "true"},
        ),
    ]:
        project = render_project(tmp_path, slug, **answers)
        rendered_text = "\n".join(
            path.read_text(errors="ignore")
            for path in project.rglob("*")
            if path.is_file() and ".git" not in path.parts
        )
        assert not (project / "config").exists()
        assert "show-config-path" not in rendered_text
        assert "Config scaffold: enabled" not in rendered_text
