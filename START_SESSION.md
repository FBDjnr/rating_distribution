# Start Session

Use `start session` when opening this workspace in Codex or VS Code.

This workspace includes a cross-platform helper at:

```text
scripts/start-session.py
```

It prepares the repository for development with a quick local check: previous-session pointers, local Git status, and Conda environment presence from `environment.yml`.

It also displays the previous chat memory from `session_memory/latest.md` and the newest file in `session_logs/` when those files exist.

The launcher needs either Python 3 on PATH or a Conda-compatible tool that can run Python from the base environment.
All command discovery should happen through `PATH` or the launcher wrappers so the workflow keeps working across operating systems and computers.

## From Codex

Type:

```text
start session
```

or, if you mistype it:

```text
star session
```

Codex should follow `AGENTS.md` and run the helper script.

## From VS Code

Open the Command Palette and run:

```text
Tasks: Run Task
```

Then choose:

```text
start session
```

There is also a `star session` alias task.

## From A Terminal

Windows:

```powershell
scripts\start-session.ps1
```

macOS or Linux:

```bash
sh scripts/start-session.sh
```

## Workflow Preferences

- Startup should be quick and local by default.
- GitHub fetch/pull is skipped by default.
- GitHub fetch/pull is always skipped when the project folder is inside Google Drive, Shared Drives, Dropbox, Box, Box Drive, or Box Sync.
- Use `--sync-git` only when an explicit network Git refresh is needed outside cloud-synced folders.
- GitHub pull is automatic only during explicit sync, only when the worktree is clean, and only when the branch can be fast-forwarded.
- Local changes are never overwritten automatically.
- Conda is preferred first for environment management and dependency checks.
- Mamba and Micromamba are fallback environment managers when Conda is unavailable.
- Existing Conda environments are not updated by default; use `--update-env` for that.
- `conda check` or `conda doctor` consistency checks are preferred for broken dependency detection, but run them only with `--health`.
- `pip check` is used only as a fallback when Conda-compatible dependency checks are unavailable.
- If neither Conda-compatible tooling nor pip is available, stop and ask whether to install Conda, install pip, or continue without environment setup.
- Environment pruning is never automatic; the helper asks first.
- The previous session memory should be loaded before new project changes begin, but full memory/log text is printed only with `--show-memory`.
- Optional project checks run only with `--full-checks`.
- When elevated or network permissions are granted, save narrow reusable command permissions when the tool supports it and record the grant in session memory or the session log.

## Full Refresh

Use this only when you actually want the slower checks:

```text
start session --sync-git --update-env --health --full-checks --show-memory
```
