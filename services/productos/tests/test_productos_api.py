import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import get_session
from app.main import create_app
from app.models import Producto


class InMemorySession:
    def __init__(self):
        self.productos: dict[uuid.UUID, Producto] = {}

    def get(self, model, id_val):
        return self.productos.get(id_val)

    def add(self, obj):
        self.productos[obj.id] = obj

    def delete(self, obj):
        self.productos.pop(obj.id, None)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def scalar(self, stmt):
        return len(self.productos)

    def scalars(self, stmt):
        sorted_items = sorted(self.productos.values(), key=lambda p: (p.created_at, p.id))
        limit = stmt._limit
        offset = stmt._offset or 0
        if limit is not None:
            slice_items = sorted_items[offset : offset + limit]
        else:
            slice_items = sorted_items[offset:]
        mock_result = MagicMock()
        mock_result.all.return_value = slice_items
        return mock_result


@pytest.fixture
def fake_db():
    return InMemorySession()


@pytest.fixture
def client(fake_db):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:private@127.0.0.1:1/test",
        db_connect_timeout_seconds=1,
    )
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: fake_db
    with TestClient(app) as test_client:
        yield test_client


def test_create_producto_minimal(client):
    payload = {"nombre": "Pan Francés", "precio": "2.50"}
    response = client.post("/productos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["nombre"] == "Pan Francés"
    assert data["descripcion"] is None
    assert data["precio"] == "2.50"
    assert data["activo"] is True
    assert data["created_at"].endswith("Z")
    assert data["updated_at"].endswith("Z")


def test_create_producto_full(client):
    payload = {
        "nombre": "  Pan de Masa Madre  ",
        "descripcion": "Elaborado con harina integral y fermentación lenta.",
        "precio": "18.75",
        "activo": False,
    }
    response = client.post("/productos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == "Pan de Masa Madre"
    assert data["descripcion"] == "Elaborado con harina integral y fermentación lenta."
    assert data["precio"] == "18.75"
    assert data["activo"] is False


def test_create_producto_rejects_empty_and_whitespace_nombre(client):
    for bad_nombre in ["", "   ", " \t \n "]:
        response = client.post("/productos", json={"nombre": bad_nombre, "precio": "5.00"})
        assert response.status_code == 422
        assert response.json()["detail"][0]["code"] == "invalid_value"
        assert response.json()["detail"][0]["loc"] == ["body", "nombre"]


def test_create_producto_rejects_long_nombre(client):
    response = client.post("/productos", json={"nombre": "A" * 151, "precio": "5.00"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_create_producto_rejects_long_descripcion(client):
    response = client.post(
        "/productos",
        json={"nombre": "Pan", "descripcion": "B" * 1001, "precio": "5.00"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


@pytest.mark.parametrize(
    "valid_precio,expected_precio",
    [
        (5.5, "5.50"),
        (5, "5.00"),
        ("5.50", "5.50"),
        ("12.99", "12.99"),
        ("100", "100.00"),
    ],
)
def test_create_producto_accepts_float_int_and_str_precio(client, valid_precio, expected_precio):
    response = client.post("/productos", json={"nombre": "Pan Flexible", "precio": valid_precio})
    assert response.status_code == 201
    assert response.json()["precio"] == expected_precio


@pytest.mark.parametrize(
    "bad_precio",
    [
        "0",  # non-positive
        "0.00",  # zero
        -3.50,  # negative float
        "-3.50",  # negative string
        5.555,  # more than 2 decimals float
        "5.555",  # more than 2 decimals string
        "1e2",  # exponential
        "abc",  # not numeric
        "",  # empty
        None,  # null
        True,  # boolean
        False,  # boolean
    ],
)
def test_create_producto_rejects_invalid_precio(client, bad_precio):
    response = client.post("/productos", json={"nombre": "Pan", "precio": bad_precio})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["body", "precio"]


@pytest.mark.parametrize("bad_activo", ["true", "false", 1, 0, None])
def test_create_producto_rejects_invalid_activo(client, bad_activo):
    response = client.post(
        "/productos",
        json={"nombre": "Pan", "precio": "5.00", "activo": bad_activo},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["body", "activo"]


def test_create_producto_rejects_extra_fields(client):
    response = client.post(
        "/productos",
        json={"nombre": "Pan", "precio": "5.00", "extra_prop": "invalida"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "extra_field"
    assert response.json()["detail"][0]["loc"] == ["body", "extra_prop"]


def test_create_producto_rejects_server_managed_fields(client):
    response = client.post(
        "/productos",
        json={
            "nombre": "Pan",
            "precio": "5.00",
            "id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "extra_field"
    assert response.json()["detail"][0]["loc"] == ["body", "id"]


def test_create_producto_rejects_non_object_body(client):
    response = client.post("/productos", json=["array"])
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["body"]


def test_create_producto_rejects_malformed_json(client):
    response = client.post(
        "/productos",
        content='{"nombre": invalid json',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["body"]


def test_list_productos_empty(client):
    response = client.get("/productos")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_productos_pagination_and_ordering(client, fake_db):
    base_time = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(5):
        p = Producto(
            id=uuid.UUID(f"00000000-0000-0000-0000-00000000000{i}"),
            nombre=f"Producto {i}",
            descripcion=None,
            precio=Decimal(f"{i + 1}.00"),
            activo=True,
            created_at=base_time.replace(minute=i),
            updated_at=base_time.replace(minute=i),
        )
        fake_db.add(p)

    # First page: limit 2, offset 0
    res1 = client.get("/productos?limit=2&offset=0")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 5
    assert len(data1["items"]) == 2
    assert data1["items"][0]["nombre"] == "Producto 0"
    assert data1["items"][1]["nombre"] == "Producto 1"

    # Second page: limit 2, offset 2
    res2 = client.get("/productos?limit=2&offset=2")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 5
    assert len(data2["items"]) == 2
    assert data2["items"][0]["nombre"] == "Producto 2"
    assert data2["items"][1]["nombre"] == "Producto 3"

    # Offset beyond total
    res3 = client.get("/productos?limit=2&offset=10")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total"] == 5
    assert data3["items"] == []


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),  # limit < 1
        (101, 0),  # limit > 100
        (-1, 0),  # limit negative
        (20, -1),  # offset negative
        ("abc", 0),  # limit not int
        (20, "xyz"),  # offset not int
    ],
)
def test_list_productos_invalid_pagination(client, limit, offset):
    response = client.get(f"/productos?limit={limit}&offset={offset}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_get_producto_by_id_success(client, fake_db):
    uid = uuid.uuid4()
    p = Producto(
        id=uid,
        nombre="Pan de Banano",
        descripcion="Delicioso",
        precio=Decimal("12.50"),
        activo=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    response = client.get(f"/productos/{uid}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(uid)
    assert data["nombre"] == "Pan de Banano"
    assert data["precio"] == "12.50"


def test_get_producto_not_found(client):
    non_existent = uuid.uuid4()
    response = client.get(f"/productos/{non_existent}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": [
            {
                "loc": ["path", "id"],
                "code": "not_found",
                "msg": "Producto no encontrado.",
            }
        ]
    }


def test_get_producto_invalid_uuid(client):
    response = client.get("/productos/no-es-un-uuid")
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


def test_patch_producto_partial_updates(client, fake_db):
    uid = uuid.uuid4()
    p = Producto(
        id=uid,
        nombre="Nombre Original",
        descripcion="Descripcion original",
        precio=Decimal("10.00"),
        activo=True,
        created_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC),
    )
    fake_db.add(p)

    # 1. Update only nombre
    res_nom = client.patch(f"/productos/{uid}", json={"nombre": "Nuevo Nombre"})
    assert res_nom.status_code == 200
    assert res_nom.json()["nombre"] == "Nuevo Nombre"
    assert res_nom.json()["precio"] == "10.00"
    assert res_nom.json()["created_at"].startswith("2026-11-01T10:00:00")

    # 2. Update only precio
    res_pre = client.patch(f"/productos/{uid}", json={"precio": "15.50"})
    assert res_pre.status_code == 200
    assert res_pre.json()["precio"] == "15.50"
    assert res_pre.json()["nombre"] == "Nuevo Nombre"

    # 3. Update only activo
    res_act = client.patch(f"/productos/{uid}", json={"activo": False})
    assert res_act.status_code == 200
    assert res_act.json()["activo"] is False

    # 4. Clear descripcion with null
    res_desc = client.patch(f"/productos/{uid}", json={"descripcion": None})
    assert res_desc.status_code == 200
    assert res_desc.json()["descripcion"] is None


def test_patch_producto_rejects_empty_patch(client):
    uid = uuid.uuid4()
    response = client.patch(f"/productos/{uid}", json={})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["body"],
                "code": "empty_patch",
                "msg": "El cuerpo de actualización no puede estar vacío.",
            }
        ]
    }


def test_patch_producto_rejects_extra_fields(client):
    uid = uuid.uuid4()
    response = client.patch(f"/productos/{uid}", json={"campo_extra": "valor"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "extra_field"
    assert response.json()["detail"][0]["loc"] == ["body", "campo_extra"]


def test_patch_producto_rejects_null_for_non_nullable_fields(client):
    uid = uuid.uuid4()
    for field in ["nombre", "precio", "activo"]:
        response = client.patch(f"/productos/{uid}", json={field: None})
        assert response.status_code == 422
        assert response.json()["detail"][0]["code"] == "invalid_value"


def test_patch_producto_not_found(client):
    uid = uuid.uuid4()
    response = client.patch(f"/productos/{uid}", json={"nombre": "Nuevo"})
    assert response.status_code == 404
    assert response.json()["detail"][0]["code"] == "not_found"


def test_delete_producto_lifecycle(client, fake_db):
    uid = uuid.uuid4()
    p = Producto(
        id=uid,
        nombre="Para Borrar",
        descripcion=None,
        precio=Decimal("5.00"),
        activo=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    # First delete -> 204 No Content
    res_del = client.delete(f"/productos/{uid}")
    assert res_del.status_code == 204
    assert res_del.text == ""

    # Second delete (repeat) -> 404 Not Found
    res_repeat = client.delete(f"/productos/{uid}")
    assert res_repeat.status_code == 404
    assert res_repeat.json()["detail"][0]["code"] == "not_found"

    # Get after delete -> 404 Not Found
    res_get = client.get(f"/productos/{uid}")
    assert res_get.status_code == 404
    assert res_get.json()["detail"][0]["code"] == "not_found"


def test_database_error_handling(client):
    broken_db = MagicMock()
    broken_db.get.side_effect = OperationalError("connection refused", {}, Exception("db down"))
    broken_db.scalar.side_effect = OperationalError("connection refused", {}, Exception("db down"))
    broken_db.add.side_effect = OperationalError("connection refused", {}, Exception("db down"))

    client.app.dependency_overrides[get_session] = lambda: broken_db

    # GET /productos/{id} triggers db error -> 503
    uid = uuid.uuid4()
    res_get = client.get(f"/productos/{uid}")
    assert res_get.status_code == 503
    assert res_get.json() == {
        "detail": [
            {
                "loc": ["server"],
                "code": "database_unavailable",
                "msg": "Base de datos no disponible.",
            }
        ]
    }
    assert "connection refused" not in res_get.text

    # GET /productos triggers db error -> 503
    res_list = client.get("/productos")
    assert res_list.status_code == 503
    assert res_list.json()["detail"][0]["code"] == "database_unavailable"


def test_openapi_schema_contains_productos(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/productos" in paths
    assert "post" in paths["/productos"]
    assert "get" in paths["/productos"]
    assert "/productos/{id}" in paths
    assert "get" in paths["/productos/{id}"]
    assert "patch" in paths["/productos/{id}"]
    assert "delete" in paths["/productos/{id}"]
