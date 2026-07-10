"""Command-line entry point for the optional lake WQ proxy stage."""
from __future__ import annotations

import argparse

from postfire_runoff.backend.pipeline.lake_wq import run_lake_wq


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run optional lake water-quality proxy screening.")
    parser.add_argument("--config", default="config/project.yaml", help="Project YAML configuration path")
    parser.add_argument("--project-root", default=None, help="Repository/project root override")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_lake_wq(args.config, project_root=args.project_root)
    print(f"Lake WQ status: {result.status}. {result.message}")
    print(f"Status table: {result.status_table}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
