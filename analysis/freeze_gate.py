"""Create and verify a normalized-text hash registry for a frozen protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def normalized_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _git(command: list[str], root: Path) -> str:
    return subprocess.run(["git", *command], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def create_registry(root: Path, protocol_path: Path, registry_path: Path, files: list[Path]) -> None:
    baseline = _git(["rev-parse", "HEAD"], root)
    registry = {
        "status": "frozen_for_confirmatory",
        "code_freeze_commit": baseline,
        "protocol_path": str(protocol_path.as_posix()),
        "entries": [
            {"path": str(path.as_posix()), "normalized_sha256": normalized_sha256(root / path)}
            for path in files
        ],
    }
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def verify_registry(root: Path, registry_path: Path) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("status") != "frozen_for_confirmatory":
        raise RuntimeError("registry is not frozen_for_confirmatory")
    protocol = json.loads((root / registry["protocol_path"]).read_text(encoding="utf-8"))
    if protocol.get("confirmatory_authorized") is not True:
        raise RuntimeError("confirmatory protocol is not authorized")
    _git(["merge-base", "--is-ancestor", registry["code_freeze_commit"], "HEAD"], root)
    if _git(["status", "--porcelain"], root):
        raise RuntimeError("working tree is not clean")
    for entry in registry["entries"]:
        path = root / entry["path"]
        if normalized_sha256(path) != entry["normalized_sha256"]:
            raise RuntimeError(f"freeze hash mismatch: {entry['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--registry", default="protocol/freeze_registry.json")
    parser.add_argument("--protocol", default="protocol/confirmatory_protocol.json")
    parser.add_argument("--files", nargs="*", default=[])
    args = parser.parse_args()
    root = Path(args.root).resolve()
    registry_path = root / args.registry
    if args.action == "create":
        if not args.files:
            raise ValueError("--files is required for create")
        create_registry(root, Path(args.protocol), registry_path, [Path(path) for path in args.files])
        print(f"saved {registry_path}")
    else:
        verify_registry(root, registry_path)
        print("FREEZE_REGISTRY_VERIFY_PASS")


if __name__ == "__main__":
    main()
