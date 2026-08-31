# COUP deployment performance

This document keeps deployment optimization measurable. Cloud Build step IDs are phase
boundaries, and the GitHub workflow writes GitHub setup/auth, source submission, and every
Cloud Build step duration to the Actions job summary.

## Measured baseline

The pre-optimization full deployment baseline is GitHub Actions run
[`33428344015`](https://github.com/baskpascal/forge-physical/actions/runs/33428344015) and
Cloud Build `9134ba70-b080-4eea-be0b-f4227ff3d6a6` (commit `cd938d9`). It used the default
Cloud Build machine, no remote Docker cache, and serial build/push/deploy steps.

| Phase | Baseline |
|---|---:|
| GitHub checkout + WIF auth + gcloud setup/verification | 11 s |
| Source upload/submission | ~2 s |
| Cloud Build source fetch | 3.8 s |
| API Docker build | 125.3 s |
| API push | 40.3 s |
| Worker Docker build | 279.5 s |
| Worker push | 229.5 s |
| Web Docker build | 162.8 s |
| Web push | 7.9 s |
| Cloud Run Job deploy | 85.4 s |
| API Cloud Run deploy | 59.8 s |
| Web Cloud Run deploy | 15.1 s |
| **Full Cloud Build wall clock** | **1,020.5 s (17:00.5)** |

The first selective/cached build on `E2_HIGHCPU_8`, Cloud Build
`8d21f6ef-eefe-4116-98bd-eda36b9ec4b1`, confirmed parallel API/web/toolchain starts. It
measured API build 95.7 s and web build 100.1 s, versus 125.3 s and 162.8 s in the baseline.
That run intentionally rebuilt the previously absent toolchain image (163.5 s build plus
143.9 s initial push) and then failed because `worker-build` invoked `gcloud` from the Docker
builder. The pipeline now performs that digest check in the Cloud SDK deployment step.
Because cache state and machine type both changed, these figures are directional evidence,
not a controlled machine-size A/B test.

The first successful optimized full deployment is GitHub Actions run
[`33438745298`](https://github.com/baskpascal/forge-physical/actions/runs/33438745298) and
Cloud Build `c13d5fcc-295d-4ce5-9e6b-c7dd4dc080a1` (commit `e913a19`). Its Cloud Build wall
clock was 488.5 s (8:08.5), a 52% reduction from the 17:00.5 baseline. The end-to-end
Actions run took about 9:43, including a roughly 60 s Cloud Build queue delay. It narrowly
missed the <=8 min p95 target because worker build and push remained the critical path:

| Phase | Baseline | First successful optimized | Change |
|---|---:|---:|---:|
| API Docker build | 125.3 s | 148.5 s | +19% |
| API push | 40.3 s | 53.1 s | +32% |
| Worker Docker build | 279.5 s | 278.9 s | ~0% |
| Worker push | 229.5 s | 187.0 s | -19% |
| Web Docker build | 162.8 s | 141.0 s | -13% |
| Web push | 7.9 s | 9.4 s | +19% |
| Cloud Run Job deploy | 85.4 s | 13.2 s | -85% |
| API Cloud Run deploy | 59.8 s | 69.9 s | +17% |
| Web Cloud Run deploy | 15.1 s | 92.0 s | +509% |
| **Cloud Build wall clock** | **1,020.5 s** | **488.5 s** | **-52%** |

The phase comparison is intentionally not presented as a controlled per-step A/B: cache
state, deploy state, and machine type differ. Wall-clock is the production outcome. The
worker result exposed that the application image copied `/root/.platformio` out of the
toolchain image, repacking and re-uploading the largest filesystem tree for every Python
change. Version `v2` makes the toolchain the worker's direct parent image and adds only the
application virtualenv above it. This preserves the real preheated compiler while allowing
Artifact Registry to reuse the stable base layers. A successful production run is still
required before claiming the resulting worker build/push reduction as measured.

The branch benchmark submission also exposed a local-source packaging issue: Terraform's
downloaded provider directory was entering the upload and Docker build context. Adding it
to both ignore contracts reduced `gcloud meta list-files-for-upload` from 246.2 MiB to
1.05 MiB (112 files). The first branch run had already uploaded the large archive; subsequent
runs use the corrected context and are the valid source-upload comparison.

The first v2 cold production build, `cbebb1d9-3b4a-4ea9-a58a-f0bfaace7559`, completed
successfully in 703.2 s (11:43.2) after 55.9 s of Cloud Build queueing. It intentionally
created and pushed the new toolchain: 292.0 s build plus 199.3 s push. Even in that cold
run, direct layer ancestry reduced worker push from 187.0 s to 39.2 s (79%). API, worker,
and web builds were 123.8 s, 153.8 s, and 124.2 s. This cold migration run is not the normal
full-deploy after value; it demonstrates both the one-time toolchain cost and the worker
layer fix. The worker/API packaging now also installs third-party Python dependencies in a
stable layer and the application itself from a small wheel layer, so source-only changes do
not repack the full Google ADK virtualenv.

## Deployment routing and cache contract

- Documentation and tests do not deploy production.
- Web application and root npm lockfile changes build/deploy only `forge-web`.
- Worker-only hardware modules build/deploy only `forge-worker`.
- Shared queue/storage/model/package changes build both API and worker.
- Stable tooling changes rebuild the pinned `coup-worker-toolchain` and then the worker.
- Infrastructure and primary deployment-pipeline changes fail safe to a full deployment.
- Application images use the immutable commit SHA tag. Mutable `cache` tags are only
  best-effort layer sources; a missing cache never fails a build.
- Cloud Run skips a new service/job revision when both effective image digest and runtime
  configuration are unchanged.

The toolchain version is intentionally explicit in `cloudbuild.yaml`. Any PlatformIO,
Espressif32, approved library, Wokwi version/SHA, or toolchain Dockerfile change must bump
`_TOOLCHAIN_VERSION`. This makes rollback auditable and keeps ordinary Python changes on the
thin worker application layer.

## Machine cost/performance tradeoff

`E2_HIGHCPU_8` increases compute used while Cloud Build is active, but API, worker, and web
builds can use the additional CPU concurrently. The measured cached API and web phase
reductions were 24% and 39%, respectively. A controlled same-source, same-cache A/B run is
still needed before attributing the whole reduction to machine size. For the hackathon the
wall-clock reduction is worth the bounded build-time compute; post-hackathon, compare total
vCPU-seconds and cost using identical warm-cache builds before retaining it permanently.

## Reproduce the benchmark

After this branch is merged, trigger one full deploy, then web-only, API-only, and worker-only
commits. Do not reuse numbers from unrelated cache states.

```bash
gcloud builds describe BUILD_ID --format=json > build.json
gcloud builds describe BUILD_ID \
  --format='table(steps.id,steps.status,steps.timing.startTime,steps.timing.endTime)'
```

For exact wall clock, subtract `createTime` from `finishTime`. For each phase, subtract its
`timing.startTime` from `timing.endTime`. The Actions run summary contains WIF/setup and
source-upload time. Report cache state and whether the stable toolchain was rebuilt with
every number.

Target acceptance remains:

| Route | Target |
|---|---:|
| Full deploy, p50 | <= 5 min |
| Full deploy, p95 | <= 8 min |
| Web only | <= 2-3 min (ideal <= 2 min) |
| API only | no web rebuild |
| Worker only | no API/web rebuild |
| Docs only | no production deploy |

Final after-values must come from successful production runs; no projected number should be
presented as measured.
