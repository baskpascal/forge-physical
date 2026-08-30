output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "artifact_repository" {
  value = google_artifact_registry_repository.backend.name
}

output "artifact_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "backend_image" {
  value = local.backend_image
}

output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "worker_job_name" {
  value = google_cloud_run_v2_job.worker.name
}

output "github_workload_identity_provider" {
  value = var.enable_github_wif ? google_iam_workload_identity_pool_provider.github[0].name : null
}

output "github_deploy_service_account" {
  value = var.enable_github_wif ? google_service_account.github_deploy[0].email : null
}

output "build_service_account" {
  value = google_service_account.build.email
}
