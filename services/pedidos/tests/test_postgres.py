"""Pruebas con la base PostgreSQL propia; no usan SQLite ni simulaciones."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.main import create_app


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
