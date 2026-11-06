import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx

logger = logging.getLogger("panaderia.pedidos.clients")


class ProductNotFoundError(Exception):
    def __init__(self, producto_id: uuid.UUID):
        self.producto_id = producto_id
        super().__init__(f"Producto con id {producto_id} no encontrado.")


class ProductInactiveError(Exception):
    def __init__(self, producto_id: uuid.UUID):
        self.producto_id = producto_id
        super().__init__(f"El producto con id {producto_id} no está activo para nuevos pedidos.")


class ProductsUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class RemoteProducto:
    id: uuid.UUID
    nombre: str
    precio: Decimal
    activo: bool


class ProductosClient:
    def __init__(
        self,
        base_url: str = "http://productos:8000",
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def get_producto(self, producto_id: uuid.UUID) -> RemoteProducto:
        url = f"{self.base_url}/productos/{producto_id}"
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = client.get(url)
        except httpx.TimeoutException as exc:
            logger.warning("Timeout al consultar servicio de productos: %s", type(exc).__name__)
            raise ProductsUnavailableError(
                "Tiempo de espera agotado al consultar el servicio de productos."
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Fallo de red al consultar productos: %s", type(exc).__name__)
            raise ProductsUnavailableError(
                "Error de conexión al consultar el servicio de productos."
            ) from exc

        if response.status_code == 404:
            raise ProductNotFoundError(producto_id)

        if response.status_code != 200:
            logger.warning(
                "Servicio de productos respondió con status inesperado: %d", response.status_code
            )
            raise ProductsUnavailableError(
                "Respuesta inesperada del servicio de productos al validar el producto."
            )

        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("La respuesta remota no es un objeto JSON.")

            # Validar coincidencia de ID
            returned_id_str = data.get("id")
            if not returned_id_str or uuid.UUID(str(returned_id_str)) != producto_id:
                raise ValueError("El ID devuelto no coincide con el producto solicitado.")

            # Validar nombre
            nombre = data.get("nombre")
            if not isinstance(nombre, str) or not nombre.strip():
                raise ValueError("El nombre devuelto por el servicio de productos es inválido.")

            # Validar estado activo
            activo = data.get("activo")
            if not isinstance(activo, bool):
                raise ValueError("El campo 'activo' devuelto por productos es inválido.")
            if not activo:
                raise ProductInactiveError(producto_id)

            # Validar precio
            precio_raw = data.get("precio")
            if not isinstance(precio_raw, (str, int, float, Decimal)):
                raise ValueError("El precio devuelto por el servicio de productos es inválido.")
            precio_dec = Decimal(str(precio_raw))
            if precio_dec <= Decimal("0"):
                raise ValueError("El precio devuelto debe ser un valor positivo.")

            return RemoteProducto(
                id=producto_id,
                nombre=nombre.strip(),
                precio=precio_dec,
                activo=True,
            )
        except (ValueError, InvalidOperation, KeyError) as exc:
            logger.warning(
                "Respuesta del servicio de productos no conforme al contrato: %s", str(exc)
            )
            raise ProductsUnavailableError(
                "Respuesta del servicio de productos no cumple con el contrato esperado."
            ) from exc
