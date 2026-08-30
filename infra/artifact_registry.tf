resource "google_artifact_registry_repository" "backend" {
  project       = var.project_id
  location      = var.region
  repository_id = local.artifact_repository
  description   = "Forge Physical backend and worker images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}
