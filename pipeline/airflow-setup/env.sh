# Source this in a WSL/Linux shell before running Airflow commands:
#   source pipeline/airflow-setup/env.sh
# It activates the Airflow virtual environment and points Airflow at this repository's DAGs.

_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source "${URBANPULSE_AIRFLOW_VENV:-$HOME/.venvs/urbanpulse-airflow}/bin/activate"

export AIRFLOW_HOME="${AIRFLOW_HOME:-$HOME/airflow-urbanpulse}"
export AIRFLOW__CORE__DAGS_FOLDER="$_repo/pipeline/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES="False"
# Where the DAG keeps downloads and intermediate files (shared with the CLI pipeline).
export URBANPULSE_CACHE_DIR="${URBANPULSE_CACHE_DIR:-$_repo/pipeline/.cache}"
export URBANPULSE_OUTPUT="${URBANPULSE_OUTPUT:-$_repo/data/melbourne_sa2_2021.csv}"

echo "Airflow env ready: AIRFLOW_HOME=$AIRFLOW_HOME, DAGs from $AIRFLOW__CORE__DAGS_FOLDER"
unset _repo
