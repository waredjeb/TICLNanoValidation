#!/usr/bin/env bash
# Environment setup for the ticlNanoVal framework + LAW on RHEL/CentOS **el8**.
#
#   source setupel8.sh
#
# This is the el8 counterpart of setup.sh. Unlike setup.sh (which assumes you have
# already sourced an el9 LCG view), this script sources an el8 LCG view for you and
# makes sure law+luigi are importable by that view's python. Just run it in a clean
# shell (no cmsenv / CMSSW -- the python runtimes are incompatible):
#
#   source setupel8.sh
#
# Notes:
#   * The newest el8 LCG view is LCG_107/x86_64-el8-gcc11-opt (ROOT 6.34, python 3.11).
#     LCG_108+ ship no el8 build. Override with TICLNANOVAL_LCG_VIEW before sourcing.
#   * law/luigi are python-version specific. The el9 view uses python 3.13, so a
#     `pip install --user law luigi` done under el9 is NOT visible here (python 3.11).
#     This script installs them to --user for python 3.11 on first run if missing.
#   * HTCondor workers do not use this install (see workflow/bootstrap.sh). For el8
#     workers, pass a matching --lcg-view, e.g.
#       --lcg-view LCG_107/x86_64-el8-gcc11-opt

export TICLNANOVAL_BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# --- 1. ROOT + python from an el8 LCG view (unless already provided) --------- #
export TICLNANOVAL_LCG_VIEW="${TICLNANOVAL_LCG_VIEW:-LCG_107/x86_64-el8-gcc11-opt}"

if ! python3 -c 'import ROOT' >/dev/null 2>&1; then
    _lcg_setup="/cvmfs/sft.cern.ch/lcg/views/${TICLNANOVAL_LCG_VIEW}/setup.sh"
    if [ -f "${_lcg_setup}" ]; then
        source "${_lcg_setup}"
        echo "sourced LCG view: ${TICLNANOVAL_LCG_VIEW}"
    else
        echo "ERROR: LCG view not found: ${_lcg_setup}" >&2
        echo "       set TICLNANOVAL_LCG_VIEW to a valid el8 view and re-source." >&2
    fi
    unset _lcg_setup
fi

# --- 2. repo-local venv (optional convenience for interactive use) ----------- #
if [ -f "${TICLNANOVAL_BASE}/.venv/bin/activate" ]; then
    source "${TICLNANOVAL_BASE}/.venv/bin/activate"
fi

# --- 3. make law + luigi importable by this python (py3.11 on el8) ----------- #
# Put the --user script dir on PATH so the `law` executable is found (also after
# a previous session already installed it).
_user_bin="$(python3 -c 'import site,os; print(os.path.join(site.getuserbase(),"bin"))' 2>/dev/null)"
[ -n "${_user_bin}" ] && [ -d "${_user_bin}" ] && export PATH="${_user_bin}:${PATH}"
unset _user_bin

if ! python3 -c 'import law, luigi' >/dev/null 2>&1; then
    echo "law/luigi not importable for this python; installing to --user ..."
    if python3 -m pip install --user --quiet law luigi; then
        _user_bin="$(python3 -c 'import site,os; print(os.path.join(site.getuserbase(),"bin"))' 2>/dev/null)"
        [ -n "${_user_bin}" ] && export PATH="${_user_bin}:${PATH}"
        unset _user_bin
    else
        echo "WARNING: could not install law/luigi automatically." >&2
        echo "         run: python3 -m pip install --user law luigi" >&2
    fi
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
