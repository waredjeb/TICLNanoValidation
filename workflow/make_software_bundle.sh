#!/usr/bin/env bash
# Build the law+luigi software bundle shipped to HTCondor workers in `bundle`
# code-mode. Run this ONCE (re-run only to update law/luigi), with an LCG view
# sourced so pip targets the same python the workers will use:
#
#   source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc13-opt/setup.sh
#   bash workflow/make_software_bundle.sh
#
# ROOT / numpy / matplotlib / PyYAML are NOT bundled — they come from the LCG
# view on the worker. Only the small, pure-python law + luigi (and their deps)
# are shipped, so the tarball stays a few MB.
set -euo pipefail

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
BUNDLE_DIR="${REPO_DIR}/.law/bundles"
STAGE="$( mktemp -d )"
trap 'rm -rf "${STAGE}"' EXIT

echo "Building software bundle with: $(command -v python3) ($(python3 --version 2>&1))"
mkdir -p "${BUNDLE_DIR}"

# Install law + luigi (and dependencies) into a relocatable target directory.
python3 -m pip install --no-cache-dir --target "${STAGE}" law luigi

# Drop bulky non-essentials to keep the tarball small (best-effort).
rm -rf "${STAGE}"/*.dist-info/RECORD "${STAGE}"/__pycache__ 2>/dev/null || true

tar -czf "${BUNDLE_DIR}/software.tgz" -C "${STAGE}" .
echo "Wrote ${BUNDLE_DIR}/software.tgz ($(du -h "${BUNDLE_DIR}/software.tgz" | cut -f1))"
echo "Contains: $(ls "${STAGE}" | tr '\n' ' ')"
