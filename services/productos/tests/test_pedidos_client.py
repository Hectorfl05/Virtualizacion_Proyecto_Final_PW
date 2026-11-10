import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app.clients.pedidos import PedidosClient, PedidosUnavailableError


class _Handler(BaseHTTPRequestHandler):
    status = 200
    body: bytes = b""
    delay = 0.0
    seen: list[str] = []

    def do_GET(self):  # noqa: N802
        type(self).seen.append(self.path)
        if type(self).delay:
            time.sleep(type(self).delay)
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.status, _Handler.body, _Handler.delay, _Handler.seen = 200, b"", 0.0, []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def _reply(status=200, payload=None, raw=None):
    _Handler.status = status
    _Handler.body = raw if raw is not None else json.dumps(payload).encode()


def test_true_when_orders_exist_and_query_is_correct(server):
    pid = uuid.uuid4()
    _reply(payload={"items": [{}], "total": 3, "limit": 1, "offset": 0})
    assert PedidosClient(server).has_pedidos(pid) is True
    parsed = urlparse(_Handler.seen[0])
    assert parsed.path == "/pedidos"
    assert parse_qs(parsed.query) == {"producto_id": [str(pid)], "limit": ["1"]}


def test_false_when_no_orders(server):
    _reply(payload={"items": [], "total": 0, "limit": 1, "offset": 0})
    assert PedidosClient(server).has_pedidos(uuid.uuid4()) is False


@pytest.mark.parametrize(
    "status,payload,raw",
    [
        (500, {"detail": "x"}, None),
        (404, {"detail": "x"}, None),
        (200, None, b"no es json"),
        (200, ["lista"], None),
        (200, {"items": []}, None),
        (200, {"total": "1"}, None),
        (200, {"total": True}, None),
        (200, {"total": -1}, None),
    ],
)
def test_bad_responses_raise_unavailable_never_false(server, status, payload, raw):
    # Ante la duda NO se debe permitir borrar: nunca devolver False por error.
    _reply(status, payload, raw)
    with pytest.raises(PedidosUnavailableError):
        PedidosClient(server).has_pedidos(uuid.uuid4())


def test_connection_refused_raises_unavailable():
    with pytest.raises(PedidosUnavailableError):
        PedidosClient("http://127.0.0.1:1", timeout_seconds=1).has_pedidos(uuid.uuid4())


def test_timeout_raises_unavailable(server):
    _reply(payload={"total": 0})
    _Handler.delay = 1.0
    with pytest.raises(PedidosUnavailableError):
        PedidosClient(server, timeout_seconds=0.2).has_pedidos(uuid.uuid4())
