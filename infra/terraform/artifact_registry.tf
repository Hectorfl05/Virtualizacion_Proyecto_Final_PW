resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.artifact_repository_name
  description   = "Repositorio Docker para Panaderia Grupo 4 (Productos, Pedidos, Frontend, Postgres)"
  format        = "DOCKER"
}

# La cuenta de servicio por defecto de los nodos necesita leer imágenes del repositorio.
data "google_project" "current" {}

resource "google_artifact_registry_repository_iam_member" "nodes_reader" {
  project    = google_artifact_registry_repository.repo.project
  location   = google_artifact_registry_repository.repo.location
  repository = google_artifact_registry_repository.repo.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}
