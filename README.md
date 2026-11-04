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
| Entorno y dependencias | uv, `.venv`, `requerimientos.txt` y `pyproject.toml` por servicio |
| Base de datos local | Docker Compose con volumen persistente |

## Estructura del proyecto

```text
.
├── README.md
├── AGENTS.md
├── .gitignore
├── .env.example
├── requerimientos.txt
├── compose.yaml                   # PostgreSQL local
├── deploy/
│   └── postgres/
│       └── 01-create-databases.sh  # Bases y usuarios separados
├── services/
│   ├── productos/
│   │   ├── .python-version
│   │   ├── .env.example
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # Aplicación y endpoints de salud
│   │   │   ├── config.py          # Variables de entorno
│   │   │   └── database.py        # Engine, Base y sesiones
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   └── tests/
│   │       ├── test_health.py
│   │       └── test_postgres.py
│   └── pedidos/                   # Misma estructura independiente
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

Desde la raíz del repositorio:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install --python .venv/bin/python -r requerimientos.txt
uv pip check --python .venv/bin/python
```

Si el entorno ya existe, activarlo en cada nueva terminal antes de entrar al directorio de un servicio. Crear un entorno propio en cada máquina.

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

Desde la raíz:

```bash
docker compose up -d postgres
docker compose ps
```

El script inicial crea las dos bases y sus usuarios, con acceso separado, únicamente cuando el volumen está vacío. Cambiar las contraseñas del `.env` después de inicializarlo no cambia las almacenadas en PostgreSQL. Los datos se guardan en el volumen `postgres_data`.

## Levantar las APIs

En una terminal para Productos, desde la raíz:

```bash
source .venv/bin/activate
cd services/productos
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

En otra terminal para Pedidos, desde la raíz:

```bash
source .venv/bin/activate
cd services/pedidos
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

| Recurso | Productos | Pedidos |
| --- | --- | --- |
| Swagger UI | http://127.0.0.1:8001/docs | http://127.0.0.1:8002/docs |
| OpenAPI | http://127.0.0.1:8001/openapi.json | http://127.0.0.1:8002/openapi.json |
| Liveness | http://127.0.0.1:8001/health/live | http://127.0.0.1:8002/health/live |
| Readiness | http://127.0.0.1:8001/health/ready | http://127.0.0.1:8002/health/ready |

`/health/live` devuelve `200` con `{"status":"ok"}` si el proceso está operativo. `/health/ready` consulta la base propia y devuelve `200` con `{"status":"ready"}` o `503` si no está disponible. La salud de Pedidos no consulta Productos. Las aplicaciones no ejecutan migraciones durante el arranque.

## Ejecutar las pruebas

Desde la raíz, con el entorno virtual activado:

```bash
ruff check services
ruff format --check services
```

Las pruebas de cada servicio se ejecutan por separado porque ambos usan un paquete local llamado `app`.

Productos, desde la raíz:

```bash
source .venv/bin/activate
cd services/productos
python -m pytest -m "not integration"
```

Pedidos, en otra terminal desde la raíz:

```bash
source .venv/bin/activate
cd services/pedidos
python -m pytest -m "not integration"
```

Estas pruebas cubren configuración, liveness independiente de la base, readiness exitoso y fallido con engine simulado, errores sin exposición de credenciales y OpenAPI.

### Integración con PostgreSQL

Con PostgreSQL levantado, definir `TEST_DATABASE_URL` en el entorno de la terminal mediante un mecanismo local seguro, usando la URL del usuario y base del servicio que se prueba. Esta variable no se carga automáticamente desde el `.env` de la aplicación. Desde cada directorio de servicio y con `.venv` activado:

```bash
python -m pytest -m integration
```

La prueba comprueba PostgreSQL 16, readiness, usuario/base, aislamiento respecto de la otra base, escritura y lectura de una tabla temporal y recuperación después de un error SQL. Requiere `TEST_DATABASE_URL`; si no está definida, la prueba se omite.

## Apagado

Detener las APIs con Ctrl+C. Desde la raíz:

```bash
docker compose down
deactivate
```

El volumen se conserva. `docker compose down -v` elimina los datos y no forma parte del apagado habitual.

## Documentación y equipo

Desarrollado por **Grupo 4 — Power Rangers**.

- [Contrato de entidades y API](docs/contrato-api.md).
- [Arquitectura e integrantes de Grupo 4 — Power Rangers](docs/arquitectura.md).

