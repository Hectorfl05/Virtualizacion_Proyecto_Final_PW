import uuid
from decimal import Decimal

import httpx
import pytest

from app.clients.productos import (
    ProductInactiveError,
    ProductNotFoundError,
    ProductosClient,
    ProductsUnavailableError,
)


def test_client_get_producto_success():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/productos/{pid}"
        return httpx.Response(
            200,
            json={
                "id": str(pid),
                "nombre": "Pan Baguette",
                "descripcion": "Crocante",
                "precio": "3.50",
                "activo": True,
                "created_at": "2026-11-06T12:00:00Z",
                "updated_at": "2026-11-06T12:00:00Z",
            },
        )

    client = ProductosClient(transport=httpx.MockTransport(handler))
    prod = client.get_producto(pid)
    assert prod.id == pid
    assert prod.nombre == "Pan Baguette"
    assert prod.precio == Decimal("3.50")
    assert prod.activo is True


def test_client_get_producto_not_found():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": [{"loc": ["path", "id"], "code": "not_found"}]})

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductNotFoundError):
        client.get_producto(pid)


def test_client_get_producto_inactive():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(pid),
                "nombre": "Pan Descontinuado",
                "precio": "2.00",
                "activo": False,
            },
        )

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductInactiveError):
        client.get_producto(pid)


def test_client_timeout():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout al leer respuesta")

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError) as exc:
        client.get_producto(pid)
    assert "Tiempo de espera agotado" in str(exc.value)


def test_client_connection_error():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("No se pudo conectar al host")

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError) as exc:
        client.get_producto(pid)
    assert "Error de conexión" in str(exc.value)


def test_client_mismatched_id_in_response():
    pid = uuid.uuid4()
    other_pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(other_pid),
                "nombre": "Pan",
                "precio": "2.00",
                "activo": True,
            },
        )

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError) as exc:
        client.get_producto(pid)
    assert "no cumple con el contrato esperado" in str(exc.value)


def test_client_corrupt_json_response():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError):
        client.get_producto(pid)


def test_client_server_error_500():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "internal error"})

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError):
        client.get_producto(pid)


def test_client_invalid_price():
    pid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(pid),
                "nombre": "Pan",
                "precio": "-5.00",
                "activo": True,
            },
        )

    client = ProductosClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProductsUnavailableError):
        client.get_producto(pid)
