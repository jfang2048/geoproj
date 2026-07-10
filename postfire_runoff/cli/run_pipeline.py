"""Command-line entry point for the post-fire runoff pipeline."""
from __future__ import annotations

import argparse
import sys

from postfire_runoff.backend.pipeline.runoff import PipelineError, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the post-fire SCS-CN runoff pipeline.")
    parser.add_argument("--config", default="config/project.yaml", help="Project YAML configuration path")
    parser.add_argument("--project-root", default=None, help="Repository/project root override")
    parser.add_argument("--force", action="store_true", help="Overwrite canonical generated outputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_pipeline(args.config, project_root=args.project_root, force=args.force)
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Pipeline {result.status}. Metadata: {result.metadata_path}")
    for name, path in result.outputs.items():
        print(f"{name}: {path}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
