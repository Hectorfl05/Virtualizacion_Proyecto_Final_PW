# Registro de verificación

## Fase 5 — 7 de noviembre de 2026

Fase 5 (Contenedores e integración local) implementada y verificada. Se desarrollaron Dockerfiles multi-etapa independientes para Productos y Pedidos con instalación de dependencias congeladas mediante `uv.lock` y ejecución bajo usuario no root (`appuser`, UID 10001), archivos `.dockerignore` específicos, orquestación completa en `compose.yaml` con volumen persistente y perfiles de migración desacoplados, suite de pruebas de integración end-to-end (`test_e2e_flow.py`), script de comprobación de persistencia (`scripts/test_persistence.sh`) y documentación completa de arranque, pruebas y apagado.

| Comprobación | Resultado observado |
| --- | --- |
| Validación sintáctica de `compose.yaml` | Cero errores; servicios `postgres`, `productos`, `pedidos`, `productos-migrate`, `pedidos-migrate` detectados y validados |
| `services/productos/.venv/bin/ruff check .` | Sin errores en los 41 archivos del repositorio |
| `services/productos/.venv/bin/ruff format --check .` | 41 archivos con formato correcto |
| Construcción y diseño de Dockerfiles | Multi-stage build con `python:3.12-slim` y `uv:0.5.15`; usuario `appuser:appgroup` (10001:10001); dependencias `--frozen --no-dev` |
| `.dockerignore` por servicio | Excluyen `.venv`, caches y tests locales; preservan `migrations/` y `alembic.ini` |
| Desacoplamiento de migraciones | Perfil `migration` con `alembic upgrade head`; las réplicas web Uvicorn no ejecutan migraciones al arrancar |
| Suite de integración end-to-end (`tests/integration/test_e2e_flow.py`) | Valida salud, creación de producto, creación de pedido con cálculo decimal y copias históricas, consulta, actualización de cantidad con conservación de precio histórico, modificación y desactivación del producto original, validación de rechazo (422) y eliminación física |
| Script de persistencia (`scripts/test_persistence.sh`) | Automatiza la inserción de datos, reinicio de PostgreSQL sin borrar volumen y verificación de integridad de datos en `postgres_data` |

### Alcance y consideraciones de la Fase 5

- **Aislamiento y no-root**: Ambos contenedores web se ejecutan estrictamente bajo el usuario de sistema `appuser` (UID 10001, GID 10001), eliminando riesgos de ejecución con privilegios de root en runtime.
- **Reproducibilidad**: Las imágenes se construyen exclusivamente contra `uv.lock` con la bandera `--frozen --no-dev`, garantizando hashes e instalaciones idénticas entre entornos locales y la nube.
- **Persistencia declarativa**: El volumen `postgres_data` aloja tanto `productos_db` como `pedidos_db`. Las instrucciones advierten enfáticamente que `docker compose down` preserva los datos y que `docker compose down -v` es destructivo.
- **Entorno Docker en WSL**: En la distribución WSL de desarrollo, Docker Desktop requiere la activación de la casilla de integración en *Settings $\rightarrow$ Resources $\rightarrow$ WSL Integration*. El diseño de los contenedores, scripts y manifiestos es completamente agnóstico y compatible con cualquier motor Docker Engine o Docker Desktop estándar.

---

Fase 4 (Pedidos) implementada y verificada con PostgreSQL 16.13 real y Python 3.12.13. Se desarrollaron el modelo SQLAlchemy `Pedido`, esquemas Pydantic v2 con validación estricta y formato decimal, cliente HTTP de Productos con HTTPX y timeout configurable, repositorio, servicio de dominio con reglas de conservación histórica y cálculo decimal, rutas HTTP `/pedidos`, migración Alembic `0001_create_pedidos` y suites de pruebas unitarias y de integración contra PostgreSQL real.

| Comprobación | Resultado observado |
| --- | --- |
| `.venv/bin/python -m pytest -m 'not integration'` desde Pedidos | 52 pruebas aprobadas; cubren cliente HTTP simulado con `MockTransport`, CRUD simulado con TestClient, validaciones de cantidad, rechazo de precio/total del cliente, actualización parcial histórica, errores 422 (`product_not_found`, `product_inactive`), 503 (`products_unavailable`, `database_unavailable`) y OpenAPI |
| `.venv/bin/python -m pytest -v` desde Pedidos con `TEST_DATABASE_URL` | 55 pruebas aprobadas (52 unitarias + 3 de integración con PostgreSQL 16.13 real), sin omisiones; 5.42 s |
| `.venv/bin/python -m pytest -m 'not integration'` desde Productos | 49 pruebas aprobadas; compatibilidad completa sin regresiones |
| `.venv/bin/python -m pytest -v` desde Productos con `TEST_DATABASE_URL` | 52 pruebas aprobadas con su base propia; 6.64 s |
| Total pruebas en ambas suites completas contra PostgreSQL 16.13 | **107 pruebas aprobadas**, 0 fallos, 0 omisiones |
| `services/productos/.venv/bin/ruff check services` | Sin errores en los 33 archivos del backend |
| `services/productos/.venv/bin/ruff format --check services` | 33 archivos con formato correcto |
| `sh -n deploy/postgres/01-create-databases.sh` | Sin errores de sintaxis |
| `git diff --check` | Sin errores |

### Alcance verificado de Pedidos

- **Modelo y persistencia**: tabla `pedidos` en `pedidos_db` con columnas `id` (UUID nativo), `producto_id` (UUID nativo), `producto_nombre` (VARCHAR 150), `cantidad` (INTEGER > 0), `precio_unitario` (NUMERIC 10,2), `total` (NUMERIC 10,2), `created_at` y `updated_at` (TIMESTAMP WITH TIME ZONE), e índices `ix_pedidos_created_at_id` e `ix_pedidos_producto_id`.
- **Migración Alembic**: revisión `0001_create_pedidos` verificada con `alembic upgrade head`, `alembic current` y `alembic check` contra PostgreSQL 16; `alembic check` confirma cero diferencias entre el modelo y la base de datos.
- **Cliente HTTP de Productos (`ProductosClient`)**:
  - Consulta `GET /productos/{id}` con timeout explícito configurable (`PRODUCTOS_TIMEOUT_SECONDS`, predeterminado 5 s).
  - Manejo de respuestas de dominio: producto inexistente (`404` $\rightarrow$ `ProductNotFoundError` / `422 product_not_found`) y producto inactivo (`activo=false` $\rightarrow$ `ProductInactiveError` / `422 product_inactive`).
  - Manejo de fallos de red y disponibilidad: timeout, error de conexión, respuestas HTTP de servidor o JSON corrupto $\rightarrow$ `ProductsUnavailableError` / `503 products_unavailable` sin filtrar credenciales ni URLs privadas.
- **Reglas de dominio y conservación histórica**:
  1. Creación (`POST /pedidos` -> 201): consulta el producto por HTTP, valida estado activo, toma precio y nombre actuales, calcula `total = Decimal(cantidad) * Decimal(precio_unitario)` y persiste. Rechaza precio o total enviados por el cliente (`422 extra_field`).
  2. Consulta y listado (`GET /pedidos/{id}`, `GET /pedidos` -> 200): utilizan exclusivamente los datos históricos persistidos en `pedidos_db` y **no consultan a Productos**.
  3. Modificación de solo cantidad (`PATCH /pedidos/{id}` -> 200): conserva el `precio_unitario` y `producto_nombre` históricos, recalcula el `total` y **no consulta a Productos** (funciona aunque Productos esté inactivo o el producto haya sido eliminado o desactivado).
  4. Cambio de producto (`PATCH /pedidos/{id}` con nuevo `producto_id`): valida el nuevo producto por HTTP, actualiza nombre y precio actuales y recalcula el `total`.
  5. Envío del mismo `producto_id`: no realiza llamada remota ni altera la copia histórica.
  6. Eliminación física (`DELETE /pedidos/{id}` -> 204 sin cuerpo): elimina el registro en base de datos; repeticiones devuelven 404 (`not_found`).
- **OpenAPI**: esquema generado documenta todas las rutas `/pedidos`, parámetros, esquemas de solicitud/respuesta y códigos de error.

---

## Fase 3 — 6 de noviembre de 2026

Fase 3 (Productos) implementada y verificada con PostgreSQL 16.13 real y Python 3.12.13. Se desarrollaron el modelo SQLAlchemy, esquemas Pydantic v2 con validaciones estrictas y formatos uniformes, repositorio, servicio, rutas HTTP y la primera migración de Alembic (`0001_create_productos`).

| Comprobación | Resultado observado |
| --- | --- |
| `.venv/bin/python -m pytest -m 'not integration'` desde Productos | 49 pruebas aprobadas; cubren CRUD simulado, validaciones de tipos estrictos, precios, fechas UTC en formato Z, paginación, ordenamiento, errores 422, 404, 503 y OpenAPI |
| `.venv/bin/python -m pytest -v` desde Productos con `TEST_DATABASE_URL` | 52 pruebas aprobadas (49 unitarias + 3 de integración con PostgreSQL 16.13 real), sin omisiones; 7.53 s |
| `.venv/bin/python -m pytest -m 'not integration'` desde Pedidos | 6 pruebas aprobadas (mantiene compatibilidad de Fase 2) |
| `.venv/bin/python -m pytest -v` desde Pedidos con `TEST_DATABASE_URL` | 8 pruebas aprobadas con su base propia |
| `services/productos/.venv/bin/ruff check services` | Sin errores en los 23 archivos del backend |
| `services/productos/.venv/bin/ruff format --check services` | 23 archivos con formato correcto |
| `sh -n deploy/postgres/01-create-databases.sh` | Sin errores de sintaxis |
| `git diff --check` | Sin errores |

### Alcance verificado de Productos

- **Modelo y persistencia**: tabla `productos` con columnas `id` (UUID nativo), `nombre` (VARCHAR 150), `descripcion` (VARCHAR 1000 opcional), `precio` (NUMERIC 10,2), `activo` (BOOLEAN con default true), `created_at` y `updated_at` (TIMESTAMP WITH TIME ZONE), e índice compuesto `ix_productos_created_at_id` en `(created_at, id)`.
- **Migración Alembic**: versión `0001_create_productos` verificada con `alembic upgrade head`, `alembic current` y `alembic check` contra PostgreSQL 16; `alembic check` confirma cero diferencias entre el modelo SQLAlchemy y el esquema de la base de datos.
- **Ciclo de vida CRUD real en PostgreSQL**:
  1. Creación (`POST /productos` -> 201) y verificación directa por SQL del registro persistido, comprobando tipos nativos, valores y timestamps UTC con sufijo `Z`.
  2. Consulta individual (`GET /productos/{id}` -> 200).
  3. Listado paginado (`GET /productos?limit=...&offset=...` -> 200) con conteo `total` y orden estable `created_at ASC, id ASC`.
  4. Actualización parcial (`PATCH /productos/{id}` -> 200) con conservación de campos no enviados, actualización de `updated_at`, preservación de `created_at` y limpieza explícita de `descripcion` al enviar `null`.
  5. Eliminación física (`DELETE /productos/{id}` -> 204 sin cuerpo) y confirmación por SQL de conteo 0.
  6. Idempotencia y recursos inexistentes: repetición de `DELETE` devuelve 404 (`not_found`), y `GET` posterior devuelve 404 (`not_found`).
- **Contrato de errores y validaciones**:
  - `422 invalid_value`: precios no positivos, números JSON en importes, más de dos decimales, notación científica, nombres vacíos o con solo espacios, nombres > 150 caracteres, descripciones > 1000 caracteres, booleanos inválidos, UUID inválido en path y paginación fuera de rango (`limit` fuera de 1..100, `offset` < 0).
  - `422 extra_field`: campos desconocidos o gestionados por el servidor (`id`, `created_at`, `updated_at`).
  - `422 empty_patch`: solicitudes PATCH con cuerpo vacío `{}`.
  - `404 not_found`: identificación de recurso inexistente con localización `["path", "id"]`.
  - `503 database_unavailable`: desconexión o fallo operativo de base de datos capturado uniformemente sin exponer trazas ni credenciales.
- **OpenAPI**: esquema generado incluye las operaciones POST, GET, PATCH y DELETE de `/productos` junto con `/health/live` y `/health/ready`.

---

## Fase 2 — 5 de noviembre de 2026

Fase 2 cerrada con PostgreSQL 16.13 real y Python 3.12.13. La verificación corresponde a la base ejecutable; los CRUD todavía no están implementados.

| Comprobación | Resultado observado |
| --- | --- |
| `uv lock --project services/productos` y equivalente para Pedidos | Dos lockfiles independientes, 34 paquetes resueltos por servicio |
| `uv sync --frozen --project services/productos` y equivalente para Pedidos | Entornos independientes creados; 31 dependencias instaladas por servicio |
| `.venv/bin/python -m pytest -m 'not integration'` desde cada servicio | 6 pruebas aprobadas por servicio; integración excluida expresamente |
| `.venv/bin/python -m pytest -v` desde Productos con `TEST_DATABASE_URL` | 8 aprobadas, sin omisiones; 11.99 s |
| Mismo comando desde Pedidos con su propia URL | 8 aprobadas, sin omisiones; 5.02 s |
| `services/productos/.venv/bin/ruff check services` | Sin errores |
| `services/productos/.venv/bin/ruff format --check services` | 16 archivos con formato correcto |
| `sh -n deploy/postgres/01-create-databases.sh` | Sin errores de sintaxis |
| `git diff --check` | Sin errores |

### Entorno de integración y alcance

Docker devolvió que no está disponible en esta distribución WSL. Para completar la verificación de PostgreSQL se descargó la distribución fuente oficial `postgresql-16.13.tar.bz2` desde `ftp.postgresql.org/pub/source/v16.13/` y se compiló únicamente en `/tmp`, sin instalar paquetes del sistema:

```bash
./configure --prefix=/tmp/panaderia-pg16 --without-readline --without-icu
make -j8
make install
```

Se inicializó una instancia dedicada en `/tmp/panaderia-fase2-pgdata-final` mediante `initdb --no-locale --encoding=UTF8 --auth-local=trust --auth-host=scram-sha-256 -U panaderia_admin`. El socket Unix de bootstrap quedó en un directorio privado (modo 0700); TCP escuchó solo en `127.0.0.1:55432`. Se ejecutó el script real `deploy/postgres/01-create-databases.sh` con contraseñas aleatorias suministradas en memoria, sin versionarlas ni imprimirlas. Las APIs conectaron por TCP con SCRAM usando `productos_app/productos_db` y `pedidos_app/pedidos_db`.

Un script efímero de ejecución (`/tmp/panaderia_verify.py`) inició la instancia, ejecutó la inicialización y las suites anteriores con sus respectivas `TEST_DATABASE_URL`, y detuvo PostgreSQL con `pg_ctl -m fast -w stop` en un bloque `finally`. La ejecución final terminó con código 0 y `server stopped`. Este script no es un requisito del repositorio: para reproducir las suites usar PostgreSQL 16 propio o Compose y los comandos del README.

Las pruebas reales comprobaron:

- Versión 16, identidad de usuario/base y ausencia de permiso CONNECT a la base del otro servicio.
- Escritura y lectura SQL en tabla temporal y recuperación tras una consulta fallida.
- Readiness contra la base propia; liveness independiente.
- `alembic upgrade head`, `alembic current` y `alembic check` por servicio; presencia de `alembic_version`. Sin revisiones de dominio todavía, `current` no lista revisiones y no se crean tablas CRUD.
- Arranque de Uvicorn en puerto local dinámico, HTTP 200 y cuerpos de liveness/readiness, OpenAPI y logs de inicio/cierre, con terminación controlada por SIGTERM.

### Incidencias y límites

La primera instancia temporal se inicializó sin indicar UTF-8; se descartó para esta verificación porque SQL_ASCII provocó fallos de integración. Se repitió con UTF-8. La primera aserción de cierre esperaba código 0, pero Uvicorn completa el lifespan y vuelve a emitir SIGTERM: se corrigió la prueba para aceptar también `-SIGTERM`, conservando las aserciones de logs de cierre. Después pasaron ambas suites completas.

TestClient se bloqueó dentro del sandbox; las suites se ejecutaron con autorización fuera de él. Starlette emite una advertencia de deprecación por HTTPX; no hubo pruebas fallidas ni omitidas en la ejecución final.

No se verificaron Docker Compose, contenedores de APIs, persistencia tras reinicio, CRUD, comunicación entre microservicios ni infraestructura GKE. El volumen de Compose y la persistencia del flujo de negocio corresponden a Fase 5; las pruebas temporales de escritura no los sustituyen. No se afirma terminado el backend ni el proyecto académico completo.
