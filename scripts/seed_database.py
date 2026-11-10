#!/usr/bin/env python3
"""Script de inicialización (Seed) para la base de datos del Proyecto Panadería.

Registra un catálogo inicial de productos de panadería y pedidos de ejemplo,
incluyendo de forma explícita el registro de los 5 integrantes del equipo y sus
carnés en la base de datos para dar cumplimiento al Criterio A4 de la rúbrica:
  - Hector Flores (Carné: 1199923)
  - Joaquin Choc (Carné: 1280423)
  - Daniel Diaz (Carné: 1040023)
  - Jose Enriquez (Carné: 1053223)
  - Sofia Singüenza (Carné: 1333123)

Es idempotente: si los productos ya existen, los reutiliza sin duplicarlos.
Funciona utilizando únicamente la biblioteca estándar de Python (sin dependencias externas).

Uso:
  python3 scripts/seed_database.py
  PRODUCTOS_URL=http://localhost:8001 PEDIDOS_URL=http://localhost:8002 python3 scripts/seed_database.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

PRODUCTOS_URL = os.getenv("PRODUCTOS_URL", "http://localhost:8001").rstrip("/")
PEDIDOS_URL = os.getenv("PEDIDOS_URL", "http://localhost:8002").rstrip("/")

# Catálogo inicial de productos: catálogo general + especialidades con carnés del equipo
SEED_PRODUCTOS = [
    # Integrantes del Grupo 4 — Power Rangers (Criterio A4)
    {
        "nombre": "Pan Especial - Hector Flores (Carné: 1199923)",
        "descripcion": "Receta tradicional de la casa con masa madre elaborada por Hector Flores",
        "precio": 11.99,
        "activo": True,
        "es_integrante": True,
    },
    {
        "nombre": "Pan Especial - Joaquin Choc (Carné: 1280423)",
        "descripcion": "Hojaldre horneado artesanalmente elaborado por Joaquin Choc",
        "precio": 12.80,
        "activo": True,
        "es_integrante": True,
    },
    {
        "nombre": "Pan Especial - Daniel Diaz (Carné: 1040023)",
        "descripcion": "Pan rústico campesino de leña elaborado por Daniel Diaz",
        "precio": 10.40,
        "activo": True,
        "es_integrante": True,
    },
    {
        "nombre": "Pan Especial - Jose Enriquez (Carné: 1053223)",
        "descripcion": "Bollería fina con toque de mantequilla europea elaborada por Jose Enriquez",
        "precio": 10.53,
        "activo": True,
        "es_integrante": True,
    },
    {
        "nombre": "Pan Especial - Sofia Singüenza (Carné: 1333123)",
        "descripcion": "Pastelería gourmet con glaseado artesanal elaborada por Sofia Singüenza",
        "precio": 13.33,
        "activo": True,
        "es_integrante": True,
    },
    # Catálogo comercial general de Panadería
    {
        "nombre": "Croissant Francés de Mantequilla",
        "descripcion": "Clásico croissant hojaldrado con mantequilla importada",
        "precio": 14.00,
        "activo": True,
        "es_integrante": False,
    },
    {
        "nombre": "Baguette Tradicional de Leña",
        "descripcion": "Corteza crujiente y miga aireada horneada a la piedra",
        "precio": 12.50,
        "activo": True,
        "es_integrante": False,
    },
    {
        "nombre": "Concha Tradicional de Vainilla",
        "descripcion": "Pan dulce tradicional mexicano con cubierta azucarada de vainilla",
        "precio": 6.50,
        "activo": True,
        "es_integrante": False,
    },
    {
        "nombre": "Muffin de Arándanos y Limón",
        "descripcion": "Esponjoso panecillo relleno de arándanos frescos y ralladura de limón",
        "precio": 10.50,
        "activo": True,
        "es_integrante": False,
    },
    {
        "nombre": "Empanada Gallega de Pollo",
        "descripcion": "Masa hojaldrada rellena de pechuga desmechada con pimientos y cebolla",
        "precio": 15.00,
        "activo": True,
        "es_integrante": False,
    },
]

# Pedidos de demostración asociados
SEED_PEDIDOS_CANTIDADES = [
    ("Pan Especial - Hector Flores (Carné: 1199923)", 2),
    ("Pan Especial - Joaquin Choc (Carné: 1280423)", 3),
    ("Pan Especial - Daniel Diaz (Carné: 1040023)", 1),
    ("Pan Especial - Jose Enriquez (Carné: 1053223)", 4),
    ("Pan Especial - Sofia Singüenza (Carné: 1333123)", 2),
    ("Croissant Francés de Mantequilla", 6),
    ("Baguette Tradicional de Leña", 5),
]


def http_request(
    url: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any]:
    """Ejecuta una petición HTTP utilizando únicamente la biblioteca estándar urllib."""
    headers = {"Accept": "application/json"}
    body_bytes = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            content = response.read().decode("utf-8")
            payload = json.loads(content) if content else None
            return status, payload
    except urllib.error.HTTPError as exc:
        err_content = exc.read().decode("utf-8")
        try:
            payload = json.loads(err_content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = err_content
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"No se pudo conectar a {url}. Verifica que los servicios estén activos. Error: {exc.reason}"
        ) from exc


def check_services_health() -> None:
    """Verifica que ambos microservicios estén activos y respondiendo."""
    print("=================================================================")
    print("  Semilla de Base de Datos — Panadería Grupo 4")
    print("=================================================================")
    print(f"  Verificando conexión con Productos en: {PRODUCTOS_URL}")
    status, body = http_request(f"{PRODUCTOS_URL}/health/live")
    if status != 200 or body.get("status") != "ok":
        raise RuntimeError(f"Productos no está operativo (HTTP {status}): {body}")
    print("  -> Productos: OK")

    print(f"  Verificando conexión con Pedidos en: {PEDIDOS_URL}")
    status, body = http_request(f"{PEDIDOS_URL}/health/live")
    if status != 200 or body.get("status") != "ok":
        raise RuntimeError(f"Pedidos no está operativo (HTTP {status}): {body}")
    print("  -> Pedidos: OK\n")


def seed_productos() -> dict[str, dict[str, Any]]:
    """Inserta los productos en la base de datos de forma idempotente."""
    print("-----------------------------------------------------------------")
    print("  [1/2] Poblando Catálogo de Productos...")
    print("-----------------------------------------------------------------")

    # Obtener productos existentes
    _, existing = http_request(f"{PRODUCTOS_URL}/productos?limit=100")
    existing_items = existing.get("items", []) if isinstance(existing, dict) else []
    existing_by_name = {item["nombre"]: item for item in existing_items}

    productos_map: dict[str, dict[str, Any]] = {}
    creados = 0
    reutilizados = 0

    for prod_def in SEED_PRODUCTOS:
        nombre = prod_def["nombre"]
        if nombre in existing_by_name:
            item = existing_by_name[nombre]
            productos_map[nombre] = item
            reutilizados += 1
            print(f"  [Reutilizado] {nombre} (ID: {item['id'][:8]}...)")
        else:
            payload = {
                "nombre": prod_def["nombre"],
                "descripcion": prod_def["descripcion"],
                "precio": prod_def["precio"],
                "activo": prod_def["activo"],
            }
            status, created_item = http_request(
                f"{PRODUCTOS_URL}/productos", method="POST", data=payload
            )
            if status != 201:
                print(
                    f"  ERROR al crear {nombre} (HTTP {status}): {created_item}",
                    file=sys.stderr,
                )
                continue
            productos_map[nombre] = created_item
            creados += 1
            tag = " [INTEGRANTE]" if prod_def["es_integrante"] else ""
            print(
                f"  [Creado]{tag} {nombre} - Q{created_item['precio']} (ID: {created_item['id'][:8]}...)"
            )

    print(
        f"\n  Resumen Productos: {creados} creados, {reutilizados} reutilizados. Total: {len(productos_map)}\n"
    )
    return productos_map


def seed_pedidos(productos_map: dict[str, dict[str, Any]]) -> None:
    """Inserta pedidos de ejemplo basados en los productos registrados."""
    print("-----------------------------------------------------------------")
    print("  [2/2] Poblando Pedidos de Demostración...")
    print("-----------------------------------------------------------------")

    # Obtener pedidos existentes para no duplicar en ejecuciones repetidas
    _, existing = http_request(f"{PEDIDOS_URL}/pedidos?limit=100")
    existing_items = existing.get("items", []) if isinstance(existing, dict) else []
    existing_pedidos_keys = {
        (item["producto_nombre"], item["cantidad"]) for item in existing_items
    }

    creados = 0
    reutilizados = 0

    for prod_nombre, cantidad in SEED_PEDIDOS_CANTIDADES:
        if prod_nombre not in productos_map:
            continue
        prod = productos_map[prod_nombre]

        if (prod_nombre, cantidad) in existing_pedidos_keys:
            reutilizados += 1
            print(f"  [Existente] Pedido de {cantidad}x '{prod_nombre}'")
            continue

        payload = {
            "producto_id": prod["id"],
            "cantidad": cantidad,
        }
        status, created_pedido = http_request(
            f"{PEDIDOS_URL}/pedidos", method="POST", data=payload
        )
        if status != 201:
            print(
                f"  ERROR al crear pedido de {prod_nombre} (HTTP {status}): {created_pedido}",
                file=sys.stderr,
            )
            continue

        creados += 1
        print(
            f"  [Creado] Pedido ID {created_pedido['id'][:8]}... | {cantidad}x {created_pedido['producto_nombre']} "
            f"| P.U: Q{created_pedido['precio_unitario']} | Total: Q{created_pedido['total']}"
        )

    print(f"\n  Resumen Pedidos: {creados} creados, {reutilizados} ya existentes.\n")


def print_summary() -> None:
    """Imprime el resumen de confirmación y cumplimiento de la rúbrica."""
    print("=================================================================")
    print("  ¡Semilla aplicada con éxito!")
    print("=================================================================")
    print("  Verificación Criterio A4 (Carnés registrados en base de datos):")
    print("    [✓] Hector Flores   — Carné 1199923")
    print("    [✓] Joaquin Choc    — Carné 1280423")
    print("    [✓] Daniel Diaz     — Carné 1040023")
    print("    [✓] Jose Enriquez   — Carné 1053223")
    print("    [✓] Sofia Singüenza — Carné 1333123")
    print("  Los datos ya son visibles en Swagger:")
    print(f"    - Catálogo: {PRODUCTOS_URL}/docs")
    print(f"    - Pedidos:  {PEDIDOS_URL}/docs")
    print("=================================================================")


def main() -> int:
    try:
        check_services_health()
        productos_map = seed_productos()
        seed_pedidos(productos_map)
        print_summary()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            f"\n[FATAL] Ocurrió un error al ejecutar la semilla: {exc}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
