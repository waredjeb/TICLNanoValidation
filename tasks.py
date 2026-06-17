"""
LAW tasks for TICL NanoAOD Validation.

This module defines LAW tasks for running validation workflows,
including single-file validation, batch processing, and HTCondor submission.
"""

import os
import json
import glob
import law
import luigi
from pathlib import Path

# Load HTCondor contrib if available
try:
    from framework import HTCondorWorkflow
    HTCONDOR_AVAILABLE = True
except Exception:
    HTCONDOR_AVAILABLE = False


class TICLValidationTask(law.Task):
    """Base task for TICL validation with common parameters."""

    # Input/output configuration
    input_file = luigi.Parameter(
        description="Input NanoAOD file path or pattern"
    )
    output_dir = luigi.Parameter(
        default="validation_output",
        description="Base output directory"
    )

    # Validation configuration
    modules = luigi.ListParameter(
        default=["distributions", "matching", "efficiency", "resolution"],
        description="List of validation modules to run"
    )
    suite = luigi.Parameter(
        default="",
        description="Validation suite name (overrides modules if set)"
    )
    analyze_hlt = luigi.BoolParameter(
        default=False,
        description="Analyze HLT collections instead of offline"
    )
    matching_method = luigi.Parameter(
        default="shared_energy",
        description="Matching method: shared_energy or score"
    )
    threads = luigi.IntParameter(
        default=4,
        description="Number of threads for RDataFrame"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the directory where this script is located
        self.base_dir = Path(__file__).parent.absolute()


class ValidateSingleFile(TICLValidationTask):
    """
    Run validation on a single NanoAOD file.

    This task runs the validation framework on a single input file
    and produces plots and metrics in the output directory.
    """

    def output(self):
        """Define output target."""
        return law.LocalFileTarget(
            os.path.join(self.output_dir, "summary.json")
        )

    def run(self):
        """Run validation on single file."""
        # Build command - cd to base dir first
        cmd = [
            f"cd {self.base_dir} &&",
            "python3 validate.py",
            "--input", os.path.abspath(self.input_file),
            "--output", os.path.abspath(self.output_dir),
            "--threads", str(self.threads),
            "--matching-method", self.matching_method,
        ]

        # Add suite or modules
        if self.suite:
            cmd.extend(["--suite", self.suite])
        else:
            cmd.extend(["--modules", ",".join(self.modules)])

        # Add HLT flag if needed
        if self.analyze_hlt:
            cmd.append("--analyze-hlt")

        # Run command
        law.util.interruptable_popen(
            " ".join(cmd),
            shell=True,
            executable="/bin/bash"
        )


class ValidateMultipleFiles(TICLValidationTask, law.LocalWorkflow):
    """
    Run validation on multiple NanoAOD files in parallel.

    This task discovers all files matching the input pattern and
    creates one branch per file for parallel processing.
    """

    max_files = luigi.IntParameter(
        default=-1,
        description="Maximum number of files to process (-1 for all)"
    )

    def create_branch_map(self):
        """Create one branch per input file."""
        # Find all matching files
        files = glob.glob(self.input_file)

        if self.max_files > 0:
            files = files[:self.max_files]

        # Create branch map
        branch_map = {}
        for i, file_path in enumerate(files):
            file_name = Path(file_path).stem
            branch_map[i] = {
                "file": file_path,
                "output": os.path.join(self.output_dir, f"file_{i}_{file_name}")
            }

        return branch_map

    def output(self):
        """Define output for this branch."""
        branch_data = self.branch_map[self.branch]
        return law.LocalFileTarget(
            os.path.join(branch_data["output"], "summary.json")
        )

    def run(self):
        """Run validation for this branch's file."""
        branch_data = self.branch_map[self.branch]

        # Build command - cd to base dir first
        cmd = [
            f"cd {self.base_dir} &&",
            "python3 validate.py",
            "--input", os.path.abspath(branch_data["file"]),
            "--output", os.path.abspath(branch_data["output"]),
            "--threads", str(self.threads),
            "--matching-method", self.matching_method,
        ]

        # Add suite or modules
        if self.suite:
            cmd.extend(["--suite", self.suite])
        else:
            cmd.extend(["--modules", ",".join(self.modules)])

        # Add HLT flag if needed
        if self.analyze_hlt:
            cmd.append("--analyze-hlt")

        # Run command
        law.util.interruptable_popen(
            " ".join(cmd),
            shell=True,
            executable="/bin/bash"
        )


# Only define HTCondor task if contrib is available
if HTCONDOR_AVAILABLE:
    class ValidateMultipleFilesHTCondor(ValidateMultipleFiles, HTCondorWorkflow):
        """
        Run validation on multiple files using HTCondor.

        This task submits validation jobs to HTCondor for parallel processing
        on a computing cluster. Configuration is inherited from HTCondorWorkflow
        base class in framework.py.
        """

        def htcondor_output_directory(self):
            """Directory for HTCondor job outputs."""
            return law.LocalDirectoryTarget(
                os.path.join(self.output_dir, "htcondor_jobs")
            )


class MergeValidationResults(TICLValidationTask):
    """
    Merge validation results from multiple files.

    This task collects summary.json files from multiple validation runs
    and creates a combined summary with aggregated metrics.
    """

    input_pattern = luigi.Parameter(
        description="Pattern for input summary.json files"
    )

    def requires(self):
        """This task requires ValidateMultipleFiles to be complete."""
        return ValidateMultipleFiles(
            input_file=self.input_file,
            output_dir=self.output_dir,
            modules=self.modules,
            suite=self.suite,
            analyze_hlt=self.analyze_hlt,
            matching_method=self.matching_method,
            threads=self.threads,
        )

    def output(self):
        """Combined summary output."""
        return law.LocalFileTarget(
            os.join(self.output_dir, "merged_summary.json")
        )

    def run(self):
        """Merge all summary.json files."""
        # Find all summary files
        summary_files = glob.glob(
            os.path.join(self.output_dir, "file_*/summary.json")
        )

        # Load and merge summaries
        merged_data = {}
        file_count = 0

        for summary_file in summary_files:
            with open(summary_file, 'r') as f:
                data = json.load(f)
                file_count += 1

                # Merge metrics (average across files)
                for collection, metrics in data.items():
                    if collection not in merged_data:
                        merged_data[collection] = {}

                    for metric_name, value in metrics.items():
                        if metric_name not in merged_data[collection]:
                            merged_data[collection][metric_name] = []
                        merged_data[collection][metric_name].append(value)

        # Calculate averages
        final_summary = {}
        for collection, metrics in merged_data.items():
            final_summary[collection] = {}
            for metric_name, values in metrics.items():
                if values:
                    final_summary[collection][metric_name] = {
                        "mean": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "n_files": len(values),
                    }

        # Add metadata
        final_summary["_metadata"] = {
            "n_files_processed": file_count,
            "input_pattern": self.input_file,
            "suite": self.suite or ",".join(self.modules),
        }

        # Write merged summary
        output = self.output()
        output.parent.touch()
        with output.open("w") as f:
            json.dump(final_summary, f, indent=2)

        print(f"Merged {file_count} validation results")
        print(f"Output: {output.path}")
