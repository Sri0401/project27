#!/usr/bin/env bash
# Pull-based continuous deployment ("GitOps") for the UrbanPulse VM.
#
# A systemd timer runs this every 5 minutes. It deploys the latest commit on main, but only after
# GitHub Actions CI has passed for that exact commit. If the new version fails its health check,
# it rolls back to the previous commit.
#
# The VM only makes outbound requests to GitHub, so SSH can stay locked to the owner's IP.
# Logs: journalctl -u urbanpulse-deploy -n 50
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/azureuser/urbanpulse}"
BRANCH="${BRANCH:-main}"
CI_WORKFLOW="${CI_WORKFLOW:-CI}"
HEALTH_URL="${HEALTH_URL:-http://localhost/api/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"

log() { echo "[deploy] $*"; }

set_version() {
  if grep -qE '^APP_VERSION=' .env; then
    sed -i -E "s/^APP_VERSION=.*/APP_VERSION=$1/" .env
  else
    echo "APP_VERSION=$1" >> .env
  fi
}

roll_out() {
  local commit="$1"
  git checkout --quiet --detach "$commit"
  set_version "${commit:0:7}"
  docker compose build --quiet
  docker compose up -d --remove-orphans
  # Reload the dataset (a cheap snapshot load) and restart the API so it records the new manifest.
  docker compose run --rm ingestor
  docker compose restart api
}

healthy() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  while ((SECONDS < deadline)); do
    if curl -fsS --max-time 5 "$HEALTH_URL" | jq -e --arg v "${1:0:7}" '.status == "ok" and .version == $v' >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# Everything runs inside main(), which bash parses in full before running it. git checkout
# below replaces this file, and bash would otherwise read the new file mid-run.
main() {
  cd "$REPO_DIR"
  # Run as the repo owner so git does not complain about directory ownership.
  git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

  git fetch --quiet origin "$BRANCH"
  current="$(git rev-parse HEAD)"
  target="$(git rev-parse "origin/$BRANCH")"

  deployed_version="$(grep -E '^APP_VERSION=' .env 2>/dev/null | cut -d= -f2 || true)"
  if [[ "$current" == "$target" && "$deployed_version" == "${target:0:7}" ]]; then
    return 0  # already running the latest commit
  fi

  # Only deploy commits that passed CI. The repository is public, so no token is needed.
  repo_path="$(git remote get-url origin | sed -E 's#(https://github.com/|git@github.com:)##; s#\.git$##')"
  ci_result="$(curl -fsS --max-time 20 \
    "https://api.github.com/repos/${repo_path}/actions/runs?head_sha=${target}&event=push&per_page=20" \
    | jq -r --arg wf "$CI_WORKFLOW" '[.workflow_runs[] | select(.name == $wf)][0] | if . == null then "missing" else (.conclusion // .status) end')"

  if [[ "$ci_result" != "success" ]]; then
    log "Commit ${target:0:7} has CI result '$ci_result'; not deploying yet"
    return 0
  fi

  log "Deploying ${target:0:7} (currently ${current:0:7})"
  if roll_out "$target" && healthy "$target"; then
    docker image prune -f >/dev/null
    log "Deployed ${target:0:7} successfully"
    exit 0
  fi

  log "Deployment of ${target:0:7} failed its health check; rolling back to ${current:0:7}"
  roll_out "$current" || true
  if healthy "$current"; then
    log "Rolled back to ${current:0:7}"
  else
    log "Rollback to ${current:0:7} is also unhealthy; manual attention needed"
  fi
  exit 1
}

main "$@"
exit $?
