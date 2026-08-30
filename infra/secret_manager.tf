resource "google_secret_manager_secret" "wokwi" {
  project   = var.project_id
  secret_id = local.wokwi_secret

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "worker_wokwi" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.wokwi.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.worker.member
}
