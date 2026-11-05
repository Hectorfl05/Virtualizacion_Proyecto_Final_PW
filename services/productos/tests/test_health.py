from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:private@127.0.0.1:1/test",
        db_connect_timeout_seconds=1,
    )


def test_liveness_is_independent_of_database(settings):
    with TestClient(create_app(settings)) as client:
        engine = MagicMock()
        client.app.state.engine = engine
        assert client.get("/health/live").json() == {"status": "ok"}
        engine.connect.assert_not_called()


def test_readiness_success_and_openapi(settings):
    with TestClient(create_app(settings)) as client:
        engine = MagicMock()
        client.app.state.engine = engine
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
        connection = engine.connect.return_value.__enter__.return_value
        assert str(connection.execute.call_args.args[0]) == "SELECT 1"
        schema = client.get("/openapi.json").json()
        assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]


def test_readiness_failure_does_not_expose_credentials(settings, caplog):
    with TestClient(create_app(settings)) as client:
        engine = MagicMock()
        engine.connect.side_effect = OperationalError("private", {}, Exception("private"))
        client.app.state.engine = engine
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "detail": [
                {
                    "loc": ["server"],
                    "code": "database_unavailable",
                    "msg": "Base de datos no disponible.",
                }
            ]
        }
        assert "private" not in response.text + caplog.text
        assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize("url", ["sqlite:///test.db", "invalid", "postgresql://u:p@db/test"])
def test_rejects_invalid_database_configuration(url):
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, database_url=url)
    assert url not in str(exc.value)
