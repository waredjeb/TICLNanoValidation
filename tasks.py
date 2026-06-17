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
    law.contrib.load("htcondor")
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
    class ValidateMultipleFilesHTCondor(ValidateMultipleFiles, law.contrib.htcondor.HTCondorWorkflow):

        def run(self):
            """Override run to add debugging."""
            print(f"DEBUG: ValidateMultipleFilesHTCondor.run() called for branch {self.branch}")
            return super().run()
        """
        Run validation on multiple files using HTCondor.

        This task submits validation jobs to HTCondor for parallel processing
        on a computing cluster.
        """

        htcondor_cpus = luigi.IntParameter(
            default=1,
            description="CPUs per HTCondor job"
        )
        htcondor_memory = luigi.Parameter(
            default="2GB",
            description="Memory per HTCondor job"
        )
        htcondor_disk = luigi.Parameter(
            default="1GB",
            description="Disk space per HTCondor job"
        )
        max_runtime = luigi.IntParameter(
            default=3600,
            description="Maximum runtime per job in seconds"
        )

        def htcondor_output_directory(self):
            """Directory for HTCondor job outputs."""
            return law.LocalDirectoryTarget(
                os.path.join(self.output_dir, "htcondor_jobs")
            )

        def htcondor_bootstrap_file(self):
            """Bootstrap file to set up environment on worker nodes."""
            bootstrap_file = law.util.rel_path(__file__, "bootstrap.sh")
            return law.JobInputFile(bootstrap_file, share=True, render_job=True)

        def htcondor_job_config(self, config, job_num, branches):
            """
            Configure the HTCondor job.

            This method is called for each job and should configure what
            command to run and how to run it.
            """
            print(f"DEBUG: htcondor_job_config called for job {job_num}, branches {branches}")

            # Render variables - available in bootstrap.sh
            config.render_variables["validation_path"] = str(self.base_dir)

            # Custom HTCondor directives (required for CERN)
            config.custom_content.append(("RequestCpus", str(self.htcondor_cpus)))
            config.custom_content.append(("RequestMemory", self.htcondor_memory))
            config.custom_content.append(("RequestDisk", self.htcondor_disk))
            config.custom_content.append(("+MaxRuntime", str(self.max_runtime)))
            config.custom_content.append(("getenv", "true"))
            config.custom_content.append(("log", "/dev/null"))  # Required by CERN HTCondor

            print(f"DEBUG: job config created successfully")
            return config

        def htcondor_create_job_file_factory(self):
            """Create HTCondor job file factory."""
            factory = super().htcondor_create_job_file_factory()

            # Set resources
            factory.request_cpus = self.htcondor_cpus
            factory.request_memory = self.htcondor_memory
            factory.request_disk = self.htcondor_disk
            factory.custom_content.append(("+MaxRuntime", str(self.max_runtime)))

            # Set environment
            factory.custom_content.append(("getenv", "True"))

            return factory


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
