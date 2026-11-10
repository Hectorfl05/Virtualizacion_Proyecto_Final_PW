#!/usr/bin/env bash
# Crea el namespace y el Secret con contrasenas aleatorias (no se imprimen ni se guardan en Git).
# Uso: bash scripts/crear_secret_gke.sh
set -euo pipefail

NS="panaderia-grupo-4"
kubectl apply -f "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/k8s/00-namespace.yaml" >/dev/null

if kubectl get secret panaderia-secrets -n "$NS" >/dev/null 2>&1; then
  echo "El Secret panaderia-secrets ya existe; no se modifica."
  exit 0
fi

admin="$(openssl rand -hex 12)"
prod="$(openssl rand -hex 12)"
ped="$(openssl rand -hex 12)"
host="postgres.${NS}.svc.cluster.local:5432"

kubectl create secret generic panaderia-secrets -n "$NS" \
  --from-literal=POSTGRES_PASSWORD="$admin" \
  --from-literal=PRODUCTOS_DB_PASSWORD="$prod" \
  --from-literal=PEDIDOS_DB_PASSWORD="$ped" \
  --from-literal=PRODUCTOS_DATABASE_URL="postgresql+psycopg://productos_app:${prod}@${host}/productos_db" \
  --from-literal=PEDIDOS_DATABASE_URL="postgresql+psycopg://pedidos_app:${ped}@${host}/pedidos_db"
