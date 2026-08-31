from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from uuid import uuid4

import google.auth
from google import genai
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import firestore, storage

from .security import redact_text
from .settings import Settings, get_settings
from .simulation import run_wokwi, wokwi_token_is_valid


def _result(status: str, detail: str) -> dict[str, object]:
    return {"implemented": True, "status": status, "detail": detail}


def _adc(settings: Settings) -> tuple[object | None, dict | None]:
    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials, None
    except DefaultCredentialsError as exc:
        return None, _result(
            "unavailable_due_to_missing_credentials",
            redact_text(str(exc), settings),
        )


def check_vertex(settings: Settings, adc_error: dict | None) -> dict:
    if not settings.google_cloud_project:
        return _result("unavailable_due_to_missing_configuration", "GOOGLE_CLOUD_PROJECT is unset.")
    if adc_error:
        return adc_error
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )
        started = time.monotonic()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents="Reply with exactly: FORGE_VERTEX_OK",
        )
        if "FORGE_VERTEX_OK" not in (response.text or ""):
            return _result("runtime_failed", "Vertex AI responded, but the verification marker was absent.")
        result = _result(
            "runtime_verified",
            f"Vertex AI generated content with {settings.gemini_model} in {settings.vertex_location}.",
        )
        result.update(
            project=settings.google_cloud_project,
            model=settings.gemini_model,
            location=settings.vertex_location,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as exc:
        return _result("runtime_failed", redact_text(f"{type(exc).__name__}: {exc}", settings))


def check_firestore(settings: Settings, adc_error: dict | None) -> dict:
    if not settings.google_cloud_project:
        return _result("unavailable_due_to_missing_configuration", "GOOGLE_CLOUD_PROJECT is unset.")
    if adc_error:
        return adc_error
    document = None
    try:
        document = firestore.Client(project=settings.google_cloud_project).collection(
            "_forge_runtime_checks"
        ).document(uuid4().hex)
        document.set({"probe": "firestore", "ephemeral": True})
        if document.get().to_dict().get("probe") != "firestore":
            return _result("runtime_failed", "Firestore read-back did not match the probe.")
        document.delete()
        return _result("runtime_verified", "Firestore write, read, and delete succeeded.")
    except Exception as exc:
        if document is not None:
            try:
                document.delete()
            except Exception:
                pass
        return _result("runtime_failed", redact_text(f"{type(exc).__name__}: {exc}", settings))


def check_storage(settings: Settings, adc_error: dict | None) -> dict:
    if not settings.artifact_bucket:
        return _result("unavailable_due_to_missing_configuration", "ARTIFACT_BUCKET is unset.")
    if adc_error:
        return adc_error
    blob = None
    try:
        blob = storage.Client(project=settings.google_cloud_project).bucket(
            settings.artifact_bucket
        ).blob(f"_forge_runtime_checks/{uuid4().hex}.txt")
        blob.upload_from_string("forge-storage-ok", content_type="text/plain")
        if blob.download_as_text() != "forge-storage-ok":
            return _result("runtime_failed", "Cloud Storage read-back did not match the probe.")
        blob.delete()
        return _result("runtime_verified", "Cloud Storage upload, download, and delete succeeded.")
    except Exception as exc:
        if blob is not None:
            try:
                blob.delete()
            except Exception:
                pass
        return _result("runtime_failed", redact_text(f"{type(exc).__name__}: {exc}", settings))


def check_wokwi(settings: Settings, project: Path | None, verified_build_id: str | None = None) -> dict:
    if not settings.wokwi_cli_token:
        return _result(
            "unavailable_due_to_missing_credentials",
            "WOKWI_CLI_TOKEN was not injected from Secret Manager.",
        )
    if not wokwi_token_is_valid(settings.wokwi_cli_token):
        return _result(
            "unavailable_due_to_invalid_credentials",
            "WOKWI_CLI_TOKEN is present but does not match the documented Wokwi CI token format.",
        )
    if not shutil.which(settings.wokwi_cli_cmd):
        return _result("unavailable_due_to_missing_configuration", "wokwi-cli is not installed.")
    if verified_build_id:
        if not settings.google_cloud_project:
            return _result("unavailable_due_to_missing_configuration", "GOOGLE_CLOUD_PROJECT is unset.")
        try:
            snapshot = firestore.Client(project=settings.google_cloud_project).collection("builds").document(verified_build_id).get()
            build = snapshot.to_dict() if snapshot.exists else None
            simulation = build.get("simulation", {}) if build else {}
            evidence = simulation.get("evidence", {})
            required = {"COUP_READY", "TEMP_NORMAL", "TEMP_ALERT", "COUP_TEST_PASS"}
            observed = set(evidence.get("expected_serial", []))
            if (
                build
                and build.get("status") == "completed"
                and simulation.get("status") == "passed"
                and evidence.get("lint_exit_code") == 0
                and evidence.get("validation_passed") is True
                and required <= observed
            ):
                result = _result("runtime_verified", "Wokwi CLI lint and temperature-alarm scenario were verified in a production worker build.")
                result.update(build_id=verified_build_id, checks=evidence.get("checks", []))
                return result
            return _result("runtime_failed", "The referenced build lacks complete Wokwi lint, scenario, and behavioral-validation evidence.")
        except Exception as exc:
            return _result("runtime_failed", redact_text(f"{type(exc).__name__}: {exc}", settings))
    if project is None:
        return _result(
            "configured",
            "Token and CLI are present; pass --wokwi-project to execute a token-backed scenario.",
        )
    result = run_wokwi(settings, project.resolve(), firmware_passed=True)
    if result.status == "passed":
        return _result("runtime_verified", "Wokwi token-backed scenario completed successfully.")
    return _result("runtime_failed", redact_text(result.summary, settings))


def run_checks(settings: Settings, wokwi_project: Path | None = None, verified_build_id: str | None = None) -> dict:
    _, adc_error = _adc(settings)
    return {
        "vertex_ai": check_vertex(settings, adc_error),
        "firestore": check_firestore(settings, adc_error),
        "cloud_storage": check_storage(settings, adc_error),
        "wokwi": check_wokwi(settings, wokwi_project, verified_build_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real cloud integration probes.")
    parser.add_argument("--wokwi-project", type=Path)
    parser.add_argument("--verified-build-id")
    args = parser.parse_args()
    print(json.dumps(run_checks(get_settings(), args.wokwi_project, args.verified_build_id), indent=2))


if __name__ == "__main__":
    main()
