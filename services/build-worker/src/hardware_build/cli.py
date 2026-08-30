from __future__ import annotations

import argparse
import io
import os
import webbrowser
import zipfile
from pathlib import Path

import httpx


def _safe_extract(data: bytes, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if destination not in target.parents and target != destination:
                raise ValueError("Artifact archive contains an unsafe path")
        archive.extractall(destination)


def main() -> None:
    parser = argparse.ArgumentParser(prog="hardware", description="Open or pull Forge Physical builds")
    parser.add_argument("command", choices=["open", "pull"])
    parser.add_argument("build_id")
    parser.add_argument("--url", default=os.getenv("FORGE_URL", "http://localhost:3000"))
    parser.add_argument("--api-url", default=os.getenv("FORGE_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--destination", default=".")
    args = parser.parse_args()
    if args.command == "open":
        webbrowser.open(f"{args.url.rstrip('/')}/build/{args.build_id}")
        return
    response = httpx.get(f"{args.api_url.rstrip('/')}/api/builds/{args.build_id}/artifacts.zip", timeout=120)
    response.raise_for_status()
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    _safe_extract(response.content, destination)
    print(f"Pulled build {args.build_id} into {destination.resolve()}")
