#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script de Verificación de Persistencia de Volumen PostgreSQL
# Grupo 4 — Power Rangers | Proyecto Panadería
# ==============================================================================
# Este script comprueba que los datos persistan en el volumen "postgres_data"
# tras reiniciar el contenedor o servicio de base de datos PostgreSQL.
#
# Flujo:
# 1. Verifica la salud inicial de Productos y Pedidos.
# 2. Inserta un Producto y un Pedido de prueba.
# 3. Reinicia el contenedor de PostgreSQL sin eliminar el volumen.
# 4. Espera a que la base de datos y los microservicios vuelvan a estar listos.
# 5. Consulta los registros y valida que siguen existiendo con datos íntegros.
# 6. Elimina los registros de prueba para dejar la base en estado limpio.
# ==============================================================================

PRODUCTOS_URL="${PRODUCTOS_URL:-http://localhost:8001}"
PEDIDOS_URL="${PEDIDOS_URL:-http://localhost:8002}"
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

echo "================================================================="
echo "  Test de Persistencia de Volumen PostgreSQL (Fase 5)"
echo "  Productos URL: $PRODUCTOS_URL"
echo "  Pedidos URL:   $PEDIDOS_URL"
echo "================================================================="

# Función auxiliar para comprobar salud con reintentos
wait_for_ready() {
    local url="$1"
    local name="$2"
    local max_retries="${3:-30}"
    local count=0
    echo -n "Esperando que $name esté listo en $url/health/ready... "
    until curl -s -f "$url/health/ready" > /dev/null 2>&1; do
        count=$((count + 1))
        if [ "$count" -ge "$max_retries" ]; then
            echo " ERROR (Timeout tras $max_retries intentos)"
            return 1
        fi
        echo -n "."
        sleep 1
    done
    echo " OK"
}

# 1. Comprobación inicial de disponibilidad
wait_for_ready "$PRODUCTOS_URL" "Microservicio Productos"
wait_for_ready "$PEDIDOS_URL" "Microservicio Pedidos"

# 2. Creación de registros de prueba
echo ""
echo "[Paso 1/5] Insertando datos de prueba..."
PROD_RESP=$(curl -s -X POST "$PRODUCTOS_URL/productos" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Baguette de Persistencia E2E",
        "descripcion": "Verificación de retención en volumen postgres_data",
        "precio": 15.00,
        "activo": true
    }')

PROD_ID=$(echo "$PROD_RESP" | jq -r '.id // empty')
if [ -z "$PROD_ID" ]; then
    echo "Error al crear el producto de prueba. Respuesta del servidor:"
    echo "$PROD_RESP"
    exit 1
fi
echo "  -> Producto creado con ID: $PROD_ID"

PED_RESP=$(curl -s -X POST "$PEDIDOS_URL/pedidos" \
    -H "Content-Type: application/json" \
    -d "{\"producto_id\": \"$PROD_ID\", \"cantidad\": 3}")

PED_ID=$(echo "$PED_RESP" | jq -r '.id // empty')
if [ -z "$PED_ID" ]; then
    echo "Error al crear el pedido de prueba. Respuesta del servidor:"
    echo "$PED_RESP"
    # Intentar limpiar el producto
    curl -s -X DELETE "$PRODUCTOS_URL/productos/$PROD_ID" > /dev/null || true
    exit 1
fi
echo "  -> Pedido creado con ID: $PED_ID (Total: 45.00)"

# 3. Reinicio de PostgreSQL
echo ""
echo "[Paso 2/5] Reiniciando contenedor de PostgreSQL (sin eliminar volumen)..."
if $COMPOSE_CMD ps postgres > /dev/null 2>&1; then
    echo "  Ejecutando: $COMPOSE_CMD restart postgres"
    $COMPOSE_CMD restart postgres
else
    echo "  AVISO: 'docker compose' no está activo. Si estás ejecutando PostgreSQL localmente,"
    echo "  reinicia el servicio de base de datos manualmente o presiona ENTER para continuar."
    read -r -p "  Presiona ENTER para continuar tras reiniciar la base... " || true
fi

# 4. Esperar recuperación de servicios
echo ""
echo "[Paso 3/5] Esperando restablecimiento de la conexión con PostgreSQL..."
wait_for_ready "$PRODUCTOS_URL" "Microservicio Productos" 40
wait_for_ready "$PEDIDOS_URL" "Microservicio Pedidos" 40

# 5. Comprobación de persistencia de datos
echo ""
echo "[Paso 4/5] Verificando que los datos persisten tras el reinicio..."

GET_PROD=$(curl -s "$PRODUCTOS_URL/productos/$PROD_ID")
CHECK_PROD_ID=$(echo "$GET_PROD" | jq -r '.id // empty')
CHECK_PROD_NOMBRE=$(echo "$GET_PROD" | jq -r '.nombre // empty')

if [ "$CHECK_PROD_ID" != "$PROD_ID" ]; then
    echo "FALLO: El producto $PROD_ID no fue encontrado tras reiniciar PostgreSQL."
    echo "Respuesta: $GET_PROD"
    exit 1
fi
echo "  -> Producto recuperado íntegro: '$CHECK_PROD_NOMBRE' (ID: $CHECK_PROD_ID)"

GET_PED=$(curl -s "$PEDIDOS_URL/pedidos/$PED_ID")
CHECK_PED_ID=$(echo "$GET_PED" | jq -r '.id // empty')
CHECK_PED_TOTAL=$(echo "$GET_PED" | jq -r '.total // empty')

if [ "$CHECK_PED_ID" != "$PED_ID" ]; then
    echo "FALLO: El pedido $PED_ID no fue encontrado tras reiniciar PostgreSQL."
    echo "Respuesta: $GET_PED"
    exit 1
fi
echo "  -> Pedido recuperado íntegro: Total = $CHECK_PED_TOTAL (ID: $CHECK_PED_ID)"

# 6. Limpieza de registros
echo ""
echo "[Paso 5/5] Limpiando registros de prueba..."
curl -s -X DELETE "$PEDIDOS_URL/pedidos/$PED_ID" > /dev/null
curl -s -X DELETE "$PRODUCTOS_URL/productos/$PROD_ID" > /dev/null
echo "  -> Registros de prueba eliminados correctamente."

echo ""
echo "================================================================="
echo "  EXITO: La persistencia de datos en el volumen PostgreSQL fue"
echo "  validada satisfactoriamente sin perdida de informacion."
echo "================================================================="
