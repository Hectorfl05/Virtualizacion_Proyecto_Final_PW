# Guía para agentes: Backend y Proyecto Panadería

## Contexto y objetivo

Este repositorio corresponde al proyecto académico **«Despliegue de una aplicación en la nube con Kubernetes e infraestructura como código»**, del curso de Virtualización, Facultad de Ingeniería, Universidad Rafael Landívar, segundo semestre de 2026 (Catedrático: Guillermo Zepeda Selman).

El caso asignado al equipo es **Panadería** (Caso #6 del Anexo A del documento oficial):
- **Entidad A**: **Productos**, administrada por el microservicio de Productos.
- **Entidad B**: **Pedidos**, administrada por el microservicio de Pedidos.
- La entidad B referencia a la entidad A.

### Identificación del equipo e integrantes registrados

* **Equipo**: Grupo 4 — Power Rangers
* **Identificador para clúster y namespace**: `panaderia-grupo-4`
* **Integrantes**:
  1. Hector Flores — Carné `1199923`
  2. Joaquin Choc — Carné `1280423`
  3. Daniel Diaz — Carné `1040023`
  4. Jose Enriquez — Carné `1053223`
  5. Sofia Singüenza — Carné `1333123`

---

## Estado técnico actual: Backend Finalizado

> [!NOTE]
> **El backend en Python ha sido 100% completado, probado y validado.**
> No quedan pendientes de lógica de negocio, persistencia, validaciones de esquemas, migraciones de base de datos ni comunicación HTTP entre microservicios.

### Resumen de lo implementado y verificado

1. **Microservicio Productos (`services/productos/`)**:
   - CRUD completo implementado con FastAPI y SQLAlchemy 2.
   - Modelo `Producto` con UUID generado por el servidor, `nombre` (1-150 caracteres), `descripcion` (hasta 1000 caracteres o null), `precio` positivo (validado flexiblemente para aceptar `float`, `int`, `Decimal` o `str`, y persistido exactamente como `NUMERIC` en PostgreSQL), `activo` (booleano) y timestamps UTC con zona (`created_at`, `updated_at`).
   - Esquemas Pydantic v2 estrictos (`extra="forbid"`) con normalización automática a dos decimales y formato uniforme de errores (`422`, `404`, `503`).
   - Migración Alembic `0001_create_productos` con tipos nativos de PostgreSQL e índices.
   - 56 pruebas unitarias y de simulación HTTP aprobadas; pruebas de integración con PostgreSQL real aprobadas.

2. **Microservicio Pedidos (`services/pedidos/`)**:
   - CRUD completo implementado con FastAPI y SQLAlchemy 2.
   - Modelo `Pedido` con UUID de servidor, `producto_id` (referencia lógica), copia inmutable `producto_nombre`, `cantidad` (entero positivo), `precio_unitario` (copia histórica) y `total` calculado en servidor mediante `Decimal` (`cantidad × precio_unitario`).
   - Cliente HTTP de Productos (`app/clients/productos.py`) basado en HTTPX con timeout explícito configurable y manejo controlado de fallos (`422` con código `product_not_found` o `product_inactive`, y `503` con código `products_unavailable` si Productos no responde).
   - Reglas de negocio: actualización de cantidad recalcula el total conservando el precio histórico; cambio de producto valida el nuevo producto por HTTP; modificación o borrado de productos no altera pedidos pasados; eliminación física.
   - Migración Alembic `0001_create_pedidos` con tipos nativos e índices.
   - 52 pruebas unitarias y de simulación HTTP aprobadas; pruebas de integración con PostgreSQL real aprobadas.

3. **Contenedores y Orquestación Local (Fase 5)**:
   - Dockerfiles multi-etapa independientes para Productos y Pedidos basados en `python:3.12-slim` y `uv`, ejecutándose con usuario no-root `appuser:appgroup` (UID/GID 10001:10001) y dependencias congeladas (`uv.lock`).
   - Orquestación en `compose.yaml` con volumen persistente `postgres_data`, script de inicialización `01-create-databases.sh` (usuarios y bases lógicas separadas) y migraciones desacopladas bajo perfil `migration`.
   - Script de validación de persistencia ante reinicio: `scripts/test_persistence.sh`.
   - Suite de pruebas de ciclo de vida end-to-end: `tests/integration/test_e2e_flow.py`.

4. **Objetos y Manifiestos de Kubernetes (`deploy/k8s/`)**:
   - Namespace propio: `00-namespace.yaml` (`panaderia-grupo-4`).
   - Configuración: `01-configmap.yaml` con nombres DNS internos (`http://productos:8000`) y plantilla segura de secretos `02-secret.example.yaml` (excluyendo secretos reales en `.gitignore`).
   - Persistencia: `03-postgres-pvc.yaml` solicitando 10Gi con ReadWriteOnce.
   - Base de Datos: `04-postgres.yaml` (Deployment con estrategia `Recreate`, réplica 1, probes `pg_isready` y Service ClusterIP 5432).
   - Migraciones: `05-migration-jobs.yaml` (Jobs batch/v1 independientes para ejecutar `alembic upgrade head` antes del arranque web).
   - Microservicios: `06-productos.yaml` y `07-pedidos.yaml` (Deployments con 2 réplicas, estrategia RollingUpdate, probes `/health/live` y `/health/ready`, y Services `type: LoadBalancer` enlazando nativamente a `localhost:8001` y `localhost:8002` en entornos locales).
   - Empaquetado y Automatización: `kustomization.yaml`, `apply.sh` y `scripts/test_k8s_endpoints.sh`.

---

## Stack y decisiones de diseño del backend

| Área | Tecnología o criterio |
| --- | --- |
| Lenguaje | Python 3.12 |
| API | FastAPI y Uvicorn |
| Validación y configuración | Pydantic 2 y pydantic-settings |
| Persistencia | PostgreSQL 16, SQLAlchemy 2 con sesiones síncronas y psycopg 3 |
| Migraciones | Alembic, independiente por servicio |
| Comunicación interna | HTTP con HTTPX, timeout explícito y URL configurable |
| Pruebas | pytest, pruebas HTTP e integración con PostgreSQL |
| Calidad | Ruff |
| Dependencias | `pyproject.toml` y `uv.lock` por servicio; instalación con `uv sync --frozen` |
| Desarrollo local | Docker Compose y Kubernetes local (Docker Desktop / WSL) |

### Reglas esenciales del dominio

1. Al crear un pedido, consultar Productos por HTTP y comprobar que exista y esté activo (`activo=true`).
2. El cliente solo envía `producto_id` y `cantidad` al crear un pedido; rechazar cualquier campo administrado por el servidor como `precio_unitario` o `total`.
3. Cambiar únicamente la cantidad conserva el precio histórico y recalcula el total con `Decimal`.
4. Cambiar de producto exige consultar el nuevo producto y tomar su nombre y precio actuales.
5. Modificar o eliminar un producto nunca altera pedidos anteriores. Las consultas de pedidos leen sus datos históricos y no dependen de la disponibilidad de Productos.
6. La eliminación de Productos y Pedidos es física. `activo` sirve para impedir nuevos pedidos sin destruir el producto.

### Contrato HTTP resumido

| Operación | Productos | Pedidos | Éxito |
| --- | --- | --- | --- |
| Crear | `POST /productos` | `POST /pedidos` | `201` |
| Listar | `GET /productos` | `GET /pedidos` | `200` |
| Consultar | `GET /productos/{id}` | `GET /pedidos/{id}` | `200` |
| Actualizar parcialmente | `PATCH /productos/{id}` | `PATCH /pedidos/{id}` | `200` |
| Eliminar | `DELETE /productos/{id}` | `DELETE /pedidos/{id}` | `204`, sin cuerpo |

* Rutas de salud en cada servicio:
  * `/health/live`: Proceso operativo (`200 {"status":"ok"}`).
  * `/health/ready`: Conexión exitosa a la base de datos propia (`200 {"status":"ready"}`).

---

## Pendientes para finalizar el proyecto completo

De acuerdo con el documento oficial **«Proyecto Final GKE.pdf»** y la lista de cotejo del Anexo B, esto es **únicamente lo que hace falta desarrollar en código y repositorio** para completar el 100% de los requisitos del proyecto:

### 1. Microservicio Frontend Web (Criterios A4, B3, B4, C1, C2, E5, E6)
- [ ] **Desarrollo del Frontend**: Crear una aplicación web (en `services/frontend/`, por ejemplo con HTML/JS y Nginx o framework SPA ligero) que consuma ambos microservicios y muestre en pantalla los datos de Productos y Pedidos.
- [ ] **Dockerfile propio**: Crear `services/frontend/Dockerfile` independiente para contenerizar la interfaz web.
- [ ] **Carnés e integrantes visibles (Criterio A4)**: Mostrar de manera visible y destacada en la interfaz web el nombre y carné de los 5 integrantes del equipo:
  - Hector Flores (`1199923`)
  - Joaquin Choc (`1280423`)
  - Daniel Diaz (`1040023`)
  - Jose Enriquez (`1053223`)
  - Sofia Singüenza (`1333123`)
- [ ] **Carnés registrados en la base de datos (Criterio A4)**: Incorporar un script de carga inicial / migración que inserte y persista los carnés de los integrantes en la base de datos.
- [ ] **Manifiesto Kubernetes para Frontend**: Declarar en `deploy/k8s/` el Deployment y el Service (`type: LoadBalancer`) del frontend para actuar como el punto de entrada público que enruta hacia los servicios internos por DNS.

### 2. Infraestructura como Código con Terraform (Criterios D1, D2, D5, G1)
- [ ] **Archivos declarativos en `infra/terraform/`**:
  - `provider.tf` / `versions.tf`: Configuración del proveedor de Google Cloud.
  - `variables.tf`: Parametrización de `project_id`, `region`, `zone` y `cluster_name` sin valores sensibles escritos en el código.
  - `vpc.tf`: Red VPC y subred con rangos secundarios para pods y services.
  - `gke.tf`: Clúster GKE Standard zonal con un node pool de **dos nodos `e2-small` de tipo spot** (preemptible/spot).
  - `artifact_registry.tf`: Repositorio Docker administrado en Google Artifact Registry (`panaderia-repo`).
  - `outputs.tf`: Comando de conexión con `gcloud` y URL de Artifact Registry.
  - `terraform.tfvars.example`: Plantilla de variables de configuración.
- [ ] **Estimación de Costos (Criterio G1)**: Elaborar el documento `docs/estimacion-costos.md` con la estimación de costos mensuales calculada para los dos nodos `e2-small` spot, almacenamiento persistente y Artifact Registry antes del despliegue.

### 3. Trazabilidad del Repositorio Git (Criterio A1)
- [ ] Asegurar que el repositorio cuente con **al menos 10 commits distribuidos en 3 días distintos** antes de la fecha límite de entrega (sin alterar fechas artificialmente).

---

## Instrucciones para futuros agentes

1. **Preservar el backend**: No modificar los modelos, esquemas, migraciones ni rutas de Productos o Pedidos a menos que sea estrictamente necesario para la integración con el Frontend.
2. **Ambiente Local vs Nube**:
   * Las pruebas locales actuales se ejecutan en Docker Desktop / WSL mediante `compose.yaml` y `scripts/test_k8s_endpoints.sh`.
   * El código de Terraform en `infra/terraform/` se mantiene puramente declarativo y parametrizado; **no intentar ejecutar `terraform apply` contra Google Cloud a menos que el usuario proporcione credenciales activas y lo autorice expresamente**.
3. **Calidad y Estilo**:
   * Cualquier código nuevo de Python o scripts debe mantener formateo limpio con `ruff` y tipado estricto.
   * Toda referencia a rutas de archivos debe usar links en formato markdown con esquema `file://`.
