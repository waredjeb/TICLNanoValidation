"""CERN lxplus HTCondor workflow base class.

Encapsulates everything CERN/lxplus-specific so the actual tasks stay generic:

* a bootstrap that sources an LCG view from CVMFS (provides ROOT + Python),
* the HTCondor directives CERN requires (``+MaxRuntime``, ``log = /dev/null``, ...),
* request resources exposed as parameters.

Code delivery to workers — ``--code-mode`` (default ``bundle``)
---------------------------------------------------------------
``bundle`` (recommended, AFS-friendly): at submit time the framework code is
tarred from the user's git checkout and law+luigi are shipped as a second tarball;
HTCondor transfers both with the job, the bootstrap unpacks them onto the worker's
*local scratch*, and the job runs from there via ``python -m law``. At runtime the
worker touches only CVMFS (ROOT/python) and local disk — **AFS is read once, at
submit, to build the bundle**, never per-job. Scales to many jobs.

``afs`` (escape hatch, quick dev): the worker imports the code directly from the
AFS checkout and uses the law already on PATH. Zero packaging, but every job reads
the repo from AFS — fine for a handful of jobs, discouraged at scale.

The law+luigi tarball is built once with ``workflow/make_software_bundle.sh``; the
code tarball is rebuilt automatically on every submit.
"""

from __future__ import annotations

import os
import subprocess

import law
import luigi

law.contrib.load("htcondor", "wlcg")

#: Default LCG view sourced on the worker. In ``bundle`` mode it provides ROOT +
#: the scientific stack (numpy/matplotlib/yaml); law+luigi come from the bundle.
#: Override with ``--lcg-view`` if needed.
DEFAULT_LCG_VIEW = "LCG_109/x86_64-el9-gcc13-opt"

#: Repository root (this file lives in <repo>/workflow/).
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where submit-time bundles are written (under the gitignored .law/ dir).
BUNDLE_DIR = os.path.join(REPO_DIR, ".law", "bundles")
SOFTWARE_BUNDLE = os.path.join(BUNDLE_DIR, "software.tgz")
REPO_BUNDLE = os.path.join(BUNDLE_DIR, "repo.tgz")


class HTCondorWorkflow(law.htcondor.HTCondorWorkflow):
    """Base HTCondor workflow configured for the CERN batch system."""

    code_mode = luigi.ChoiceParameter(
        default="bundle",
        choices=("bundle", "afs"),
        significant=False,
        description="how the worker gets the code+law: 'bundle' (ship tarballs via "
        "HTCondor, run from local scratch; AFS-free at runtime) or 'afs' (import "
        "directly from the AFS checkout); default: bundle",
    )
    transfer_logs = luigi.BoolParameter(
        default=True, significant=False, description="transfer job logs; default: True"
    )
    max_runtime = luigi.IntParameter(
        default=3600, significant=False, description="max job runtime [s]; default: 3600"
    )
    htcondor_cpus = luigi.IntParameter(
        default=2, significant=False, description="CPUs per job; default: 2"
    )
    htcondor_memory = luigi.Parameter(
        default="4GB", significant=False, description="memory per job; default: 4GB"
    )
    htcondor_disk = luigi.Parameter(
        default="2GB", significant=False, description="disk per job; default: 2GB"
    )
    lcg_view = luigi.Parameter(
        default=DEFAULT_LCG_VIEW,
        significant=False,
        description=f"CVMFS LCG view to source on the worker; default: {DEFAULT_LCG_VIEW}",
    )

    def htcondor_output_directory(self):
        # Local directory (on the submit node) for the per-job control files
        # (status, stdout/err). Job *results* go to their own targets.
        return law.LocalDirectoryTarget(
            os.path.join(REPO_DIR, ".law", "jobs", self.__class__.__name__)
        )

    def htcondor_bootstrap_file(self):
        bootstrap = os.path.join(REPO_DIR, "workflow", "bootstrap.sh")
        return law.JobInputFile(bootstrap, share=True, render_job=True)

    # -- bundle helpers ---------------------------------------------------- #
    @staticmethod
    def _build_repo_bundle() -> str:
        """Tar the git-tracked files of the checkout (incl. uncommitted edits)."""
        os.makedirs(BUNDLE_DIR, exist_ok=True)
        file_list = subprocess.check_output(
            ["git", "-C", REPO_DIR, "ls-files", "-z"]
        )
        subprocess.run(
            ["tar", "-czf", REPO_BUNDLE, "-C", REPO_DIR, "--null", "-T", "-"],
            input=file_list,
            check=True,
        )
        return REPO_BUNDLE

    @staticmethod
    def _software_bundle() -> str:
        if not os.path.exists(SOFTWARE_BUNDLE):
            raise RuntimeError(
                "software bundle not found at {}.\nBuild it once (with an LCG view "
                "sourced):\n  bash workflow/make_software_bundle.sh".format(SOFTWARE_BUNDLE)
            )
        return SOFTWARE_BUNDLE

    def htcondor_job_config(self, config, job_num, branches):
        # Variables consumed by bootstrap.sh ({{...}} placeholders).
        config.render_variables["code_mode"] = str(self.code_mode)
        config.render_variables["repo_dir"] = REPO_DIR
        config.render_variables["lcg_view"] = self.lcg_view
        # Capture the EOS base on the submit node so workers don't depend on $USER.
        config.render_variables["eos_base"] = os.environ.get("TICLNANOVAL_EOS_BASE", "")

        if str(self.code_mode) == "bundle":
            # Ship code + law/luigi with the job; unpacked to local scratch on the
            # worker. share=True -> transferred once per submission. The input-file
            # keys become {{repo_bundle}} / {{sw_bundle}} render variables.
            config.input_files["repo_bundle"] = law.JobInputFile(
                self._build_repo_bundle(), share=True, render=False
            )
            config.input_files["sw_bundle"] = law.JobInputFile(
                self._software_bundle(), share=True, render=False
            )
            config.custom_content.append(("should_transfer_files", "YES"))
            config.custom_content.append(("when_to_transfer_output", "ON_EXIT"))

        # CERN-required directives.
        config.custom_content.append(("RequestCpus", str(self.htcondor_cpus)))
        config.custom_content.append(("RequestMemory", self.htcondor_memory))
        config.custom_content.append(("RequestDisk", self.htcondor_disk))
        config.custom_content.append(("+MaxRuntime", str(self.max_runtime)))
        config.custom_content.append(("log", "/dev/null"))
        return config
