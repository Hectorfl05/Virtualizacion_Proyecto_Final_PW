#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script de Despliegue Ordenado en Kubernetes (GKE)
# Grupo 4 — Power Rangers | Proyecto Panadería
# ==============================================================================

NAMESPACE="panaderia-grupo-4"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
IS_LOCAL=false
if [[ "$CURRENT_CONTEXT" =~ (docker-desktop|minikube|kind-.*) ]] || [ "${LOCAL_DEV:-false}" = "true" ]; then
    IS_LOCAL=true
fi

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16}"
PRODUCTOS_IMAGE="${PRODUCTOS_IMAGE:-panaderia-productos:latest}"
PEDIDOS_IMAGE="${PEDIDOS_IMAGE:-panaderia-pedidos:latest}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-panaderia-frontend:latest}"

echo "================================================================="
echo "  Iniciando Despliegue Ordenado en Kubernetes"
echo "  Namespace: $NAMESPACE"
if [ "$IS_LOCAL" = "true" ]; then
    echo "  Modo: Local ($CURRENT_CONTEXT) - Usando imágenes locales"
else
    echo "  Modo: Remoto / GKE ($CURRENT_CONTEXT) - Usando Artifact Registry"
fi
echo "================================================================="

# 1. Namespace
echo ""
echo "[Paso 1/7] Aplicando Namespace..."
kubectl apply -f "$SCRIPT_DIR/00-namespace.yaml"

# 2. ConfigMap
echo ""
echo "[Paso 2/7] Aplicando ConfigMap..."
kubectl apply -f "$SCRIPT_DIR/01-configmap.yaml"

# 3. Secret
echo ""
echo "[Paso 3/7] Verificando Secret..."
if kubectl get secret panaderia-secrets -n "$NAMESPACE" > /dev/null 2>&1; then
    echo "  -> Secret 'panaderia-secrets' ya existe en el namespace."
elif [ -f "$SCRIPT_DIR/02-secret.yaml" ]; then
    echo "  -> Aplicando $SCRIPT_DIR/02-secret.yaml..."
    kubectl apply -f "$SCRIPT_DIR/02-secret.yaml"
else
    echo "ERROR: No se encontró el secret 'panaderia-secrets' ni el archivo 02-secret.yaml."
    echo "Crea el secret antes de continuar. Ejemplo:"
    echo "  kubectl create secret generic panaderia-secrets -n $NAMESPACE \\"
    echo "    --from-literal=POSTGRES_PASSWORD='TU_PASSWORD_ADMIN' \\"
    echo "    --from-literal=PRODUCTOS_DB_PASSWORD='TU_PASSWORD_PRODUCTOS' \\"
    echo "    --from-literal=PEDIDOS_DB_PASSWORD='TU_PASSWORD_PEDIDOS' \\"
    echo "    --from-literal=PRODUCTOS_DATABASE_URL='postgresql+psycopg://productos_app:PASS@postgres.$NAMESPACE.svc.cluster.local:5432/productos_db' \\"
    echo "    --from-literal=PEDIDOS_DATABASE_URL='postgresql+psycopg://pedidos_app:PASS@postgres.$NAMESPACE.svc.cluster.local:5432/pedidos_db'"
    exit 1
fi

# Preparación de imágenes locales (si aplica)
if [ "$IS_LOCAL" = "true" ] && docker info > /dev/null 2>&1; then
    echo ""
    echo "[Preparación Local] Verificando y construyendo imágenes locales si no existen..."
    if ! docker image inspect "$PRODUCTOS_IMAGE" > /dev/null 2>&1; then
        echo "  -> Construyendo $PRODUCTOS_IMAGE..."
        docker build -t "$PRODUCTOS_IMAGE" "$ROOT_DIR/services/productos"
    fi
    if ! docker image inspect "$PEDIDOS_IMAGE" > /dev/null 2>&1; then
        echo "  -> Construyendo $PEDIDOS_IMAGE..."
        docker build -t "$PEDIDOS_IMAGE" "$ROOT_DIR/services/pedidos"
    fi
    if ! docker image inspect "$FRONTEND_IMAGE" > /dev/null 2>&1; then
        echo "  -> Construyendo $FRONTEND_IMAGE..."
        docker build -t "$FRONTEND_IMAGE" "$ROOT_DIR/services/frontend"
    fi
fi

# 4. PVC y PostgreSQL
echo ""
echo "[Paso 4/7] Aplicando PersistentVolumeClaim y Deployment de PostgreSQL..."
kubectl apply -f "$SCRIPT_DIR/03-postgres-pvc.yaml"

if [ "$IS_LOCAL" = "true" ]; then
    sed "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/postgres:16|${POSTGRES_IMAGE}|g" \
        "$SCRIPT_DIR/04-postgres.yaml" | kubectl apply -f -
else
    kubectl apply -f "$SCRIPT_DIR/04-postgres.yaml"
fi

echo "  -> Esperando que el pod de PostgreSQL esté Ready..."
kubectl wait --namespace "$NAMESPACE" \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/name=postgres \
    --timeout=180s

# 5. Jobs de Migración
echo ""
echo "[Paso 5/7] Ejecutando Jobs de Migración Alembic..."
# Eliminar jobs anteriores si existen para permitir re-ejecución
kubectl delete job productos-migration-job pedidos-migration-job -n "$NAMESPACE" --ignore-not-found=true

if [ "$IS_LOCAL" = "true" ]; then
    sed -e "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/productos:1.0.0|${PRODUCTOS_IMAGE}|g" \
        -e "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/pedidos:1.0.0|${PEDIDOS_IMAGE}|g" \
        "$SCRIPT_DIR/05-migration-jobs.yaml" | kubectl apply -f -
else
    kubectl apply -f "$SCRIPT_DIR/05-migration-jobs.yaml"
fi

echo "  -> Esperando completitud de migraciones..."
kubectl wait --namespace "$NAMESPACE" \
    --for=condition=complete job/productos-migration-job \
    --timeout=120s
kubectl wait --namespace "$NAMESPACE" \
    --for=condition=complete job/pedidos-migration-job \
    --timeout=120s

# 6. Microservicios Web y Frontend
echo ""
echo "[Paso 6/7] Desplegando microservicios Productos, Pedidos y Frontend..."
if [ "$IS_LOCAL" = "true" ]; then
    sed "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/productos:1.0.0|${PRODUCTOS_IMAGE}|g" \
        "$SCRIPT_DIR/06-productos.yaml" | kubectl apply -f -
    sed "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/pedidos:1.0.0|${PEDIDOS_IMAGE}|g" \
        "$SCRIPT_DIR/07-pedidos.yaml" | kubectl apply -f -
    sed "s|us-central1-docker.pkg.dev/panaderia-grupo-4/panaderia-repo/frontend:1.0.0|${FRONTEND_IMAGE}|g" \
        "$SCRIPT_DIR/08-frontend.yaml" | kubectl apply -f -
else
    kubectl apply -f "$SCRIPT_DIR/06-productos.yaml"
    kubectl apply -f "$SCRIPT_DIR/07-pedidos.yaml"
    kubectl apply -f "$SCRIPT_DIR/08-frontend.yaml"
fi

echo "  -> Esperando que los Deployments estén disponibles..."
kubectl rollout status deployment/productos -n "$NAMESPACE" --timeout=120s
kubectl rollout status deployment/pedidos -n "$NAMESPACE" --timeout=120s
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=120s

echo ""
echo "================================================================="
echo "  Despliegue completado con éxito."
echo "  Verifica el estado con:"
echo "    kubectl get all,pvc -n $NAMESPACE"
echo "================================================================="
