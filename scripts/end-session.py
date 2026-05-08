#!/usr/bin/env python3
"""Close a workspace session, log what changed, commit, and push.

This helper is intentionally conservative. It will not force-push, reset,
discard changes, or delete local files. It records enough context for a future
start-session run to recover the previous conversation and project state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Iterable


PORTABLE_ENV_FILE = "environment.yml"
LOCK_ENV_FILE = "environment.lock.yml"
SESSION_LOG_DIR = "session_logs"
SESSION_MEMORY_DIR = "session_memory"
LATEST_MEMORY_FILE = "latest.md"


@dataclass
class SessionReport:
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    environment: list[str] = field(default_factory=list)
    git: list[str] = field(default_factory=list)


def is_windows() -> bool:
    return platform.system().lower().startswith("windows")


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_command(command: Iterable[str]) -> None:
    print("+ " + " ".join(str(part) for part in command))


def run(
    command: list[str],
    cwd: Path | None = None,
    *,
    check: bool = False,
    show: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [str(part) for part in command]
    if is_windows() and command and command[0].lower().endswith((".bat", ".cmd")):
        command = ["cmd", "/d", "/c", *command]

    if show:
        print_command(command)

    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    if result.stdout and show:
        print(result.stdout.rstrip())

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command, result.stdout)

    return result


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def workspace_root() -> Path:
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "scripts":
        return script_path.parent.parent
    return Path.cwd().resolve()


def repo_root(workspace: Path) -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], workspace, check=True, show=False)
    return Path(result.stdout.strip()).resolve()


def git_output(args: list[str], repo: Path, *, check: bool = False) -> str:
    result = run(["git", *args], repo, check=check, show=False)
    return result.stdout.strip() if result.stdout else ""


def git_has_remotes(repo: Path) -> bool:
    return bool(git_output(["remote"], repo))


def git_upstream(repo: Path) -> str | None:
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo,
        show=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_ahead_behind(repo: Path) -> tuple[int, int] | None:
    result = run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], repo, show=False)
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])


def git_is_clean(repo: Path) -> bool:
    return git_output(["status", "--porcelain"], repo) == ""


def pull_fast_forward_if_safe(repo: Path, report: SessionReport) -> None:
    if not git_has_remotes(repo):
        report.git.append("No Git remotes configured.")
        return

    fetch = run(["git", "fetch", "--all", "--prune"], repo)
    if fetch.returncode == 0:
        report.actions.append("Fetched all remotes before closing the session.")
    else:
        report.warnings.append("Could not fetch remotes before closing the session.")
        return

    upstream = git_upstream(repo)
    ahead_behind = git_ahead_behind(repo) if upstream else None
    if not upstream or ahead_behind is None:
        report.git.append("Current branch has no upstream branch.")
        return

    ahead, behind = ahead_behind
    if behind > 0 and ahead == 0 and git_is_clean(repo):
        pull = run(["git", "pull", "--ff-only"], repo)
        if pull.returncode == 0:
            report.actions.append(f"Pulled fast-forward updates from {upstream}.")
        else:
            report.warnings.append("Fast-forward pull failed before closing the session.")
    elif behind > 0 and ahead == 0:
        report.git.append(f"Branch is behind {upstream}, but local changes exist; pull skipped.")
    elif ahead > 0 and behind > 0:
        report.warnings.append(f"Branch has diverged from {upstream}; manual Git sync is needed.")
    elif ahead > 0:
        report.git.append(f"Branch is ahead of {upstream} by {ahead} commit(s).")
    else:
        report.git.append(f"Branch is up to date with {upstream}.")


def find_environment_file(root: Path) -> Path | None:
    for name in ("environment.yml", "environment.yaml"):
        path = root / name
        if path.exists():
            return path
    return None


def parse_environment_name(path: Path) -> str | None:
    pattern = re.compile(r"^\s*name\s*:\s*(.+?)\s*(?:#.*)?$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip().strip("\"'")
    return None


def find_env_tool(explicit: str | None) -> str | None:
    if explicit:
        expanded = Path(explicit).expanduser()
        if expanded.exists():
            return str(expanded)
        found = shutil.which(explicit)
        if found:
            return found

    for command in ("conda", "mamba", "micromamba"):
        found = shutil.which(command)
        if found:
            return found
    return None


def clean_conda_export(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("prefix:"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def env_exists(tool: str, env_name: str, root: Path) -> bool:
    result = run([tool, "env", "list"], root, show=False)
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        normalized = [part.replace("*", "") for part in parts]
        if env_name in normalized or Path(parts[-1]).name == env_name:
            return True
    return False


def export_environment(root: Path, args: argparse.Namespace, report: SessionReport) -> None:
    print_section("Environment")
    env_file = find_environment_file(root)
    if env_file is None:
        report.environment.append("No environment.yml or environment.yaml found.")
        print(report.environment[-1])
        return

    env_name = args.conda_env or parse_environment_name(env_file)
    if not env_name:
        report.warnings.append(f"{env_file.name} has no top-level environment name.")
        print(report.warnings[-1])
        return

    if args.skip_env_export:
        report.environment.append("Skipped environment export by request.")
        print(report.environment[-1])
        return

    tool = find_env_tool(args.conda_exe)
    if not tool:
        report.warnings.append(
            "Could not update environment.yml because Conda, Mamba, and Micromamba were unavailable."
        )
        print(report.warnings[-1])
        return

    if not env_exists(tool, env_name, root):
        report.warnings.append(f"Could not update environment files because environment '{env_name}' was not found.")
        print(report.warnings[-1])
        return

    portable = run([tool, "env", "export", "-n", env_name, "--from-history"], root)
    if portable.returncode == 0 and portable.stdout.strip():
        (root / PORTABLE_ENV_FILE).write_text(clean_conda_export(portable.stdout), encoding="utf-8")
        report.environment.append(f"Updated {PORTABLE_ENV_FILE} from Conda environment '{env_name}'.")
    else:
        report.warnings.append(f"Could not refresh {PORTABLE_ENV_FILE} from '{env_name}'.")

    lock = run([tool, "env", "export", "-n", env_name, "--no-builds"], root)
    if lock.returncode == 0 and lock.stdout.strip():
        (root / LOCK_ENV_FILE).write_text(clean_conda_export(lock.stdout), encoding="utf-8")
        report.environment.append(f"Updated {LOCK_ENV_FILE} from Conda environment '{env_name}'.")
    else:
        report.warnings.append(f"Could not refresh {LOCK_ENV_FILE} from '{env_name}'.")


def latest_session_log(root: Path) -> Path | None:
    log_dir = root / SESSION_LOG_DIR
    if not log_dir.exists():
        return None
    logs = sorted(path for path in log_dir.glob("*.md") if path.is_file())
    return logs[-1] if logs else None


def commit_for_file(repo: Path, path: Path) -> str | None:
    rel = path.relative_to(repo).as_posix()
    result = run(["git", "log", "-n", "1", "--format=%H", "--", rel], repo, show=False)
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def collect_changes_since_previous_log(repo: Path, previous_log: Path | None) -> dict[str, str]:
    if previous_log is None:
        return {
            "previous_log": "No previous session log found.",
            "commits": "",
            "names": "",
            "stat": "",
        }

    previous_commit = commit_for_file(repo, previous_log)
    rel_log = previous_log.relative_to(repo).as_posix()
    if not previous_commit:
        return {
            "previous_log": f"{rel_log} exists but has not been committed yet.",
            "commits": "",
            "names": "",
            "stat": "",
        }

    return {
        "previous_log": f"{rel_log} last touched in {previous_commit[:12]}.",
        "commits": git_output(["log", "--oneline", f"{previous_commit}..HEAD"], repo),
        "names": git_output(["diff", "--name-status", f"{previous_commit}..HEAD"], repo),
        "stat": git_output(["diff", "--stat", f"{previous_commit}..HEAD"], repo),
    }


def read_text_arg(value: str | None, file_value: str | None) -> str:
    if file_value:
        return Path(file_value).expanduser().read_text(encoding="utf-8").strip()
    return (value or "").strip()


def write_chat_memory(root: Path, chat_summary: str, timestamp: str, pretty_date: str) -> tuple[Path, Path]:
    memory_dir = root / SESSION_MEMORY_DIR
    memory_dir.mkdir(exist_ok=True)
    archive = memory_dir / f"{timestamp}.md"
    latest = memory_dir / LATEST_MEMORY_FILE

    content = "\n".join(
        [
            f"# Session Memory: {pretty_date}",
            "",
            "## Chat Summary",
            chat_summary or "No chat summary was supplied for this session.",
            "",
            "## Resume Prompt",
            "At the next `start session`, read this file and the latest session log before making changes.",
            "",
        ]
    )

    archive.write_text(content, encoding="utf-8")
    latest.write_text(content, encoding="utf-8")
    return archive, latest


def write_session_log(
    root: Path,
    summary: str,
    chat_summary: str,
    env_report: SessionReport,
    changes: dict[str, str],
    timestamp: str,
    pretty_date: str,
) -> Path:
    log_dir = root / SESSION_LOG_DIR
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{timestamp}.md"

    status = git_output(["status", "--short", "--branch"], root)
    diff_stat = git_output(["diff", "--stat"], root)

    practices = [
        "Save all editor tabs before running `end session`.",
        "Review `git status --short --branch` before pushing.",
        "Keep private files in ignored folders such as `meeting_notes/`.",
        "Avoid switching laptops until `git status` says the branch is synced with its upstream.",
        "Do not force-push unless you intentionally coordinated a history rewrite.",
    ]

    sections: list[str] = [
        f"# Session Log: {pretty_date}",
        "",
        "## Task Summary",
        summary,
        "",
        "## Chat Summary For Next Session",
        chat_summary or "No chat summary was supplied for this session.",
        "",
        "## Previous Session Log",
        changes["previous_log"],
        "",
        "## Commits Since Previous Session Log",
    ]

    sections.extend(code_or_empty(changes["commits"], "No committed changes since the previous session log."))
    sections.extend(["", "## Files Changed Since Previous Session Log"])
    sections.extend(code_or_empty(changes["names"], "No committed file changes since the previous session log."))
    sections.extend(["", "## Diff Stat Since Previous Session Log"])
    sections.extend(code_or_empty(changes["stat"], "No committed diff stat since the previous session log."))

    sections.extend(["", "## Environment"])
    sections.extend(bullets_or_empty(env_report.environment, "No environment updates recorded."))

    sections.extend(["", "## Git And Sync Notes"])
    sections.extend(bullets_or_empty(env_report.git, "No Git sync notes recorded."))

    sections.extend(["", "## Actions"])
    sections.extend(bullets_or_empty(env_report.actions, "No automatic actions recorded."))

    sections.extend(["", "## Warnings"])
    sections.extend(bullets_or_empty(env_report.warnings, "No warnings recorded."))

    sections.extend(["", "## Working Tree Before Commit"])
    sections.extend(code_or_empty(status, "Working tree was clean before this log file was created."))

    sections.extend(["", "## Uncommitted Diff Stat Before Commit"])
    sections.extend(code_or_empty(diff_stat, "No uncommitted diff stat before this log file was created."))

    sections.extend(["", "## Good Closing Practices"])
    sections.extend(f"- {item}" for item in practices)
    sections.append("")

    log_file.write_text("\n".join(sections), encoding="utf-8")
    return log_file


def code_or_empty(text: str, empty: str) -> list[str]:
    if not text.strip():
        return [empty]
    return ["```text", text.strip(), "```"]


def bullets_or_empty(items: list[str], empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def short_commit_summary(summary: str) -> str:
    cleaned = " ".join(summary.split())
    return cleaned[:64] if cleaned else "Close workspace session"


def commit_and_push(root: Path, summary: str, args: argparse.Namespace, report: SessionReport) -> None:
    print_section("Commit And Push")
    run(["git", "add", "--all"], root, check=True)

    staged = run(["git", "diff", "--cached", "--quiet"], root, show=False)
    if staged.returncode == 0:
        print("No changes to commit.")
        report.git.append("No changes to commit.")
        return

    message = args.commit_message or f"End session: {short_commit_summary(summary)}"
    run(["git", "commit", "-m", message], root, check=True)
    report.actions.append(f"Created commit: {message}")

    if args.no_push:
        report.git.append("Skipped push because --no-push was set.")
        return

    upstream = git_upstream(root)
    branch = git_output(["branch", "--show-current"], root)

    if upstream:
        push = run(["git", "push"], root)
    else:
        push = run(["git", "push", "-u", "origin", branch], root)

    if push.returncode == 0:
        report.actions.append("Pushed committed changes to GitHub.")
    else:
        report.warnings.append("Git push failed. Fetch, resolve any divergence, then push manually.")
        raise SystemExit(push.returncode)

    final = git_output(["status", "--short", "--branch"], root)
    print(final)
    report.git.append(final)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End a workspace session and sync with GitHub.")
    parser.add_argument(
        "summary",
        nargs="*",
        help="Short task summary. Codex should supply this when the user says `end session`.",
    )
    parser.add_argument("--summary-file", help="Read the task summary from a UTF-8 text file.")
    parser.add_argument("--chat-summary", help="Short chat memory to load during the next start session.")
    parser.add_argument("--chat-summary-file", help="Read the chat memory from a UTF-8 text file.")
    parser.add_argument("--conda-env", help="Conda environment name. Defaults to the name in environment.yml.")
    parser.add_argument("--conda-exe", default=os.environ.get("CONDA_EXE"), help="Path or command for conda/mamba.")
    parser.add_argument("--skip-env-export", action="store_true", help="Do not refresh environment export files.")
    parser.add_argument("--commit-message", help="Override the default Git commit message.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally without pushing to GitHub.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not command_exists("git"):
        raise SystemExit("Git is required for end-session.")

    root = repo_root(workspace_root())
    os.chdir(root)

    summary = read_text_arg(" ".join(args.summary), args.summary_file)
    if not summary and sys.stdin.isatty():
        summary = input("Task summary: ").strip()
    if not summary:
        raise SystemExit("A task summary is required.")

    chat_summary = read_text_arg(args.chat_summary, args.chat_summary_file)
    now = dt.datetime.now().astimezone()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    pretty_date = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    report = SessionReport()

    print_section("End Session")
    print(f"Workspace root: {root}")
    print(f"Operating system: {platform.system()} {platform.release()}")

    previous_log = latest_session_log(root)
    changes = collect_changes_since_previous_log(root, previous_log)

    pull_fast_forward_if_safe(root, report)
    export_environment(root, args, report)
    memory_archive, latest_memory = write_chat_memory(root, chat_summary, timestamp, pretty_date)
    log_file = write_session_log(root, summary, chat_summary, report, changes, timestamp, pretty_date)

    report.actions.append(f"Saved session log: {log_file.relative_to(root).as_posix()}")
    report.actions.append(f"Saved chat memory: {latest_memory.relative_to(root).as_posix()}")
    report.actions.append(f"Archived chat memory: {memory_archive.relative_to(root).as_posix()}")

    commit_and_push(root, summary, args, report)

    print_section("End Session Summary")
    for item in report.actions:
        print(f"- {item}")
    for item in report.environment:
        print(f"- {item}")
    for item in report.git:
        print(f"- {item}")
    if report.warnings:
        print("Warnings:")
        for item in report.warnings:
            print(f"- {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
