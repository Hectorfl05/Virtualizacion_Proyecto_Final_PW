# Desarrollo Local y Contenedores

Esta guía describe el entorno de desarrollo local, la arquitectura de contenedores con Docker Compose y los procedimientos de migración, prueba y persistencia de datos del proyecto Panadería (Grupo 4 — Power Rangers).

---

## 1. Modos de Ejecución Local

El proyecto soporta dos modos de ejecución local:
1. **Modo Contenedores (Docker Compose - Recomendado)**: PostgreSQL, ambos microservicios y migraciones se ejecutan en contenedores Docker aislados, comunicados mediante DNS interno y con volumen persistente.
2. **Modo Directo en Host (Python + Uvicorn)**: PostgreSQL se ejecuta en Docker o como servicio nativo, mientras que las APIs se ejecutan en terminales locales usando los entornos virtuales de `services/productos/.venv` y `services/pedidos/.venv`.

---

## 2. Variables de Entorno

| Variable | Alcance | Descripción / Valor predeterminado |
| --- | --- | --- |
| `DATABASE_URL` | Cada microservicio | Cadena de conexión obligatoria: `postgresql+psycopg://USUARIO:PASSWORD@HOST:PUERTO/BASE`. |
| `DB_CONNECT_TIMEOUT_SECONDS` | Cada microservicio | Timeout para la conexión con PostgreSQL (por defecto `3`, rango 1–30 s). |
| `LOG_LEVEL` | Cada microservicio | Nivel de bitácora (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; por defecto `INFO`). |
| `PRODUCTOS_BASE_URL` | Pedidos | URL del microservicio de Productos (`http://productos:8000` en Compose; `http://localhost:8001` en host). |
| `PRODUCTOS_TIMEOUT_SECONDS` | Pedidos | Timeout HTTP para consultas a Productos (por defecto `5.0` s). |
| `TEST_DATABASE_URL` | Pruebas de integración | URL síncrona exclusiva para `pytest -m integration`. No se carga desde `.env`. |

> [!IMPORTANT]
> Nunca imprimir variables de conexión ni versionar archivos `.env`. Las plantillas `.env.example` en la raíz y en cada servicio contienen marcadores que deben completarse localmente.

---

## 3. Arquitectura de Contenedores (Docker)

Ambos microservicios cuentan con su propio `Dockerfile` y `.dockerignore` independientes:

- **Multi-stage build**:
  - *Etapa 1 (`builder`)*: Imagen base `python:3.12-slim` con el binario de `uv` (`0.5.15`). Copia exclusivamente `pyproject.toml` y `uv.lock` e instala dependencias con `uv sync --frozen --no-dev --no-install-project`. Luego copia el código de la aplicación y ejecuta `uv sync --frozen --no-dev` pre-compilando bytecode (`UV_COMPILE_BYTECODE=1`).
  - *Etapa 2 (`runner`)*: Imagen limpia `python:3.12-slim`. Se crea el usuario de sistema no privilegiado `appuser:appgroup` con `UID=10001` y `GID=10001`. Se copia el directorio `/app` con los permisos correspondientes.
- **Seguridad**:
  - La aplicación corre estrictamente bajo el usuario no root `appuser`.
  - No se incluyen herramientas de compilación ni caches de desarrollo en la imagen final.
- **Entrypoint y puertos**:
  - Ambos contenedores exponen el puerto `8000` internamente.
  - El comando predeterminado es `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

---

## 4. Orquestación con Docker Compose (`compose.yaml`)

El archivo [compose.yaml](../compose.yaml) coordina los siguientes servicios en una red compartida con resolución DNS automática:

| Servicio Compose | Imagen / Build Context | Puerto Host | Puerto Contenedor | Propósito |
| --- | --- | --- | --- | --- |
| `postgres` | `postgres:16` | `5432` | `5432` | Motor PostgreSQL con dos bases (`productos_db` y `pedidos_db`) y volumen `postgres_data`. |
| `productos-migrate` | `./services/productos` (perfil `migration`) | N/A | N/A | Ejecuta `alembic upgrade head` para Productos y finaliza. |
| `pedidos-migrate` | `./services/pedidos` (perfil `migration`) | N/A | N/A | Ejecuta `alembic upgrade head` para Pedidos y finaliza. |
| `productos` | `./services/productos` | `8001` | `8000` | Microservicio de Productos. |
| `pedidos` | `./services/pedidos` | `8002` | `8000` | Microservicio de Pedidos. Conecta con Productos vía `http://productos:8000`. |
| `frontend` | `./services/frontend` | `8080` | `8080` | Interfaz Web y Reverse Proxy Nginx hacia `/api/productos` y `/api/pedidos`. |

### Comprobaciones de Salud (`healthcheck`)
- `postgres`: verifica operatividad mediante `pg_isready -U panaderia_admin -d postgres`.
- `productos` y `pedidos`: verifican operatividad hacia `/health/ready` mediante probe nativo en Python (`python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"`).
- `pedidos` declara `depends_on` condicional: espera a que tanto `postgres` como `productos` reporten estado `healthy`.

---

## 5. Ejecución de Migraciones Desacopladas

Para evitar conflictos de concurrencia y bloqueos de esquema al escalar réplicas en Kubernetes o Compose, los servidores web **no ejecutan migraciones al arrancar**.

Las migraciones se ejecutan explícitamente mediante los servicios de perfil `migration`:

```bash
# Ejecutar migraciones bajo demanda:
docker compose run --rm productos-migrate
docker compose run --rm pedidos-migrate

# O ejecutar ambas simultáneamente:
docker compose --profile migration up productos-migrate pedidos-migrate
```

---

## 6. Pruebas de Integración y Persistencia

### Prueba de Flujo End-to-End (E2E)
Con el stack levantado (`productos` en `8001` y `pedidos` en `8002`):

```bash
# Ejecución directa como script:
python tests/integration/test_e2e_flow.py

# O con pytest:
services/productos/.venv/bin/python -m pytest tests/integration/test_e2e_flow.py -v
```

Esta prueba valida el ciclo completo:
1. Comprobación de salud (`/health/live` y `/health/ready`) en ambos servicios.
2. Creación de un Producto vía `POST /productos`.
3. Creación de un Pedido vía `POST /pedidos` referenciando el producto, calculando total con precisión decimal y almacenando precio y nombre históricos.
4. Consulta individual y listado paginado.
5. Modificación de cantidad en Pedido vía `PATCH /pedidos/{id}` conservando el precio histórico.
6. Modificación y desactivación del Producto original vía `PATCH /productos/{id}`.
7. Comprobación de que el Pedido anterior conserva sus datos históricos inalterados.
8. Verificación de rechazo (`422 product_inactive`) al intentar crear un nuevo pedido con el producto inactivo.
9. Eliminación física de Pedido y Producto con confirmación de estado `404`.

### Prueba de Persistencia de Volumen tras Reinicio
Para comprobar que los datos persisten en el volumen `postgres_data` tras reiniciar PostgreSQL:

```bash
./scripts/test_persistence.sh
```

El script inserta datos de prueba, reinicia el contenedor de base de datos (`docker compose restart postgres`), espera la reconexión y valida que los registros persisten sin pérdida de información.

---

## 7. Apagado y Reglas de Persistencia

Para detener el stack de contenedores:

```bash
docker compose down
```

Este comando detiene y remueve los contenedores y la red de Compose, pero **conserva intacto el volumen `postgres_data`**.

> [!CAUTION]
> **Peligro de pérdida de datos con `-v` / `--volumes`**:
> El uso de `docker compose down -v` elimina permanentemente el volumen `postgres_data`, borrando todas las tablas, esquemas, usuarios y datos almacenados. Únicamente debe usarse cuando se desee reiniciar deliberadamente el entorno local desde cero.
