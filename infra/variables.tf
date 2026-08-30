variable "project_id" {
  description = "Google Cloud project that hosts Forge Physical."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region."
  type        = string
  default     = "us-central1"
}

variable "image" {
  description = "Existing backend image to run in Cloud Run. Build and push it after the bootstrap resources apply."
  type        = string
}

variable "public_build_url" {
  description = "Public Next.js Build Room URL; use localhost until the frontend is deployed."
  type        = string
  default     = "http://localhost:3000"
}

variable "github_repository" {
  description = "Optional GitHub owner/repository for OIDC federation, e.g. owner/forge-physical."
  type        = string
  default     = null
  nullable    = true
}
