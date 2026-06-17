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

## Future Integration: LAW

The framework is designed to integrate with LAW (Luigi Analysis Workflow) for distributed execution on HTCondor. The core analysis code is independent of the workflow layer, making it easy to:

1. Run locally (current implementation)
2. Wrap with LAW tasks for grid submission
3. Scale to large datasets

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
