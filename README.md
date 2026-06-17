# NanoAOD TICL Validation Framework

A modular framework for validating and evaluating TICL (HGCAL Iterative Clustering) performance using ROOT's RDataFrame.

## Features

- **Modular architecture**: Easy to add new validation modules
- **RDataFrame-based**: Fast analysis with implicit multi-threading
- **Multiple validation modules**:
  - Distributions: Basic kinematic distributions
  - Matching: Sim-Reco matching quality metrics
  - Efficiency: Efficiency and fake rate calculations
  - Resolution: Energy/pT resolution studies
- **Flexible matching**: SharedEnergyFraction or Score-based matching
- **Preset suites**: Quick, performance, full_validation, etc.
- **Multi-collection support**: Analyze multiple trackster/candidate collections
- **HLT and offline**: Support for both online (HLT) and offline collections

## Quick Start

```bash
# Basic distribution plots
python validation/validate.py --input step4_inNANOAODSIM.root --modules distributions

# Full validation suite
python validation/validate.py --input step4_inNANOAODSIM.root --suite full_validation

# Specific modules
python validation/validate.py --input "data/*.root" --modules matching,efficiency

# HLT analysis
python validation/validate.py --input step2.root --modules all --analyze-hlt
```

## Command-Line Options

### Input
- `--input FILE`: Input file(s), supports glob patterns

### Modules
- `--modules LIST`: Comma-separated list of modules (or 'all')
- `--suite NAME`: Use preset validation suite

### Collections
- `--collections LIST`: Specific collections to analyze
- `--analyze-hlt`: Analyze HLT collections
- `--analyze-offline`: Analyze offline collections (default)

### Output
- `--output DIR`: Output directory (default: validation_output)
- `--no-png`: Don't save PNG plots
- `--no-pdf`: Don't save PDF plots

### Configuration
- `--matching-method`: Use 'shared_energy' (default) or 'score'
- `--no-mt`: Disable multi-threading
- `--threads N`: Number of threads

### Utilities
- `--list-suites`: List available validation suites
- `--list-modules`: List available modules

## Validation Suites

- **quick**: Distributions only (fast sanity check)
- **matching_only**: Just matching quality
- **performance**: Distributions + Matching + Efficiency
- **full_validation**: All modules
- **resolution_study**: Resolution analysis
- **efficiency_study**: Efficiency analysis

## Module Dependencies

Some modules depend on others:
- `efficiency` → requires `matching`
- `resolution` → requires `matching`

The framework automatically resolves dependencies.

## Output Structure

```
validation_output/
├── distributions/
│   ├── ticlTrackstersCLUE3DHigh/
│   │   ├── eta.png
│   │   ├── eta.pdf
│   │   ├── energy.png
│   │   └── ...
│   └── TICLCandidates/
│       └── ...
├── matching/
│   └── ...
├── efficiency/
│   └── ...
├── resolution/
│   └── ...
└── summary.json
```

## Matching Configuration

Two matching methods are available:

### SharedEnergyFraction (default)
- Sim2Reco: `SEF = SharedEnergy / Sim_RawEnergy > 0.5`
- Reco2Sim: `SEF = SharedEnergy / Reco_RawEnergy > 0.5`

### Score-based
- Sim2Reco: `Score < 0.2`
- Reco2Sim: `Score < 0.6`

Thresholds are configurable in `config.py`.

## Default Collections

### Offline
- ticlTrackstersCLUE3DHigh
- ticlTracksterLinks
- ticlTracksterLinksSuperclusteringDNN
- ticlCandidate

### HLT (with `--analyze-hlt`)
- hltTiclTrackstersCLUE3DHigh
- hltTiclTracksterLinks
- hltTiclTracksterLinksSuperclusteringDNN
- hltTiclCandidate

## Adding New Modules

1. Create a new module in `validation/modules/`:

```python
from validation.core.base_module import ValidationModule

class MyModule(ValidationModule):
    def __init__(self, config):
        super().__init__(config, name="mymodule")
        self.dependencies = []  # List dependencies
    
    def define_columns(self, rdf):
        # Define new RDataFrame columns
        return rdf
    
    def book_histograms(self, collection):
        # Return histogram definitions
        return {}
    
    def fill_histograms(self, rdf, collection):
        # Fill and return histograms
        return {}
    
    def plot(self, histograms, metrics, output_dir, collection):
        # Generate plots
        pass
```

2. Register in `validate.py`:
```python
from validation.modules.mymodule import MyModule

MODULE_REGISTRY = {
    # ...
    "mymodule": MyModule,
}
```

## LAW Integration (HTCondor Workflows)

The framework integrates with LAW (Luigi Analysis Workflow) for distributed execution on HTCondor and managing large-scale validation campaigns.

### Setup

```bash
# Source the setup script
source setup.sh

# Or manually
export LAW_HOME="$(pwd)/.law"
export LAW_CONFIG_FILE="$(pwd)/law.cfg"
```

### LAW Tasks

#### ValidateSingleFile
Run validation on a single file (useful for testing):

```bash
law run ValidateSingleFile \
    --input step4_inNANOAODSIM.root \
    --output results/ \
    --suite full_validation
```

#### ValidateMultipleFiles
Run validation on multiple files locally in parallel:

```bash
# Using glob pattern
law run ValidateMultipleFiles \
    --input 'data/*.root' \
    --output batch_results/ \
    --suite performance \
    --workers 4

# Limit number of files
law run ValidateMultipleFiles \
    --input 'data/*.root' \
    --max-files 10 \
    --output batch_results/
```

#### ValidateMultipleFilesHTCondor
Submit validation jobs to HTCondor for cluster execution:

```bash
law run ValidateMultipleFilesHTCondor \
    --input '/eos/cms/store/data/*.root' \
    --output htcondor_results/ \
    --suite full_validation \
    --htcondor-cpus 2 \
    --htcondor-memory 4GB \
    --max-runtime 7200
```

#### MergeValidationResults
Merge results from multiple validation runs:

```bash
law run MergeValidationResults \
    --input 'data/*.root' \
    --output batch_results/ \
    --suite full_validation
```

### LAW Task Parameters

Common parameters for all tasks:
- `--input`: Input file pattern
- `--output-dir`: Base output directory
- `--modules`: List of modules (comma-separated)
- `--suite`: Validation suite name
- `--analyze-hlt`: Analyze HLT collections
- `--matching-method`: Matching method (shared_energy, score)
- `--threads`: Threads per job

HTCondor-specific parameters:
- `--htcondor-cpus`: CPUs per job
- `--htcondor-memory`: Memory per job (e.g., 2GB, 4GB)
- `--htcondor-disk`: Disk space per job
- `--max-runtime`: Maximum runtime in seconds

### Monitoring LAW Workflows

```bash
# Check task status
law run ValidateMultipleFiles --input 'data/*.root' --print-status -1

# List output files
law run ValidateMultipleFiles --input 'data/*.root' --print-output -1

# Remove outputs (for rerunning)
law run ValidateMultipleFiles --input 'data/*.root' --remove-output -1

# Check dependencies
law run ValidateMultipleFiles --input 'data/*.root' --print-deps -1
```

### Configuration Files

- `law.cfg`: LAW configuration (HTCondor settings, output paths)
- `luigi.cfg`: Luigi backend configuration (workers, scheduling)
- `setup.sh`: Environment setup script

### Example Workflow

```bash
# 1. Setup environment
source setup.sh

# 2. Test on single file
law run ValidateSingleFile --input test.root --output test_output/

# 3. Run on batch locally
law run ValidateMultipleFiles --input 'data/*.root' --output local_batch/

# 4. Submit to HTCondor
law run ValidateMultipleFilesHTCondor \
    --input '/eos/cms/store/data/phase2/*.root' \
    --output htcondor_batch/ \
    --htcondor-cpus 4 \
    --htcondor-memory 8GB

# 5. Merge results
law run MergeValidationResults --input 'data/*.root' --output htcondor_batch/
```

## Requirements

- ROOT (with RDataFrame support)
- Python 3.7+

## Examples

### Compare multiple files
```bash
python validation/validate.py --input "v1/*.root,v2/*.root" --suite performance
```

### Custom collections
```bash
python validation/validate.py --input file.root --modules all \
    --collections ticlTrackstersCLUE3DHigh,TICLCandidates
```

### Resolution study
```bash
python validation/validate.py --input file.root --suite resolution_study \
    --matching-method shared_energy
```
