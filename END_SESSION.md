# End Session

Use `end session` when closing this workspace in Codex or VS Code.

This workspace includes a cross-platform helper at:

```text
scripts/end-session.py
```

It closes the loop by refreshing environment exports when possible, writing a new session log, saving chat memory for the next session, committing local project changes, and pushing the branch to GitHub.

## From Codex

Type:

```text
end session
```

Codex should follow `AGENTS.md`, prepare a task summary and chat summary, then run the helper.

## From VS Code

Open the Command Palette and run:

```text
Tasks: Run Task
```

Then choose:

```text
end session
```

## From A Terminal

Windows:

```powershell
scripts\end-session.ps1 "Short task summary" --chat-summary "Short chat summary"
```

The PowerShell wrapper skips Microsoft Store execution aliases before launch, checks real `python`, `python3`, and `py` launchers with `--version`, and uses Conda when needed. In Codex, reuse the persisted approval for the PowerShell wrapper when available; if the wrapper is blocked by the execution environment, use:

```powershell
conda run -n base python scripts/end-session.py "Short task summary" --chat-summary "Short chat summary"
```

macOS or Linux:

```bash
sh scripts/end-session.sh "Short task summary" --chat-summary "Short chat summary"
```

## Workflow Preferences

- GitHub updates are pushed only through normal Git commits.
- Force-push, reset, and deleting files are never automatic.
- `meeting_notes/` stays local-only because it is ignored by `.gitignore`.
- If Conda, Mamba, or Micromamba is unavailable, the helper records that environment exports could not be refreshed.
- Save all open editor tabs before running the command so the committed files match what you see in VS Code.
