"""Alembic y Uvicorn reales contra la base propia de pruebas."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, inspect


@pytest.mark.integration
def test_migrations_and_uvicorn(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Definir TEST_DATABASE_URL para verificar PostgreSQL real")
    env = {**os.environ, "DATABASE_URL": url}
    service_dir = Path(__file__).resolve().parents[1]
    for command in (("upgrade", "head"), ("current",), ("check",)):
        subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            cwd=service_dir,
            env=env,
            check=True,
            capture_output=True,
        )
    engine = create_engine(url)
    try:
        tables = inspect(engine).get_table_names()
        assert "alembic_version" in tables
        assert "pedidos" in tables
    finally:
        engine.dispose()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "uvicorn.log").open("w+") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=service_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False
            ) as client:
                deadline = time.monotonic() + 20
                while True:
                    assert process.poll() is None, "Uvicorn terminó antes de estar listo"
                    try:
                        response = client.get("/health/live")
                        break
                    except httpx.ConnectError:
                        assert time.monotonic() < deadline, "Uvicorn no arrancó en 20 segundos"
                        time.sleep(0.1)
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                ready = client.get("/health/ready")
                assert ready.status_code == 200
                assert ready.json() == {"status": "ready"}
                schema = client.get("/openapi.json")
                assert schema.status_code == 200
                assert "/health/ready" in schema.json()["paths"]
                assert "/pedidos" in schema.json()["paths"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        # Uvicorn vuelve a emitir SIGTERM después de ejecutar el cierre del lifespan.
        assert process.returncode in (0, -signal.SIGTERM)
        log.seek(0)
        output = log.read()
        assert "iniciado" in output
        assert "detenido" in output
