#!/usr/bin/env bash
# Environment setup for the ticlNanoVal framework + LAW.
#
#   source setup.sh
#
# On lxplus, in a clean shell (no cmsenv), source one LCG view first (for ROOT),
# e.g.:  source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc13-opt/setup.sh
# law + luigi must be importable by that python (pip install --user law luigi, or
# a venv). HTCondor workers do not use this install — see workflow/framework.py.
#
# If a repo-local venv exists, activate it (optional convenience for interactive use).

export TICLNANOVAL_BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -f "${TICLNANOVAL_BASE}/.venv/bin/activate" ]; then
    source "${TICLNANOVAL_BASE}/.venv/bin/activate"
fi

export PYTHONPATH="${TICLNANOVAL_BASE}:${PYTHONPATH}"
export LAW_HOME="${TICLNANOVAL_BASE}/.law"
export LAW_CONFIG_FILE="${TICLNANOVAL_BASE}/law.cfg"
export LUIGI_CONFIG_PATH="${TICLNANOVAL_BASE}/luigi.cfg"

# EOS base for the wlcg_fs_ticl target (law.cfg can't do bash substring expansion).
# Defaults to your personal EOS area; override before sourcing to change it.
export TICLNANOVAL_EOS_BASE="${TICLNANOVAL_EOS_BASE:-root://eosuser.cern.ch//eos/user/${USER:0:1}/${USER}/TICLNanoValidation}"

mkdir -p "${LAW_HOME}/jobs"

# Enable shell tab-completion for `law` if available.
command -v law >/dev/null 2>&1 && source "$( law completion )" 2>/dev/null

echo "ticlNanoVal ready (base: ${TICLNANOVAL_BASE})"
echo "  CLI : python3 -m ticlNanoVal.cli run -c configs/base.yaml -c configs/offline.yaml -i FILE -o OUT"
echo "  LAW : law run ValidateFile --configs configs/base.yaml,configs/offline.yaml --input-files FILE --output-dir OUT"
