# Forge Physical Google Cloud infrastructure

Terraform creates only the production MVP dependencies: Artifact Registry, Firestore, a private
artifact bucket, least-privilege runtime/build identities, the Cloud Run API and worker Job, and an
empty Wokwi secret. It never stores a secret value in state.

Infrastructure runs in `us-central1`; Gemini 3.5 Flash inference uses independent multi-region
`VERTEX_LOCATION=us` on the API and worker.

## Bootstrap and deploy

Authenticate with OAuth/ADC, then use the same project in Terraform:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project supple-voyage-507119-v0 # Project display name: coup

Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
# First create the registry and foundation, then push the application image.
terraform apply -target=google_artifact_registry_repository.backend

docker build -f services/build-worker/Dockerfile -t us-central1-docker.pkg.dev/supple-voyage-507119-v0/forge-physical/backend:prod .
docker push us-central1-docker.pkg.dev/supple-voyage-507119-v0/forge-physical/backend:prod

terraform fmt
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

After apply, use `terraform output -raw api_url` for `/health`, and execute the Job with
`gcloud run jobs execute forge-worker --region us-central1`. The Job intentionally fails without a
`BUILD_ID`; that proves it is executable but not a real build. A real API `prototype_start` call
sets the override.

To add or rotate Wokwi without exposing it in Terraform state, pass the token only through standard
input: `gcloud secrets versions add wokwi-cli-token --data-file=-`. The Job reads Secret Manager
`latest`; do not add the token to Terraform variables, GitHub, or Cloud Build substitutions.

## GitHub Actions WIF

The repository is restricted to `baskpascal/forge-physical` by the provider condition and the
service-account principal binding. After applying Terraform, set these GitHub Actions repository
variables from Terraform outputs (no JSON key is used):

```powershell
terraform output -raw github_workload_identity_provider # GCP_WORKLOAD_IDENTITY_PROVIDER
terraform output -raw github_service_account             # GCP_SERVICE_ACCOUNT
# GCP_PROJECT_ID=supple-voyage-507119-v0
# GCP_REGION=us-central1
```

Set the provider output as `GCP_WIF_PROVIDER` (not a secret). The checked-in workflow uses GitHub
OIDC -> Workload Identity Federation -> `forge-build`, stages source in the dedicated build-source
bucket, and submits Cloud Build as that same identity. It does not use a service-account key.
