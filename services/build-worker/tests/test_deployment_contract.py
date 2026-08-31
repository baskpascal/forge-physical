from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_api_runtime_excludes_hardware_tooling():
    dockerfile = (REPOSITORY_ROOT / "services/build-worker/Dockerfile").read_text(
        encoding="utf-8"
    )
    api_stage = dockerfile.split("FROM runtime-base AS api-runtime", 1)[1].split(
        "ARG TOOLCHAIN_IMAGE", 1
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
