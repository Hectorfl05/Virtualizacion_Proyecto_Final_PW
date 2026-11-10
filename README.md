# Panadería — Productos y Pedidos

**Proyecto Final: Despliegue de una aplicación en la nube con Kubernetes e infraestructura como código**  
*Curso: Virtualización — Universidad Rafael Landívar — Segundo Semestre 2026*  
**Caso asignado:** #6 Panadería (Entidad A: **Productos**, Entidad B: **Pedidos**)  
**Equipo:** Grupo 4 — Power Rangers  

---

## Integrantes del Equipo

| Nombre | Carné | Rol / Responsabilidad |
| --- | --- | --- |
| Hector Flores | `1199923` | Backend, Arquitectura e Integración |
| Joaquin Choc | `1280423` | Backend, Infraestructura y Manifiestos K8s |
| Daniel Diaz | `1040023` | Backend, Modelos de Datos y Pruebas |
| Jose Enriquez | `1053223` | Backend, Migraciones y Contenedores |
| Sofia Singüenza | `1333123` | Backend, Validación y Documentación |

---

## Descripción del Proyecto

Sistema distribuido compuesto por dos microservicios desacoplados construidos en Python 3.12 con FastAPI y PostgreSQL 16:
* **Microservicio Productos**: Administra el catálogo de productos de la panadería (creación, listado paginado, consulta individual, actualización parcial y eliminación física).
* **Microservicio Pedidos**: Gestiona los pedidos de los clientes. Cada pedido contiene un producto y una cantidad. Consume al microservicio de Productos mediante HTTP para validar existencia y estado activo, congelando de manera inmutable el nombre y precio históricos en el momento de la compra.

### Stack Tecnológico

| Área | Tecnología |
| --- | --- |
| **Lenguaje** | Python 3.12 |
| **Framework Web** | FastAPI 0.115 + Uvicorn (ASGI) |
| **Validación y Configuración** | Pydantic 2 y pydantic-settings |
| **Persistencia** | PostgreSQL 16 con sesiones síncronas de SQLAlchemy 2 y driver psycopg 3 |
| **Migraciones** | Alembic (configuración e historial independiente por microservicio) |
| **Comunicación HTTP** | HTTPX con timeouts explícitos y manejo controlado de excepciones de red |
| **Pruebas y Calidad** | pytest, pytest-cov y Ruff (linter y formateador) |
| **Gestor de Paquetes** | uv con dependencias congeladas (`uv.lock`) |
| **Contenedores** | Dockerfiles multi-etapa independientes sobre `python:3.12-slim` con usuario no-root `appuser:appgroup` (10001:10001) |
| **Orquestación Local** | Docker Compose (`compose.yaml`) y Kubernetes (`deploy/k8s/`) |

---

## Estructura del Repositorio

```text
.
├── README.md                          # Presentación, integrantes y guía de despliegue
├── AGENTS.md                          # Guía técnica, estado del proyecto y contexto de desarrollo
├── .gitignore                         # Exclusión de secretos, entornos virtuales y binarios
├── .env.example                       # Plantilla de variables para Docker Compose
├── compose.yaml                       # Orquestación de contenedores y base de datos local
├── Proyecto FInal GKE.pdf            # Especificación y lista de cotejo oficial del proyecto
├── scripts/
│   ├── test_k8s_endpoints.sh          # Despliegue y validación automatizada en Kubernetes
│   ├── test_persistence.sh            # Comprobación de persistencia tras reinicio de PostgreSQL
│   ├── seed_database.py               # Semilla inicial con catálogo y carnés del equipo (A4)
│   └── start_port_forward.sh          # Script de soporte para túneles port-forward opcionales
├── deploy/
│   ├── postgres/
│   │   └── 01-create-databases.sh     # Script de inicialización de usuarios y bases lógicas
│   └── k8s/                           # Manifiestos declarativos de Kubernetes
│       ├── 00-namespace.yaml          # Namespace 'panaderia-grupo-4'
│       ├── 01-configmap.yaml          # Configuración no sensible y URLs DNS internas
│       ├── 02-secret.example.yaml     # Plantilla segura de credenciales (no versionadas)
│       ├── 03-postgres-pvc.yaml       # PersistentVolumeClaim de 10Gi para PostgreSQL
│       ├── 04-postgres.yaml           # Deployment (Recreate) y Service de PostgreSQL
│       ├── 05-migration-jobs.yaml     # Jobs batch/v1 para migraciones Alembic
│       ├── 06-productos.yaml          # Deployment (2 réplicas) y Service LoadBalancer
│       ├── 07-pedidos.yaml            # Deployment (2 réplicas) y Service LoadBalancer
│       ├── 08-frontend.yaml           # Deployment (2 réplicas) y Service LoadBalancer (Reverse Proxy)
│       ├── kustomization.yaml         # Configuración Kustomize unificada
│       └── apply.sh                   # Script de aplicación ordenado paso a paso
├── services/
│   ├── frontend/
│   │   ├── Dockerfile                 # Contenedor Nginx no-root (puerto 8080)
│   │   ├── nginx.conf                 # Configuración de Reverse Proxy (/api) y estáticos
│   │   └── public/                    # Archivos SPA (HTML, CSS y JS con carnés del equipo)
│   ├── productos/
│   │   ├── Dockerfile                 # Construcción multi-etapa con uv y usuario 10001
│   │   ├── pyproject.toml / uv.lock   # Dependencias congeladas
│   │   ├── alembic.ini / migrations/  # Historial de migraciones Alembic
│   │   ├── app/                       # Código fuente (models, schemas, repository, service, routes)
│   │   └── tests/                     # Pruebas unitarias y de integración
│   └── pedidos/
│       ├── Dockerfile                 # Construcción multi-etapa con uv y usuario 10001
│       ├── pyproject.toml / uv.lock   # Dependencias congeladas
│       ├── alembic.ini / migrations/  # Historial de migraciones Alembic
│       ├── app/                       # Código fuente y cliente HTTP de Productos
│       └── tests/                     # Pruebas unitarias, cliente HTTP y PostgreSQL
├── tests/
│   └── integration/
│       └── test_e2e_flow.py           # Suite de pruebas de integración end-to-end (E2E)
├── infra/
│   └── terraform/                     # Infraestructura como Código para Google Cloud
└── docs/
    ├── arquitectura.md                # Diagramas de arquitectura y flujo del sistema
    ├── contrato-api.md                # Contrato detallado de endpoints, payloads y errores
    ├── desarrollo-local.md            # Guía detallada para desarrolladores
    ├── kubernetes.md                  # Manual de objetos y despliegue en Kubernetes
    └── pruebas.md                     # Registro y comandos de verificación ejecutados
```

---

## Instrucciones de Despliegue y Ejecución

Tienes tres opciones para ejecutar el backend, según el propósito deseado:

### Opción 1: Despliegue en Kubernetes Local (Recomendado)

Esta opción despliega toda la arquitectura de pods, volúmenes y servicios en Kubernetes (por ejemplo, en Docker Desktop Kubernetes o Minikube):

1. **Requisitos previos**:
   * Tener Docker Desktop ejecutándose con Kubernetes habilitado (*Settings -> Kubernetes -> Enable Kubernetes*), o un clúster local como Minikube/Kind activo.
   * Asignar permisos de ejecución a los scripts (en Linux/WSL):
     ```bash
     chmod +x scripts/*.sh deploy/k8s/*.sh
     ```

2. **Ejecutar el script automatizado**:
   ```bash
   ./scripts/test_k8s_endpoints.sh
   ```
   El script realiza automáticamente todo el ciclo:
   - Compila las imágenes Docker locales de `productos` y `pedidos`.
   - Crea el namespace `panaderia-grupo-4` y el ConfigMap compartido.
   - Genera el Secret seguro `panaderia-secrets` si no existe.
   - Despliega PostgreSQL 16 y espera a que su PVC de 10Gi esté enlazado y listo.
   - Ejecuta los Jobs de migración Alembic (`productos-migration-job` y `pedidos-migration-job`) de forma aislada.
   - Despliega los microservicios con 2 réplicas cada uno y servicios `type: LoadBalancer`.
   - Ejecuta la suite de pruebas E2E contra los pods activos para certificar que todo funciona.

3. **Verificar el estado de los recursos en Kubernetes**:
   ```bash
   kubectl get all,pvc -n panaderia-grupo-4
   ```

4. **Acceso a los endpoints en el Host**:
   Al usar servicios `type: LoadBalancer`, los puertos se enlazan nativamente a `localhost`:
   * 🥐 **Swagger de Productos**: [http://localhost:8001/docs](http://localhost:8001/docs)
   * 📦 **Swagger de Pedidos**: [http://localhost:8002/docs](http://localhost:8002/docs)
   * 🩺 **Salud Productos**: [http://localhost:8001/health/live](http://localhost:8001/health/live)
   * 🩺 **Salud Pedidos**: [http://localhost:8002/health/live](http://localhost:8002/health/live)

5. **Prueba rápida desde la terminal**:
   * En Linux / WSL:
     ```bash
     curl -s http://localhost:8001/health/live
     curl -s http://localhost:8002/health/live
     ```
   * En Windows PowerShell:
     ```powershell
     curl.exe -s http://localhost:8001/health/live
     irm http://localhost:8001/health/live
     ```

6. **Detener o limpiar el entorno de Kubernetes**:
   Si deseas eliminar todos los pods, servicios y datos de prueba:
   ```bash
   kubectl delete namespace panaderia-grupo-4
   ```

---

### Opción 2: Ejecución con Docker Compose

Ideal para desarrollo local rápido con contenedores:

1. **Configurar variables de entorno iniciales**:
   ```bash
   cp -n .env.example .env
   ```
2. **Construir y levantar la base de datos**:
   ```bash
   docker compose build
   docker compose up -d postgres
   ```
3. **Ejecutar las migraciones de base de datos**:
   ```bash
   docker compose run --rm productos-migrate
   docker compose run --rm pedidos-migrate
   ```
4. **Levantar los microservicios web**:
   ```bash
   docker compose up -d productos pedidos
   ```
5. **Comprobar la persistencia tras reinicio**:
   ```bash
   ./scripts/test_persistence.sh
   ```
6. **Apagar el stack conservando datos**:
   ```bash
   docker compose down
   ```
   *(Nota: Nunca utilices `docker compose down -v` a menos que desees eliminar permanentemente el volumen de datos de PostgreSQL).*

---

### Opción 3: Ejecución Nativa en el Host (Python + uv)

Para depurar código fuente directamente en tu entorno local:

1. **Sincronizar dependencias congeladas**:
   ```bash
   uv sync --frozen --project services/productos
   uv sync --frozen --project services/pedidos
   ```
2. **Configurar los archivos `.env`**:
   ```bash
   cp -n services/productos/.env.example services/productos/.env
   cp -n services/pedidos/.env.example services/pedidos/.env
   ```
   *(Configura las contraseñas correspondientes en cada archivo).*
3. **Iniciar el microservicio de Productos (puerto 8001)**:
   ```bash
   cd services/productos
   .venv/bin/python -m alembic upgrade head
   .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
   ```
4. **Iniciar el microservicio de Pedidos (puerto 8002)**:
   ```bash
   cd services/pedidos
   .venv/bin/python -m alembic upgrade head
   .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
   ```

---

## Verificación y Pruebas Automatizadas

El proyecto cuenta con suites exhaustivas de pruebas unitarias, de integración con PostgreSQL real y pruebas de ciclo de vida end-to-end:

### 1. Pruebas Unitarias y de Simulación HTTP
Ejecutar sin necesidad de base de datos activa:

```bash
# Productos (56 pruebas: validaciones, esquemas, CRUD en memoria, endpoints)
(cd services/productos && uv run pytest tests -m "not integration")

# Pedidos (52 pruebas: cliente HTTP, timeouts, errores controlados, cálculo decimal)
(cd services/pedidos && uv run pytest tests -m "not integration")
```

### 2. Pruebas de Integración End-to-End (E2E)
Con los servicios levantados en Kubernetes o Compose:

```bash
python3 tests/integration/test_e2e_flow.py
```
Esta prueba ejecuta de forma secuencial:
* Verificación de endpoints de salud (`/health/live` y `/health/ready`).
* Creación de un producto con precio decimal.
* Creación de un pedido asociado verificando cálculo financiero exacto (`Decimal`).
* Consulta del pedido y verificación de preservación histórica.
* Modificación y desactivación del producto, comprobando que pedidos anteriores no se alteran y que nuevos pedidos sobre productos inactivos se rechazan con código 422 (`product_inactive`).
* Eliminación física controlada de registros.

### 3. Calidad de Código con Ruff
```bash
(cd services/productos && uv run ruff check . && uv run ruff format --check .)
(cd services/pedidos && uv run ruff check . && uv run ruff format --check .)
```

### 4. Semilla de Datos y Registro de Carnés (Criterio A4)
Para poblar la base de datos con el catálogo comercial inicial y registrar los 5 integrantes del equipo con sus carnés en la base de datos:
```bash
python3 scripts/seed_database.py
```
*(Nota: El script es idempotente; si los registros ya existen, los reutiliza sin duplicarlos).*

---

## Documentación Técnica Adicional

* 📐 [Arquitectura del Sistema y Diagramas](docs/arquitectura.md)
* 📋 [Contrato de Endpoints, Payloads y Errores de API](docs/contrato-api.md)
* ☸️ [Guía y Manifiestos de Kubernetes](docs/kubernetes.md)
* 💻 [Guía de Desarrollo Local y Variables de Entorno](docs/desarrollo-local.md)
* 🧪 [Registro Detallado de Pruebas y Comandos](docs/pruebas.md)
