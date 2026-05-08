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

If the helper needs network access for Git fetch/pull or Conda package installation and the current environment blocks network access, ask for approval and rerun the needed command with elevated/network permissions.

## Required Behavior

The `start session` workflow should:

1. Detect the operating system, shell, workspace root, and Git repository root.
2. Load and display the previous chat memory and latest session log when present.
3. Check Git status and remotes.
4. Fetch from all remotes with pruning of stale remote-tracking refs.
5. Pull from GitHub automatically only when:
   - the current branch has an upstream branch
   - the worktree is clean
   - the local branch is behind the upstream branch
   - the local branch is not ahead of the upstream branch
6. Never overwrite, reset, stash, rebase, or discard local changes without explicit user approval.
7. Use Conda as the preferred environment manager.
8. Fall back to Mamba or Micromamba only when Conda is unavailable.
9. Read `environment.yml` or `environment.yaml` from the workspace root.
10. Create the environment if it does not exist.
11. Update the environment if it already exists.
12. Ask before using Conda's `--prune` option.
13. Run lightweight health checks and report anything that needs user action.

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
