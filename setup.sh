#!/bin/bash
# Setup script for TICL NanoAOD Validation with LAW

# Get the directory of this script
export TICL_VALIDATION_BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set LAW environment variables
export LAW_HOME="${TICL_VALIDATION_BASE}/.law"
export LAW_CONFIG_FILE="${TICL_VALIDATION_BASE}/law.cfg"
export LAW_JOB_FILE_DIR="${TICL_VALIDATION_BASE}/.law/jobs"
export LAW_TARGET_CACHE="${TICL_VALIDATION_BASE}/.law/cache"

# Create necessary directories
mkdir -p "${LAW_HOME}"
mkdir -p "${LAW_JOB_FILE_DIR}"
mkdir -p "${LAW_TARGET_CACHE}"

# Add the validation directory to PYTHONPATH
export PYTHONPATH="${TICL_VALIDATION_BASE}:${PYTHONPATH}"

# Setup Luigi (LAW's backend)
export LUIGI_CONFIG_PATH="${TICL_VALIDATION_BASE}/luigi.cfg"

echo "TICL NanoAOD Validation environment setup complete!"
echo "Base directory: ${TICL_VALIDATION_BASE}"
echo "LAW home: ${LAW_HOME}"
echo ""
echo "Usage examples:"
echo "  # Run validation on single file"
echo "  law run ValidateSingleFile --input step4.root --output results/"
echo ""
echo "  # Run validation on multiple files locally"
echo "  law run ValidateMultipleFiles --input 'data/*.root' --output results/"
echo ""
echo "  # Submit to HTCondor"
echo "  law run ValidateMultipleFilesHTCondor --input 'data/*.root' --output results/"
echo ""
echo "  # Check task status"
echo "  law run ValidateMultipleFiles --input 'data/*.root' --print-status -1"
echo ""
