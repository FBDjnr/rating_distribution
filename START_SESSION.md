# Start Session

Use `start session` when opening this workspace in Codex or VS Code.

This workspace includes a cross-platform helper at:

```text
scripts/start-session.py
```

It prepares the repository for development by checking Git sync, preparing the Conda environment from `environment.yml`, and running lightweight project readiness checks.

It also displays the previous chat memory from `session_memory/latest.md` and the newest file in `session_logs/` when those files exist.

The launcher needs either Python 3 on PATH or a Conda-compatible tool that can run Python from the base environment.

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

- GitHub pull is automatic only when the worktree is clean and the branch can be fast-forwarded.
- Local changes are never overwritten automatically.
- Conda is preferred first.
- Mamba and Micromamba are fallback options.
- Environment pruning is never automatic; the helper asks first.
- The previous session memory should be read before new project changes begin.
