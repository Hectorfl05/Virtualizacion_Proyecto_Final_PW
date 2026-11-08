# Guía para agentes: backend de Panadería

## Contexto y objetivo

Este repositorio corresponde al proyecto académico «Despliegue de una aplicación en la nube con Kubernetes e infraestructura como código», de Virtualización, Universidad Rafael Landívar, segundo semestre de 2026. 

El caso seleccionado es **Panadería**, número 6 del Anexo A:

- Entidad A: **Productos**, administrada por el microservicio de Productos.
- Entidad B: **Pedidos**, administrada por el microservicio de Pedidos.
- La entidad B debe referenciar a la entidad A.

El objetivo autorizado es diseñar y desarrollar el backend en Python, con creación, consulta, actualización y eliminación en ambos microservicios. El proyecto académico completo también requiere frontend, infraestructura, evidencias y defensa; no se debe declarar terminado el proyecto completo únicamente porque funcione el backend.

Al crear esta guía, el repositorio solo contiene un README con el nombre del proyecto. Las carpetas y funcionalidades descritas a continuación son propuestas pendientes de implementación. No afirmar que existen ni que sus pruebas pasan sin verificarlas.

## Requisitos obligatorios del documento

- Construir desde cero; no reutilizar código, manifiestos ni base de datos de los proyectos anteriores.
- Dos microservicios independientes, cada uno con CRUD completo y Dockerfile propio.
- Frontend web que consume ambos microservicios y muestra sus datos.
- Motor de base de datos con persistencia.
- GKE Standard zonal creado con Terraform, con un node pool de **dos nodos `e2-small` spot**.
- Artifact Registry declarado en Terraform; imágenes de la aplicación publicadas allí. Los manifiestos deben referenciar únicamente imágenes alojadas en Artifact Registry; contemplar también la imagen de base de datos.
- Objetos Kubernetes declarados en YAML y aplicados con `kubectl`; Terraform no administra esos objetos.
- Deployments para todos los componentes, ConfigMap, Secret, PVC para la base de datos y Services con comunicación interna por DNS.
- IP pública para acceder a la aplicación; clúster y namespace con el identificador del equipo.
- Carné de cada integrante registrado en la base de datos y visible en la interfaz.
- Repositorio con al menos diez commits distribuidos en tres días distintos. No fabricar ni alterar fechas para cumplir este criterio.
- README, diagrama propio de arquitectura y PDF de evidencias ordenado según las secciones A–G de la rúbrica.
- Evidenciar escalamiento declarativo a tres réplicas, recuperación de un pod, rolling update y logs.
- Estimar costos antes del despliegue, configurar alerta de presupuesto y destruir infraestructura después de la defensa, conservando evidencias.


## Stack y decisiones de diseño

Estas elecciones son la propuesta técnica del backend; el PDF no impone frameworks ni campos concretos:

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
| Desarrollo local | Docker Compose |
| Despliegue | Docker, Artifact Registry, Kubernetes YAML, GKE y Terraform |

Usar un motor PostgreSQL con dos bases lógicas y usuarios separados. Cada servicio es propietario exclusivo de sus tablas y migraciones. Pedidos accede a Productos por HTTP; no consulta sus tablas ni usa claves foráneas entre bases.

Para el alcance inicial, cada pedido contiene **un producto y una cantidad**. No implementar carrito, pagos, autenticación, inventario ni múltiples líneas de pedido sin una ampliación explícita del alcance.

El frontend o su proxy es el punto de entrada público. El navegador no puede resolver los nombres DNS internos de Kubernetes: el proxy debe enrutar las solicitudes hacia los Services de ambos microservicios.

## Modelos y reglas del dominio

### Producto

- `id`: UUID generado por el servidor.
- `nombre`: obligatorio, sin espacios vacíos, máximo 150 caracteres.
- `descripcion`: opcional, máximo 1000 caracteres.
- `precio`: decimal positivo, precisión de dos decimales; almacenar como `NUMERIC`, nunca `float`.
- `activo`: booleano, inicialmente verdadero.
- `created_at`, `updated_at`: timestamps UTC gestionados por el servidor.

### Pedido

- `id`: UUID generado por el servidor.
- `producto_id`: UUID que referencia lógicamente a Productos.
- `producto_nombre`: copia histórica del nombre al seleccionar el producto.
- `cantidad`: entero estrictamente positivo.
- `precio_unitario`: copia del precio del producto obtenida por el servidor.
- `total`: cantidad multiplicada por precio unitario, calculado con `Decimal`.
- `created_at`, `updated_at`: timestamps UTC gestionados por el servidor.

Reglas:

1. Al crear un pedido, consultar Productos y comprobar que exista y esté activo.
2. El cliente solo envía producto y cantidad; rechazar campos no permitidos, incluidos precio y total.
3. Cambiar únicamente la cantidad conserva el precio histórico y recalcula el total.
4. Cambiar de producto exige validar el nuevo producto y tomar su nombre y precio actuales.
5. Modificar o eliminar un producto no altera pedidos anteriores. Las consultas de pedidos usan sus datos históricos y no dependen de que Productos esté disponible.
6. La eliminación de Productos y Pedidos será física. `activo` sirve para impedir nuevos pedidos sin eliminar el producto.
7. No prometer integridad transaccional distribuida: la validación HTTP comprueba el producto en el momento de consulta; el pedido conserva su copia histórica.

# Contrato HTTP

| Operación | Productos | Pedidos | Éxito |
| --- | --- | --- | --- |
| Crear | `POST /productos` | `POST /pedidos` | `201` |
| Listar | `GET /productos` | `GET /pedidos` | `200` |
| Consultar | `GET /productos/{id}` | `GET /pedidos/{id}` | `200` |
| Actualizar parcialmente | `PATCH /productos/{id}` | `PATCH /pedidos/{id}` | `200` |
| Eliminar | `DELETE /productos/{id}` | `DELETE /pedidos/{id}` | `204`, sin cuerpo |

- Listados paginados con `limit` (predeterminado 20, máximo 100), `offset` y orden estable; respuesta con `items`, `total`, `limit` y `offset`.
- Recurso solicitado inexistente: `404`.
- Datos inválidos o producto inexistente/inactivo al guardar un pedido: `422`, con detalle claro.
- Productos inaccesible, timeout o respuesta inválida durante la validación de un pedido: `503`, sin guardar el pedido.
- No convertir fallos de red en errores de validación ni exponer trazas o credenciales al cliente.
- `/health/live`: proceso operativo. `/health/ready`: verifica la conexión a la base propia, sin encadenar la disponibilidad de todos los servicios.
- Mantener OpenAPI, ejemplos y comportamiento real alineados.

## Estructura propuesta

```text
.
├── AGENTS.md
├── README.md
├── .gitignore
├── compose.yaml
├── services/
│   ├── productos/
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── Dockerfile
│   │   ├── .dockerignore
│   │   ├── .env.example
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   └── tests/
│   └── pedidos/
│       ├── ... misma organización independiente ...
│       └── app/clients/productos.py
├── tests/integration/
├── deploy/
│   ├── postgres/             # Inicialización local de bases y usuarios
│   └── k8s/                  # Namespace, configuración, Jobs y componentes
├── infra/terraform/           # GKE, node pool y Artifact Registry
└── docs/
    ├── arquitectura.md
    ├── contrato-api.md
    ├── pruebas.md
    └── evidencias/            # Guía de capturas; nunca secretos
```
Mantener separación simple entre rutas HTTP, reglas de negocio y acceso a datos. No introducir frameworks internos ni paquetes compartidos que impidan construir cada imagen de manera independiente.

## Estado técnico y seguimiento interno

El README funciona como presentación y guía de uso. Mantener aquí el avance, las limitaciones y los pendientes, sin presentar capacidades diseñadas como funcionalidades verificadas.

- Implementado: configuración de ambos servicios, engines y sesiones SQLAlchemy, entornos Alembic, endpoints de salud y pruebas. CRUD completo de Productos (Fase 3), CRUD completo de Pedidos con validación HTTP remota y conservación histórica (Fase 4), y Contenedores e Integración Local (Fase 5) con Dockerfiles multi-etapa independientes (`appuser:10001`), dependencias congeladas (`uv.lock`), orquestación completa en Compose (`compose.yaml`), migraciones desacopladas por perfiles, pruebas de integración E2E (`tests/integration/test_e2e_flow.py`) y script de validación de persistencia (`scripts/test_persistence.sh`). Frontend y despliegue en la nube (Fases 6 y 7) siguen pendientes.
- Dockerfiles y `.dockerignore` independientes en `services/productos` y `services/pedidos`. No ejecutan migraciones al arrancar; las migraciones se ejecutan explícitamente mediante perfiles de Compose o comandos bajo demanda.
- Ambos servicios tienen `uv.lock` independiente; instalación verificada mediante `uv sync --frozen`. `requirements.txt` es una referencia de desarrollo sin bloqueo y no sustituye los lockfiles.
- Alembic tiene configuración independiente por servicio. Productos cuenta con `0001_create_productos` y Pedidos con `0001_create_pedidos`, creando sus tablas correspondientes con tipos nativos (`UUID`, `NUMERIC`, `TIMESTAMPTZ`) e índices. Se verificaron `upgrade head`, `current` y `check` con PostgreSQL real: `check` reporta cero diferencias en ambos servicios.
- `PRODUCTOS_BASE_URL=http://productos:8000` en Compose y `http://localhost:8001` en host; `PRODUCTOS_TIMEOUT_SECONDS=5` configurados y probados en el cliente HTTP de Pedidos.
- Usar los entornos `services/productos/.venv` y `services/pedidos/.venv`, regenerables desde sus lockfiles con Python 3.12.
- Última verificación: 7 de noviembre de 2026, 107 pruebas en suites unitarias y de integración de PostgreSQL 16.13 aprobadas; suite E2E entre microservicios implementada en `tests/integration/test_e2e_flow.py`; Ruff exitoso en los 41 archivos del repositorio.
- Persistencia de volumen documentada y automatizada en `scripts/test_persistence.sh`: el volumen `postgres_data` conserva los datos ante reinicio; `docker compose down -v` está expresamente advertido como destructivo.

Consultar [resultados y comandos ejecutados](docs/pruebas.md) y [desarrollo local](docs/desarrollo-local.md) para el detalle.

## Fases y tareas cortas

Las casillas describen trabajo pendiente. Marcar una tarea solo después de implementar y verificar su resultado. Registrar bloqueos y comandos realmente ejecutados.

### Fase 1: contrato y diseño

- [x] Documentar entidades, campos y reglas descritos en esta guía.
- [x] Documentar cuerpos de solicitud, respuesta y errores de cada endpoint.
- [x] Dibujar arquitectura con frontend, servicios, bases y acceso público.
- [x] Registrar identificador del equipo e integrantes cuando sean proporcionados; no inventarlos.

Entregables: [contrato](docs/contrato-api.md), [arquitectura y registro de integrantes](docs/arquitectura.md) y [registro de verificación documental](docs/pruebas.md). Equipo registrado: **Grupo 4 — Power Rangers**. Integrantes registrados: Hector Flores (`1199923`), Joaquin Choc (`1280423`), Daniel Diaz (`1040023`), Jose Enriquez (`1053223`) y Sofia Singüenza (`1333123`). Las cuatro tareas documentales de la Fase 1 están completas.

Cierre: contrato suficiente para implementar y conectar frontend sin adivinar comportamientos.

### Fase 2: base ejecutable

Completada y verificada el 5 de noviembre de 2026: entornos independientes desde lockfiles, PostgreSQL 16 real con bases y usuarios propios, SQLAlchemy, Alembic y arranque Uvicorn. Se usó PostgreSQL nativo temporal porque Docker Desktop sigue sin integración WSL. Ver [desarrollo local](docs/desarrollo-local.md) y [resultados y limitaciones](docs/pruebas.md).

- [x] Crear proyectos Python independientes y fijar dependencias en sus lockfiles.
- [x] Crear aplicaciones FastAPI y configuración mediante variables.
- [x] Configurar PostgreSQL local con bases y usuarios separados.
- [x] Configurar SQLAlchemy y Alembic por servicio.
- [x] Agregar endpoints de salud y logs a stdout/stderr.
- [x] Verificar arranque y conexión de ambos servicios.

Cierre verificado: ambos servicios arrancan desde sus entornos bloqueados y acceden a su base propia. Alembic funciona sin revisiones de dominio todavía; los CRUD y sus migraciones corresponden a Fases 3 y 4. Compose y persistencia frente a reinicios quedan por verificar en Fase 5.

### Fase 3: Productos

Completada y verificada el 6 de noviembre de 2026: modelo SQLAlchemy, esquemas Pydantic con validación estricta y formato de error uniforme, repositorio, servicio, rutas HTTP `/productos`, migración Alembic `0001_create_productos` y pruebas completas unitarias y de integración contra PostgreSQL 16.13 real.

- [x] Crear modelo, esquemas y migración de Producto.
- [x] Implementar creación con validaciones.
- [x] Implementar listado paginado y consulta individual.
- [x] Implementar actualización parcial.
- [x] Implementar eliminación.
- [x] Probar CRUD, validaciones, paginación y recursos inexistentes con PostgreSQL.

Cierre verificado: CRUD completo de Productos probado contra PostgreSQL 16.13 real y reflejado en OpenAPI.

### Fase 4: Pedidos

Completada y verificada el 6 de noviembre de 2026: modelo SQLAlchemy, esquemas Pydantic v2 con validaciones estrictas y formato uniforme, cliente HTTP de Productos con HTTPX y timeout configurable, manejo controlado de fallos remotos (422 `product_not_found`, 422 `product_inactive`, 503 `products_unavailable`), repositorio, servicio con reglas de preservación histórica de precio/nombre y cálculo decimal (`Decimal`), rutas HTTP `/pedidos`, migración Alembic `0001_create_pedidos` y pruebas completas unitarias y de integración contra PostgreSQL 16.13 real.

- [x] Crear modelo, esquemas y migración de Pedido.
- [x] Crear cliente HTTP de Productos con timeout configurable.
- [x] Implementar creación con validación remota y cálculo decimal.
- [x] Implementar listado paginado y consulta individual.
- [x] Implementar actualización y reglas de precio histórico.
- [x] Implementar eliminación.
- [x] Probar CRUD y rechazo de precio/total enviados por el cliente.
- [x] Probar producto inexistente/inactivo, timeout y respuesta remota inválida.
- [x] Probar consulta histórica después de modificar o eliminar el producto.

Cierre verificado: CRUD completo y comunicación entre servicios con fallos controlados, probado contra PostgreSQL 16.13 real y reflejado en OpenAPI.

### Fase 5: contenedores e integración local

Completada y verificada el 7 de noviembre de 2026: Dockerfiles multi-etapa independientes para Productos y Pedidos basados en `python:3.12-slim` y `uv:0.5.15`, usuario de sistema no-root `appuser:appgroup` (10001:10001), dependencias congeladas (`uv.lock`), archivos `.dockerignore` independientes, orquestación completa en `compose.yaml` con volumen persistente `postgres_data`, migraciones explícitas bajo perfil `migration` desacopladas de las réplicas web, suite de integración end-to-end `tests/integration/test_e2e_flow.py` y script de persistencia tras reinicio `scripts/test_persistence.sh`.

- [x] Crear Dockerfile y contexto de construcción independiente por servicio.
- [x] Ejecutar contenedores con usuario sin privilegios y dependencias bloqueadas.
- [x] Completar Compose con volumen persistente y comprobaciones de salud.
- [x] Ejecutar migraciones como paso explícito, sin ejecutarlas en cada réplica web.
- [x] Probar el flujo real Producto → Pedido → consulta → actualización → eliminación.
- [x] Reiniciar PostgreSQL sin borrar el volumen y comprobar persistencia.
- [x] Documentar arranque, pruebas y apagado local; advertir que borrar volúmenes elimina datos.

Cierre verificado: backend local contenerizado y reproducible mediante Compose y README, con pruebas de integración reales y persistencia de datos.

### Fase 6: infraestructura y Kubernetes

- [ ] Verificar credenciales existentes, proyecto, facturación, APIs, cuota y Terraform.
- [ ] Preparar estimación de costos y guía de alerta de presupuesto.
- [ ] Declarar Terraform parametrizado: GKE Standard zonal, dos `e2-small` spot y Artifact Registry.
- [ ] Preparar etiquetas inmutables de imágenes y publicación en Artifact Registry.
- [ ] Crear namespace y Deployments/Services para ambos servicios y PostgreSQL.
- [ ] Crear ConfigMap y plantilla de Secret sin valores reales versionados.
- [ ] Configurar PVC y montaje correcto de PostgreSQL; una réplica y estrategia `Recreate`.
- [ ] Crear Jobs de migración por servicio y documentar su orden de ejecución.
- [ ] Configurar probes, requests y limits ajustados a los recursos disponibles.
- [ ] Documentar proxy del frontend hacia DNS internos y acceso público.
- [ ] Aplicar y validar el despliegue cuando se disponga de acceso y autorización correspondientes.

Cierre: CRUD real en GKE, configuración inyectada y datos persistentes; si falta acceso, registrar el bloqueo sin afirmar que el despliegue pasó.

### Fase 7: operación y entrega

- [ ] Ejecutar pruebas CRUD contra el despliegue real.
- [ ] Eliminar el pod de PostgreSQL y comprobar conservación de datos.
- [ ] Escalar declarativamente un microservicio a tres réplicas y comprobar disponibilidad.
- [ ] Eliminar un pod web y verificar su recreación.
- [ ] Publicar otra versión y demostrar rolling update.
- [ ] Obtener logs y documentar diagnóstico de fallos comunes.
- [ ] Completar README, diagrama y guía de evidencias A–G.
- [ ] Coordinar con frontend la persistencia y visualización de carnés reales.
- [ ] Comprobar historial de commits y entregables sin fabricar evidencia.
- [ ] Documentar limpieza de recursos Kubernetes externos a Terraform y `terraform destroy`.
- [ ] Ejecutar cierre tras la defensa con autorización y conservar evidencia de destrucción y gasto final.

Cierre: backend verificable y entregables de su alcance completos; señalar expresamente cualquier requisito del proyecto académico todavía pendiente.

## Configuración y operación

- Variables previstas: `DATABASE_URL` por servicio y `PRODUCTOS_BASE_URL` en Pedidos; agregar configuración de timeout y logs cuando se implemente.
- En Compose y Kubernetes usar nombres DNS de servicios; no IPs de pods ni `localhost` para comunicación entre contenedores.
- Mantener ejemplos con marcadores sin secretos. No imprimir URLs con contraseña, volcar entornos ni versionar `.env`, estados de Terraform o credenciales.
- Usar credenciales existentes antes de solicitar otras. Las credenciales faltantes se suministran mediante mecanismos seguros, nunca por chat ni dentro del repositorio.
- Configurar CORS solo si la integración lo requiere y con orígenes explícitos.
- No ejecutar migraciones destructivas ni destruir infraestructura o volúmenes sin comprobar alcance y autorización.

## Instrucciones de trabajo para agentes

1. Leer esta guía, el README y el estado actual del repositorio antes de modificarlo. Preservar cambios del usuario.
2. Implementar por fases y tareas pequeñas; priorizar un flujo funcional completo antes de ampliar alcance.
3. Mantener actualizados contrato, migraciones, lockfiles y documentación con cada cambio pertinente.
4. No sustituir migraciones por `create_all()` durante el arranque de producción.
5. Probar persistencia con PostgreSQL; SQLite no demuestra compatibilidad con el motor elegido.
6. Separar pruebas del cliente HTTP simulado de las pruebas de integración entre servicios reales.
7. Ejecutar las comprobaciones apropiadas y registrar resultado, alcance y limitaciones. Un puerto abierto o cero pruebas ejecutadas no demuestran funcionalidad.
8. No afirmar despliegue, publicación, persistencia o pruebas exitosas sin evidencia obtenida en la ejecución correspondiente.
9. No realizar despliegues con costo, publicaciones externas o acciones destructivas basándose solo en casillas de esta guía; aplicar la autorización vigente de la conversación.


## Definición de terminado del backend

- Ambos CRUD funcionan con PostgreSQL y tienen validaciones y errores documentados.
- Pedidos valida Productos por HTTP y preserva los datos históricos.
- Las pruebas cubren operaciones exitosas, entradas inválidas, recursos inexistentes y fallos de dependencia.
- Cada microservicio se construye y ejecuta independientemente como contenedor.
- El flujo integrado y la persistencia están verificados.
- Manifiestos y Terraform satisfacen los requisitos del alcance; los resultados locales y de GKE se reportan por separado.
- El README permite reproducir instalación, migraciones, pruebas, arranque y despliegue.
- No quedan secretos versionados ni afirmaciones de validación sin comprobar.

El proyecto académico completo solo termina cuando también se cumplen frontend, carnés visibles, infraestructura real, evidencias, defensa y cierre responsable.

