resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.zone

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  # Se elimina el node pool por defecto para crear uno administrado
  remove_default_node_pool = true
  initial_node_count       = 1

  # Permitir destruir el clúster sin bloqueos (ideal para proyectos académicos)
  deletion_protection = false

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods-range"
    services_secondary_range_name = "services-range"
  }
}

resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.cluster_name}-node-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  
  # Criterio GKE: Node pool de exactamente 2 nodos
  node_count = 2

  node_config {
    machine_type = "e2-small"
    spot         = true # Criterio GKE: Nodos tipo spot (preemptible)

    # Permisos suficientes para descargar imágenes de Artifact Registry
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      team = "power-rangers"
    }
  }
}