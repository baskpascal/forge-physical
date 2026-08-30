locals {
  name_prefix     = "forge"
  repository_name = "forge-physical"
  artifact_bucket = "${var.project_id}-forge-artifacts"
  api_sa          = "forge-api@${var.project_id}.iam.gserviceaccount.com"
  worker_sa       = "forge-worker@${var.project_id}.iam.gserviceaccount.com"
  build_sa        = "forge-build@${var.project_id}.iam.gserviceaccount.com"
  deploy_sa       = "forge-github-deploy@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_service" "required" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = local.repository_name
  format        = "DOCKER"
  description   = "Forge Physical backend and worker image"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "artifacts" {
  name                        = local.artifact_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.required]
}

resource "google_firestore_database" "builds" {
  project                     = var.project_id
  name                        = "(default)"
  location_id                 = var.region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "api" {
  account_id   = "forge-api"
  display_name = "Forge Physical API runtime"
}

resource "google_service_account" "worker" {
  account_id   = "forge-worker"
  display_name = "Forge Physical worker runtime"
}

resource "google_service_account" "build" {
  account_id   = "forge-build"
  display_name = "Forge Physical Cloud Build deployer"
}

resource "google_service_account" "github_deploy" {
  count        = var.github_repository == null ? 0 : 1
  account_id   = "forge-github-deploy"
  display_name = "Forge Physical GitHub Actions deployer"
}

resource "google_secret_manager_secret" "wokwi" {
  secret_id = "wokwi-cli-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.api_sa}"
}

resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.worker_sa}"
}

resource "google_project_iam_member" "worker_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${local.worker_sa}"
}

resource "google_storage_bucket_iam_member" "api_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.api_sa}"
}

resource "google_storage_bucket_iam_member" "worker_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${local.worker_sa}"
}

resource "google_secret_manager_secret_iam_member" "worker_wokwi" {
  secret_id = google_secret_manager_secret.wokwi.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.worker_sa}"
}

resource "google_project_iam_member" "build_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/run.admin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${local.build_sa}"
}

resource "google_service_account_iam_member" "build_runtime_user" {
  for_each = toset([local.api_sa, local.worker_sa])

  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.build_sa}"
}

resource "google_cloud_run_v2_job" "worker" {
  name     = "forge-worker"
  location = var.region

  template {
    template {
      service_account = local.worker_sa
      timeout         = "1800s"
      max_retries     = 0

      containers {
        image   = var.image
        command = ["python"]
        args    = ["-m", "hardware_build.run_job"]

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        env {
          name  = "BUILD_STORE"
          value = "firestore"
        }
        env {
          name  = "ARTIFACT_BUCKET"
          value = google_storage_bucket.artifacts.name
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "GOOGLE_CLOUD_REGION"
          value = var.region
        }
        env {
          name  = "GOOGLE_GENAI_USE_VERTEXAI"
          value = "true"
        }
        env {
          name  = "GEMINI_MODEL"
          value = "gemini-3.5-flash"
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.builds,
    google_project_iam_member.worker_firestore,
    google_project_iam_member.worker_vertex,
    google_storage_bucket_iam_member.worker_artifacts,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "api_invokes_worker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.worker.name
  # The API supplies BUILD_ID through RunJobRequest overrides. run.invoker only
  # covers executions without overrides; run.developer grants runWithOverrides.
  role   = "roles/run.developer"
  member = "serviceAccount:${local.api_sa}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "forge-api"
  location = var.region

  # The provider reads Cloud Run's legacy computed root scaling block even
  # though desired scaling lives in template.scaling. Ignore that API echo.
  lifecycle {
    ignore_changes = [scaling]
  }

  template {
    service_account = local.api_sa

    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GEMINI_MODEL"
        value = "gemini-3.5-flash"
      }
      env {
        name  = "BUILD_STORE"
        value = "firestore"
      }
      env {
        name  = "ARTIFACT_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
      env {
        name  = "CLOUD_RUN_JOB_NAME"
        value = google_cloud_run_v2_job.worker.id
      }
      env {
        name  = "PUBLIC_BUILD_URL"
        value = var.public_build_url
      }
    }
  }

  depends_on = [
    google_project_iam_member.api_firestore,
    google_storage_bucket_iam_member.api_artifacts,
    google_cloud_run_v2_job_iam_member.api_invokes_worker,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_api" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = var.github_repository == null ? 0 : 1
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "OIDC identities for ${var.github_repository}"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.github_repository == null ? 0 : 1
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "forge"
  display_name                       = "Forge Physical GitHub Actions"
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  count              = var.github_repository == null ? 0 : 1
  service_account_id = google_service_account.github_deploy[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "github_build_submit" {
  count   = var.github_repository == null ? 0 : 1
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${local.deploy_sa}"
}

resource "google_service_account_iam_member" "github_uses_build" {
  count              = var.github_repository == null ? 0 : 1
  service_account_id = google_service_account.build.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.deploy_sa}"
}
