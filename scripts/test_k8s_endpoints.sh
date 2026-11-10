#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script de Prueba End-to-End de Despliegue en Kubernetes
# Grupo 4 — Power Rangers | Proyecto Panadería
# ==============================================================================
# Permite levantar y probar toda la estructura de Kubernetes (Pods, Services,
# Migraciones y Endpoints) sin necesidad de ejecutar Terraform previamente.
#
# Flujo:
# 1. Verifica la conexión con el clúster activo de Kubernetes (kubectl).
# 2. Crea el Namespace 'panaderia-grupo-4' y el Secret con credenciales seguras.
# 3. Despliega PostgreSQL y el PVC; espera a que el Pod esté en estado 'Ready'.
# 4. Ejecuta los Jobs de migración Alembic y espera su completitud.
# 5. Despliega los microservicios de Productos y Pedidos.
# 6. Establece port-forwarding hacia localhost:8001 (Productos) y localhost:8002 (Pedidos).
# 7. Ejecuta la suite de pruebas E2E (tests/integration/test_e2e_flow.py) contra los Pods.
# 8. Muestra el estado final y limpia los túneles port-forward al terminar.
# ==============================================================================

NAMESPACE="panaderia-grupo-4"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
K8S_DIR="$ROOT_DIR/deploy/k8s"

PRODUCTOS_PORT="${PRODUCTOS_PORT:-8001}"
PEDIDOS_PORT="${PEDIDOS_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16}"
PRODUCTOS_IMAGE="${PRODUCTOS_IMAGE:-panaderia-productos:latest}"
PEDIDOS_IMAGE="${PEDIDOS_IMAGE:-panaderia-pedidos:latest}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-panaderia-frontend:latest}"

echo "================================================================="
echo "  Prueba de Despliegue y Endpoints en Kubernetes (Sin Terraform)"
echo "  Namespace: $NAMESPACE"
echo "================================================================="

# 1. Comprobar que kubectl se comunica con un clúster activo
echo ""
echo "[Paso 1/6] Verificando conectividad con Kubernetes..."
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "ERROR: No fue posible comunicarse con el clúster de Kubernetes."
    echo "Verifica que el contexto esté activo con: kubectl config get-contexts"
    exit 1
fi
CURRENT_CONTEXT=$(kubectl config current-context)
echo "  -> Clúster conectado exitosamente (Contexto actual: $CURRENT_CONTEXT)"

# 2. Namespace y Secret
echo ""
echo "[Paso 2/6] Preparando Namespace y Secret de credenciales..."
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
kubectl apply -f "$K8S_DIR/01-configmap.yaml"

if [ -f "$K8S_DIR/02-secret.yaml" ]; then
    echo "  -> Aplicando Secret desde $K8S_DIR/02-secret.yaml..."
    kubectl apply -f "$K8S_DIR/02-secret.yaml"
elif ! kubectl get secret panaderia-secrets -n "$NAMESPACE" > /dev/null 2>&1; then
    echo "  -> Creando Secret 'panaderia-secrets' con credenciales seguras de prueba..."
    ADMIN_PASS="SecretAdmin_$(openssl rand -hex 6)"
    PROD_PASS="SecretProd_$(openssl rand -hex 6)"
    PED_PASS="SecretPed_$(openssl rand -hex 6)"

    kubectl create secret generic panaderia-secrets \
      --namespace "$NAMESPACE" \
      --from-literal=POSTGRES_PASSWORD="$ADMIN_PASS" \
      --from-literal=PRODUCTOS_DB_PASSWORD="$PROD_PASS" \
      --from-literal=PEDIDOS_DB_PASSWORD="$PED_PASS" \
      --from-literal=PRODUCTOS_DATABASE_URL="postgresql+psycopg://productos_app:${PROD_PASS}@postgres.${NAMESPACE}.svc.cluster.local:5432/productos_db" \
      --from-literal=PEDIDOS_DATABASE_URL="postgresql+psycopg://pedidos_app:${PED_PASS}@postgres.${NAMESPACE}.svc.cluster.local:5432/pedidos_db"
else
    echo "  -> Secret 'panaderia-secrets' ya existe en el namespace."
fi

# 3. Base de Datos PostgreSQL
echo ""
echo "[Paso 3/6] Desplegando PostgreSQL y PersistentVolumeClaim..."
kubectl apply -f "$K8S_DIR/03-postgres-pvc.yaml"
sed "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/postgres:16|${POSTGRES_IMAGE}|g" \
    "$K8S_DIR/04-postgres.yaml" | kubectl apply -f -

echo "  -> Esperando que PostgreSQL esté Ready..."
kubectl rollout status deployment/postgres -n "$NAMESPACE" --timeout=120s
echo "  -> PostgreSQL está listo."

# 4. Construcción automática de imágenes de microservicios
echo ""
echo "[Paso 4/7] Verificando y construyendo imágenes de microservicios..."
if docker info > /dev/null 2>&1; then
    echo "  -> Motor Docker detectado. Construyendo imágenes automáticamente..."
    echo "     Construyendo imagen $PRODUCTOS_IMAGE..."
    docker build -t "$PRODUCTOS_IMAGE" "$ROOT_DIR/services/productos"
    echo "     Construyendo imagen $PEDIDOS_IMAGE..."
    docker build -t "$PEDIDOS_IMAGE" "$ROOT_DIR/services/pedidos"
    echo "     Construyendo imagen $FRONTEND_IMAGE..."
    docker build -t "$FRONTEND_IMAGE" "$ROOT_DIR/services/frontend"
    echo "  -> Imágenes locales listas y registradas en el motor de contenedores."
else
    echo "  -> AVISO: Docker daemon no responde en /var/run/docker.sock en esta terminal WSL."
    echo "     Para que el script construya las imágenes automáticamente, activa la integración en:"
    echo "       Docker Desktop -> Settings (⚙️) -> Resources -> WSL Integration -> Tu distribución -> Apply & Restart"
    echo "     Alternativamente, puedes construirlas una sola vez en PowerShell / CMD:"
    echo "       docker build -t panaderia-productos:latest ./services/productos"
    echo "       docker build -t panaderia-pedidos:latest ./services/pedidos"
    echo "       docker build -t panaderia-frontend:latest ./services/frontend"
fi

# 5. Jobs de Migración Alembic
echo ""
echo "[Paso 5/7] Ejecutando Jobs de Migración de Base de Datos..."
kubectl delete job productos-migration-job pedidos-migration-job -n "$NAMESPACE" --ignore-not-found=true > /dev/null 2>&1 || true

sed -e "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/productos:1.0.0|${PRODUCTOS_IMAGE}|g" \
    -e "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/pedidos:1.0.0|${PEDIDOS_IMAGE}|g" \
    "$K8S_DIR/05-migration-jobs.yaml" | kubectl apply -f -

echo "  -> Esperando completitud de migraciones..."
kubectl wait --namespace "$NAMESPACE" \
    --for=condition=complete job/productos-migration-job \
    --timeout=90s
kubectl wait --namespace "$NAMESPACE" \
    --for=condition=complete job/pedidos-migration-job \
    --timeout=90s
echo "  -> Migraciones aplicadas con éxito en ambas bases lógicas."

# 6. Microservicios Web y Frontend
echo ""
echo "[Paso 6/7] Desplegando microservicios Productos, Pedidos y Frontend..."
sed "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/productos:1.0.0|${PRODUCTOS_IMAGE}|g" \
    "$K8S_DIR/06-productos.yaml" | kubectl apply -f -

sed "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/pedidos:1.0.0|${PEDIDOS_IMAGE}|g" \
    "$K8S_DIR/07-pedidos.yaml" | kubectl apply -f -

sed "s|us-central1-docker.pkg.dev/proyecto-gcp/panaderia-repo/frontend:1.0.0|${FRONTEND_IMAGE}|g" \
    "$K8S_DIR/08-frontend.yaml" | kubectl apply -f -

echo "  -> Esperando disponibilidad de réplicas..."
kubectl rollout status deployment/productos -n "$NAMESPACE" --timeout=90s
kubectl rollout status deployment/pedidos -n "$NAMESPACE" --timeout=90s
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=90s
echo "  -> Todos los pods de Productos, Pedidos y Frontend están operativos."

# 7. Verificación de Endpoints y Pruebas E2E
echo ""
echo "[Paso 7/7] Verificando endpoints y ejecutando pruebas E2E..."

# Verificar si los servicios LoadBalancer ya están respondiendo directamente en localhost
if curl -s "http://localhost:$PRODUCTOS_PORT/health/ready" > /dev/null 2>&1 && \
   curl -s "http://localhost:$PEDIDOS_PORT/health/ready" > /dev/null 2>&1 && \
   curl -s "http://localhost:$FRONTEND_PORT/health" > /dev/null 2>&1; then
    echo "  -> Endpoints alcanzables directamente en localhost (LoadBalancer nativo)."
else
    echo "  -> Iniciando túnel port-forward auxiliar..."
    PID_PF_PROD=""
    PID_PF_PED=""
    PID_PF_FRONT=""
    cleanup() {
        echo ""
        echo "Cerrando túneles port-forward..."
        [ -n "$PID_PF_PROD" ] && kill "$PID_PF_PROD" 2>/dev/null || true
        [ -n "$PID_PF_PED" ] && kill "$PID_PF_PED" 2>/dev/null || true
        [ -n "$PID_PF_FRONT" ] && kill "$PID_PF_FRONT" 2>/dev/null || true
    }
    trap cleanup EXIT INT TERM

    kubectl port-forward svc/productos "$PRODUCTOS_PORT:8000" -n "$NAMESPACE" > /dev/null 2>&1 &
    PID_PF_PROD=$!
    kubectl port-forward svc/pedidos "$PEDIDOS_PORT:8000" -n "$NAMESPACE" > /dev/null 2>&1 &
    PID_PF_PED=$!
    kubectl port-forward svc/frontend "$FRONTEND_PORT:8080" -n "$NAMESPACE" > /dev/null 2>&1 &
    PID_PF_FRONT=$!

    echo -n "Esperando que los endpoints respondan... "
    count=0
    until curl -s "http://localhost:$PRODUCTOS_PORT/health/ready" > /dev/null 2>&1 && \
          curl -s "http://localhost:$PEDIDOS_PORT/health/ready" > /dev/null 2>&1 && \
          curl -s "http://localhost:$FRONTEND_PORT/health" > /dev/null 2>&1; do
        count=$((count + 1))
        if [ "$count" -ge 30 ]; then
            echo " ERROR (Timeout al conectar con los endpoints)"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo " OK"
fi

echo ""
echo "================================================================="
echo "  Ejecutando Suite de Pruebas E2E contra los Pods de Kubernetes"
echo "================================================================="
PRODUCTOS_URL="http://localhost:$PRODUCTOS_PORT" \
PEDIDOS_URL="http://localhost:$PEDIDOS_PORT" \
python3 "$ROOT_DIR/tests/integration/test_e2e_flow.py"

echo ""
echo "================================================================="
echo "  Poblando Base de Datos con Catálogo Inicial y Carnés (Criterio A4)"
echo "================================================================="
PRODUCTOS_URL="http://localhost:$PRODUCTOS_PORT" \
PEDIDOS_URL="http://localhost:$PEDIDOS_PORT" \
python3 "$ROOT_DIR/scripts/seed_database.py"

echo ""
echo "================================================================="
echo "  RESUMEN DEL ESTADO DE LOS RECURSOS EN KUBERNETES"
echo "================================================================="
kubectl get pods,services,pvc -n "$NAMESPACE"

echo ""
echo "================================================================="
echo "  EXITO: La infraestructura de Kubernetes y todos los endpoints"
echo "  del backend fueron validados satisfactoriamente."
echo "================================================================="
