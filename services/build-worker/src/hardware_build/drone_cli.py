from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from .drone import (
    DroneScopeError,
    build_version,
    create_version,
    init_project,
    load_state,
    test_version,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="coup", description="COUP Drone Alpha")
    parser.add_argument("--project", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init").add_argument("path", nargs="?", default=".")
    for name in ("create", "change"):
        command = commands.add_parser(name)
        command.add_argument("intent")
    for name in ("build", "test", "status", "open"):
        command = commands.add_parser(name)
        command.add_argument("--build")
    commands.choices["test"].add_argument("--endpoint", default="udpin://0.0.0.0:14540")
    commands.choices["test"].add_argument("--launcher", help="Pinned PX4 SIH launcher command; alternatively set COUP_PX4_SITL_COMMAND.")
    args = parser.parse_args()
    try:
        root = Path(args.path if args.command == "init" else args.project)
        if args.command == "init":
            init_project(root)
            print(f"Initialized COUP Quad Alpha in {root.resolve()}")
            return
        if args.command in {"create", "change"}:
            record = create_version(root, args.intent)
            print(f"Created BUILD {record['id']} ({record['spec']['stability']} stability, {record['spec']['responsiveness']} responsiveness)")
            return
        if args.command == "build":
            record = build_version(root, args.build)
        elif args.command == "test":
            record = test_version(root, args.build, args.endpoint, args.launcher)
        else:
            state = load_state(root)
            record = next((item for item in state["builds"] if item["id"] == (args.build or state["builds"][-1]["id"])), None)
            if not record:
                raise DroneScopeError("Build not found.")
            if args.command == "open":
                webbrowser.open(Path(record["root"]).as_uri())
                return
        print(json.dumps(record, indent=2))
    except DroneScopeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
