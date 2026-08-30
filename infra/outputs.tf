output "artifact_bucket" { value = google_storage_bucket.artifacts.name }
output "artifact_repository" { value = google_artifact_registry_repository.backend.name }
output "api_url" { value = google_cloud_run_v2_service.api.uri }
output "worker_job_name" { value = google_cloud_run_v2_job.worker.name }
output "worker_job_resource_name" { value = google_cloud_run_v2_job.worker.id }
output "wokwi_secret_name" { value = google_secret_manager_secret.wokwi.name }
output "github_workload_identity_provider" {
  value = var.github_repository == null ? null : google_iam_workload_identity_pool_provider.github[0].name
}
