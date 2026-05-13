# Codex Workspace Instructions

## Start Session Command

When the user types `start session`, treat it as a request to prepare the workspace for development.

Also accept `star session` as an alias for the same workflow, because it is a likely typo.

Before making project changes, read the latest durable context if it exists:

- `session_memory/latest.md`
- the newest `session_logs/*.md` file

Run the workspace helper:

```bash
python scripts/start-session.py
```

If `python` is not available on macOS or Linux, try:

```bash
python3 scripts/start-session.py
```

The workspace also includes launcher wrappers:

- Windows PowerShell: `scripts/start-session.ps1`
- Windows Command Prompt: `scripts/start-session.cmd`
- macOS/Linux shell: `sh scripts/start-session.sh`

By default, keep startup fast and local. Do not run network Git sync, Conda solves, dependency health checks, notebook checks, test discovery, or long memory dumps unless the user asks for a full refresh or a specific check.

If the helper needs network access for an explicit Git sync or Conda package installation and the current environment blocks network access, ask for approval and rerun the needed command with elevated/network permissions.

When asking for elevated or network permissions, request a stable persisted permission for the narrow command pattern whenever the tool supports it. Record newly granted permissions in the session memory or session log so future sessions know what was approved. Prefer OS-agnostic command names and repo-relative paths; use machine-specific absolute paths only when no portable option is available.

## Required Behavior

The `start session` workflow should:

1. Detect the operating system, shell, workspace root, and Git repository root.
2. Load the previous chat memory and latest session log when present, but display only concise paths or short snippets unless full context is requested.
3. Check local Git status and remotes.
4. Do not fetch from or pull GitHub by default.
5. Never fetch from or pull GitHub during `start session` when the workspace path is inside Google Drive, Shared Drives, Dropbox, Box, Box Drive, or Box Sync.
6. When the user explicitly requests Git sync with `--sync-git`, fetch from all remotes with pruning of stale remote-tracking refs only outside cloud-synced folders.
7. Pull from GitHub automatically only during explicit Git sync and only when:
   - the current branch has an upstream branch
   - the worktree is clean
   - the local branch is behind the upstream branch
   - the local branch is not ahead of the upstream branch
8. Never overwrite, reset, stash, rebase, or discard local changes without explicit user approval.
9. Use Conda as the preferred environment manager.
10. Fall back to Mamba or Micromamba only when Conda is unavailable.
11. Use pip only as a backup for dependency checks or Python package work when Conda-compatible tooling is unavailable.
12. If neither Conda-compatible tooling nor pip is available, notify the user and ask whether to install Conda, install pip, or continue without environment setup.
13. Read `environment.yml` or `environment.yaml` from the workspace root.
14. Create the environment if it does not exist.
15. Do not update an existing environment by default; update it only when the user requests `--update-env` or a full refresh.
16. Ask before using Conda's `--prune` option.
17. Check broken dependencies with Conda's native health check, such as `conda check`/`conda doctor` consistency checks, only when the user requests `--health`; use `pip check` only as a fallback.
18. Keep optional checks opt-in via `--full-checks` so startup stays short.
19. Keep the workflow OS- and computer-agnostic by resolving commands from `PATH`, using launcher wrappers, and avoiding hard-coded user-specific paths.

## Optional Checks To Include

When relevant, also check:

- `.pre-commit-config.yaml`, and ask before installing hooks.
- Git LFS status when LFS appears to be used.
- Git submodule status when `.gitmodules` exists.
- `.env.example` versus local `.env`, without printing secrets.
- Notebook kernel readiness when notebooks are present.
- Project instructions in `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, and `.vscode/`.
- Lightweight test or lint discovery, preferring collect-only checks before full test runs.

## Session Summary

At the end of `start session`, summarize:

- Current branch and Git sync status.
- Whether the worktree is clean or modified.
- Conda environment name and status.
- Whether packages were created or updated.
- Health check results.
- Any decisions needed from the user.
- The recommended next command.

## End Session Command

When the user types `end session`, treat it as a request to close the workspace carefully and sync the project.

Before running the helper, write two concise summaries:

- Task summary: what was done to the project since the last logged session.
- Chat summary: context from the conversation that a future Codex session should know.

Run the workspace helper and pass both summaries:

```bash
python scripts/end-session.py "TASK SUMMARY" --chat-summary "CHAT SUMMARY"
```

If `python` is not available on macOS or Linux, try:

```bash
python3 scripts/end-session.py "TASK SUMMARY" --chat-summary "CHAT SUMMARY"
```

The workspace also includes launcher wrappers:

- Windows PowerShell: `scripts/end-session.ps1`
- Windows Command Prompt: `scripts/end-session.cmd`
- macOS/Linux shell: `sh scripts/end-session.sh`

The `end session` workflow should:

1. Save all relevant project changes on the local machine.
2. Refresh `environment.yml` and `environment.lock.yml` from the Conda environment when Conda, Mamba, or Micromamba is available.
3. If the environment manager is unavailable, record that limitation in the session log and continue.
4. Summarize commits and file changes since the newest prior `session_logs/*.md` file.
5. Write a new timestamped file in `session_logs/`.
6. Write the durable chat memory to `session_memory/latest.md` and archive it in `session_memory/`.
7. Respect `.gitignore`, including local-only folders such as `meeting_notes/`.
8. Stage, commit, and push changes to GitHub.
9. Never force-push, reset, discard, or delete local files without explicit user approval.
10. If GitHub has changed in a way that prevents a safe push, stop and explain the manual sync needed.

Good closing practices:

- Save all open editor tabs before `end session`.
- Run or record the relevant tests or notebook validation when practical.
- Check `git status --short --branch` before closing VS Code or switching laptops.
- Keep private notes, credentials, raw data, and machine-specific files ignored.
- Wait for the final push to finish before opening the repo on another computer.
