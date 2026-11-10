"""Pruebas con la base PostgreSQL propia; no usan SQLite ni simulaciones."""

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.main import create_app
from app.routes import get_producto_service
from app.service import ProductoService


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
            assert row == ("productos_db", "productos_app")
            assert not connection.execute(
                text("SELECT has_database_privilege(current_user, 'pedidos_db', 'CONNECT')")
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
def test_postgres_productos_crud_lifecycle():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Definir TEST_DATABASE_URL para verificar PostgreSQL real")
    settings = Settings(_env_file=None, database_url=url)
    app = create_app(settings)
    # Pedidos tiene su propia base: aquí se simula que el producto no tiene pedidos.
    no_orders = MagicMock()
    no_orders.has_pedidos.return_value = False
    stub_service = ProductoService(pedidos_client=no_orders)
    app.dependency_overrides[get_producto_service] = lambda: stub_service
    with TestClient(app) as client:
        # 1. Crear producto con datos completos y verificar respuesta HTTP 201
        create_res = client.post(
            "/productos",
            json={
                "nombre": "Pan de Campo Real PG",
                "descripcion": "Horneado en horno de leña",
                "precio": "14.50",
                "activo": True,
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        pid = data["id"]
        assert data["precio"] == "14.50"
        assert data["activo"] is True
        assert data["created_at"].endswith("Z")
        assert data["updated_at"].endswith("Z")

        # 2. Comprobar persistencia real en PostgreSQL directamente con SQL
        with client.app.state.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, nombre, descripcion, precio, activo, created_at, updated_at "
                    "FROM productos WHERE id = :id"
                ),
                {"id": pid},
            ).one()
            assert str(row[0]) == pid
            assert row[1] == "Pan de Campo Real PG"
            assert row[2] == "Horneado en horno de leña"
            assert row[3] == Decimal("14.50")
            assert row[4] is True
            assert row[5] is not None
            assert row[6] is not None

        # 3. Consultar vía HTTP GET /productos/{id}
        get_res = client.get(f"/productos/{pid}")
        assert get_res.status_code == 200
        assert get_res.json()["nombre"] == "Pan de Campo Real PG"
        assert get_res.json()["precio"] == "14.50"

        # 4. Listar vía HTTP GET /productos
        list_res = client.get("/productos?limit=10&offset=0")
        assert list_res.status_code == 200
        assert list_res.json()["total"] >= 1
        ids = [item["id"] for item in list_res.json()["items"]]
        assert pid in ids

        # 5. Actualizar vía HTTP PATCH /productos/{id}
        patch_res = client.patch(
            f"/productos/{pid}",
            json={"precio": "16.00", "descripcion": None},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["precio"] == "16.00"
        assert patch_res.json()["descripcion"] is None

        # 6. Comprobar actualización directamente en PostgreSQL
        with client.app.state.engine.connect() as conn:
            row = conn.execute(
                text("SELECT precio, descripcion FROM productos WHERE id = :id"),
                {"id": pid},
            ).one()
            assert row[0] == Decimal("16.00")
            assert row[1] is None

        # 7. Eliminar físicamente vía HTTP DELETE /productos/{id}
        del_res = client.delete(f"/productos/{pid}")
        assert del_res.status_code == 204
        assert del_res.text == ""

        # 8. Comprobar eliminación física en PostgreSQL directamente
        with client.app.state.engine.connect() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM productos WHERE id = :id"),
                {"id": pid},
            ).scalar_one()
            assert count == 0

        # 9. Comprobar que repetir DELETE devuelve 404
        assert client.delete(f"/productos/{pid}").status_code == 404

        # 10. Comprobar que consultar el producto eliminado devuelve 404
        assert client.get(f"/productos/{pid}").status_code == 404
