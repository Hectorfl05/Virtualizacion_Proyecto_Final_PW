# Despliegue en Kubernetes (GKE)

Esta guía detalla la arquitectura de objetos de Kubernetes, dimensionamiento de recursos, orden de despliegue, procedimientos operativos y evidencias de resiliencia para el proyecto de microservicios de Panadería (Grupo 4 — Power Rangers).

---

## 1. Arquitectura de Objetos Kubernetes

```mermaid
graph TD
    Client["Cliente / Navegador (Internet / Host)"] -->|"IP Pública / Localhost"| LB["Service LoadBalancer / Proxy Frontend"]

    subgraph K8sCluster["Clúster GKE Standard (2 nodos e2-small spot)"]
        subgraph NS["Namespace: panaderia-grupo-4"]
            subgraph ConfigSec["Configuración y Secretos"]
                CM["ConfigMap\n(panaderia-config)"]
                Sec["Secret\n(panaderia-secrets)"]
            end

            subgraph Storage["Persistencia"]
                PVC["PVC: postgres-pvc\n(10Gi, standard-rwo)"]
            end

            subgraph DB["Base de Datos (Recreate, 1 Réplica)"]
                SvcPG["Service: postgres\n(ClusterIP: 5432)"]
                PodPG["Pod: postgres:16\n(pg_isready probes)"]
            end

            subgraph Migrations["Jobs de Migración (batch/v1)"]
                JobProd["Job: productos-migration-job\n(alembic upgrade head)"]
                JobPed["Job: pedidos-migration-job\n(alembic upgrade head)"]
            end

            subgraph ProdSvc["Microservicio Productos"]
                SvcProd["Service: productos\n(LoadBalancer: 8001 / ClusterIP: 8000)"]
                PodProd1["Pod: productos (10001)\nReplica 1"]
                PodProd2["Pod: productos (10001)\nReplica 2"]
            end

            subgraph PedSvc["Microservicio Pedidos"]
                SvcPed["Service: pedidos\n(LoadBalancer: 8002 / ClusterIP: 8000)"]
                PodPed1["Pod: pedidos (10001)\nReplica 1"]
                PodPed2["Pod: pedidos (10001)\nReplica 2"]
            end
        end
    end

    LB -->|"Puerto 8001 / /api/productos"| SvcProd
    LB -->|"Puerto 8002 / /api/pedidos"| SvcPed

    SvcProd --> PodProd1
    SvcProd --> PodProd2

    SvcPed --> PodPed1
    SvcPed --> PodPed2

    PodPed1 -->|"HTTP (DNS: productos:8000)"| SvcProd
    PodPed2 -->|"HTTP (DNS: productos:8000)"| SvcProd

    PodPG --> PVC
    SvcPG --> PodPG

    JobProd --> SvcPG
    JobPed --> SvcPG

    PodProd1 --> SvcPG
    PodProd2 --> SvcPG
    PodPed1 --> SvcPG
    PodPed2 --> SvcPG

    CM -.-> PodProd1
    CM -.-> PodPed1
    Sec -.-> PodProd1
    Sec -.-> PodPed1
    Sec -.-> PodPG
```

---

## 2. Dimensionamiento de Recursos (Nodos `e2-small` Spot)

El clúster de GKE Standard zonal cuenta con **dos nodos `e2-small` spot**. Cada nodo dispone de 2 vCPUs compartidas y 2 GB de memoria RAM (~1.2–1.4 GB asignables a pods tras descontar componentes de sistema `kubelet`, `kube-proxy`, `fluentbit`).

Para garantizar alta disponibilidad y evitar desalojos por OOM (*Out Of Memory*), los recursos se distribuyen estrictamente:

| Componente | Réplicas | CPU Request | Mem Request | CPU Limit | Mem Limit | Memoria Total Requests |
|---|---|---|---|---|---|---|
| `postgres` | 1 (Recreate) | 100m | 256Mi | 500m | 512Mi | 256 MiB |
| `productos` | 2 (RollingUpdate) | 50m | 128Mi | 300m | 256Mi | 256 MiB |
| `pedidos` | 2 (RollingUpdate) | 50m | 128Mi | 300m | 256Mi | 256 MiB |
| Migraciones (Jobs) | Efímero | 50m | 128Mi | 250m | 256Mi | 128 MiB (temporal) |
| **Total en ejecución** | **5 pods** | **300m** | **768 MiB** | **1700m** | **1536 MiB** | **~768 MiB** |

> [!TIP]
> Incluso al escalar declarativamente `productos` o `pedidos` a 3 réplicas (añadiendo 128 MiB), el total de memoria solicitada permanece alrededor de 896 MiB, distribuyéndose cómodamente entre los dos nodos sin saturar la cuota.

---

## 3. Catálogo de Manifiestos (`deploy/k8s/`)

| Archivo | Tipo de Recurso | Descripción |
|---|---|---|
| [`00-namespace.yaml`](../deploy/k8s/00-namespace.yaml) | `Namespace` | Crea el namespace aislado `panaderia-grupo-4` con etiquetas de equipo y proyecto. |
| [`01-configmap.yaml`](../deploy/k8s/01-configmap.yaml) | `ConfigMap` | Variables no sensibles (`LOG_LEVEL`, `PRODUCTOS_BASE_URL`, timeouts, nombres de bases y puertos). |
| [`02-secret.example.yaml`](../deploy/k8s/02-secret.example.yaml) | `Secret` (Plantilla) | Plantilla sin contraseñas versionadas para contraseñas y cadenas `DATABASE_URL`. |
| [`03-postgres-pvc.yaml`](../deploy/k8s/03-postgres-pvc.yaml) | `PersistentVolumeClaim` | Solicita 10 GiB en almacenamiento `standard-rwo` (ReadWriteOnce) para retención de datos. |
| [`04-postgres.yaml`](../deploy/k8s/04-postgres.yaml) | `ConfigMap`, `Deployment`, `Service` | PostgreSQL 16 con `01-create-databases.sh`, réplica 1, estrategia `Recreate`, probes `pg_isready` y servicio ClusterIP `postgres:5432`. |
| [`05-migration-jobs.yaml`](../deploy/k8s/05-migration-jobs.yaml) | `Job` (batch/v1) | Jobs para ejecutar `alembic upgrade head` en `productos_db` y `pedidos_db` de forma aislada. |
| [`06-productos.yaml`](../deploy/k8s/06-productos.yaml) | `Deployment`, `Service` | 2 réplicas, usuario `appuser:10001`, probes `/health/live` y `/health/ready`, servicio ClusterIP `productos:8000`. |
| [`07-pedidos.yaml`](../deploy/k8s/07-pedidos.yaml) | `Deployment`, `Service` | 2 réplicas, usuario `appuser:10001`, probes, consumo de Productos por DNS interno, servicio `pedidos` (LoadBalancer / ClusterIP 8000). |
| [`kustomization.yaml`](../deploy/k8s/kustomization.yaml) | `Kustomization` | Configuración unificada de recursos para el namespace. |
| [`apply.sh`](../deploy/k8s/apply.sh) | Script Bash | Script de aplicación automatizado y ordenado con verificación de condiciones. |

---

## 4. Procedimiento de Despliegue Ordenado

### Paso 1: Configurar el Secret de Credenciales
Antes de desplegar los componentes, crear el secreto en Kubernetes mediante `kubectl` de forma segura (sin escribir contraseñas en archivos versionados):

```bash
kubectl apply -f deploy/k8s/00-namespace.yaml

kubectl create secret generic panaderia-secrets \
  --namespace panaderia-grupo-4 \
  --from-literal=POSTGRES_PASSWORD='TU_PASSWORD_ADMIN' \
  --from-literal=PRODUCTOS_DB_PASSWORD='TU_PASSWORD_PRODUCTOS' \
  --from-literal=PEDIDOS_DB_PASSWORD='TU_PASSWORD_PEDIDOS' \
  --from-literal=PRODUCTOS_DATABASE_URL='postgresql+psycopg://productos_app:TU_PASSWORD_PRODUCTOS@postgres.panaderia-grupo-4.svc.cluster.local:5432/productos_db' \
  --from-literal=PEDIDOS_DATABASE_URL='postgresql+psycopg://pedidos_app:TU_PASSWORD_PEDIDOS@postgres.panaderia-grupo-4.svc.cluster.local:5432/pedidos_db'
```

### Paso 2: Publicar Imágenes en Artifact Registry
Los manifiestos esperan que las imágenes residan en Artifact Registry con etiquetas inmutables:

```bash
# Autenticar Docker con GCP
gcloud auth configure-docker us-central1-docker.pkg.dev

# Construir y etiquetar
docker build -t us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/productos:1.0.0 ./services/productos
docker build -t us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/pedidos:1.0.0 ./services/pedidos

# Copiar imagen de postgres oficial a Artifact Registry
docker pull postgres:16
docker tag postgres:16 us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/postgres:16

# Publicar
docker push us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/productos:1.0.0
docker push us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/pedidos:1.0.0
docker push us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/postgres:16
```

### Paso 3: Ejecutar el Despliegue
Ejecutar el script ordenado:

```bash
./deploy/k8s/apply.sh
```

O aplicar los manifiestos manualmente en el orden documentado:
1. `kubectl apply -f deploy/k8s/01-configmap.yaml`
2. `kubectl apply -f deploy/k8s/03-postgres-pvc.yaml`
3. `kubectl apply -f deploy/k8s/04-postgres.yaml`
4. Esperar a que el pod de PostgreSQL esté listo:
   `kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n panaderia-grupo-4 --timeout=120s`
5. Ejecutar Jobs de migración:
   `kubectl apply -f deploy/k8s/05-migration-jobs.yaml`
   `kubectl wait --for=condition=complete job/productos-migration-job -n panaderia-grupo-4 --timeout=60s`
   `kubectl wait --for=condition=complete job/pedidos-migration-job -n panaderia-grupo-4 --timeout=60s`
6. Desplegar microservicios (servicios expuestos vía LoadBalancer y ClusterIP):
   `kubectl apply -f deploy/k8s/06-productos.yaml`
   `kubectl apply -f deploy/k8s/07-pedidos.yaml`

---

## 5. Guía de Evidencias Requeridas (Rúbrica Secciones A–G)

### A. Escalamiento Declarativo a 3 Réplicas
Demostrar el escalamiento horizontal de réplicas en Kubernetes:

```bash
# Escalamiento declarativo
kubectl scale deployment/productos --replicas=3 -n panaderia-grupo-4

# Comprobar la creación de la tercera réplica y estado Ready
kubectl get deployment productos -n panaderia-grupo-4
kubectl get pods -l app.kubernetes.io/name=productos -n panaderia-grupo-4
```

### B. Recuperación de un Pod (Resiliencia)
Demostrar que Kubernetes detecta la eliminación de un pod y crea uno nuevo automáticamente para mantener el número de réplicas deseado:

```bash
# Obtener nombre de un pod activo
POD_NAME=$(kubectl get pods -n panaderia-grupo-4 -l app.kubernetes.io/name=productos -o jsonpath='{.items[0].metadata.name}')

# Eliminar el pod
kubectl delete pod "$POD_NAME" -n panaderia-grupo-4

# Verificar inmediatamente la recreación del pod de reemplazo
kubectl get pods -l app.kubernetes.io/name=productos -n panaderia-grupo-4 -w
```

### C. Demostración de Rolling Update sin Indisponibilidad
Demostrar la actualización progresiva de versión sin caída del servicio:

```bash
# Actualizar la imagen a una nueva versión
kubectl set image deployment/productos productos=us-central1-docker.pkg.dev/PROYECTO_GCP/panaderia-repo/productos:1.0.1 -n panaderia-grupo-4

# Observar el despliegue progresivo (maxSurge=1, maxUnavailable=0)
kubectl rollout status deployment/productos -n panaderia-grupo-4

# Inspeccionar el historial de despliegues
kubectl rollout history deployment/productos -n panaderia-grupo-4
```

### D. Inspección de Logs y Salud
Capturar bitácoras de los pods en ejecución:

```bash
# Logs del microservicio de Productos
kubectl logs -n panaderia-grupo-4 -l app.kubernetes.io/name=productos --tail=50

# Logs del microservicio de Pedidos
kubectl logs -n panaderia-grupo-4 -l app.kubernetes.io/name=pedidos --tail=50

# Logs de los jobs de migración
kubectl logs job/productos-migration-job -n panaderia-grupo-4
kubectl logs job/pedidos-migration-job -n panaderia-grupo-4
```

### E. Persistencia de PostgreSQL ante Eliminación de Pod
Demostrar que los datos persisten en el volumen `postgres-pvc` cuando el pod de base de datos se destruye y vuelve a crearse:

```bash
# 1. Crear un producto de prueba vía HTTP
# 2. Eliminar el pod de PostgreSQL
kubectl delete pod -n panaderia-grupo-4 -l app.kubernetes.io/name=postgres

# 3. Esperar a que el controlador recree el pod y monte el PVC
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n panaderia-grupo-4 --timeout=120s

# 4. Consultar el producto creado: debe retornar los mismos datos intactos
```

---

## 6. Limpieza Responsable de Recursos

Para destruir los recursos de Kubernetes conservando la infraestructura base de Terraform:

```bash
kubectl delete namespace panaderia-grupo-4
```

Esto eliminará automáticamente todos los Deployments, Services, ConfigMaps, Secrets, Jobs, Ingress y el PersistentVolumeClaim asociado, liberando las cuotas y discos del proyecto.
