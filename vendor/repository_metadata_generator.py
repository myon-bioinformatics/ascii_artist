#!/usr/bin/env python3
"""Generate canonical repository metadata JSON and JSONL from a Git checkout.

Requires vendored gh_identity.py in the same directory.
"""
from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Mapping
from pathlib import Path
import os
import sys
from types import ModuleType


def _load_gh_identity() -> ModuleType:
    path = Path(__file__).with_name("gh_identity.py")
    spec = importlib.util.spec_from_file_location("gh_identity", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load gh_identity: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


GHI = _load_gh_identity()


def record_from_checkout(
    root: Path,
    full_name: str,
    *,
    env: Mapping[str, str] | None = None,
    github_reported_size_bytes: int | None = None,
    working_tree_bytes: int | None = None,
    release_artifact_bytes: int | None = None,
    tooling: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> dict:
    env = os.environ if env is None else env
    return GHI.repository_metadata_v1(
        root,
        repository=full_name,
        env=env,
        generated_at=generated_at,
        tooling=dict(tooling or {}),
        measurements={
            "github_reported_size_bytes": github_reported_size_bytes,
            "working_tree_bytes": working_tree_bytes,
            "release_artifact_bytes": release_artifact_bytes,
        },
    )


def write_metadata(record: dict, output_dir: Path) -> tuple[Path, Path]:
    paths = GHI.write_repository_metadata(record, output_dir)
    return output_dir / paths["json"], output_dir / paths["jsonl"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/name")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    write_metadata(record_from_checkout(args.root.resolve(), args.repository), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
