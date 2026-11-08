"""Prueba de integración end-to-end del flujo completo entre microservicios.

Verifica el ciclo de vida:
1. Comprobación de salud (/health/live y /health/ready) de Productos y Pedidos.
2. Creación de Producto (POST /productos).
3. Creación de Pedido referenciando dicho producto (POST /pedidos).
4. Consulta de Pedido individual (GET /pedidos/{id}) y listado (GET /pedidos).
5. Actualización parcial de Pedido (PATCH /pedidos/{id}) y recálculo de total.
6. Modificación y desactivación de Producto original.
7. Comprobación de que el pedido previo mantiene su precio y nombre histórico intactos.
8. Validación de rechazo (422) al intentar crear nuevo pedido con producto inactivo.
9. Eliminación física de Pedido (DELETE /pedidos/{id}) y comprobación de 404.
10. Eliminación física de Producto (DELETE /productos/{id}) y comprobación de 404.
"""

import os
import sys
from decimal import Decimal

import httpx

PRODUCTOS_URL = os.getenv("PRODUCTOS_URL", "http://localhost:8001").rstrip("/")
PEDIDOS_URL = os.getenv("PEDIDOS_URL", "http://localhost:8002").rstrip("/")


def test_health_endpoints():
    """Verifica que ambos microservicios respondan 200 en live y ready."""
    with httpx.Client(timeout=5.0) as client:
        # Productos
        res = client.get(f"{PRODUCTOS_URL}/health/live")
        assert res.status_code == 200, f"Productos live falló: {res.text}"
        assert res.json() == {"status": "ok"}

        res = client.get(f"{PRODUCTOS_URL}/health/ready")
        assert res.status_code == 200, f"Productos ready falló: {res.text}"
        assert res.json() == {"status": "ready"}

        # Pedidos
        res = client.get(f"{PEDIDOS_URL}/health/live")
        assert res.status_code == 200, f"Pedidos live falló: {res.text}"
        assert res.json() == {"status": "ok"}

        res = client.get(f"{PEDIDOS_URL}/health/ready")
        assert res.status_code == 200, f"Pedidos ready falló: {res.text}"
        assert res.json() == {"status": "ready"}


def test_full_e2e_lifecycle():
    """Ejecuta el ciclo de vida completo Producto -> Pedido -> Actualización -> Eliminación."""
    with httpx.Client(timeout=10.0) as client:
        # 1. Crear Producto
        producto_payload = {
            "nombre": "Croissant de Almendras E2E",
            "descripcion": "Hojaldre horneado con almendras y mantequilla",
            "precio": "18.50",
            "activo": True,
        }
        res_prod = client.post(f"{PRODUCTOS_URL}/productos", json=producto_payload)
        assert res_prod.status_code == 201, f"Crear producto falló: {res_prod.text}"
        producto_data = res_prod.json()
        producto_id = producto_data["id"]
        assert producto_data["nombre"] == producto_payload["nombre"]
        assert Decimal(str(producto_data["precio"])) == Decimal("18.50")
        assert producto_data["activo"] is True

        try:
            # 2. Crear Pedido referenciando el producto
            pedido_payload = {
                "producto_id": producto_id,
                "cantidad": 4,
            }
            res_ped = client.post(f"{PEDIDOS_URL}/pedidos", json=pedido_payload)
            assert res_ped.status_code == 201, f"Crear pedido falló: {res_ped.text}"
            pedido_data = res_ped.json()
            pedido_id = pedido_data["id"]
            assert pedido_data["producto_id"] == producto_id
            assert pedido_data["producto_nombre"] == "Croissant de Almendras E2E"
            assert Decimal(str(pedido_data["precio_unitario"])) == Decimal("18.50")
            assert pedido_data["cantidad"] == 4
            assert Decimal(str(pedido_data["total"])) == Decimal("74.00")

            try:
                # 3. Consultar Pedido individual
                res_get = client.get(f"{PEDIDOS_URL}/pedidos/{pedido_id}")
                assert res_get.status_code == 200
                assert res_get.json()["id"] == pedido_id
                assert Decimal(str(res_get.json()["total"])) == Decimal("74.00")

                # 4. Listar Pedidos
                res_list = client.get(f"{PEDIDOS_URL}/pedidos?limit=10&offset=0")
                assert res_list.status_code == 200
                items = res_list.json()["items"]
                ids = [p["id"] for p in items]
                assert pedido_id in ids

                # 5. Actualización parcial de cantidad en Pedido
                res_patch_ped = client.patch(
                    f"{PEDIDOS_URL}/pedidos/{pedido_id}",
                    json={"cantidad": 6},
                )
                assert res_patch_ped.status_code == 200
                updated_ped = res_patch_ped.json()
                assert updated_ped["cantidad"] == 6
                # Debe conservar precio_unitario histórico y recalcular total exacto
                assert Decimal(str(updated_ped["precio_unitario"])) == Decimal("18.50")
                assert Decimal(str(updated_ped["total"])) == Decimal("111.00")

                # 6. Modificar y desactivar Producto original
                res_patch_prod = client.patch(
                    f"{PRODUCTOS_URL}/productos/{producto_id}",
                    json={"precio": "25.00", "activo": False},
                )
                assert res_patch_prod.status_code == 200
                assert Decimal(str(res_patch_prod.json()["precio"])) == Decimal("25.00")
                assert res_patch_prod.json()["activo"] is False

                # 7. Verificar que el Pedido previo mantiene sus datos históricos
                res_hist = client.get(f"{PEDIDOS_URL}/pedidos/{pedido_id}")
                assert res_hist.status_code == 200
                hist_ped = res_hist.json()
                assert Decimal(str(hist_ped["precio_unitario"])) == Decimal("18.50")
                assert Decimal(str(hist_ped["total"])) == Decimal("111.00")
                assert hist_ped["producto_nombre"] == "Croissant de Almendras E2E"

                # 8. Rechazar creación de nuevo pedido con producto inactivo (422)
                res_inactivo = client.post(
                    f"{PEDIDOS_URL}/pedidos",
                    json={"producto_id": producto_id, "cantidad": 2},
                )
                assert res_inactivo.status_code == 422
                error_body = res_inactivo.json()
                assert error_body["detail"][0]["code"] == "product_inactive"

            finally:
                # 9. Eliminación física de Pedido
                res_del_ped = client.delete(f"{PEDIDOS_URL}/pedidos/{pedido_id}")
                assert res_del_ped.status_code == 204
                # Confirmar 404
                res_del_check = client.get(f"{PEDIDOS_URL}/pedidos/{pedido_id}")
                assert res_del_check.status_code == 404

        finally:
            # 10. Eliminación física de Producto
            res_del_prod = client.delete(f"{PRODUCTOS_URL}/productos/{producto_id}")
            assert res_del_prod.status_code == 204
            # Confirmar 404
            res_prod_check = client.get(f"{PRODUCTOS_URL}/productos/{producto_id}")
            assert res_prod_check.status_code == 404


if __name__ == "__main__":
    print(f"Probando salud en {PRODUCTOS_URL} y {PEDIDOS_URL}...")
    test_health_endpoints()
    print("Salud OK. Probando ciclo de vida E2E...")
    test_full_e2e_lifecycle()
    print("Prueba E2E completada con éxito.")
    sys.exit(0)
