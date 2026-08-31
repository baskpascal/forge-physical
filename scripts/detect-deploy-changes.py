from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

DOC_ONLY_ROOTS = ("docs/", ".github/ISSUE_TEMPLATE/")
DOC_ONLY_FILES = {"README.md", "HACKATHON.md", "LICENSE"}
NO_RUNTIME_ROOTS = ("services/build-worker/tests/",)
NO_RUNTIME_FILES = {
    ".gitignore",
    "AGENTS.md",
}

# The API and worker are installed from the same Python package. Only modules
# outside the API import graph may route worker-only. Hardware generation modules
# remain shared until the local API fallback is split from the production API.
WORKER_ONLY_MODULES = {
    "cli.py",
    "integration_check.py",
    "run_job.py",
    "smoke.py",
}
API_ONLY_MODULES = {"api.py", "mcp_server.py"}


def _normalized(raw_path: str) -> str:
    return raw_path.replace("\\", "/").removeprefix("./")


def classify(paths: list[str]) -> dict[str, bool]:
    flags = {"api": False, "worker": False, "web": False, "toolchain": False, "config": False}
    for raw_path in paths:
        path = _normalized(raw_path)
        if (
            not path
            or path in DOC_ONLY_FILES
            or path in NO_RUNTIME_FILES
            or path.startswith(DOC_ONLY_ROOTS + NO_RUNTIME_ROOTS)
        ):
            continue
        if path.startswith("apps/web/"):
            flags["web"] = True
        elif path in {"package.json", "package-lock.json"}:
            # The root npm lockfile only feeds the web image today.
            flags["web"] = True
        elif path == ".dockerignore":
            # This changes every Docker build context even though it is not
            # copied into an image, so conservatively rebuild all runtimes.
            flags.update(api=True, worker=True, web=True)
        elif path.startswith("services/build-worker/tooling/") or path == (
            "services/build-worker/Dockerfile.toolchain"
        ):
            flags["worker"] = True
            flags["toolchain"] = True
        elif path == "services/build-worker/Dockerfile":
            flags["api"] = True
            flags["worker"] = True
        elif path.startswith("services/build-worker/src/hardware_build/"):
            module = path.rsplit("/", 1)[-1]
            if module in WORKER_ONLY_MODULES:
                flags["worker"] = True
            elif module in API_ONLY_MODULES:
                flags["api"] = True
            else:
                # Unknown and transitively shared modules rebuild both runtimes.
                flags["api"] = True
                flags["worker"] = True
        elif path.startswith("services/build-worker/"):
            # pyproject and unknown production package inputs affect both images.
            flags["api"] = True
            flags["worker"] = True
        elif path == "cloudbuild.web.yaml":
            flags["web"] = True
            flags["config"] = True
        elif path == "cloudbuild.image.yaml":
            flags["api"] = True
            flags["worker"] = True
            flags["config"] = True
        elif path.startswith("infra/") or path in {
            "cloudbuild.yaml",
            ".github/workflows/deploy-google-cloud.yml",
            "scripts/detect-deploy-changes.py",
        }:
            flags.update(api=True, worker=True, web=True, config=True)
        elif path.startswith(("scripts/", ".github/")):
            continue
        else:
            # Unknown production inputs fail safe to a full application deploy.
            flags.update(api=True, worker=True, web=True)
    flags["deploy"] = flags["api"] or flags["worker"] or flags["web"]
    return flags


def changed_paths(base: str, head: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head], text=True
    )
    return [line for line in output.splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    paths = args.paths or (changed_paths(args.base, args.head) if args.base else [])
    flags = classify(paths)
    if args.all:
        flags.update(api=True, worker=True, web=True, deploy=True, config=True)
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.writelines(f"{key}={str(value).lower()}\n" for key, value in flags.items())
    print(json.dumps({"paths": paths, **flags}, sort_keys=True))


if __name__ == "__main__":
    main()
