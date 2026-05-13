#!/usr/bin/env python3
"""Prepare a workspace for a development session.

The default path is intentionally quick:
- it checks local Git status without network access
- it skips GitHub fetch/pull inside cloud-synced folders
- it verifies the Conda environment exists without solving every run
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CLOUD_SYNC_DIR_NAMES = {
    "google drive",
    "my drive",
    "shared drives",
    "dropbox",
    "box",
    "box drive",
    "box sync",
}


@dataclass
class Summary:
    git: list[str] = field(default_factory=list)
    environment: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_command(cmd: Iterable[str]) -> None:
    print("+ " + " ".join(str(part) for part in cmd))


def run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = False,
    show: bool = True,
    capture: bool = True,
    echo_output: bool | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    if echo_output is None:
        echo_output = show
    if show:
        print_command(cmd)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        message = f"{cmd[0]} could not be found: {exc}"
        if capture:
            result = subprocess.CompletedProcess(cmd, 127, message)
        else:
            print(message)
            result = subprocess.CompletedProcess(cmd, 127)
    except subprocess.TimeoutExpired as exc:
        message = f"Command timed out after {timeout} second(s): {' '.join(str(part) for part in cmd)}"
        if exc.stdout:
            message = f"{exc.stdout.rstrip()}\n{message}"
        if capture:
            result = subprocess.CompletedProcess(cmd, 124, message)
        else:
            print(message)
            result = subprocess.CompletedProcess(cmd, 124)
    if capture and result.stdout and echo_output:
        print(result.stdout.rstrip())
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout)
    return result


def resolve_command(command: str) -> str | None:
    return shutil.which(command)


def command_exists(command: str) -> bool:
    return resolve_command(command) is not None


def command_label(command: str) -> str:
    name = Path(command).name
    lower = name.lower()
    for suffix in (".exe", ".bat", ".cmd"):
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return name


def ask_yes_no(question: str, *, default: bool = False, assume_no: bool = False) -> bool:
    if assume_no or not sys.stdin.isatty():
        print(f"{question} {'[default: no]' if not default else '[default: yes]'}")
        return default

    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def cloud_sync_folder(path: Path) -> str | None:
    for part in path.resolve().parts:
        if part.casefold() in CLOUD_SYNC_DIR_NAMES:
            return part
    return None


def print_limited_lines(text: str, *, max_lines: int = 30) -> None:
    lines = text.splitlines()
    for line in lines[:max_lines]:
        print(line)
    if len(lines) > max_lines:
        print(f"... {len(lines) - max_lines} more line(s) omitted. Run Git directly for full status.")


def find_workspace_root() -> Path:
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "scripts":
        return script_path.parent.parent
    return Path.cwd().resolve()


def git_root(workspace: Path) -> Path | None:
    if not command_exists("git"):
        return None
    result = run(["git", "rev-parse", "--show-toplevel"], workspace, show=False, echo_output=False)
    if result.returncode != 0 or not result.stdout:
        return None
    return Path(result.stdout.strip()).resolve()


def git_has_remotes(repo: Path) -> bool:
    result = run(["git", "remote"], repo, show=False, echo_output=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def git_is_clean(repo: Path) -> bool:
    result = run(["git", "status", "--porcelain"], repo, show=False, echo_output=False)
    return result.returncode == 0 and result.stdout.strip() == ""


def git_upstream(repo: Path) -> str | None:
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo,
        show=False,
        echo_output=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_ahead_behind(repo: Path) -> tuple[int, int] | None:
    result = run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
        repo,
        show=False,
        echo_output=False,
    )
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])


def handle_git(workspace: Path, summary: Summary, sync_git: bool) -> None:
    print_section("Git")
    if not command_exists("git"):
        print("Git is not installed or not on PATH.")
        summary.warnings.append("Git is unavailable.")
        return

    repo = git_root(workspace)
    if repo is None:
        print("This workspace is not currently inside a Git repository.")
        summary.git.append("Not a Git repository.")
        return

    print(f"Repository root: {repo}")
    status = run(["git", "status", "--short", "--branch"], repo, show=False, echo_output=False)
    if status.stdout:
        print_limited_lines(status.stdout)
    run(["git", "remote", "-v"], repo, show=False, echo_output=False)

    cloud_folder = cloud_sync_folder(workspace)
    if cloud_folder:
        print(f"Cloud-synced folder detected ({cloud_folder}); GitHub fetch/pull is skipped.")
        summary.git.append(f"Cloud-synced workspace ({cloud_folder}); GitHub fetch/pull skipped.")
        sync_git = False

    has_remotes = git_has_remotes(repo)
    if not has_remotes:
        summary.git.append("No Git remote is configured.")
    elif sync_git:
        fetch = run(["git", "fetch", "--all", "--prune"], repo, timeout=120)
        if fetch.returncode == 0:
            summary.actions.append("Fetched all Git remotes and pruned stale remote-tracking refs.")
        else:
            summary.warnings.append("Git fetch failed. Network access or credentials may be needed.")
    else:
        summary.git.append("Remote fetch/pull skipped for quick start. Use --sync-git for an explicit network sync.")

    clean = git_is_clean(repo)
    upstream = git_upstream(repo)
    ahead_behind = git_ahead_behind(repo) if upstream else None

    if not clean:
        print("Worktree has local changes. Automatic pull is skipped.")
        summary.git.append("Worktree has local changes; pull skipped.")
        return

    if not upstream:
        print("Current branch has no upstream. Automatic pull is skipped.")
        summary.git.append("Clean worktree; no upstream branch.")
        return

    if ahead_behind is None:
        summary.warnings.append("Could not compare local branch with upstream.")
        return

    ahead, behind = ahead_behind
    if not sync_git:
        if ahead == 0 and behind == 0:
            print("Branch matches the last known upstream state.")
            summary.git.append("Clean and matches last known upstream state.")
        else:
            print(f"Local comparison with upstream: ahead {ahead}, behind {behind}.")
            summary.git.append(f"Local comparison only: ahead {ahead}, behind {behind}; no pull attempted.")
        return

    if behind > 0 and ahead == 0:
        print(f"Clean worktree and branch is behind {upstream} by {behind} commit(s). Pulling.")
        pull = run(["git", "pull", "--ff-only"], repo)
        if pull.returncode == 0:
            summary.actions.append(f"Pulled fast-forward updates from {upstream}.")
            summary.git.append("Clean and updated from upstream.")
        else:
            summary.warnings.append("Fast-forward pull failed; manual Git action is needed.")
    elif ahead > 0 and behind > 0:
        print(f"Branch has diverged from {upstream}: ahead {ahead}, behind {behind}.")
        summary.git.append("Clean but diverged from upstream; manual Git action needed.")
    elif ahead > 0:
        print(f"Branch is ahead of {upstream} by {ahead} commit(s).")
        summary.git.append("Clean and ahead of upstream.")
    elif behind > 0:
        summary.git.append(f"Clean and behind {upstream} by {behind} commit(s).")
    else:
        print("Branch is clean and up to date.")
        summary.git.append("Clean and up to date.")


def find_environment_file(workspace: Path) -> Path | None:
    for name in ("environment.yml", "environment.yaml"):
        path = workspace / name
        if path.exists():
            return path
    return None


def parse_environment_name(env_file: Path) -> str | None:
    name_pattern = re.compile(r"^\s*name\s*:\s*(.+?)\s*(?:#.*)?$")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        match = name_pattern.match(line)
        if match:
            raw = match.group(1).strip()
            return raw.strip("\"'")
    return None


def choose_env_tool() -> str | None:
    for command in ("conda", "mamba", "micromamba"):
        resolved = resolve_command(command)
        if resolved:
            return resolved
    return None


def pip_is_available(env_tool: str, env_name: str, workspace: Path) -> bool:
    result = env_run(env_tool, env_name, ["python", "-m", "pip", "--version"], workspace)
    return result.returncode == 0


def run_dependency_health_check(env_tool: str, env_name: str, workspace: Path, summary: Summary) -> None:
    tool_name = command_label(env_tool).lower()

    if tool_name == "conda":
        check = run(
            [env_tool, "check", "-n", env_name, "consistency", "-v"],
            workspace,
            timeout=120,
        )
        output = check.stdout or ""
        if check.returncode == 0 and "not consistent" not in output.lower() and "error running health check" not in output.lower():
            summary.checks.append("Conda consistency check passed.")
            return
        if check.returncode == 124:
            summary.warnings.append("Conda consistency check timed out; falling back to pip if available.")
        elif "invalid choice" in output.lower() or "unknown command" in output.lower():
            summary.warnings.append("Conda consistency check is unavailable; falling back to pip if available.")
        else:
            summary.warnings.append("Conda consistency check reported dependency issues.")
            return
    else:
        summary.checks.append(f"{command_label(env_tool)} is managing the environment; Conda consistency check is unavailable.")

    if pip_is_available(env_tool, env_name, workspace):
        pip_check = env_run(env_tool, env_name, ["python", "-m", "pip", "check"], workspace)
        if pip_check.returncode == 0:
            summary.checks.append("pip dependency check passed as a fallback.")
        else:
            summary.warnings.append("pip fallback dependency check reported issues.")
    else:
        summary.warnings.append(
            "No Conda consistency check or pip fallback is available; ask before installing Conda, pip, or continuing without dependency verification."
        )


def env_exists(tool: str, env_name: str, workspace: Path) -> bool:
    result = run([tool, "env", "list", "--json"], workspace, show=False, echo_output=False)
    if result.returncode == 0 and result.stdout:
        try:
            data = json.loads(result.stdout)
            for env_path in data.get("envs", []):
                if Path(env_path).name == env_name:
                    return True
        except json.JSONDecodeError:
            pass

    result = run([tool, "env", "list"], workspace, show=False, echo_output=False)
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].replace("*", "") == env_name:
            return True
        if parts and Path(parts[-1]).name == env_name:
            return True
    return False


def env_run(tool: str, env_name: str, args: list[str], workspace: Path) -> subprocess.CompletedProcess[str]:
    return run([tool, "run", "-n", env_name, *args], workspace)


def handle_environment(
    workspace: Path,
    summary: Summary,
    assume_no: bool,
    *,
    update_env: bool,
    health: bool,
) -> tuple[str | None, str | None]:
    print_section("Conda Environment")
    env_file = find_environment_file(workspace)
    if env_file is None:
        print("No environment.yml or environment.yaml found.")
        summary.environment.append("No Conda environment file found.")
        return None, None

    env_name = parse_environment_name(env_file)
    if not env_name:
        print(f"{env_file.name} does not define a top-level environment name.")
        summary.warnings.append("Conda environment file is missing a top-level name.")
        return None, None

    tool = choose_env_tool()
    if not tool:
        print("No Conda-compatible tool found. Conda is preferred for this workspace.")
        if command_exists("pip"):
            summary.warnings.append(
                "No Conda-compatible tool found; pip is available only as a fallback. Ask before installing Conda or continuing without Conda environment setup."
            )
        else:
            summary.warnings.append(
                "No Conda-compatible tool or pip found. Ask whether to install Conda, install pip, or continue without environment setup."
            )
        return env_name, None

    print(f"Environment file: {env_file}")
    print(f"Environment name: {env_name}")
    print(f"Environment manager: {command_label(tool)} ({tool})")

    exists = env_exists(tool, env_name, workspace)
    if exists:
        if update_env:
            use_prune = ask_yes_no(
                "Prune packages not listed in the environment file?",
                default=False,
                assume_no=assume_no,
            )
            cmd = [tool, "env", "update", "-n", env_name, "-f", str(env_file)]
            if use_prune:
                cmd.append("--prune")
            result = run(cmd, workspace)
            if result.returncode == 0:
                summary.environment.append(f"Updated Conda environment '{env_name}'.")
                if use_prune:
                    summary.actions.append("Environment update used --prune after confirmation.")
            else:
                summary.warnings.append(f"Failed to update Conda environment '{env_name}'.")
        else:
            print(f"Environment '{env_name}' exists. Update skipped for quick start.")
            summary.environment.append(f"Found Conda environment '{env_name}'; update skipped.")
    else:
        result = run([tool, "env", "create", "-f", str(env_file)], workspace)
        if result.returncode == 0:
            summary.environment.append(f"Created Conda environment '{env_name}'.")
        else:
            summary.warnings.append(f"Failed to create Conda environment '{env_name}'.")

    print("Verifying Python inside the environment.")
    env_run(tool, env_name, ["python", "--version"], workspace)
    if health:
        run_dependency_health_check(tool, env_name, workspace, summary)
    else:
        summary.checks.append("Dependency health check skipped for quick start. Use --health to run it.")

    return env_name, tool


def existing_files(workspace: Path, names: Iterable[str]) -> list[Path]:
    return [workspace / name for name in names if (workspace / name).exists()]


def read_limited(path: Path, *, max_chars: int = 1200) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[truncated]"


def latest_session_log(workspace: Path) -> Path | None:
    log_dir = workspace / "session_logs"
    if not log_dir.exists():
        return None
    logs = sorted(path for path in log_dir.glob("*.md") if path.is_file())
    return logs[-1] if logs else None


def show_previous_session_memory(workspace: Path, summary: Summary, show_contents: bool) -> None:
    print_section("Previous Session Memory")

    memory_file = workspace / "session_memory" / "latest.md"
    if memory_file.exists():
        print(f"Chat memory: {memory_file.relative_to(workspace)}")
        if show_contents:
            print(read_limited(memory_file))
        summary.checks.append("Loaded previous chat memory.")
    else:
        print("No session_memory/latest.md file found yet.")
        summary.checks.append("No previous chat memory file found.")

    log_file = latest_session_log(workspace)
    if log_file:
        print()
        print(f"Latest session log: {log_file.relative_to(workspace)}")
        if show_contents:
            print(read_limited(log_file))
        summary.checks.append("Loaded latest session log.")
    else:
        print("No previous session log found.")
        summary.checks.append("No previous session log found.")


def run_optional_checks(workspace: Path, summary: Summary, env_name: str | None, env_tool: str | None, assume_no: bool) -> None:
    print_section("Project Checks")

    instruction_files = existing_files(
        workspace,
        ("README.md", "CONTRIBUTING.md", "AGENTS.md", ".vscode/settings.json", ".vscode/tasks.json"),
    )
    if instruction_files:
        print("Project instruction files found:")
        for path in instruction_files:
            print(f"- {path.relative_to(workspace)}")
        summary.checks.append("Project instruction files detected.")

    pre_commit_config = workspace / ".pre-commit-config.yaml"
    if pre_commit_config.exists():
        print(".pre-commit-config.yaml found.")
        summary.checks.append("pre-commit configuration detected.")
        if env_name and env_tool:
            pre_commit = env_run(env_tool, env_name, ["pre-commit", "--version"], workspace)
            if pre_commit.returncode == 0:
                install_hooks = ask_yes_no(
                    "Install or refresh pre-commit hooks for this repo?",
                    default=False,
                    assume_no=assume_no,
                )
                if install_hooks:
                    hook_result = env_run(env_tool, env_name, ["pre-commit", "install"], workspace)
                    if hook_result.returncode == 0:
                        summary.actions.append("Installed pre-commit hooks.")
                    else:
                        summary.warnings.append("pre-commit hook installation failed.")
            else:
                summary.warnings.append("pre-commit config exists, but pre-commit is not available in the environment.")

    gitmodules = workspace / ".gitmodules"
    if gitmodules.exists() and command_exists("git"):
        run(["git", "submodule", "status"], workspace)
        summary.checks.append("Checked Git submodule status.")

    gitattributes = workspace / ".gitattributes"
    if gitattributes.exists() and "filter=lfs" in gitattributes.read_text(encoding="utf-8", errors="ignore"):
        if command_exists("git"):
            lfs = run(["git", "lfs", "status"], workspace)
            if lfs.returncode == 0:
                summary.checks.append("Checked Git LFS status.")
            else:
                summary.warnings.append("Git LFS appears to be used, but git lfs status failed.")

    env_example = workspace / ".env.example"
    if env_example.exists():
        local_env = workspace / ".env"
        if local_env.exists():
            print(".env.example and .env both exist. Secrets were not printed.")
            summary.checks.append(".env file exists for .env.example.")
        else:
            print(".env.example exists, but .env is missing.")
            summary.warnings.append(".env.example exists but .env is missing.")

    notebooks = list(workspace.glob("*.ipynb"))
    notebooks_dir = workspace / "notebooks"
    if notebooks_dir.exists():
        notebooks.extend(notebooks_dir.glob("*.ipynb"))
    if notebooks:
        print(f"Notebook files detected: {len(notebooks)}")
        if env_name and env_tool:
            kernel_check = env_run(env_tool, env_name, ["python", "-m", "ipykernel", "--version"], workspace)
            if kernel_check.returncode == 0:
                summary.checks.append("Notebook kernel package ipykernel is available.")
            else:
                summary.warnings.append("Notebooks detected, but ipykernel is not available in the environment.")

    test_markers = [
        workspace / "pytest.ini",
        workspace / "tox.ini",
        workspace / "noxfile.py",
        workspace / "tests",
    ]
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        has_pytest = "[tool.pytest" in text or "pytest" in text
    else:
        has_pytest = False

    if any(path.exists() for path in test_markers) or has_pytest:
        print("Pytest-style tests appear to be configured. Running collect-only check.")
        if env_name and env_tool:
            result = env_run(env_tool, env_name, ["python", "-m", "pytest", "--collect-only"], workspace)
        else:
            result = run([sys.executable, "-m", "pytest", "--collect-only"], workspace)
        if result.returncode == 0:
            summary.checks.append("pytest collect-only passed.")
        else:
            summary.warnings.append("pytest collect-only failed or pytest is unavailable.")

    vscode_settings = workspace / ".vscode" / "settings.json"
    if vscode_settings.exists():
        try:
            settings = json.loads(vscode_settings.read_text(encoding="utf-8"))
            interpreter = settings.get("python.defaultInterpreterPath") or settings.get("python.pythonPath")
            if interpreter:
                print(f"VS Code Python interpreter setting: {interpreter}")
                summary.checks.append("VS Code Python interpreter setting detected.")
            elif env_name:
                print(f"VS Code has settings.json. Suggested interpreter environment: {env_name}")
                summary.checks.append("Suggested matching VS Code interpreter environment.")
        except json.JSONDecodeError:
            summary.warnings.append(".vscode/settings.json is not valid JSON.")


def print_summary(summary: Summary) -> None:
    print_section("Session Summary")
    sections = [
        ("Git", summary.git),
        ("Environment", summary.environment),
        ("Checks", summary.checks),
        ("Actions", summary.actions),
        ("Warnings / Decisions Needed", summary.warnings),
    ]
    for title, items in sections:
        print(f"{title}:")
        if items:
            for item in items:
                print(f"- {item}")
        else:
            print("- Nothing to report.")
        print()
    print("Recommended next command: start work. Use --sync-git --update-env --health --full-checks only when you need a full refresh.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare this workspace for a development session.")
    parser.add_argument(
        "--assume-no",
        action="store_true",
        help="Answer no to interactive prompts such as environment pruning.",
    )
    parser.add_argument(
        "--sync-git",
        action="store_true",
        help="Fetch remotes and fast-forward pull when safe. Ignored inside Google Drive, Shared Drives, Dropbox, or Box folders.",
    )
    parser.add_argument(
        "--update-env",
        action="store_true",
        help="Update an existing Conda environment from environment.yml. By default, start session only verifies it exists.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run the Conda dependency consistency check. Skipped by default for speed.",
    )
    parser.add_argument(
        "--full-checks",
        action="store_true",
        help="Run optional project checks such as pre-commit, notebooks, Git LFS, submodules, and pytest discovery.",
    )
    parser.add_argument(
        "--show-memory",
        action="store_true",
        help="Print snippets of previous memory and latest session log. By default, only their paths are shown.",
    )
    args = parser.parse_args()

    workspace = find_workspace_root()
    summary = Summary()

    print_section("Start Session")
    print(f"Workspace root: {workspace}")
    print(f"Operating system: {platform.system()} {platform.release()}")
    print(f"Shell: {os.environ.get('SHELL') or os.environ.get('COMSPEC') or 'unknown'}")

    show_previous_session_memory(workspace, summary, args.show_memory)
    handle_git(workspace, summary, args.sync_git)
    env_name, env_tool = handle_environment(
        workspace,
        summary,
        args.assume_no,
        update_env=args.update_env,
        health=args.health,
    )
    if args.full_checks:
        run_optional_checks(workspace, summary, env_name, env_tool, args.assume_no)
    else:
        summary.checks.append("Optional project checks skipped for quick start. Use --full-checks to run them.")
    print_summary(summary)

    return 0 if not summary.warnings else 1


if __name__ == "__main__":
    raise SystemExit(main())
