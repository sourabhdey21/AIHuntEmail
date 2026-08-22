#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${IMAGE:-sourabhdey21/huntmail:latest}"

if command -v docker >/dev/null 2>&1; then
  ENGINE=docker
elif command -v podman >/dev/null 2>&1; then
  ENGINE=podman
else
  echo "Install Docker or Podman, then: $ENGINE login"
  echo "After login: IMAGE=$IMAGE $0"
  exit 1
fi

"$ENGINE" build -t "$IMAGE" "$ROOT"
"$ENGINE" push "$IMAGE"
echo "Pushed $IMAGE"
