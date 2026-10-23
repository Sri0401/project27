#!/usr/bin/env bash
# One-time Airflow setup for WSL (Ubuntu) or Linux/macOS. No admin rights needed.
#
#   bash pipeline/airflow-setup/setup_wsl.sh
#
# Installs uv (a fast Python package manager) into ~/.local/bin, creates a Python 3.12
# virtual environment in ~/.venvs/urbanpulse-airflow, and installs Airflow pinned with the
# project's official constraints file, so every dependency version is known to work together.
set -euo pipefail

AIRFLOW_VERSION="3.3.2"
PYTHON_VERSION="3.12"
VENV="${URBANPULSE_AIRFLOW_VENV:-$HOME/.venvs/urbanpulse-airflow}"
CONSTRAINTS="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo ">> Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo ">> Creating $VENV (Python $PYTHON_VERSION)"
uv venv --quiet --python "$PYTHON_VERSION" "$VENV"

echo ">> Installing Airflow $AIRFLOW_VERSION and the pipeline's dependencies"
# The pipeline's own packages are given by name only: the constraints file decides their
# versions, so they cannot conflict with Airflow's.
uv pip install --quiet --python "$VENV/bin/python" \
  "apache-airflow==${AIRFLOW_VERSION}" httpx shapely pytest \
  --constraint "$CONSTRAINTS"

"$VENV/bin/airflow" version
echo ">> Done. Next: source pipeline/airflow-setup/env.sh, then 'airflow standalone'"
