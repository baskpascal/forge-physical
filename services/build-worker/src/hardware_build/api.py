from __future__ import annotations

import io
import re
import zipfile
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException
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
from .storage import BuildNotFoundError, get_store


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


settings = get_settings()
app = FastAPI(title="Forge Physical API", version="0.1.0", lifespan=lifespan)
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
            "wokwi": {"status": "configured" if settings.wokwi_cli_token else "implemented"},
        },
        "note": "Configuration is not runtime verification. Run python -m hardware_build.integration_check.",
    }


@app.post("/api/builds", status_code=202)
def start(request: StartBuildRequest) -> dict:
    return create_build(request.prompt).model_dump(mode="json")


@app.post("/api/builds/{build_id}/updates", status_code=202)
def update(build_id: str, request: UpdateBuildRequest) -> dict:
    try:
        return update_build(build_id, request.change).model_dump(mode="json")
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
    settings = get_settings()
    root = (settings.build_artifact_dir / build_id).resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if root.exists():
            for path in artifact_files(root):
                archive.write(path, path.relative_to(root))
        elif settings.artifact_bucket:
            blobs = list(storage.Client().list_blobs(settings.artifact_bucket, prefix=f"{build_id}/"))
            if not blobs:
                raise HTTPException(404, "No artifacts are available yet")
            for blob in blobs:
                archive.writestr(blob.name.removeprefix(f"{build_id}/"), blob.download_as_bytes())
        else:
            raise HTTPException(404, "No artifacts are available yet")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="forge-{build_id}.zip"'})


@app.get("/api/builds/{build_id}/artifacts/{artifact_path:path}")
def artifact(build_id: str, artifact_path: str) -> Response:
    """Serve a single public build artifact without exposing the storage backend."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", build_id):
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
