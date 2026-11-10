#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script para Exponer Endpoints de Kubernetes al Host
# Grupo 4 — Power Rangers | Proyecto Panadería
# ==============================================================================

NAMESPACE="panaderia-grupo-4"

echo "================================================================="
echo "  Exponiendo Microservicios de Kubernetes en Localhost"
echo "================================================================="
echo "  -> Productos: http://localhost:8001"
echo "     Swagger UI: http://localhost:8001/docs"
echo "  -> Pedidos:   http://localhost:8002"
echo "     Swagger UI: http://localhost:8002/docs"
echo "================================================================="
echo "Presiona Ctrl+C para detener los túneles."
echo ""

kubectl port-forward svc/productos 8001:8000 -n "$NAMESPACE" &
PID1=$!

kubectl port-forward svc/pedidos 8002:8000 -n "$NAMESPACE" &
PID2=$!

trap "kill $PID1 $PID2 2>/dev/null || true; echo 'Túneles cerrados.'" EXIT INT TERM
wait
