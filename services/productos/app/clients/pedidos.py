import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid

logger = logging.getLogger("panaderia.productos.clients")


class PedidosUnavailableError(Exception):
    pass


class PedidosClient:
    """Consulta a Pedidos si un producto tiene pedidos (sin FK entre bases)."""

    def __init__(self, base_url: str = "http://pedidos:8000", timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def has_pedidos(self, producto_id: uuid.UUID) -> bool:
        query = urllib.parse.urlencode({"producto_id": str(producto_id), "limit": 1})
        url = f"{self.base_url}/pedidos?{query}"
        # Sin proxies del entorno: la llamada es siempre interna al clúster.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(url, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise PedidosUnavailableError(f"Estado inesperado {response.status}.")
                data = json.loads(response.read())
        except PedidosUnavailableError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("Fallo al consultar pedidos: %s", type(exc).__name__)
            raise PedidosUnavailableError("No se pudo consultar el servicio de pedidos.") from exc

        total = data.get("total") if isinstance(data, dict) else None
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise PedidosUnavailableError("Respuesta de pedidos no cumple el contrato.")
        return total > 0
