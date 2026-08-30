# Forge Physical Google Cloud infrastructure

This Terraform stack provisions the minimum production backend: required APIs, Artifact Registry,
Firestore Native, two private buckets, dedicated runtime/build identities, Cloud Run API and worker
job, an empty Wokwi secret, and GitHub OIDC Workload Identity Federation.

Terraform never accepts a secret value. Create a Secret Manager version separately and pass only its
numeric version through `wokwi_secret_version`.

## Prerequisites

```powershell
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJECT_ID
gcloud config set project PROJECT_ID
```

The project must have an open billing account. Confirm before applying:

```powershell
gcloud beta billing projects describe PROJECT_ID --format="value(billingEnabled)"
```

## Bootstrap and deploy

The first deployment has a two-phase bootstrap because Cloud Run cannot reference the application
image until its Artifact Registry repository exists.

```powershell
Set-Location infra
Copy-Item terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with only non-sensitive values.

terraform init
terraform fmt -check
terraform validate

# Bootstrap APIs, registry, identities, state stores and WIF.
terraform apply `
  -target=google_project_service.required `
  -target=google_artifact_registry_repository.backend `
  -target=google_firestore_database.default `
  -target=google_storage_bucket.artifacts `
  -target=google_storage_bucket.build_source `
  -target=google_secret_manager_secret.wokwi `
  -target=google_service_account.api `
  -target=google_service_account.worker `
  -target=google_service_account.build `
  -target=google_service_account.github_deploy `
  -target=google_iam_workload_identity_pool.github `
  -target=google_iam_workload_identity_pool_provider.github

Set-Location ..
$sha = git rev-parse HEAD
$image = "us-central1-docker.pkg.dev/PROJECT_ID/forge-physical/backend:$sha"
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
docker build -f services/build-worker/Dockerfile -t $image .
docker push $image

Set-Location infra
terraform plan -var="backend_image=$image" -out=tfplan
terraform apply tfplan
terraform output
```

If `(default)` Firestore already exists, import it once before planning:

```powershell
terraform import google_firestore_database.default "projects/PROJECT_ID/databases/(default)"
```

## Wokwi token

Do not pass the token to Terraform. Add it interactively, then set only its version number:

```powershell
$token = Read-Host "Wokwi CLI token" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
try {
  [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) |
    gcloud secrets versions add wokwi-cli-token --data-file=-
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}
terraform apply -var="backend_image=$image" -var="wokwi_secret_version=1"
```

The local state files and `terraform.tfvars` are ignored by Git. No service-account key is used.
