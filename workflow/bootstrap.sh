#!/usr/bin/env bash
# Bootstrap executed on the HTCondor worker before the LAW job runs.
# Placeholders in {{...}} are rendered by HTCondorWorkflow.htcondor_job_config().

action() {
    # 1. Provide ROOT + Python (+ numpy) from a CVMFS LCG view.
    local lcg_setup="/cvmfs/sft.cern.ch/lcg/views/{{lcg_view}}/setup.sh"
    if [ -f "${lcg_setup}" ]; then
        source "${lcg_setup}"
    else
        echo "ERROR: LCG view not found: ${lcg_setup}" >&2
        return 1
    fi

    # 2. Make the framework importable and point LAW at this repo's config.
    export PYTHONPATH="{{repo_dir}}:${PYTHONPATH}"
    export LAW_HOME="{{repo_dir}}/.law"
    export LAW_CONFIG_FILE="{{repo_dir}}/law.cfg"

    cd "{{repo_dir}}" || return 1

    echo "Bootstrap OK: $(python3 -c 'import ROOT,sys; print(\"ROOT\", ROOT.__version__, \"py\", sys.version.split()[0])')"
}
action "$@"
