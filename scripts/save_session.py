#!/usr/bin/env python3
"""Save a work session, refresh Conda environment files, commit, and push."""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


PROJECT_ENV_NAME = "rating-dist-env"
PORTABLE_ENV_FILE = "environment.yml"
LOCK_ENV_FILE = "environment.lock.yml"


def is_windows() -> bool:
    return platform.system().lower().startswith("windows")


def run(command: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [str(part) for part in command]
    if is_windows() and command and command[0].lower().endswith((".bat", ".cmd")):
        command = ["cmd", "/d", "/c", *command]

    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if check and result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)

    return result


def repo_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def candidate_conda_paths() -> list[Path]:
    home = Path.home()
    names = ("miniforge3", "miniconda3", "mambaforge", "anaconda3")
    paths: list[Path] = []

    for name in names:
        paths.extend(
            [
                home / name / "bin" / "conda",
                home / name / "condabin" / "conda",
                home / name / "Scripts" / "conda.exe",
                home / name / "condabin" / "conda.bat",
            ]
        )

    paths.extend(
        [
            Path("/opt/homebrew/bin/conda"),
            Path("/opt/miniforge3/bin/conda"),
            Path("/opt/miniconda3/bin/conda"),
            Path("/opt/anaconda3/bin/conda"),
        ]
    )

    if is_windows():
        program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        for root in (program_data, local_app_data):
            if not str(root):
                continue
            for name in names:
                paths.extend(
                    [
                        root / name / "Scripts" / "conda.exe",
                        root / name / "condabin" / "conda.bat",
                    ]
                )

    return paths


def find_conda(explicit: str | None) -> str:
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            return str(explicit_path)
        found = shutil.which(explicit)
        if found:
            return found

    for command in ("conda", "mamba"):
        found = shutil.which(command)
        if found:
            return found

    for candidate in candidate_conda_paths():
        if candidate.exists():
            return str(candidate)

    raise SystemExit(
        "Could not find conda or mamba.\n"
        "Install Miniforge/Miniconda, open a terminal where conda is on PATH, "
        "or set CONDA_EXE to the full path of conda."
    )


def env_name_from_file(path: Path) -> str | None:
    if not path.exists():
        return None

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip() or None

    return None


def clean_conda_export(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.startswith("prefix:")]
    return "\n".join(lines).rstrip() + "\n"


def export_environment(conda: str, env_name: str, root: Path) -> str:
    portable = run(["conda" if conda == "conda" else conda, "env", "export", "-n", env_name, "--from-history"])
    lock = run(["conda" if conda == "conda" else conda, "env", "export", "-n", env_name, "--no-builds"])

    (root / PORTABLE_ENV_FILE).write_text(clean_conda_export(portable.stdout), encoding="utf-8")
    (root / LOCK_ENV_FILE).write_text(clean_conda_export(lock.stdout), encoding="utf-8")

    return (
        f"Updated {PORTABLE_ENV_FILE} with portable top-level dependencies and "
        f"{LOCK_ENV_FILE} with the full current export from Conda environment "
        f"'{env_name}' using {conda}."
    )


def short_commit_summary(summary: str) -> str:
    return " ".join(summary.split())[:60]


def write_session_log(root: Path, summary: str, env_status: str) -> Path:
    now = dt.datetime.now().astimezone()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    pretty_date = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    log_dir = root / "session_logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{timestamp}.md"

    status_before = run(["git", "status", "--short"], cwd=root).stdout.strip()
    diff_stat = run(["git", "diff", "--stat"], cwd=root, check=False).stdout.strip()

    content = [
        f"# Session Log: {pretty_date}",
        "",
        "## Summary",
        summary,
        "",
        "## Environment",
        env_status,
        "",
        "## Changed Files Before Commit",
    ]

    if status_before:
        content.extend(["```text", status_before, "```"])
    else:
        content.append("No working tree changes before this log file was created.")

    content.extend(["", "## Diff Stat Before Commit"])
    if diff_stat:
        content.extend(["```text", diff_stat, "```"])
    else:
        content.append("No diff stat available before this log file was created.")

    log_file.write_text("\n".join(content) + "\n", encoding="utf-8")
    return log_file


def commit_and_push(root: Path, summary: str, commit_message: str | None, no_push: bool) -> None:
    run(["git", "add", "."], cwd=root)

    staged = run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
    if staged.returncode == 0:
        print("No changes to commit.")
        return

    message = commit_message or f"Session update: {short_commit_summary(summary)}"
    run(["git", "commit", "-m", message], cwd=root)

    if no_push:
        print("Committed changes, but skipped push because --no-push was set.")
        return

    branch = run(["git", "branch", "--show-current"], cwd=root).stdout.strip()
    upstream = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=root,
        check=False,
    )

    if upstream.returncode == 0:
        run(["git", "push"], cwd=root)
    else:
        run(["git", "push", "-u", "origin", branch], cwd=root)

    commit_hash = run(["git", "rev-parse", "--short", "HEAD"], cwd=root).stdout.strip()
    print(f"Committed: {commit_hash} {message}")
    print(f"Pushed branch: {branch}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log a session, update Conda environment files, commit, and push."
    )
    parser.add_argument("summary", nargs="*", help="Short note describing what changed.")
    parser.add_argument(
        "--conda-env",
        default=os.environ.get("CONDA_ENV") or PROJECT_ENV_NAME,
        help=f"Conda environment name to export. Default: {PROJECT_ENV_NAME}.",
    )
    parser.add_argument(
        "--conda-exe",
        default=os.environ.get("CONDA_EXE"),
        help="Full path to conda/mamba if it is not on PATH.",
    )
    parser.add_argument(
        "--skip-env-export",
        action="store_true",
        default=os.environ.get("SKIP_ENV_EXPORT") == "1",
        help="Skip refreshing environment.yml and environment.lock.yml.",
    )
    parser.add_argument(
        "--commit-message",
        default=os.environ.get("COMMIT_MESSAGE"),
        help="Override the default Git commit message.",
    )
    parser.add_argument("--no-push", action="store_true", help="Commit locally without pushing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = " ".join(args.summary).strip()
    if not summary:
        summary = input("Session summary: ").strip()

    if not summary:
        raise SystemExit("A short session summary is required.")

    root = repo_root()
    os.chdir(root)

    if args.skip_env_export:
        env_status = "Skipped environment export because --skip-env-export or SKIP_ENV_EXPORT=1 was set."
    else:
        conda = find_conda(args.conda_exe)
        env_name = args.conda_env or env_name_from_file(root / PORTABLE_ENV_FILE) or PROJECT_ENV_NAME
        env_status = export_environment(conda, env_name, root)

    log_file = write_session_log(root, summary, env_status)
    commit_and_push(root, summary, args.commit_message, args.no_push)
    print(f"Saved session log: {log_file.relative_to(root)}")


if __name__ == "__main__":
    main()
