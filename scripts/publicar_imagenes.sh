#!/usr/bin/env bash
# Construye y publica las imagenes en Artifact Registry.
# Uso (Cloud Shell): bash scripts/publicar_imagenes.sh [PROYECTO] [VERSION]
set -euo pipefail

PROYECTO="${1:-$(gcloud config get-value project 2>/dev/null)}"
VERSION="${2:-1.1.0}"
REGION="us-central1"
REPO="panaderia-repo"
REG="${REGION}-docker.pkg.dev/${PROYECTO}/${REPO}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" -q >/dev/null 2>&1

# Docker Hub puede fallar por tiempo de espera desde Cloud Shell: se usa el espejo publico de Google.
traer_base() {
  local imagen="$1"
  docker image inspect "$imagen" >/dev/null 2>&1 && return 0
  echo "Descargando $imagen desde mirror.gcr.io..."
  timeout 180 docker pull -q "mirror.gcr.io/library/${imagen}" >/dev/null
  docker tag "mirror.gcr.io/library/${imagen}" "$imagen"
}
# La red de Cloud Shell a veces rechaza conexiones de forma intermitente: se reintenta el envio.
subir() {
  for intento in 1 2 3 4 5 6; do
    docker push -q "$1" >/dev/null && return 0
    echo "  envio fallido (intento ${intento}), reintentando..."
    sleep 8
  done
  return 1
}

traer_base python:3.12-slim
traer_base nginx:1.27-alpine
traer_base postgres:16

for servicio in productos pedidos frontend; do
  echo "==> ${servicio}:${VERSION}"
  docker build -q -t "${REG}/${servicio}:${VERSION}" "${RAIZ}/services/${servicio}" >/dev/null
  subir "${REG}/${servicio}:${VERSION}"
done

echo "==> postgres:16"
docker tag postgres:16 "${REG}/postgres:16"
subir "${REG}/postgres:16"

echo "Imagenes publicadas en ${REG}:"
gcloud artifacts docker images list "${REG}" --format="value(package,tags)" | sort -u
