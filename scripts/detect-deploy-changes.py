from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def classify(paths: list[str]) -> dict[str, bool]:
    flags = {"api": False, "worker": False, "web": False, "toolchain": False, "config": False}
    ignored_roots = ("docs/", ".github/ISSUE_TEMPLATE/")
    ignored_files = {"README.md", "HACKATHON.md", "LICENSE"}
    for raw_path in paths:
        path = raw_path.replace("\\", "/").lstrip("./")
        if not path or path in ignored_files or path.startswith(ignored_roots):
            continue
        if path.startswith("apps/web/") or path in {"package.json", "package-lock.json"}:
            flags["web"] = True
        elif path.startswith("services/build-worker/tooling/") or path.endswith("Dockerfile.toolchain"):
            flags["worker"] = True
            flags["toolchain"] = True
        elif path.startswith("services/build-worker/"):
            # API and worker currently share one audited Python package. Rebuild both for package
            # changes; tooling is isolated above so ordinary app changes never rebuild toolchains.
            flags["api"] = True
            flags["worker"] = True
        elif path.startswith(("infra/", "cloudbuild")) or path == ".github/workflows/deploy-google-cloud.yml":
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
