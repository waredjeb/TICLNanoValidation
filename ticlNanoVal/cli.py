"""Command-line entry point: ``ticlval run ...`` (and small listing helpers).

This is a thin driver around :func:`ticlNanoVal.pipeline.run_from_yaml`. LAW tasks
may call this entry point or the pipeline API directly.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional


def _build_overrides(args) -> dict:
    """Translate CLI flags into a config-overrides dict (wins over YAML)."""
    run: dict = {}
    if args.modules:
        run["modules"] = [m.strip() for m in args.modules.split(",") if m.strip()]
    if args.reco_keys:
        run["reco_keys"] = [r.strip() for r in args.reco_keys.split(",") if r.strip()]
    if args.threads is not None:
        run["threads"] = args.threads
    if args.no_mt:
        run["enable_mt"] = False
    overrides: dict = {}
    if run:
        overrides["run"] = run
    if args.strategy:
        overrides["matching"] = {"strategy": args.strategy}
    return overrides


def _cmd_run(args) -> int:
    from .pipeline import run_from_yaml

    overrides = _build_overrides(args)
    summary = run_from_yaml(
        config_paths=args.config,
        input_files=args.input,
        output_dir=args.output,
        overrides=overrides,
    )
    print(f"Done. {len(summary)} collection(s) -> {args.output}/summary.json")
    return 0


def _cmd_list(args) -> int:
    from .matching import available_strategies
    from .modules import available_modules

    print("Modules:    ", ", ".join(available_modules()))
    print("Strategies: ", ", ".join(available_strategies()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ticlval", description="TICL NanoAOD validation")
    p.add_argument(
        "-v", "--verbose", action="store_true", help="debug-level logging"
    )
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run the validation pipeline")
    r.add_argument(
        "-c", "--config", action="append", required=True,
        help="YAML config file; repeat to layer (e.g. base.yaml then offline.yaml)",
    )
    r.add_argument("-i", "--input", required=True, help="input file(s)/glob")
    r.add_argument("-o", "--output", default="validation_output", help="output dir")
    r.add_argument("--modules", help="override modules (comma-separated)")
    r.add_argument("--reco-keys", dest="reco_keys", help="override reco keys (comma-sep)")
    r.add_argument("--strategy", help="override matching strategy")
    r.add_argument("--threads", type=int, help="RDataFrame threads")
    r.add_argument("--no-mt", action="store_true", help="disable implicit MT")
    r.set_defaults(func=_cmd_run)

    l = sub.add_parser("list", help="list available modules and strategies")
    l.set_defaults(func=_cmd_list)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
