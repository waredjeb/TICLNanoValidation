"""
Framework base classes for TICL validation with LAW.
"""

import os
import math
import law
import luigi

# Load HTCondor contrib
law.contrib.load("htcondor")


class HTCondorWorkflow(law.htcondor.HTCondorWorkflow):
    """
    Base HTCondor workflow configured for CERN batch system.

    All HTCondor tasks should inherit from this to get CERN-specific
    configuration automatically.
    """

    max_runtime = luigi.IntParameter(
        default=3600,
        significant=False,
        description="maximum runtime in seconds; default: 3600",
    )

    htcondor_cpus = luigi.IntParameter(
        default=2,
        significant=False,
        description="CPUs per HTCondor job; default: 2"
    )

    htcondor_memory = luigi.Parameter(
        default="4GB",
        significant=False,
        description="Memory per HTCondor job; default: 4GB"
    )

    htcondor_disk = luigi.Parameter(
        default="2GB",
        significant=False,
        description="Disk space per HTCondor job; default: 2GB"
    )

    def htcondor_bootstrap_file(self):
        """Bootstrap file to set up environment on worker nodes."""
        bootstrap_file = law.util.rel_path(__file__, "bootstrap.sh")
        return law.JobInputFile(bootstrap_file, share=True, render_job=True)

    def htcondor_job_config(self, config, job_num, branches):
        """Configure HTCondor job for CERN batch system."""
        # Render variables - available in bootstrap.sh
        config.render_variables["validation_path"] = os.path.dirname(os.path.abspath(__file__))

        # Custom HTCondor directives (required for CERN)
        config.custom_content.append(("RequestCpus", str(self.htcondor_cpus)))
        config.custom_content.append(("RequestMemory", self.htcondor_memory))
        config.custom_content.append(("RequestDisk", self.htcondor_disk))
        config.custom_content.append(("+MaxRuntime", str(self.max_runtime)))
        config.custom_content.append(("getenv", "true"))
        config.custom_content.append(("log", "/dev/null"))  # Required by CERN HTCondor

        return config
