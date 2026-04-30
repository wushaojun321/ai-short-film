#!/usr/bin/env bash
set -Eeuo pipefail

# Pull latest code, rebuild Docker images, and restart the full stack.
#
# Typical server usage:
#   cd /root/ai-short-film
#   ./scripts/update-server.sh
#
# Optional overrides:
#   BRANCH=main ./scripts/update-server.sh
#   SERVICES="api worker-llm worker-image worker-video worker-merge frontend" ./scripts/update-server.sh
#   PRUNE=1 ./scripts/update-server.sh
#   ./scripts/update-server.sh --health-only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REMOTE="${REMOTE:-origin}"
SERVICES="${SERVICES:-}"
PRUNE="${PRUNE:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-2}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

die() {
  printf '\n[ERROR] %s\n' "$*" >&2
  exit 1
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose is not installed."
  fi
}

run_health_check() {
  log "Checking API health inside api container..."
  compose exec -T \
    -e HEALTH_RETRIES="$HEALTH_RETRIES" \
    -e HEALTH_INTERVAL="$HEALTH_INTERVAL" \
    api python - <<'PY'
import json
import os
import sys
import time
import urllib.request

url = "http://127.0.0.1:8000/health"
retries = int(os.environ.get("HEALTH_RETRIES", "30"))
interval = float(os.environ.get("HEALTH_INTERVAL", "2"))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
last_error = None

for attempt in range(1, retries + 1):
    try:
        with opener.open(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "ok":
            print("api health ok")
            sys.exit(0)
        last_error = f"unexpected health payload: {payload}"
    except Exception as exc:
        last_error = str(exc)

    if attempt < retries:
        print(f"api health not ready ({attempt}/{retries}): {last_error}", file=sys.stderr)
        time.sleep(interval)

print(f"health check failed after {retries} attempts: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

cd "$REPO_DIR"

[[ -d .git ]] || die "$REPO_DIR is not a git repository."
[[ -f docker-compose.yml ]] || die "$REPO_DIR/docker-compose.yml not found."
[[ -f backend/.env ]] || die "backend/.env not found. Refusing to deploy without runtime secrets."

if [[ "${1:-}" == "--health-only" ]]; then
  run_health_check
  exit 0
fi

if [[ "$ALLOW_DIRTY" != "1" ]] && ! git diff --quiet; then
  die "Working tree has local modifications. Commit/stash them or rerun with ALLOW_DIRTY=1."
fi

if [[ "$ALLOW_DIRTY" != "1" ]] && [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  die "Working tree has untracked files. Commit/remove them or rerun with ALLOW_DIRTY=1."
fi

BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
[[ "$BRANCH" != "HEAD" ]] || die "Detached HEAD. Set BRANCH explicitly, for example: BRANCH=main $0"

log "Repository: $REPO_DIR"
log "Updating from $REMOTE/$BRANCH"
git fetch --prune "$REMOTE"
git pull --ff-only "$REMOTE" "$BRANCH"

if [[ -n "$SERVICES" ]]; then
  # shellcheck disable=SC2206
  SERVICE_ARGS=($SERVICES)
  log "Building selected services: ${SERVICE_ARGS[*]}"
  compose build "${SERVICE_ARGS[@]}"

  log "Restarting selected services: ${SERVICE_ARGS[*]}"
  compose up -d --remove-orphans "${SERVICE_ARGS[@]}"
else
  log "Building all services..."
  compose build

  log "Restarting all services..."
  compose up -d --remove-orphans
fi

run_health_check

log "Current service status:"
compose ps

if [[ "$PRUNE" == "1" ]]; then
  log "Pruning unused Docker images..."
  docker image prune -f
fi

log "Update completed."
