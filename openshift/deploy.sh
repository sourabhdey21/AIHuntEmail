#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAMESPACE="${NAMESPACE:-huntmail}"
IMAGE="${IMAGE:-docker.io/sourabhdey21/huntmail:latest}"

if ! command -v oc >/dev/null 2>&1; then
  echo "oc is not installed or not on PATH."
  exit 1
fi

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null 2>&1 || oc new-project "$NAMESPACE"
oc project "$NAMESPACE" >/dev/null

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Create $ROOT/.env first so the SMTP secret can be applied."
  exit 1
fi

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT/.env" > "$ENV_FILE"
oc create secret generic huntmail-smtp \
  --from-env-file="$ENV_FILE" \
  --dry-run=client -o yaml | oc apply -f -

oc apply -f "$ROOT/openshift/huntmail.yaml"
oc set image deployment/huntmail "huntmail=$IMAGE"
oc rollout status deployment/huntmail --timeout=180s || true
echo "Route:"
oc get route huntmail -o jsonpath='https://{.spec.host}{"\n"}' || true
