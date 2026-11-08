# Panadería — Productos y Pedidos

Backend para gestionar los productos de una panadería y los pedidos de sus clientes mediante dos microservicios independientes. El objetivo es ofrecer operaciones de creación, consulta, actualización y eliminación, con persistencia en PostgreSQL y comunicación HTTP entre servicios. El diseño contempla un producto por pedido y la conservación del nombre y precio históricos del producto seleccionado.

## Stack

| Área | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 |
| API y servidor | FastAPI y Uvicorn |
| Validación y configuración | Pydantic 2 y pydantic-settings |
| Persistencia | PostgreSQL 16, SQLAlchemy 2 síncrono y psycopg 3 |
| Migraciones | Alembic, independiente por servicio |
| Cliente HTTP y pruebas HTTP | HTTPX |
| Pruebas y calidad | pytest y Ruff |
| Entorno y dependencias | uv, `.venv`, `pyproject.toml` y `uv.lock` por servicio |
| Contenedores y orquestación | Dockerfile multi-etapa independiente (`appuser:10001`) y Docker Compose |
| Base de datos local | PostgreSQL 16 con volumen persistente (`postgres_data`) |

## Estructura del proyecto

```text
.
├── README.md
├── AGENTS.md
├── .gitignore
├── .env.example
├── requirements.txt              # Referencia histórica; no es un lockfile
├── compose.yaml                   # Orquestación de PostgreSQL, microservicios y migraciones
├── scripts/
│   └── test_persistence.sh       # Validación de persistencia tras reinicio de PostgreSQL
├── deploy/
│   └── postgres/
│       └── 01-create-databases.sh  # Bases y usuarios separados
├── services/
│   ├── productos/
│   │   ├── Dockerfile             # Multi-stage build con uv y usuario no-root appuser (10001)
│   │   ├── .dockerignore
│   │   ├── .python-version
│   │   ├── .env.example
│   │   ├── uv.lock
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 20261106_0001_create_productos_table.py
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # Aplicación, manejadores de error y endpoints de salud
│   │   │   ├── config.py          # Variables de entorno
│   │   │   ├── database.py        # Engine, Base y sesiones
│   │   │   ├── models.py          # Modelo SQLAlchemy de Producto
│   │   │   ├── schemas.py         # Esquemas Pydantic v2 y validaciones
│   │   │   ├── repository.py      # Acceso a datos y consultas
│   │   │   ├── service.py         # Lógica de dominio y reglas de negocio
│   │   │   └── routes.py          # Rutas HTTP /productos
│   │   └── tests/
│   │       ├── test_health.py
│   │       ├── test_productos_api.py
│   │       ├── test_postgres.py
│   │       └── test_runtime.py
│   └── pedidos/
│       ├── Dockerfile             # Multi-stage build con uv y usuario no-root appuser (10001)
│       ├── .dockerignore
│       ├── .python-version
│       ├── .env.example
│       ├── uv.lock
│       ├── pyproject.toml
│       ├── alembic.ini
│       ├── migrations/
│       │   ├── env.py
│       │   ├── script.py.mako
│       │   └── versions/
│       │       └── 20261106_0001_create_pedidos_table.py
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py            # Aplicación, manejadores de error y endpoints de salud
│       │   ├── config.py          # Variables de entorno
│       │   ├── database.py        # Engine, Base y sesiones
│       │   ├── models.py          # Modelo SQLAlchemy de Pedido
│       │   ├── schemas.py         # Esquemas Pydantic v2 y validaciones
│       │   ├── repository.py      # Acceso a datos y consultas
│       │   ├── service.py         # Lógica de dominio y reglas de precio histórico
│       │   ├── routes.py          # Rutas HTTP /pedidos
│       │   └── clients/
│       │       ├── __init__.py
│       │       └── productos.py   # Cliente HTTP de Productos con timeout configurable
│       └── tests/
│           ├── test_health.py
│           ├── test_productos_client.py
│           ├── test_pedidos_api.py
│           ├── test_postgres.py
│           └── test_runtime.py
├── tests/
│   └── integration/
│       ├── __init__.py
│       └── test_e2e_flow.py       # Flujo integrado end-to-end entre microservicios
└── docs/
    ├── arquitectura.md
    ├── contrato-api.md
    ├── desarrollo-local.md
    └── pruebas.md
```

`.venv` se genera localmente y está excluido de Git. Para el desarrollo local, PostgreSQL se ejecuta con Compose y las APIs en el host.

## Requisitos

- Python 3.12 y uv disponibles en la terminal.
- Acceso al registro de paquetes para instalar las dependencias.
- Docker Engine o Docker Desktop con Docker Compose y acceso a la imagen `postgres:16`, para levantar la base local. En WSL, habilitar la integración de la distribución con Docker Desktop.
- Puertos locales 8001 y 8002 disponibles para las APIs y 5432 para PostgreSQL; el de PostgreSQL puede cambiarse mediante `POSTGRES_PORT`.
- Una terminal Bash, como Linux, macOS o WSL, para los comandos siguientes.

Las pruebas HTTP simuladas no requieren Docker ni PostgreSQL. Para readiness exitoso, migraciones online y pruebas de integración se necesita PostgreSQL 16 con las dos bases y usuarios configurados.

## Preparar el entorno

Cada servicio tiene su propio entorno y lockfile. Desde la raíz:

```bash
uv sync --frozen --project services/productos
uv sync --frozen --project services/pedidos
```

Los comandos siguientes usan el intérprete de cada servicio. No requieren activar el antiguo entorno común. `requirements.txt` se conserva como referencia; no se usa para la instalación reproducible.

## Configurar y levantar PostgreSQL

Copiar las plantillas solo si aún no existen los archivos `.env`, para conservar cualquier configuración local:

```bash
cp -n .env.example .env
cp -n services/productos/.env.example services/productos/.env
cp -n services/pedidos/.env.example services/pedidos/.env
```

Editar el `.env` de la raíz y reemplazar `POSTGRES_PASSWORD`, `PRODUCTOS_DB_PASSWORD` y `PEDIDOS_DB_PASSWORD` por valores locales distintos. Luego configurar `DATABASE_URL` en el `.env` de cada servicio con la contraseña correspondiente:

| Servicio | Usuario | Base | Host desde las APIs locales |
| --- | --- | --- | --- |
| Productos | `productos_app` | `productos_db` | `localhost` |
| Pedidos | `pedidos_app` | `pedidos_db` | `localhost` |

El formato de la URL es `postgresql+psycopg://USUARIO:CONTRASENA@localhost:5432/BASE`. Codificar los caracteres reservados de las credenciales para URL y ajustar el puerto si se cambia `POSTGRES_PORT`. No versionar los `.env` ni usar el usuario administrador en las APIs.

Ambos servicios permiten configurar `LOG_LEVEL` y `DB_CONNECT_TIMEOUT_SECONDS`. Consulta las variables de entorno en la [guía de desarrollo local](docs/desarrollo-local.md).

## Ejecución con Docker Compose (Stack Completo)

Docker Compose orquesta PostgreSQL, las migraciones bajo demanda y ambos microservicios construidos con Dockerfiles multi-etapa y usuario no-root `appuser` (UID 10001).

1. **Construir las imágenes de los microservicios**:
   ```bash
   docker compose build
   ```

2. **Levantar PostgreSQL con volumen persistente**:
   ```bash
   docker compose up -d postgres
   docker compose ps
   ```
   El script inicial `01-create-databases.sh` crea `productos_db` y `pedidos_db` con sus respectivos usuarios solo cuando el volumen está vacío. Los datos se conservan en el volumen `postgres_data`.

3. **Ejecutar migraciones como paso explícito**:
   Las migraciones de base de datos no se ejecutan dentro del ciclo de vida de los servidores web para evitar condiciones de carrera al escalar réplicas. Se ejecutan bajo demanda:
   ```bash
   docker compose run --rm productos-migrate
   docker compose run --rm pedidos-migrate
   ```
   *(Alternativamente: `docker compose --profile migration up productos-migrate pedidos-migrate`)*.

4. **Levantar los microservicios web**:
   ```bash
   docker compose up -d productos pedidos
   ```
   Ambos contenedores cuentan con comprobaciones de salud automáticas hacia `/health/ready` y se comunican entre sí mediante resolución DNS interna de Docker Compose (`http://productos:8000`).

5. **Verificar el flujo integrado end-to-end (E2E)**:
   ```bash
   python tests/integration/test_e2e_flow.py
   ```
   O mediante pytest:
   ```bash
   services/productos/.venv/bin/python -m pytest tests/integration/test_e2e_flow.py
   ```

6. **Comprobar la persistencia de datos tras reinicio**:
   ```bash
   ./scripts/test_persistence.sh
   ```

## Ejecución en el Host (Desarrollo Directo)

Si se desea depurar o desarrollar ejecutando Uvicorn directamente en el host (con PostgreSQL levantado en Docker o nativo):

En una terminal para Productos, desde la raíz:

```bash
cd services/productos
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

En otra terminal para Pedidos, desde la raíz:

```bash
cd services/pedidos
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

| Recurso | Productos | Pedidos |
| --- | --- | --- |
| Swagger UI | http://127.0.0.1:8001/docs | http://127.0.0.1:8002/docs |
| OpenAPI | http://127.0.0.1:8001/openapi.json | http://127.0.0.1:8002/openapi.json |
| Liveness | http://127.0.0.1:8001/health/live | http://127.0.0.1:8002/health/live |
| Readiness | http://127.0.0.1:8001/health/ready | http://127.0.0.1:8002/health/ready |

`/health/live` devuelve `200` con `{"status":"ok"}` si el proceso está operativo. `/health/ready` consulta la base propia y devuelve `200` con `{"status":"ready"}` o `503` si no está disponible. La salud de Pedidos no consulta Productos. Las aplicaciones no ejecutan migraciones durante el arranque.

## Ejecutar las pruebas

Desde la raíz:

```bash
services/productos/.venv/bin/ruff check services
services/productos/.venv/bin/ruff format --check services
```

Las pruebas de cada servicio se ejecutan por separado porque ambos usan un paquete local llamado `app`.

Productos, desde la raíz:

```bash
cd services/productos
.venv/bin/python -m pytest -m "not integration"
```

Pedidos, en otra terminal desde la raíz:

```bash
cd services/pedidos
.venv/bin/python -m pytest -m "not integration"
```

En Productos, estas pruebas cubren configuración, salud, OpenAPI, CRUD completo simulado con TestClient, validaciones estrictas (tipos, precio decimal, fechas UTC con Z, nombres y descripciones), paginación ordenada, actualizaciones parciales (PATCH con preservación y limpieza con null), eliminación y errores uniformes (422 invalid_value/extra_field/empty_patch, 404 not_found, 503 database_unavailable). En Pedidos cubren salud, configuración, OpenAPI, cliente HTTP de Productos con HTTPX y transportes simulados (éxito, inactivo, no encontrado, timeout, fallo de red, JSON corrupto), CRUD completo simulado de pedidos, cálculo decimal, reglas de conservación de precio/nombre histórico y rechazo de campos de escritura no permitidos.

### Integración con PostgreSQL

Con PostgreSQL levantado, definir `TEST_DATABASE_URL` en el entorno de la terminal mediante un mecanismo local seguro, usando la URL del usuario y base del servicio que se prueba. Esta variable no se carga automáticamente desde el `.env` de la aplicación. Desde cada directorio de servicio con su entorno independiente:

```bash
.venv/bin/python -m pytest -m integration
```

La prueba comprueba PostgreSQL 16, readiness, usuario/base, aislamiento respecto de la otra base, escritura y lectura de una tabla temporal y recuperación después de un error SQL. En ambos servicios comprueba además el ciclo de vida CRUD real en PostgreSQL (creación con tipos nativos UUID, NUMERIC y TIMESTAMPTZ, consulta individual, listado paginado ordenado, actualización parcial y eliminación física) y las migraciones Alembic de las tablas `productos` y `pedidos` con `alembic check` limpio (cero diferencias). Requieren `TEST_DATABASE_URL`; si no está definida, las pruebas se omiten. Usar bases locales dedicadas a desarrollo/pruebas, nunca producción.

Consulta los [resultados verificados y limitaciones](docs/pruebas.md) y la [guía de desarrollo local](docs/desarrollo-local.md).

## Apagado y Persistencia

Si se ejecutaron las APIs en el host, detenerlas con `Ctrl+C`. Para detener el stack de contenedores desde la raíz:

```bash
docker compose down
```

El volumen `postgres_data` se conserva intacto entre ejecuciones.

> [!CAUTION]
> **No utilizar `docker compose down -v` salvo que se desee restablecer la base de datos desde cero.**
> La opción `-v` o `--volumes` elimina el volumen persistente `postgres_data`, borrando permanentemente todas las tablas, usuarios y datos creados.

## Documentación y equipo

Desarrollado por **Grupo 4 — Power Rangers**.

- [Contrato de entidades y API](docs/contrato-api.md).
- [Arquitectura e integrantes de Grupo 4 — Power Rangers](docs/arquitectura.md).

