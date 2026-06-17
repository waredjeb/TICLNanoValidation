"""CERN lxplus HTCondor workflow base class.

Encapsulates everything CERN/lxplus-specific so the actual tasks stay generic:

* a bootstrap that sources an LCG view from CVMFS (provides ROOT + Python),
* the HTCondor directives CERN requires (``+MaxRuntime``, ``log = /dev/null``, ...),
* request resources exposed as parameters.

Workers on lxplus do not share a filesystem with the submit node, but they do see
CVMFS and (read) the AFS submit directory. The bootstrap therefore sources the LCG
view and puts the framework directory on ``PYTHONPATH``.
"""

from __future__ import annotations

import os

import law
import luigi

law.contrib.load("htcondor", "wlcg")

#: Default LCG view used on the worker. Override with ``--lcg-view`` if needed.
DEFAULT_LCG_VIEW = "LCG_105/x86_64-el9-gcc13-opt"

#: Repository root (this file lives in <repo>/workflow/).
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HTCondorWorkflow(law.htcondor.HTCondorWorkflow):
    """Base HTCondor workflow configured for the CERN batch system."""

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

    def htcondor_job_config(self, config, job_num, branches):
        # Variables consumed by bootstrap.sh ({{...}} placeholders).
        config.render_variables["repo_dir"] = REPO_DIR
        config.render_variables["lcg_view"] = self.lcg_view

        # CERN-required directives.
        config.custom_content.append(("RequestCpus", str(self.htcondor_cpus)))
        config.custom_content.append(("RequestMemory", self.htcondor_memory))
        config.custom_content.append(("RequestDisk", self.htcondor_disk))
        config.custom_content.append(("+MaxRuntime", str(self.max_runtime)))
        config.custom_content.append(("log", "/dev/null"))
        return config
