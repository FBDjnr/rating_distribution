#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/save_session.sh "Short note about what changed"

What this does:
  1. Refreshes environment.yml from your Conda environment.
  2. Creates a dated markdown log in session_logs/.
  3. Stages all trackable project changes.
  4. Commits the changes.
  5. Pushes the current branch to GitHub.

Optional settings:
  CONDA_ENV=rating-dist-env
      Use a specific Conda environment name.

  CONDA_EXE=/path/to/conda
      Use a specific Conda executable if conda is not on PATH.

  COMMIT_MESSAGE="Your commit message"
      Override the default commit message.

  SKIP_ENV_EXPORT=1
      Skip refreshing environment.yml.
USAGE
}

find_conda() {
  if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE}" ]]; then
    printf '%s\n' "${CONDA_EXE}"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return 0
  fi

  if command -v mamba >/dev/null 2>&1; then
    command -v mamba
    return 0
  fi

  local candidates=(
    "${HOME}/miniforge3/bin/conda"
    "${HOME}/miniconda3/bin/conda"
    "${HOME}/mambaforge/bin/conda"
    "/opt/homebrew/bin/conda"
    "/opt/miniforge3/bin/conda"
    "/opt/miniconda3/bin/conda"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

env_name_from_file() {
  if [[ -f environment.yml ]]; then
    awk -F ': *' '/^name:/ { print $2; exit }' environment.yml
  fi
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

summary="${*:-}"
if [[ -z "${summary}" ]]; then
  printf "Session summary: "
  IFS= read -r summary
fi

if [[ -z "${summary}" ]]; then
  echo "A short session summary is required." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

timestamp="$(date +"%Y-%m-%d_%H-%M-%S")"
pretty_date="$(date +"%Y-%m-%d %H:%M:%S %Z")"
log_file="session_logs/${timestamp}.md"
mkdir -p session_logs

if [[ "${SKIP_ENV_EXPORT:-0}" == "1" ]]; then
  env_status="Skipped environment export because SKIP_ENV_EXPORT=1."
else
  conda_cmd="$(find_conda || true)"
  if [[ -z "${conda_cmd}" ]]; then
    cat >&2 <<'ERROR'
Could not find conda or mamba, so environment.yml was not updated.

Try one of these:
  1. Run this from a terminal where conda is available.
  2. Set CONDA_EXE=/full/path/to/conda before running this script.
  3. Run with SKIP_ENV_EXPORT=1 if you intentionally do not want to update environment.yml.
ERROR
    exit 1
  fi

  env_name="${CONDA_ENV:-${CONDA_DEFAULT_ENV:-}}"
  if [[ -z "${env_name}" ]]; then
    env_name="$(env_name_from_file || true)"
  fi

  tmp_env="$(mktemp)"
  if [[ -n "${env_name}" ]]; then
    "${conda_cmd}" env export -n "${env_name}" --no-builds > "${tmp_env}"
    env_status="Updated environment.yml from Conda environment '${env_name}' using ${conda_cmd}."
  else
    "${conda_cmd}" env export --no-builds > "${tmp_env}"
    env_status="Updated environment.yml from the active Conda environment using ${conda_cmd}."
  fi

  awk '!/^prefix: /' "${tmp_env}" > environment.yml
  rm -f "${tmp_env}"
fi

status_before="$(git status --short)"
diff_stat="$(git diff --stat || true)"

{
  echo "# Session Log: ${pretty_date}"
  echo
  echo "## Summary"
  echo "${summary}"
  echo
  echo "## Environment"
  echo "${env_status}"
  echo
  echo "## Changed Files Before Commit"
  if [[ -n "${status_before}" ]]; then
    printf '```text\n%s\n```\n' "${status_before}"
  else
    echo "No working tree changes before this log file was created."
  fi
  echo
  echo "## Diff Stat Before Commit"
  if [[ -n "${diff_stat}" ]]; then
    printf '```text\n%s\n```\n' "${diff_stat}"
  else
    echo "No diff stat available before this log file was created."
  fi
} > "${log_file}"

git add .

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

short_summary="$(printf '%s' "${summary}" | tr '\n' ' ' | cut -c 1-60)"
commit_message="${COMMIT_MESSAGE:-Session update: ${short_summary}}"

git commit -m "${commit_message}"

branch="$(git branch --show-current)"
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "${branch}"
fi

commit_hash="$(git rev-parse --short HEAD)"
echo "Saved session log: ${log_file}"
echo "Committed: ${commit_hash} ${commit_message}"
echo "Pushed branch: ${branch}"
