resource "google_cloud_run_v2_job" "worker" {
  project             = var.project_id
  name                = local.worker_job
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1

    template {
      service_account = google_service_account.worker.email
      timeout         = "1800s"
      max_retries     = 0

      containers {
        image   = local.backend_image
        command = ["python"]
        args    = ["-m", "hardware_build.run_job"]

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        dynamic "env" {
          for_each = local.common_environment
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.wokwi_secret_version == null ? [] : [var.wokwi_secret_version]
          content {
            name = "WOKWI_CLI_TOKEN"
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.wokwi.secret_id
                version = env.value
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.backend,
    google_firestore_database.default,
    google_project_iam_member.project_roles,
    google_secret_manager_secret_iam_member.worker_wokwi,
    google_storage_bucket_iam_member.worker_artifact_writer,
  ]
}

resource "google_cloud_run_v2_service" "api" {
  project             = var.project_id
  name                = local.api_service
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.backend_image

      ports {
        container_port = 8080
      }

      resources {
        cpu_idle = true
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      dynamic "env" {
        for_each = merge(local.common_environment, {
          CLOUD_RUN_JOB_NAME = "projects/${var.project_id}/locations/${var.region}/jobs/${local.worker_job}"
          PUBLIC_BUILD_URL   = var.public_build_url
        })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_cloud_run_v2_job.worker,
    google_project_iam_member.project_roles,
    google_storage_bucket_iam_member.api_artifact_reader,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_api" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job_iam_member" "api_dispatches_worker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.worker.name
  role     = "roles/run.invoker"
  member   = google_service_account.api.member
}
