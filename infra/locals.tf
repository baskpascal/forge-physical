locals {
  artifact_repository = "forge-physical"
  artifact_bucket     = "${var.project_id}-forge-artifacts"
  build_source_bucket = "${var.project_id}-forge-build-source"
  api_service         = "forge-api"
  worker_job          = "forge-worker"
  wokwi_secret        = "wokwi-cli-token"

  backend_image = coalesce(
    var.backend_image,
    "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_repository}/backend:latest"
  )

  common_environment = {
    GOOGLE_CLOUD_PROJECT      = var.project_id
    GOOGLE_CLOUD_REGION       = var.region
    GOOGLE_GENAI_USE_VERTEXAI = "true"
    GEMINI_MODEL              = var.gemini_model
    BUILD_STORE               = "firestore"
    ARTIFACT_BUCKET           = local.artifact_bucket
  }
}
