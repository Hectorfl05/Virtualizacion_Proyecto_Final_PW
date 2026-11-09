variable "project_id" {
  description = "El ID del proyecto de Google Cloud"
  type        = string
}

variable "region" {
  description = "La región para los recursos"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "La zona para el clúster GKE Standard"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "Nombre del clúster de GKE"
  type        = string
  default     = "panaderia-grupo-4"
}

variable "artifact_repository_name" {
  description = "Nombre del repositorio en Artifact Registry"
  type        = string
  default     = "panaderia-repo"
}