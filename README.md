# Rating Distribution

## Save A Work Session

Use this command when you finish a work session:

```bash
./scripts/save_session.sh "Briefly describe what changed"
```

The workflow will:

- update `environment.yml` from the Conda environment named in that file
- create a dated markdown log in `session_logs/`
- commit all trackable changes
- push the commit to GitHub

If `conda` is not available in your terminal, open a fresh VS Code terminal or run:

```bash
source ~/.zshrc
```

Your Conda install is Miniforge, so `conda` should resolve from:

```text
/Users/fbilsond/miniforge3/bin/conda
```

You can also point the script to Conda explicitly:

```bash
CONDA_EXE=/full/path/to/conda ./scripts/save_session.sh "Briefly describe what changed"
```

If you want to save a session without refreshing `environment.yml`, use:

```bash
SKIP_ENV_EXPORT=1 ./scripts/save_session.sh "Briefly describe what changed"
```
