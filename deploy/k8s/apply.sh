#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script de Despliegue Ordenado en Kubernetes (GKE)
# Grupo 4 — Power Rangers | Proyecto Panadería
# ==============================================================================

NAMESPACE="panaderia-grupo-4"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================================="
echo "  Iniciando Despliegue Ordenado en Kubernetes"
echo "  Namespace: $NAMESPACE"
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

# 4. PVC y PostgreSQL
echo ""
echo "[Paso 4/7] Aplicando PersistentVolumeClaim y Deployment de PostgreSQL..."
kubectl apply -f "$SCRIPT_DIR/03-postgres-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/04-postgres.yaml"

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
kubectl apply -f "$SCRIPT_DIR/05-migration-jobs.yaml"

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
kubectl apply -f "$SCRIPT_DIR/06-productos.yaml"
kubectl apply -f "$SCRIPT_DIR/07-pedidos.yaml"
kubectl apply -f "$SCRIPT_DIR/08-frontend.yaml"

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
