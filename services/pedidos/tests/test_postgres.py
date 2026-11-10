"""Pruebas con la base PostgreSQL propia; no usan SQLite ni simulaciones."""

import os
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.clients.productos import RemoteProducto
from app.config import Settings
from app.main import create_app
from app.routes import get_pedido_service
from app.service import PedidoService


@pytest.fixture(autouse=True, scope="module")
def ensure_schema():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        env = {**os.environ, "DATABASE_URL": url}
        service_dir = Path(__file__).resolve().parents[1]
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=service_dir,
            env=env,
            check=True,
            capture_output=True,
        )


@pytest.mark.integration
def test_postgres_readiness_and_database_isolation():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Definir TEST_DATABASE_URL para verificar PostgreSQL real")
    settings = Settings(_env_file=None, database_url=url)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json() == {"status": "ready"}
        with client.app.state.engine.connect() as connection:
            row = connection.execute(text("SELECT current_database(), current_user")).one()
            assert row == ("pedidos_db", "pedidos_app")
            assert not connection.execute(
                text("SELECT has_database_privilege(current_user, 'productos_db', 'CONNECT')")
            ).scalar_one()
            assert connection.execute(text("SHOW server_version_num")).scalar_one().startswith("16")
        # Tabla temporal aislada a esta conexión: confirma escritura sin datos residuales.
        with client.app.state.engine.begin() as connection:
            connection.execute(text("CREATE TEMP TABLE fase2_probe (value integer) ON COMMIT DROP"))
            connection.execute(text("INSERT INTO fase2_probe VALUES (42)"))
            assert connection.execute(text("SELECT value FROM fase2_probe")).scalar_one() == 42
        # Un fallo de sesión no impide posteriores comprobaciones de salud.
        with pytest.raises(SQLAlchemyError):
            with client.app.state.engine.begin() as connection:
                connection.execute(text("SELECT * FROM tabla_inexistente_fase2"))
        assert client.get("/health/ready").status_code == 200


@pytest.mark.integration
def test_postgres_pedidos_crud_lifecycle():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Definir TEST_DATABASE_URL para verificar PostgreSQL real")
    settings = Settings(_env_file=None, database_url=url)

    mock_client = MagicMock()
    prod_id = uuid.uuid4()
    mock_client.get_producto.return_value = RemoteProducto(
        id=prod_id,
        nombre="Pan Campesino Real",
        precio=Decimal("8.50"),
        activo=True,
    )

    app = create_app(settings)
    test_service = PedidoService(productos_client=mock_client)
    app.dependency_overrides[get_pedido_service] = lambda: test_service

    with TestClient(app) as client:
        # 1. Crear pedido y verificar HTTP 201
        create_res = client.post(
            "/pedidos",
            json={"producto_id": str(prod_id), "cantidad": 4},
        )
        assert create_res.status_code == 201
        data = create_res.json()
        pedido_id = data["id"]
        assert data["producto_nombre"] == "Pan Campesino Real"
        assert data["precio_unitario"] == "8.50"
        assert data["total"] == "34.00"
        assert data["created_at"].endswith("Z")
        assert data["updated_at"].endswith("Z")

        # 2. Comprobar persistencia real en PostgreSQL con tipos nativos
        with client.app.state.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, producto_id, producto_nombre, cantidad, precio_unitario, total "
                    "FROM pedidos WHERE id = :id"
                ),
                {"id": pedido_id},
            ).one()
            assert str(row[0]) == pedido_id
            assert str(row[1]) == str(prod_id)
            assert row[2] == "Pan Campesino Real"
            assert row[3] == 4
            assert row[4] == Decimal("8.50")
            assert row[5] == Decimal("34.00")

        # 3. Consultar vía HTTP GET /pedidos/{id} (no consulta Productos)
        mock_client.get_producto.reset_mock()
        get_res = client.get(f"/pedidos/{pedido_id}")
        assert get_res.status_code == 200
        assert get_res.json()["producto_nombre"] == "Pan Campesino Real"
        assert get_res.json()["total"] == "34.00"
        mock_client.get_producto.assert_not_called()

        # 4. Listar vía HTTP GET /pedidos
        list_res = client.get("/pedidos?limit=10&offset=0")
        assert list_res.status_code == 200
        assert list_res.json()["total"] >= 1
        ids = [item["id"] for item in list_res.json()["items"]]
        assert pedido_id in ids

        # 5. Actualizar solo cantidad vía HTTP PATCH: conserva precio y recalcula total
        patch_res = client.patch(
            f"/pedidos/{pedido_id}",
            json={"cantidad": 5},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["cantidad"] == 5
        assert patch_res.json()["precio_unitario"] == "8.50"
        assert patch_res.json()["total"] == "42.50"
        mock_client.get_producto.assert_not_called()

        # 6. Comprobar actualización en PostgreSQL
        with client.app.state.engine.connect() as conn:
            row = conn.execute(
                text("SELECT cantidad, total FROM pedidos WHERE id = :id"),
                {"id": pedido_id},
            ).one()
            assert row[0] == 5
            assert row[1] == Decimal("42.50")

        # 7. Eliminar físicamente vía HTTP DELETE /pedidos/{id}
        del_res = client.delete(f"/pedidos/{pedido_id}")
        assert del_res.status_code == 204
        assert del_res.text == ""

        # 8. Comprobar eliminación física en PostgreSQL directamente
        with client.app.state.engine.connect() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM pedidos WHERE id = :id"),
                {"id": pedido_id},
            ).scalar_one()
            assert count == 0

        # 9. Repetir DELETE devuelve 404
        assert client.delete(f"/pedidos/{pedido_id}").status_code == 404

        # 10. GET posterior devuelve 404
        assert client.get(f"/pedidos/{pedido_id}").status_code == 404
