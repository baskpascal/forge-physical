variable "project_id" {
  description = "Google Cloud project that hosts Forge Physical."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region."
  type        = string
  default     = "us-central1"
}

variable "api_image" {
  description = "Existing lightweight API image to run in Cloud Run."
  type        = string
}

variable "worker_image" {
  description = "Existing prewarmed worker image to run as the Cloud Run Job."
  type        = string
}

variable "web_image" {
  description = "Existing Build Room image to run in Cloud Run."
  type        = string
}

variable "public_build_url" {
  description = "Public Next.js Build Room URL used for API links and CORS."
  type        = string
  default     = "https://forge-web-rldj6ghw7q-uc.a.run.app"
}

variable "public_api_url" {
  description = "Public API base URL used in artifact links."
  type        = string
  default     = "https://forge-api-rldj6ghw7q-uc.a.run.app"
}

variable "github_repository" {
  description = "Optional GitHub owner/repository for OIDC federation, e.g. owner/forge-physical."
  type        = string
  default     = "baskpascal/forge-physical"
  nullable    = true
}
