#!/usr/bin/env python3
"""
Main validation script for NanoAOD TICL validation.

Usage:
    python validate.py --input file.root --modules distributions,matching
    python validate.py --input "files/*.root" --suite full_validation
    python validate.py --input file.root --collections ticlTrackstersCLUE3DHigh
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import ROOT

from validation.config import ValidationConfig, CollectionConfig, OutputConfig
from validation.core.data_loader import DataLoader
from validation.modules import (
    DistributionsModule,
    MatchingModule,
    EfficiencyModule,
    ResolutionModule,
)
from validation.presets.suites import get_suite, list_suites


# Module registry
MODULE_REGISTRY = {
    "distributions": DistributionsModule,
    "matching": MatchingModule,
    "efficiency": EfficiencyModule,
    "resolution": ResolutionModule,
}


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="NanoAOD TICL Validation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run basic distributions
  python validate.py --input step4.root --modules distributions

  # Full validation suite
  python validate.py --input step4.root --suite full_validation

  # Custom module selection
  python validate.py --input "files/*.root" --modules matching,efficiency

  # Specific collections only
  python validate.py --input step4.root --modules all \\
      --collections ticlTrackstersCLUE3DHigh,TICLCandidates

  # HLT and offline comparison
  python validate.py --input step2.root --modules all --analyze-hlt --analyze-offline
        """
    )

    # Input
    parser.add_argument(
        "--input",
        help="Input file(s). Can be a single file, glob pattern, or comma-separated list."
    )

    # Modules
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--modules",
        help="Comma-separated list of modules to run (or 'all')"
    )
    group.add_argument(
        "--suite",
        choices=list(list_suites().keys()),
        help="Preset validation suite to run"
    )

    # Collections
    parser.add_argument(
        "--collections",
        help="Comma-separated list of collections to analyze (default: all)"
    )

    parser.add_argument(
        "--analyze-hlt",
        action="store_true",
        help="Analyze HLT collections"
    )

    parser.add_argument(
        "--analyze-offline",
        action="store_true",
        default=True,
        help="Analyze offline collections (default: True)"
    )

    # Output
    parser.add_argument(
        "--output",
        default="validation_output",
        help="Output directory (default: validation_output)"
    )

    parser.add_argument(
        "--no-png",
        action="store_true",
        help="Don't save PNG plots"
    )

    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Don't save PDF plots"
    )

    # Configuration
    parser.add_argument(
        "--matching-method",
        choices=["shared_energy", "score"],
        default="shared_energy",
        help="Matching method (default: shared_energy)"
    )

    parser.add_argument(
        "--no-mt",
        action="store_true",
        help="Disable multi-threading"
    )

    parser.add_argument(
        "--threads",
        type=int,
        help="Number of threads (default: auto)"
    )

    # Listing
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="List available validation suites and exit"
    )

    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List available modules and exit"
    )

    return parser.parse_args()


def create_config(args) -> ValidationConfig:
    """Create validation configuration from arguments."""
    config = ValidationConfig()

    # Output configuration
    config.output.output_dir = args.output
    config.output.save_png = not args.no_png
    config.output.save_pdf = not args.no_pdf

    # Multi-threading
    config.enable_mt = not args.no_mt
    if args.threads:
        config.num_threads = args.threads

    # Matching
    config.matching.method = args.matching_method

    # Collections
    if args.collections:
        custom_collections = [c.strip() for c in args.collections.split(",")]
        config.collections.trackster_collections = [
            c for c in custom_collections if "Candidate" not in c
        ]
        config.collections.candidate_collections = [
            c for c in custom_collections if "Candidate" in c
        ]

    config.collections.analyze_hlt = args.analyze_hlt
    config.collections.analyze_offline = args.analyze_offline

    # Modules
    if args.suite:
        config.modules = get_suite(args.suite)
        config.suite = args.suite
    else:
        if args.modules == "all":
            config.modules = list(MODULE_REGISTRY.keys())
        else:
            config.modules = [m.strip() for m in args.modules.split(",")]

    return config


def resolve_module_order(modules: List[str]) -> List[str]:
    """
    Resolve module execution order based on dependencies.

    Args:
        modules: List of module names to run

    Returns:
        Ordered list of modules with dependencies satisfied
    """
    ordered = []
    processed = set()

    def add_module(name: str):
        if name in processed:
            return

        module_class = MODULE_REGISTRY[name]
        module_instance = module_class(None)  # Temporary instance for dependencies

        # Add dependencies first
        for dep in module_instance.get_dependencies():
            if dep in modules and dep not in processed:
                add_module(dep)

        ordered.append(name)
        processed.add(name)

    for module in modules:
        add_module(module)

    return ordered


def run_validation(config: ValidationConfig, input_files: str):
    """
    Run validation pipeline.

    Args:
        config: Validation configuration
        input_files: Input file pattern
    """
    print("=" * 80)
    print("NanoAOD TICL Validation")
    print("=" * 80)

    # Create output directory
    output_dir = Path(config.output.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\nLoading data...")
    loader = DataLoader(config)
    rdf = loader.load_files(input_files)

    # Instantiate modules
    print(f"\nInitializing modules: {', '.join(config.modules)}")
    ordered_modules = resolve_module_order(config.modules)
    print(f"Execution order: {', '.join(ordered_modules)}")

    modules = []
    for module_name in ordered_modules:
        module_class = MODULE_REGISTRY[module_name]
        module = module_class(config)
        modules.append(module)
        print(f"  - {module}")

    # Define columns (all modules)
    print("\nDefining columns...")
    for module in modules:
        print(f"  {module.name}...")
        rdf = module.define_columns(rdf)

    # Get collections to analyze
    collections = config.collections.get_all_collections()
    print(f"\nCollections to analyze: {', '.join(collections)}")

    # Run analysis for each collection
    all_metrics = {}

    for collection in collections:
        print(f"\n{'=' * 80}")
        print(f"Analyzing collection: {collection}")
        print(f"{'=' * 80}")

        # Check if collection exists
        if not loader.collection_exists(rdf, collection):
            print(f"  Warning: Collection {collection} not found in input file. Skipping.")
            continue

        collection_metrics = {}

        # Run each module
        for module in modules:
            print(f"\nRunning module: {module.name}")

            try:
                # Fill histograms
                print("  Filling histograms...")
                histograms = module.fill_histograms(rdf, collection)

                # Trigger computation
                print("  Computing histograms...")
                computed_hists = {k: v.GetValue() for k, v in histograms.items()}

                # Compute metrics
                print("  Computing metrics...")
                metrics = module.compute_metrics(computed_hists, collection)
                collection_metrics.update(metrics)

                # Generate plots
                print("  Generating plots...")
                module_output_dir = output_dir / module.name
                module.plot(computed_hists, metrics, module_output_dir, collection)

            except Exception as e:
                print(f"  Error in module {module.name}: {e}")
                import traceback
                traceback.print_exc()

        all_metrics[collection] = collection_metrics

    # Save summary metrics
    if config.output.save_summary_json:
        summary_file = output_dir / "summary.json"
        print(f"\nSaving summary metrics to {summary_file}")
        with open(summary_file, "w") as f:
            json.dump(all_metrics, f, indent=2)

    print("\n" + "=" * 80)
    print("Validation complete!")
    print(f"Results saved to: {output_dir}")
    print("=" * 80)


def main():
    """Main entry point."""
    args = parse_arguments()

    # Handle listing modes
    if args.list_suites:
        print("Available validation suites:")
        for suite_name, modules in list_suites().items():
            print(f"  {suite_name:20s} : {', '.join(modules)}")
        return 0

    if args.list_modules:
        print("Available modules:")
        for module_name, module_class in MODULE_REGISTRY.items():
            module = module_class(ValidationConfig())
            deps = module.get_dependencies()
            deps_str = f" (depends on: {', '.join(deps)})" if deps else ""
            print(f"  {module_name:20s}{deps_str}")
        return 0

    # Validate required arguments for running validation
    if not args.input:
        print("Error: --input is required (unless using --list-suites or --list-modules)")
        return 1

    if not args.modules and not args.suite:
        print("Error: Either --modules or --suite is required")
        return 1

    # Create configuration
    config = create_config(args)

    # Validate modules
    for module in config.modules:
        if module not in MODULE_REGISTRY:
            print(f"Error: Unknown module '{module}'")
            print(f"Available modules: {', '.join(MODULE_REGISTRY.keys())}")
            return 1

    # Run validation
    try:
        run_validation(config, args.input)
        return 0
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
