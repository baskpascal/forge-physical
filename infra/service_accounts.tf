resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "forge-api"
  display_name = "Forge API runtime"
  description  = "Cloud Run API identity; dispatches jobs and reads build artifacts."
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "forge-worker"
  display_name = "Forge worker runtime"
  description  = "Cloud Run Job identity; uses Vertex AI, Firestore, Storage and Wokwi secret access."
}

resource "google_service_account" "build" {
  project      = var.project_id
  account_id   = "forge-build"
  display_name = "Forge Cloud Build"
  description  = "Builds images and deploys Cloud Run revisions without a long-lived key."
}

resource "google_service_account" "github_deploy" {
  count = var.enable_github_wif ? 1 : 0

  project      = var.project_id
  account_id   = "forge-github-deploy"
  display_name = "Forge GitHub deploy"
  description  = "Receives short-lived GitHub OIDC credentials and submits Cloud Build builds."
}

locals {
  project_roles = {
    api_firestore        = [google_service_account.api.member, "roles/datastore.user"]
    worker_firestore     = [google_service_account.worker.member, "roles/datastore.user"]
    worker_vertex        = [google_service_account.worker.member, "roles/aiplatform.user"]
    worker_service_usage = [google_service_account.worker.member, "roles/serviceusage.serviceUsageConsumer"]
    build_artifacts      = [google_service_account.build.member, "roles/artifactregistry.writer"]
    build_builder        = [google_service_account.build.member, "roles/cloudbuild.builds.builder"]
    build_logs           = [google_service_account.build.member, "roles/logging.logWriter"]
    build_run_admin      = [google_service_account.build.member, "roles/run.admin"]
    github_cloudbuild    = var.enable_github_wif ? [google_service_account.github_deploy[0].member, "roles/cloudbuild.builds.editor"] : null
    github_service_usage = var.enable_github_wif ? [google_service_account.github_deploy[0].member, "roles/serviceusage.serviceUsageConsumer"] : null
  }
}

resource "google_project_iam_member" "project_roles" {
  for_each = { for name, binding in local.project_roles : name => binding if binding != null }

  project = var.project_id
  member  = each.value[0]
  role    = each.value[1]
}

resource "google_storage_bucket_iam_member" "api_artifact_reader" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.api.member
}

resource "google_storage_bucket_iam_member" "worker_artifact_writer" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = google_service_account.worker.member
}

resource "google_storage_bucket_iam_member" "build_source_admin" {
  bucket = google_storage_bucket.build_source.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.build.member
}

resource "google_storage_bucket_iam_member" "github_source_admin" {
  count = var.enable_github_wif ? 1 : 0

  bucket = google_storage_bucket.build_source.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.github_deploy[0].member
}

resource "google_service_account_iam_member" "build_can_use_api" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.build.member
}

resource "google_service_account_iam_member" "build_can_use_worker" {
  service_account_id = google_service_account.worker.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.build.member
}

resource "google_service_account_iam_member" "github_can_use_build" {
  count = var.enable_github_wif ? 1 : 0

  service_account_id = google_service_account.build.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.github_deploy[0].member
}
