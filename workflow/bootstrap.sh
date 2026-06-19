#!/usr/bin/env bash
# Bootstrap executed on the HTCondor worker before the LAW job runs.
# Placeholders in {{...}} are rendered by HTCondorWorkflow.htcondor_job_config().
#
# Two code-delivery modes (see workflow/framework.py):
#   bundle : extract the shipped code + law/luigi tarballs to local scratch and
#            run from there (AFS-free at runtime).
#   afs    : import the code directly from the AFS checkout, use law on PATH.

action() {
    # 1. ROOT + python (+ scientific stack) from a CVMFS LCG view.
    local lcg_setup="/cvmfs/sft.cern.ch/lcg/views/{{lcg_view}}/setup.sh"
    if [ -f "${lcg_setup}" ]; then
        source "${lcg_setup}"
    else
        echo "ERROR: LCG view not found: ${lcg_setup}" >&2
        return 1
    fi

    if [ "{{code_mode}}" = "afs" ]; then
        # --- afs mode: run in place from the AFS checkout ----------------- #
        export PYTHONPATH="{{repo_dir}}:${PYTHONPATH}"
        export LAW_HOME="{{repo_dir}}/.law"
        export LAW_CONFIG_FILE="{{repo_dir}}/law.cfg"
        cd "{{repo_dir}}" || return 1
    else
        # --- bundle mode: unpack onto local scratch ---------------------- #
        local work="${LAW_JOB_HOME:-${PWD}}/ticlnanoval"
        mkdir -p "${work}/.sw"
        tar -xzf "{{repo_bundle}}" -C "${work}"     || { echo "ERROR: unpack repo bundle" >&2; return 1; }
        tar -xzf "{{sw_bundle}}"  -C "${work}/.sw"  || { echo "ERROR: unpack sw bundle"  >&2; return 1; }

        # law+luigi come from the shipped tarball; the framework from the repo.
        export PYTHONPATH="${work}:${work}/.sw:${PYTHONPATH}"
        export LAW_HOME="${work}/.law"
        export LAW_CONFIG_FILE="${work}/law.cfg"

        # Provide a `law` executable (the job wrapper calls bare `law`); route it
        # through the shipped package so we don't depend on a console-script shebang.
        mkdir -p "${work}/bin"
        printf '#!/usr/bin/env bash\nexec python3 -m law "$@"\n' > "${work}/bin/law"
        chmod +x "${work}/bin/law"
        export PATH="${work}/bin:${PATH}"

        cd "${work}" || return 1
        law index --quiet 2>/dev/null || law index 2>/dev/null
    fi

    # EOS base for wlcg stageout (captured from the submit node; law.cfg reads it).
    export TICLNANOVAL_EOS_BASE="{{eos_base}}"

    if ! command -v law >/dev/null 2>&1; then
        echo "ERROR: 'law' not available after bootstrap (mode={{code_mode}})" >&2
        return 1
    fi

    echo "Bootstrap OK: $(python3 -c 'import ROOT, sys; print("ROOT", ROOT.__version__, "py", sys.version.split()[0])')"
}
action "$@"
