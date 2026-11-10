import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.clients.productos import (
    ProductInactiveError,
    ProductNotFoundError,
    ProductsUnavailableError,
    RemoteProducto,
)
from app.config import Settings
from app.database import get_session
from app.main import create_app
from app.models import Pedido
from app.routes import get_pedido_service
from app.service import PedidoService


class InMemorySession:
    def __init__(self):
        self.pedidos: dict[uuid.UUID, Pedido] = {}

    def get(self, model, id_val):
        return self.pedidos.get(id_val)

    def add(self, obj):
        self.pedidos[obj.id] = obj

    def delete(self, obj):
        self.pedidos.pop(obj.id, None)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def scalar(self, stmt):
        return len(self.pedidos)

    def scalars(self, stmt):
        sorted_items = sorted(self.pedidos.values(), key=lambda p: (p.created_at, p.id))
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
def mock_productos_client():
    client = MagicMock()
    client.get_producto.return_value = RemoteProducto(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        nombre="Pan de Bono",
        precio=Decimal("4.50"),
        activo=True,
    )
    return client


@pytest.fixture
def client(fake_db, mock_productos_client):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:private@127.0.0.1:1/test",
        db_connect_timeout_seconds=1,
    )
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: fake_db
    test_service = PedidoService(productos_client=mock_productos_client)
    app.dependency_overrides[get_pedido_service] = lambda: test_service

    with TestClient(app) as test_client:
        yield test_client


def test_create_pedido_success(client, mock_productos_client):
    prod_id = uuid.uuid4()
    mock_productos_client.get_producto.return_value = RemoteProducto(
        id=prod_id,
        nombre="Pan Francés",
        precio=Decimal("2.50"),
        activo=True,
    )

    response = client.post(
        "/pedidos",
        json={"producto_id": str(prod_id), "cantidad": 3},
    )
    assert response.status_code == 201
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["producto_id"] == str(prod_id)
    assert data["producto_nombre"] == "Pan Francés"
    assert data["cantidad"] == 3
    assert data["precio_unitario"] == "2.50"
    assert data["total"] == "7.50"
    assert data["created_at"].endswith("Z")
    assert data["updated_at"].endswith("Z")
    mock_productos_client.get_producto.assert_called_once_with(prod_id)


def test_create_pedido_rejects_price_and_total(client):
    prod_id = str(uuid.uuid4())
    # Sending precio should be rejected with extra_field
    res_precio = client.post(
        "/pedidos",
        json={"producto_id": prod_id, "cantidad": 2, "precio": "2.50"},
    )
    assert res_precio.status_code == 422
    assert res_precio.json()["detail"][0]["code"] == "extra_field"
    assert res_precio.json()["detail"][0]["loc"] == ["body", "precio"]

    # Sending total should be rejected with extra_field
    res_total = client.post(
        "/pedidos",
        json={"producto_id": prod_id, "cantidad": 2, "total": "5.00"},
    )
    assert res_total.status_code == 422
    assert res_total.json()["detail"][0]["code"] == "extra_field"
    assert res_total.json()["detail"][0]["loc"] == ["body", "total"]


def test_create_pedido_rejects_server_managed_fields(client):
    prod_id = str(uuid.uuid4())
    res_id = client.post(
        "/pedidos",
        json={"producto_id": prod_id, "cantidad": 1, "id": str(uuid.uuid4())},
    )
    assert res_id.status_code == 422
    assert res_id.json()["detail"][0]["code"] == "extra_field"


@pytest.mark.parametrize("bad_cant", [0, -1, 2.5, "3", True, False, None])
def test_create_pedido_rejects_invalid_cantidad(client, bad_cant):
    response = client.post(
        "/pedidos",
        json={"producto_id": str(uuid.uuid4()), "cantidad": bad_cant},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"
    assert response.json()["detail"][0]["loc"] == ["body", "cantidad"]


def test_create_pedido_rejects_invalid_producto_id(client):
    for bad_id in ["not-a-uuid", 123, None]:
        response = client.post("/pedidos", json={"producto_id": bad_id, "cantidad": 1})
        assert response.status_code == 422
        assert response.json()["detail"][0]["code"] == "invalid_value"


def test_create_pedido_empty_body(client):
    response = client.post("/pedidos", json={})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_create_pedido_malformed_json(client):
    response = client.post(
        "/pedidos",
        content='{"producto_id": broken',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_create_pedido_non_object_body(client):
    response = client.post("/pedidos", json=["an", "array"])
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_create_pedido_product_not_found(client, mock_productos_client):
    prod_id = uuid.uuid4()
    mock_productos_client.get_producto.side_effect = ProductNotFoundError(prod_id)

    response = client.post("/pedidos", json={"producto_id": str(prod_id), "cantidad": 2})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["code"] == "product_not_found"
    assert data["detail"][0]["loc"] == ["body", "producto_id"]
    assert "no existe" in data["detail"][0]["msg"]


def test_create_pedido_product_inactive(client, mock_productos_client):
    prod_id = uuid.uuid4()
    mock_productos_client.get_producto.side_effect = ProductInactiveError(prod_id)

    response = client.post("/pedidos", json={"producto_id": str(prod_id), "cantidad": 2})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["code"] == "product_inactive"
    assert data["detail"][0]["loc"] == ["body", "producto_id"]
    assert "no está activo" in data["detail"][0]["msg"]


def test_create_pedido_products_service_unavailable(client, mock_productos_client):
    prod_id = uuid.uuid4()
    mock_productos_client.get_producto.side_effect = ProductsUnavailableError("Timeout remoto")

    response = client.post("/pedidos", json={"producto_id": str(prod_id), "cantidad": 2})
    assert response.status_code == 503
    data = response.json()
    assert data["detail"][0]["code"] == "products_unavailable"
    assert data["detail"][0]["loc"] == ["server"]
    assert "no está disponible" in data["detail"][0]["msg"]


def test_list_pedidos_empty(client):
    response = client.get("/pedidos")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_pedidos_pagination_and_ordering(client, fake_db, mock_productos_client):
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
    for i in range(5):
        p = Pedido(
            id=uuid.UUID(f"00000000-0000-0000-0000-00000000000{i}"),
            producto_id=uuid.uuid4(),
            producto_nombre=f"Producto {i}",
            cantidad=i + 1,
            precio_unitario=Decimal("5.00"),
            total=Decimal(f"{(i + 1) * 5}.00"),
            created_at=base_time.replace(minute=i),
            updated_at=base_time.replace(minute=i),
        )
        fake_db.add(p)

    res1 = client.get("/pedidos?limit=2&offset=0")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 5
    assert len(data1["items"]) == 2
    assert data1["items"][0]["producto_nombre"] == "Producto 0"
    assert data1["items"][1]["producto_nombre"] == "Producto 1"

    # Verify ProductosClient was NOT called during list
    mock_productos_client.get_producto.assert_not_called()


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (-1, 0), (20, -1), ("abc", 0), (20, "xyz")],
)
def test_list_pedidos_invalid_pagination(client, limit, offset):
    response = client.get(f"/pedidos?limit={limit}&offset={offset}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_get_pedido_success(client, fake_db, mock_productos_client):
    pid = uuid.uuid4()
    p = Pedido(
        id=pid,
        producto_id=uuid.uuid4(),
        producto_nombre="Pan Queso",
        cantidad=4,
        precio_unitario=Decimal("3.50"),
        total=Decimal("14.00"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    response = client.get(f"/pedidos/{pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pid)
    assert data["producto_nombre"] == "Pan Queso"
    assert data["precio_unitario"] == "3.50"
    assert data["total"] == "14.00"

    # ProductosClient was NOT called during get
    mock_productos_client.get_producto.assert_not_called()


def test_get_pedido_not_found(client):
    response = client.get(f"/pedidos/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"][0]["code"] == "not_found"
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


def test_get_pedido_invalid_uuid(client):
    response = client.get("/pedidos/invalid-uuid")
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "invalid_value"


def test_patch_pedido_update_cantidad_only_preserves_historical_data(
    client, fake_db, mock_productos_client
):
    pid = uuid.uuid4()
    prod_id = uuid.uuid4()
    p = Pedido(
        id=pid,
        producto_id=prod_id,
        producto_nombre="Pan Antiguo",
        cantidad=2,
        precio_unitario=Decimal("5.50"),
        total=Decimal("11.00"),
        created_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC),
    )
    fake_db.add(p)

    # Actualizar solo cantidad a 4: total debe ser 22.00, precio_unitario 5.50
    response = client.patch(f"/pedidos/{pid}", json={"cantidad": 4})
    assert response.status_code == 200
    data = response.json()
    assert data["cantidad"] == 4
    assert data["precio_unitario"] == "5.50"
    assert data["total"] == "22.00"
    assert data["producto_nombre"] == "Pan Antiguo"
    assert data["created_at"].startswith("2026-11-01T10:00:00")

    # IMPORTANT: ProductosClient must NOT be called when only updating cantidad!
    mock_productos_client.get_producto.assert_not_called()


def test_patch_pedido_update_producto_id_calls_remote(client, fake_db, mock_productos_client):
    pid = uuid.uuid4()
    old_prod_id = uuid.uuid4()
    new_prod_id = uuid.uuid4()

    p = Pedido(
        id=pid,
        producto_id=old_prod_id,
        producto_nombre="Pan Viejo",
        cantidad=3,
        precio_unitario=Decimal("4.00"),
        total=Decimal("12.00"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    mock_productos_client.get_producto.return_value = RemoteProducto(
        id=new_prod_id,
        nombre="Pan Nuevo Fresco",
        precio=Decimal("6.00"),
        activo=True,
    )

    response = client.patch(f"/pedidos/{pid}", json={"producto_id": str(new_prod_id)})
    assert response.status_code == 200
    data = response.json()
    assert data["producto_id"] == str(new_prod_id)
    assert data["producto_nombre"] == "Pan Nuevo Fresco"
    assert data["precio_unitario"] == "6.00"
    assert data["cantidad"] == 3  # Preserved quantity
    assert data["total"] == "18.00"  # 3 * 6.00
    mock_productos_client.get_producto.assert_called_once_with(new_prod_id)


def test_patch_pedido_same_producto_id_does_not_call_remote(client, fake_db, mock_productos_client):
    pid = uuid.uuid4()
    prod_id = uuid.uuid4()
    p = Pedido(
        id=pid,
        producto_id=prod_id,
        producto_nombre="Pan Original",
        cantidad=2,
        precio_unitario=Decimal("5.00"),
        total=Decimal("10.00"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    response = client.patch(
        f"/pedidos/{pid}",
        json={"producto_id": str(prod_id), "cantidad": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cantidad"] == 5
    assert data["total"] == "25.00"
    assert data["producto_nombre"] == "Pan Original"
    assert data["precio_unitario"] == "5.00"

    # Enviar el mismo producto_id no debe llamar a ProductosClient
    mock_productos_client.get_producto.assert_not_called()


def test_patch_pedido_rejects_empty_patch(client):
    response = client.patch(f"/pedidos/{uuid.uuid4()}", json={})
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "empty_patch"


def test_patch_pedido_rejects_extra_fields(client):
    response = client.patch(
        f"/pedidos/{uuid.uuid4()}",
        json={"cantidad": 3, "precio": "10.00"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == "extra_field"


def test_patch_pedido_rejects_null_on_fields(client):
    for bad_field in [{"cantidad": None}, {"producto_id": None}]:
        response = client.patch(f"/pedidos/{uuid.uuid4()}", json=bad_field)
        assert response.status_code == 422
        assert response.json()["detail"][0]["code"] == "invalid_value"


def test_delete_pedido_lifecycle(client, fake_db, mock_productos_client):
    pid = uuid.uuid4()
    p = Pedido(
        id=pid,
        producto_id=uuid.uuid4(),
        producto_nombre="Para Borrar",
        cantidad=1,
        precio_unitario=Decimal("5.00"),
        total=Decimal("5.00"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_db.add(p)

    res_del = client.delete(f"/pedidos/{pid}")
    assert res_del.status_code == 204
    assert res_del.text == ""

    # Repeat delete returns 404
    res_repeat = client.delete(f"/pedidos/{pid}")
    assert res_repeat.status_code == 404
    assert res_repeat.json()["detail"][0]["code"] == "not_found"

    # Get after delete returns 404
    res_get = client.get(f"/pedidos/{pid}")
    assert res_get.status_code == 404

    # ProductosClient was NOT called during delete
    mock_productos_client.get_producto.assert_not_called()


def test_database_error_handling(client):
    broken_db = MagicMock()
    broken_db.get.side_effect = OperationalError("connection refused", {}, Exception("db down"))
    broken_db.scalar.side_effect = OperationalError("connection refused", {}, Exception("db down"))

    client.app.dependency_overrides[get_session] = lambda: broken_db

    res_get = client.get(f"/pedidos/{uuid.uuid4()}")
    assert res_get.status_code == 503
    assert res_get.json()["detail"][0]["code"] == "database_unavailable"


def test_openapi_schema_contains_pedidos(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/pedidos" in paths
    assert "post" in paths["/pedidos"]
    assert "get" in paths["/pedidos"]
    assert "/pedidos/{id}" in paths
    assert "get" in paths["/pedidos/{id}"]
    assert "patch" in paths["/pedidos/{id}"]
    assert "delete" in paths["/pedidos/{id}"]
