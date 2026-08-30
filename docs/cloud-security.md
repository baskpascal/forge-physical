# Production secrets and identity

Forge uses three separate configuration planes:

| Data | Production source | Examples |
| --- | --- | --- |
| Private secrets | Google Secret Manager, injected by Cloud Run | `WOKWI_CLI_TOKEN`, future private external API keys |
| Backend configuration | Cloud Run environment variables | project, region, bucket, model, URLs |
| Public web configuration | Vercel environment variables | `NEXT_PUBLIC_BUILD_API_URL`, Firebase public web config |

Vertex AI, Firestore, Cloud Storage, and Cloud Run APIs use Application Default Credentials (ADC).
Cloud Run obtains short-lived credentials from the attached `forge-api` or `forge-worker` service
account. No service-account key file or production `GOOGLE_APPLICATION_CREDENTIALS` is required.

## One-time Google Cloud setup

Run this in Bash or Cloud Shell after replacing the first four values:

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export GITHUB_OWNER="your-github-owner"
export GITHUB_REPO="your-github-owner/your-repository"

gcloud config set project "$PROJECT_ID"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
BUCKET="${PROJECT_ID}-forge-artifacts"
BUILD_SOURCE_BUCKET="${PROJECT_ID}-forge-build-source"

gcloud services enable \
  aiplatform.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  firestore.googleapis.com iamcredentials.googleapis.com run.googleapis.com \
  secretmanager.googleapis.com sts.googleapis.com storage.googleapis.com

gcloud artifacts repositories describe forge-physical --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create forge-physical --repository-format=docker --location="$REGION"
gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://${BUILD_SOURCE_BUCKET}" --location="$REGION" --uniform-bucket-level-access

for ACCOUNT in forge-api forge-worker forge-build forge-github-deploy; do
  gcloud iam service-accounts describe "${ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1 || \
    gcloud iam service-accounts create "$ACCOUNT" --display-name="$ACCOUNT"
done

API_SA="forge-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="forge-worker@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="forge-build@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOY_SA="forge-github-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${API_SA}" --role=roles/datastore.user
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${WORKER_SA}" --role=roles/datastore.user
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${WORKER_SA}" --role=roles/aiplatform.user
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${API_SA}" --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${WORKER_SA}" --role=roles/storage.objectUser

# Create the secret without putting its value in shell history, then enter it at the prompt.
gcloud secrets describe wokwi-cli-token >/dev/null 2>&1 || \
  gcloud secrets create wokwi-cli-token --replication-policy=automatic
read -rsp "Wokwi CLI token: " WOKWI_TOKEN; echo
printf %s "$WOKWI_TOKEN" | gcloud secrets versions add wokwi-cli-token --data-file=-
unset WOKWI_TOKEN
gcloud secrets add-iam-policy-binding wokwi-cli-token --member="serviceAccount:${WORKER_SA}" --role=roles/secretmanager.secretAccessor

# Cloud Build executes the deployment, but cannot become either runtime identity beyond deployment.
for ROLE in roles/artifactregistry.writer roles/logging.logWriter roles/run.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${BUILD_SA}" --role="$ROLE"
done
for RUNTIME_SA in "$API_SA" "$WORKER_SA"; do
  gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
    --member="serviceAccount:${BUILD_SA}" --role=roles/iam.serviceAccountUser
done
gcloud secrets add-iam-policy-binding wokwi-cli-token --member="serviceAccount:${BUILD_SA}" --role=roles/secretmanager.viewer

# GitHub can submit builds, but receives only short-lived OIDC-derived credentials.
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${DEPLOY_SA}" --role=roles/cloudbuild.builds.editor
gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA" \
  --member="serviceAccount:${DEPLOY_SA}" --role=roles/iam.serviceAccountUser
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${DEPLOY_SA}" --role=roles/storage.objectAdmin
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${BUILD_SA}" --role=roles/storage.objectViewer

gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe forge --workload-identity-pool=github --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc forge \
    --location=global --workload-identity-pool=github \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository == '${GITHUB_REPO}'"

POOL_NAME="$(gcloud iam workload-identity-pools describe github --location=global --format='value(name)')"
PROVIDER_NAME="$(gcloud iam workload-identity-pools providers describe forge --workload-identity-pool=github --location=global --format='value(name)')"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --member="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${GITHUB_REPO}" \
  --role=roles/iam.workloadIdentityUser

printf 'GitHub variable GCP_PROJECT_ID=%s\n' "$PROJECT_ID"
printf 'GitHub variable GCP_REGION=%s\n' "$REGION"
printf 'GitHub variable GCP_WORKLOAD_IDENTITY_PROVIDER=%s\n' "$PROVIDER_NAME"
printf 'GitHub variable GCP_DEPLOY_SERVICE_ACCOUNT=%s\n' "$DEPLOY_SA"
printf 'GitHub variable GCP_BUILD_SERVICE_ACCOUNT=%s\n' "$BUILD_SA"
```

After the first deployment, grant the API permission to execute only the worker job:

```bash
gcloud run jobs add-iam-policy-binding forge-worker --region="$REGION" \
  --member="serviceAccount:${API_SA}" --role=roles/run.invoker
```

Create GitHub **repository variables**, not secrets, for the five printed values plus:
`PUBLIC_BUILD_URL=https://your-app.vercel.app`, `PUBLIC_API_URL` set to the deployed Cloud Run API
URL (or its custom domain), and `WOKWI_SECRET_VERSION=1`. The workflow never accepts a
service-account JSON. Obtain the API URL after an initial deploy with:

```bash
gcloud run services describe forge-api --region="$REGION" --format='value(status.url)'
```

## Vercel

Set the project root to `apps/web`, then configure Preview and Production values:

```bash
vercel env add NEXT_PUBLIC_BUILD_API_URL production
vercel env add NEXT_PUBLIC_FIREBASE_API_KEY production
vercel env add NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN production
vercel env add NEXT_PUBLIC_FIREBASE_PROJECT_ID production
vercel env add NEXT_PUBLIC_FIREBASE_APP_ID production
```

All `NEXT_PUBLIC_*` values are bundled into browser JavaScript and therefore must never contain a
secret. Restrict the Firebase browser API key by API and HTTP referrer in Google Cloud.

## Local development

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
$env:GOOGLE_CLOUD_PROJECT='YOUR_PROJECT_ID'
$env:ARTIFACT_BUCKET='YOUR_PROJECT_ID-forge-artifacts'

# Fetches Wokwi from Secret Manager into the child process only; writes no .env file.
.\scripts\with-gcp-secrets.ps1 -Command npm -CommandArgs @('run','smoke')

# Real, scoped write/read/delete probes for Vertex, Firestore and Storage.
.\.venv\Scripts\python.exe -m hardware_build.integration_check
```

Use `.env.local` only for public frontend development values. The backend deliberately does not load
`.env`; it reads the process environment, Cloud Run injection, and ADC.

## Rotation

Add a new Secret Manager version, change `WOKWI_SECRET_VERSION`, deploy, verify, and then disable the
old version. Cloud Run receives the secret only at instance/job startup, and application logs redact
known secret values and common credential shapes.
