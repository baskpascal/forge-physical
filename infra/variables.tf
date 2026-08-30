variable "project_id" {
  description = "Google Cloud project ID that hosts Forge Physical."
  type        = string
}

variable "region" {
  description = "Regional location for Cloud Run and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location. Keep immutable after creation."
  type        = string
  default     = "us-central1"
}

variable "backend_image" {
  description = "Immutable backend image URI. Override with a commit-SHA tag after pushing it."
  type        = string
  default     = null
  nullable    = true
}

variable "gemini_model" {
  description = "Vertex AI Gemini model used by the ADK worker."
  type        = string
  default     = "gemini-3.5-flash"
}

variable "public_build_url" {
  description = "Public Vercel Build Room base URL."
  type        = string
  default     = "http://localhost:3000"
}

variable "wokwi_secret_version" {
  description = "Pinned Secret Manager version to inject. Leave null until a real token version exists."
  type        = string
  default     = null
  nullable    = true
  sensitive   = false
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to exchange OIDC tokens."
  type        = string
  default     = "baskpascal/forge-physical"
}

variable "enable_github_wif" {
  description = "Provision GitHub Actions Workload Identity Federation."
  type        = bool
  default     = true
}
