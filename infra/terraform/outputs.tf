output "cluster_name" {
  description = "Nombre del clúster desplegado"
  value       = google_container_cluster.primary.name
}

output "artifact_registry_url" {
  description = "Ruta base para etiquetar imágenes Docker"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}"
}

output "gcloud_connect_command" {
  description = "Comando para configurar kubectl"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --zone ${var.zone} --project ${var.project_id}"
}