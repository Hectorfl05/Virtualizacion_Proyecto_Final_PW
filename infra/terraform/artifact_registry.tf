resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.artifact_repository_name
  description   = "Repositorio Docker para Panaderia Grupo 4 (Productos, Pedidos, Frontend, Postgres)"
  format        = "DOCKER"
}