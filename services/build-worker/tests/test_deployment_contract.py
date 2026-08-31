from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_api_runtime_excludes_hardware_tooling():
    dockerfile = (REPOSITORY_ROOT / "services/build-worker/Dockerfile").read_text(
        encoding="utf-8"
    )
    api_stage = dockerfile.split("FROM runtime-base AS api-runtime", 1)[1].split(
        "FROM ${TOOLCHAIN_IMAGE} AS tooling-runtime", 1
    )[0]

    assert "platformio" not in api_stage.lower()
    assert "wokwi" not in api_stage.lower()
    assert "/root/.platformio" not in api_stage


def test_worker_runtime_keeps_prewarmed_hardware_tooling():
    dockerfile = (REPOSITORY_ROOT / "services/build-worker/Dockerfile").read_text(
        encoding="utf-8"
    )
    worker_stage = dockerfile.split("FROM runtime-base AS worker-runtime", 1)[1]

    assert "PLATFORMIO_CMD=/opt/platformio-venv/bin/platformio" in worker_stage
    assert "COPY --from=tooling-runtime /usr/local/bin/wokwi-cli" in worker_stage
    assert "COPY --from=tooling-runtime --chown=forge:forge /root/.platformio" in worker_stage


def test_cloud_build_publishes_and_deploys_distinct_runtime_images():
    cloudbuild = (REPOSITORY_ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")

    assert "--target api-runtime" in cloudbuild
    assert "--target worker-runtime" in cloudbuild
    assert "${_REPOSITORY}/api:${_IMAGE_TAG}" in cloudbuild
    assert "${_REPOSITORY}/worker:${_IMAGE_TAG}" in cloudbuild
    assert "api-deploy" in cloudbuild
    assert "worker-deploy" in cloudbuild
    assert "waitFor: [api-push]" in cloudbuild
    assert "waitFor: [worker-push]" in cloudbuild


def test_cloud_build_builders_do_not_call_gcloud():
    cloudbuild = (REPOSITORY_ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    worker_build = cloudbuild.split("- id: worker-build", 1)[1].split(
        "- id: web-build", 1
    )[0]

    assert "gcloud " not in worker_build
    assert "docker build" in worker_build


def test_worker_deploy_skips_unchanged_image_and_uses_job_image_path():
    cloudbuild = (REPOSITORY_ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    worker_deploy = cloudbuild.split("- id: worker-deploy", 1)[1].split(
        "- id: api-deploy", 1
    )[0]

    assert "spec.template.spec.template.spec.containers[0].image" in worker_deploy
    assert "worker image/config unchanged; skipping revision" in worker_deploy
    assert "gcloud artifacts docker images describe" in worker_deploy


def test_remote_cache_is_best_effort_and_embedded_in_images():
    for filename in ("cloudbuild.yaml", "cloudbuild.image.yaml", "cloudbuild.web.yaml"):
        cloudbuild = (REPOSITORY_ROOT / filename).read_text(encoding="utf-8")
        assert "--cache-from" in cloudbuild
        assert "BUILDKIT_INLINE_CACHE=1" in cloudbuild
        assert "docker pull" in cloudbuild and "|| true" in cloudbuild


def test_builds_and_deploys_have_explicit_parallel_dependencies():
    cloudbuild = (REPOSITORY_ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")

    assert "id: api-build" in cloudbuild and "waitFor: ['-']" in cloudbuild
    assert "id: web-build" in cloudbuild
    assert "waitFor: [toolchain-push]" in cloudbuild
    assert "waitFor: [api-build]" in cloudbuild
    assert "waitFor: [worker-build]" in cloudbuild
    assert "waitFor: [web-build]" in cloudbuild
    assert "waitFor: [web-push]" in cloudbuild


def test_stable_toolchain_is_not_rebuilt_for_python_changes():
    dockerfile = (REPOSITORY_ROOT / "services/build-worker/Dockerfile.toolchain").read_text(
        encoding="utf-8"
    )
    cloudbuild = (REPOSITORY_ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")

    assert "platformio==6.1.19" in dockerfile
    assert "espressif32@6.12.0" in dockerfile
    assert "sha256sum --check --strict" in dockerfile
    assert "_BUILD_TOOLCHAIN: 'false'" in cloudbuild
    assert "coup-worker-toolchain:${_TOOLCHAIN_VERSION}" in cloudbuild


def test_terraform_assigns_each_image_to_the_correct_runtime():
    variables = (REPOSITORY_ROOT / "infra/variables.tf").read_text(encoding="utf-8")
    terraform = (REPOSITORY_ROOT / "infra/main.tf").read_text(encoding="utf-8")

    assert 'variable "api_image"' in variables
    assert 'variable "worker_image"' in variables
    assert "image   = var.worker_image" in terraform
    assert "image = var.api_image" in terraform
