# Rating Distribution

## Save A Work Session

The cross-platform command is:

```bash
python scripts/save_session.py "Briefly describe what changed"
```

On macOS or Linux, you can also use:

```bash
./scripts/save_session.sh "Briefly describe what changed"
```

On Windows Command Prompt or PowerShell, you can use:

```bat
scripts\save_session.bat "Briefly describe what changed"
```

The workflow will:

- update `environment.yml` with portable top-level dependencies from `rating-dist-env`
- update `environment.lock.yml` with the full current Conda export
- create a dated markdown log in `session_logs/`
- commit all trackable changes
- push the commit to GitHub

`environment.yml` is meant for recreating the project on any operating system:

```bash
conda env create -f environment.yml
```

`environment.lock.yml` is a fuller record of the current environment. It is useful when recreating this setup on a similar machine, but it may not solve cleanly across operating systems.

## New Computer Setup

Install Git and Miniforge or Miniconda, then clone the repository and create the environment:

```bash
git clone git@github.com:FBDjnr/rating_distribution.git
cd rating_distribution
conda env create -f environment.yml
conda activate rating-dist-env
```

If `conda` is not available in your terminal, open a fresh terminal after installing Miniforge/Miniconda or point the script to Conda explicitly:

```bash
CONDA_EXE=/full/path/to/conda python scripts/save_session.py "Briefly describe what changed"
```

If you want to save a session without refreshing the environment files, add `--skip-env-export`.
