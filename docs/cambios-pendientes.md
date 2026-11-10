# Cambios requeridos y posibles

Proyecto Panadería, Grupo 4 — Power Rangers. Estado a la fecha de entrega: martes 10 de noviembre de 2026.

La aplicación está desplegada y probada en GKE. Lo que falta es, sobre todo, documentación y evidencia. La primera sección lista lo que la lista de cotejo exige. La segunda lista mejoras que no son obligatorias.

## 1. Cambios requeridos

### Documentos y entrega

| # | Cambio | Criterio | Descripción |
|---|--------|----------|-------------|
| R1 | Escribir `docs/estimacion-costos.md` | G1 (3 pts) | Estimación mensual de 2 nodos `e2-small` spot, disco persistente, Artifact Registry y balanceadores. Debe estar elaborada antes del despliegue. Después se completa la cifra marcada como `[US$ __]` en la lámina 11 de la presentación. |
| R2 | Decidir la rama de entrega | A1, C3, D1 | `main` volvió al estado anterior con un revert, por lo que sus manifiestos apuntan al proyecto de registro equivocado (`panaderia-grupo-4`) y Terraform no da permiso de lectura a los nodos. Un despliegue desde `main` falla con `ImagePullBackOff`. Se debe entregar `develop` o fusionarla de nuevo en `main` antes de entregar el enlace. |
| R3 | Actualizar el README | A2 | Agregar los pasos de despliegue en GKE: Terraform, `scripts/publicar_imagenes.sh`, `scripts/crear_secret_gke.sh` y `deploy/k8s/apply.sh`, además de la regla de eliminación de productos. |
| R4 | Subir la entrega al portal | Admisión | Antes del martes 10 de noviembre a las 17:59: enlace del repositorio, PDF de evidencias y diagrama de arquitectura. |

### Evidencias que faltan o deben repetirse

| # | Cambio | Criterio | Descripción |
|---|--------|----------|-------------|
| R5 | Captura de `terraform plan` | D3 | La salida del plan se perdió al desplazarse la terminal. Repetir `terraform plan` y capturarlo completo. |
| R6 | Captura de `terraform apply` | D4 | El índice del PDF de evidencias no tiene esta sección. Mostrar los 6 recursos creados. |
| R7 | Capturas con reloj y proyecto | Admisión | Todas las capturas deben mostrar el reloj del sistema y la salida de `gcloud config list` con `virtualizacion-proyecto-pr`. |
| R8 | Repetir capturas de Kubernetes en el clúster actual | E1–E6, F1–F4 | El clúster se recreó con Terraform. Las evidencias tomadas antes del cambio muestran otro clúster y deben rehacerse. |
| R9 | Demostraciones operativas | E4, F1–F4 | Probar en el clúster actual: borrar el pod de PostgreSQL y conservar los datos, escalar Productos a 3 réplicas de forma declarativa, borrar un pod y ver que se recrea, actualizar de `1.1.0` a `1.1.1` y mostrar los logs. Se probaron antes en una instalación de prueba, no en este clúster. |
| R10 | Alerta de presupuesto | Sección 5 | El enunciado pide configurarla en Google Cloud. No hay constancia de que exista. |
| R11 | Evidencia de cierre | G2, G3 | Después de la defensa: `terraform destroy` con su salida, y la captura del panel de facturación con el gasto final. Fecha límite: viernes 13 de noviembre a las 23:59. |

### Antes de la defensa

| # | Cambio | Descripción |
|---|--------|-------------|
| R12 | Respaldar el estado de Terraform | El archivo de estado solo existe en la sesión de Cloud Shell. Sin él, `terraform destroy` no puede borrar lo creado. Copiarlo a Cloud Storage o conservarlo antes de cerrar la sesión. |
| R13 | Completar la presentación | Lámina 11: cifra de costos. Lámina 12: confirmar la IP pública, que cambia si se recrea el clúster. |
| R14 | Mantener el clúster encendido | El clúster debe estar en ejecución y accesible durante la defensa, con todos los integrantes presentes. |

## 2. Cambios posibles

Ninguno es obligatorio. Se ordenan por utilidad para la defensa.

### Funcionamiento

| # | Cambio | Descripción |
|---|--------|-------------|
| P1 | Evitar la caída breve en el rolling update | En una prueba, 9 de 40 solicitudes no recibieron respuesta durante un reinicio, aunque la estrategia es `maxUnavailable: 0`. Agregar una espera `preStop` y una sonda de preparación más estricta suele resolverlo. |
| P2 | Guardar los carnés en una tabla propia | Hoy se registran como productos "Pan Especial" mediante el script de carga, y solo existen si alguien lo ejecuta. Una tabla de integrantes creada por migración, leída por el frontend, sería más fiel a A4 y no ensuciaría el catálogo. |
| P3 | Paginación real en el frontend | Los listados piden hasta 100 registros. Con más de 100 productos o pedidos, el resto no se vería. |
| P4 | Condición de carrera al borrar | Entre la consulta a Pedidos y el borrado, otro usuario puede crear un pedido. Es poco probable; se cierra con un bloqueo o forzando primero `activo=false`. |

### Infraestructura

| # | Cambio | Descripción |
|---|--------|-------------|
| P5 | Habilitar las APIs desde Terraform | Hubo que activar a mano la API de Resource Manager antes del `plan`. Declararlas con `google_project_service` evita ese paso en un proyecto nuevo. |
| P6 | Estado remoto de Terraform | Guardar el estado en un bucket de Cloud Storage evita perderlo y permite trabajar desde otra sesión. |
| P7 | Parametrizar el ID de proyecto en los manifiestos | Hoy hay que editar cada línea `image:` si cambia el proyecto. Kustomize o una variable en `apply.sh` lo centralizaría. |
| P8 | Usar el espejo de Google para las imágenes base | Docker Hub agota el tiempo en Cloud Shell. El script `publicar_imagenes.sh` ya usa `mirror.gcr.io`; los Dockerfiles aún apuntan a Docker Hub. |

### Calidad

| # | Cambio | Descripción |
|---|--------|-------------|
| P9 | Ejecutar `ruff` | No se ejecutó en esta máquina. Correr `ruff check` y `ruff format` en ambos servicios antes de entregar. |
| P10 | Ajustar la prueba `test_runtime` en Windows | Falla solo por el código de salida del proceso en Windows; las comprobaciones HTTP pasan. Se corrige aceptando el código que Windows devuelve. |
| P11 | Integración continua | Un flujo de GitHub Actions que corra las pruebas y `ruff` en cada confirmación evitaría regresiones. |
