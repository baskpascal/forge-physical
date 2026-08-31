from __future__ import annotations

import io
import logging
import re
import zipfile
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from google.cloud import storage

from .artifacts import (
    artifact_files,
    artifact_media_type,
    build_public_artifact_paths,
    public_artifact_path,
)
from .mcp_server import mcp
from .models import StartBuildRequest, UpdateBuildRequest
from .orchestrator import run_build
from .service import artifacts_payload, create_build, status_payload, update_build
from .settings import get_settings
from .simulation import wokwi_token_is_valid
from .storage import (
    BuildAdmissionRejected,
    BuildAdmissionUnavailable,
    BuildNotFoundError,
    get_store,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


settings = get_settings()
logger = logging.getLogger("forge.api")
app = FastAPI(title="Forge Physical API", version="0.1.0", lifespan=lifespan)
_BUILD_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        settings.public_build_url.rstrip("/"),
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.get("/")
def root() -> dict:
    return {"service": "forge-physical", "status": "ready", "mcp": "/mcp"}


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "integrations": {
            "vertex_ai": {"status": "configured" if settings.gemini_configured else "implemented"},
            "firestore": {"status": "configured" if settings.build_store == "firestore" and settings.google_cloud_project else "implemented"},
            "cloud_storage": {"status": "configured" if settings.artifact_bucket else "implemented"},
            "wokwi": {
                "status": (
                    "configured"
                    if wokwi_token_is_valid(settings.wokwi_cli_token)
                    else "invalid_credentials"
                    if settings.wokwi_cli_token
                    else "implemented"
                )
            },
        },
        "admission": {
            "status": "enabled"
            if settings.build_max_concurrent > 0 or settings.build_request_budget > 0
            else "disabled",
            "max_concurrent": settings.build_max_concurrent,
            "request_budget": settings.build_request_budget,
            "window_seconds": settings.build_request_window_seconds,
        },
        "note": "Configuration is not runtime verification. Run python -m hardware_build.integration_check.",
    }


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _admission_http_error(exc: BuildAdmissionRejected) -> HTTPException:
    logger.warning("Build admission rejected", extra={"reason": exc.reason})
    return HTTPException(
        status_code=429,
        detail="Per-client build request limit reached. Retry after the indicated delay.",
        headers={"Retry-After": str(exc.retry_after)},
    )


def _admission_unavailable_error() -> HTTPException:
    logger.error("Build admission storage unavailable")
    return HTTPException(
        status_code=503,
        detail="Build admission is temporarily unavailable. Retry shortly.",
        headers={"Retry-After": "30"},
    )


@app.post("/api/builds", status_code=202)
def start(payload: StartBuildRequest, request: Request) -> dict:
    try:
        return create_build(payload.prompt, client_key=_client_key(request)).model_dump(mode="json")
    except BuildAdmissionRejected as exc:
        raise _admission_http_error(exc) from exc
    except BuildAdmissionUnavailable as exc:
        raise _admission_unavailable_error() from exc


@app.post("/api/builds/{build_id}/updates", status_code=202)
def update(build_id: str, payload: UpdateBuildRequest, request: Request) -> dict:
    try:
        return update_build(
            build_id,
            payload.change,
            client_key=_client_key(request),
        ).model_dump(mode="json")
    except BuildAdmissionRejected as exc:
        raise _admission_http_error(exc) from exc
    except BuildAdmissionUnavailable as exc:
        raise _admission_unavailable_error() from exc
    except BuildNotFoundError as exc:
        raise HTTPException(404, "Build not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/builds/{build_id}")
def status(build_id: str) -> dict:
    try:
        return status_payload(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(404, "Build not found") from exc


@app.get("/api/builds/{build_id}/artifacts")
def artifacts(build_id: str) -> dict:
    try:
        return artifacts_payload(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(404, "Build not found") from exc


@app.get("/api/builds/{build_id}/artifacts.zip")
def artifact_archive(build_id: str) -> StreamingResponse:
    if not _BUILD_ID_PATTERN.fullmatch(build_id):
        raise HTTPException(404, "Artifacts not found")
    try:
        build = get_store().get(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(404, "Build not found") from exc
    allowed_paths = build_public_artifact_paths(build)
    if not allowed_paths:
        raise HTTPException(404, "No artifacts are available yet")

    settings = get_settings()
    root = (settings.build_artifact_dir / build_id).resolve()
    buffer = io.BytesIO()
    archived = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if root.exists():
            for path in artifact_files(root):
                relative = path.relative_to(root).as_posix()
                if relative in allowed_paths:
                    archive.write(path, relative)
                    archived += 1
        elif settings.artifact_bucket:
            blobs = list(storage.Client().list_blobs(settings.artifact_bucket, prefix=f"{build_id}/"))
            blobs = [
                blob
                for blob in blobs
                if blob.name.removeprefix(f"{build_id}/") in allowed_paths
            ]
            if not blobs:
                raise HTTPException(404, "No artifacts are available yet")
            for blob in blobs:
                archive.writestr(blob.name.removeprefix(f"{build_id}/"), blob.download_as_bytes())
                archived += 1
        else:
            raise HTTPException(404, "No artifacts are available yet")
    if archived == 0:
        raise HTTPException(404, "No artifacts are available yet")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="forge-{build_id}.zip"'})


@app.get("/api/builds/{build_id}/artifacts/{artifact_path:path}")
def artifact(build_id: str, artifact_path: str) -> Response:
    """Serve a single public build artifact without exposing the storage backend."""
    if not _BUILD_ID_PATTERN.fullmatch(build_id):
        raise HTTPException(404, "Artifact not found")
    canonical = public_artifact_path(artifact_path)
    if canonical is None:
        raise HTTPException(404, "Artifact not found")
    try:
        build = get_store().get(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(404, "Build not found") from exc
    if canonical not in build_public_artifact_paths(build):
        raise HTTPException(404, "Artifact not found")

    settings = get_settings()
    build_root = (settings.build_artifact_dir / build_id).resolve()
    local_path = (build_root / canonical).resolve()
    if local_path.is_relative_to(build_root) and local_path.is_file():
        return FileResponse(local_path, media_type=artifact_media_type(canonical))

    if settings.artifact_bucket:
        blob = storage.Client().bucket(settings.artifact_bucket).blob(f"{build_id}/{canonical}")
        if blob.exists():
            return Response(
                content=blob.download_as_bytes(),
                media_type=artifact_media_type(canonical),
            )

    raise HTTPException(404, "Artifact is not available yet")


@app.post("/internal/run/{build_id}", status_code=202)
def internal_run(build_id: str, authorization: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if not settings.internal_worker_token:
        raise HTTPException(503, "HTTP worker dispatch is disabled")
    if authorization != f"Bearer {settings.internal_worker_token}":
        raise HTTPException(401, "Invalid worker token")
    import threading
    threading.Thread(target=run_build, args=(build_id,), daemon=True, name=f"build-{build_id}").start()
    return {"build_id": build_id, "status": "dispatched"}


app.mount("/", mcp.streamable_http_app())


def run() -> None:
    uvicorn.run("hardware_build.api:app", host="0.0.0.0", port=8080)
