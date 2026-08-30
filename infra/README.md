# Forge Physical Google Cloud infrastructure

Terraform creates only the production MVP dependencies: Artifact Registry, Firestore, a private
artifact bucket, least-privilege runtime/build identities, the Cloud Run API and worker Job, and an
empty Wokwi secret. It never stores a secret value in state.

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

To enable Wokwi after receiving a token, add a Secret Manager version interactively and update the
Cloud Run Job through a separate, reviewable Terraform change. Do not add the token to this file,
Terraform variables, GitHub, or Cloud Build substitutions.
