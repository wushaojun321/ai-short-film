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
  compose exec -T api python - <<'PY'
import json
import sys
import urllib.request

url = "http://127.0.0.1:8000/health"
try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print(f"health check failed: {exc}", file=sys.stderr)
    sys.exit(1)

if payload.get("status") != "ok":
    print(f"unexpected health payload: {payload}", file=sys.stderr)
    sys.exit(1)

print("api health ok")
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
