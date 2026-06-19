# ticlNanoVal

A small, flexible framework for validating **TICL NanoAOD** ROOT files produced by
the CMSSW ntuplizer. It runs the same analysis on **HLT** and **offline** files —
which are structurally identical but differ in collection names — by changing
*configuration only*, never code.

The framework is built around three ideas:

* **ROOT RDataFrame** for the event loop (implicit multithreading, multi-file).
* **LAW / Luigi** for scheduling (run locally or submit one HTCondor job per file).
* A **config-driven schema** that abstracts collection names, so analysis modules
  reference *logical* keys (`clue3d`, `cp`, `energy`) instead of physical branches.

```
input files ──▶ DataLoader (RDataFrame) ──▶ matching strategy ──▶ modules ──▶ summary.json + plots
                                   (standardized match columns)
```

---

## Layout

```
ticlNanoVal/              # the framework (pure analysis, no LAW)
  config/                 #   YAML loading + typed RunConfig
  data/                   #   DataLoader (RDataFrame) + CollectionSchema (name abstraction)
  matching/               #   matching strategies + standardized output (base, score, shared_energy)
  modules/                #   analysis modules (distributions, efficiency)
  plotting/               #   matplotlib/mplhep plotter
  pipeline.py             #   the single place that wires load -> match -> modules -> outputs
  cli.py                  #   `ticlval run ...` / `ticlval list`
workflow/                 # LAW layer (thin: orchestration only, imports ROOT lazily)
  framework.py            #   CERN/lxplus HTCondor base + bootstrap wiring
  tasks.py                #   ValidateFile(s){Local,HTCondor}, MergeHistograms, PlotValidation
  bootstrap.sh            #   sourced on the HTCondor worker (LCG view + unpack bundle)
  make_software_bundle.sh #   one-time: build the law+luigi tarball shipped to workers
configs/                  # base.yaml (settings) + hlt.yaml / offline.yaml (schemas)
tests/                    # smoke tests (config/schema always; pipeline if sample files present)
```

The clean separation is deliberate: **LAW tasks never touch RDataFrame, matching,
or modules** — they only build a `RunConfig` and call `pipeline.run`. All physics
flow lives in `pipeline.py`.

---

## Setup

ROOT (with PyROOT) must come from your environment — an LCG view or CMSSW. On lxplus,
source **one** LCG view in a clean shell (do *not* mix with a `cmsenv`/CMSSW
environment — the python runtimes are incompatible):

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc13-opt/setup.sh
```

`law`/`luigi` are needed only for the workflow layer; install them for the LCG python
(a `pip install --user law luigi`, or a venv, is fine). Then, for every session, from
the repo root:

```bash
source setup.sh
```

`setup.sh` puts the framework on `PYTHONPATH`, points LAW at `law.cfg` / `luigi.cfg`,
activates a repo-local `.venv` if you made one, and sets `TICLNANOVAL_EOS_BASE` (the
EOS area used for `wlcg` output — override it before sourcing to change the destination).

> **HTCondor users:** the workers do **not** use your interactive law install — they
> get code + law/luigi shipped with the job (see the HTCondor section below). Build the
> small software bundle once:
> ```bash
> bash workflow/make_software_bundle.sh   # with an LCG view sourced
> ```

---

## Running

### CLI (no LAW)

```bash
# offline file
python3 -m ticlNanoVal.cli run \
    -c configs/base.yaml -c configs/offline.yaml \
    -i ../step4_inNANOAODSIM.root -o validation_output

# HLT file (only the schema config changes)
python3 -m ticlNanoVal.cli run \
    -c configs/base.yaml -c configs/hlt.yaml \
    -i ../step2.root -o validation_output

# list what's available; override modules/strategy/threads on the fly
python3 -m ticlNanoVal.cli list
python3 -m ticlNanoVal.cli run -c configs/base.yaml -c configs/offline.yaml \
    -i FILE -o OUT --modules distributions --strategy score --threads 8
```

Configs are **layered** in order (later wins): start from `base.yaml`, add a schema
file, then CLI flags override both.

### LAW — locally

```bash
law index   # once, after adding/renaming tasks

# single file
law run ValidateFile \
    --configs configs/base.yaml,configs/offline.yaml \
    --input-files ../step4_inNANOAODSIM.root \
    --output-dir validation_output --threads 4

# many files: one branch per file -> per-file histograms, then merge + final plots.
# Running the tail task pulls the whole chain (Validate -> Merge -> Plot):
law run PlotValidation \
    --configs configs/base.yaml,configs/offline.yaml \
    --input-files '/path/to/*.root' \
    --output-dir validation_output \
    --workflow local --store local --workers 4
```

The per-file event loop is parallelized (here locally via `--workers`); the histogram
**merge and final plotting run locally** and cheaply. See *Multi-file workflow* below.

### LAW — HTCondor (lxplus)

One job per input file. **Code delivery is AFS-friendly:** by default (`--code-mode
bundle`) the framework code is tarred from your git checkout at submit time and
law/luigi are shipped as a second tarball; HTCondor transfers both with the job, the
bootstrap unpacks them onto the worker's **local scratch**, and the job runs from
there. At runtime the worker reads only **CVMFS** (ROOT/python via the LCG view) and
local disk — **AFS is read once, at submit, to build the bundle**, never per-job.

Build the law/luigi bundle once (re-run only to update law):

```bash
bash workflow/make_software_bundle.sh      # with an LCG view sourced
```

Then submit. Smoke-test the batch step alone with one file first:

```bash
law run ValidateFilesHTCondor \
    --configs configs/base.yaml,configs/offline.yaml \
    --input-files '/eos/.../*.root' \
    --output-dir my_run --max-files 1 \
    --max-runtime 3600 --htcondor-cpus 2 --htcondor-memory 4GB
```

For the full run, do it in two steps: submit the per-file jobs to HTCondor, then run
the tail task to merge + plot **locally** on the submit node.

```bash
# 1) per-file event loop on HTCondor (accepts the --max-runtime/--htcondor-* flags)
law run ValidateFilesHTCondor \
    --configs configs/base.yaml,configs/offline.yaml \
    --input-files '/eos/.../*.root' \
    --output-dir /eos/user/x/xxx/my_run --store local \
    --max-runtime 3600 --htcondor-cpus 2 --htcondor-memory 4GB

# 2) merge + final plots locally
law run PlotValidation \
    --configs configs/base.yaml,configs/offline.yaml \
    --input-files '/eos/.../*.root' \
    --output-dir /eos/user/x/xxx/my_run --store local --workflow htcondor
```

`PlotValidation` is a plain task, so HTCondor flags (`--max-runtime`, `--htcondor-*`,
`--poll-interval`) are **not** accepted on it — they belong to `ValidateFilesHTCondor`.
Step 2 won't resubmit as long as `configs`, `input-files`, `output-dir`, `max-files`
and `store` match step 1 (the HTCondor resource flags are `significant=False`). To run
it as a single command instead, pass those flags prefixed, e.g.
`--ValidateFilesHTCondor-max-runtime 3600`.

#### Output store on lxplus

* `--store local` writes via POSIX paths. Point `--output-dir` at your **EOS fuse mount**
  (`/eos/user/<i>/<user>/...`) or AFS work area — both are mounted on lxplus and on CERN
  HTCondor workers (with the forwarded Kerberos token). This is the recommended default.
* `--store wlcg` stages via **gfal2** (XRootD under the hood) to `TICLNANOVAL_EOS_BASE`.
  It only works if `gfal2` python bindings are importable — **the standard LCG views with
  python 3.13 do not ship them**, so `--store wlcg` fails with
  `gfal2 is not installed`. Use `--store local` with an `/eos` path instead, unless you
  have a gfal2-enabled environment.

#### Merge + plot only (re-plot from existing histograms)

If the per-file `hists_*.root` already exist, you can run **only** the merge + final
plots — no jobs, no `--input-files`, no workflow — by pointing `--hists` at them:

```bash
law run PlotValidation \
    --configs configs/base.yaml,configs/offline.yaml \
    --hists '/eos/user/w/wredjeb/TestLAW/Tests/ticlruns/test1/hists_*.root' \
    --output-dir /eos/user/w/wredjeb/TestLAW/Tests/ticlruns/test1
```

This is the quickest way to re-derive `merged.root`, the combined plots and
`summary.json` after a tweak to plot styling/metrics. (Note: changing *binning*
requires re-running the per-file jobs, since histograms are booked there.)
Alternatively, with no `--hists`, `PlotValidation` reuses an already-complete
`ValidateFilesHTCondor`/`Local` (matching params) and does only merge + plot.

Output store (`--store`):

* `--store local` — write results under `--output-dir` on a mounted FS (e.g. your AFS
  work area). One small write per job.
* `--store wlcg` (default for HTCondor) — stage results to EOS via XRootD
  (`wlcg_fs_ticl` in `law.cfg`, rooted at `TICLNANOVAL_EOS_BASE`).

Either way the worker authenticates with the Kerberos credential CERN HTCondor
forwards to the job. That credential is valid for ~25 h, so for very long jobs run
`voms-proxy-init --voms cms` first (a grid proxy lasts ~192 h).

**Escape hatch — `--code-mode afs`:** skip bundling and import the code directly from
the AFS checkout, using the law already on your `PATH`. Zero packaging, but every job
reads the repo from AFS — fine for a handful of jobs, discouraged at scale. The repo
must then live on a path the workers can read (AFS), and the `--lcg-view` must match
the python your interactive law was installed for.

---

## Configuration

Everything tunable lives in YAML; no core code edits required.

* **`configs/base.yaml`** — schema-independent: threads, MT, module list, matching
  strategy + thresholds, binning, output formats.
* **`configs/{hlt,offline}.yaml`** — the *schema*: maps logical keys to physical
  branch names. Field templates (`{coll}_raw_energy`) and association templates
  (`{sim}2{reco}ByHits`) are expanded per collection, so the two files differ only
  in the actual names (`hltTiclTrackstersCLUE3DHigh` vs `ticlTrackstersCLUE3DHigh`).

Because the schema is data, the **efficiency module adapts automatically**: offline
files carry only `sim2reco`, so it reports efficiency; HLT files also carry
`reco2sim`, so it additionally reports fake rate — with no code change.

---

## Extending

### Add a module

Subclass `AnalysisModule` (`ticlNanoVal/modules/base.py`) and register it. A module
is collection-agnostic: the pipeline calls it once per reco collection, and it
reads branches only through `schema` and matching only through the standardized
`MatchColumns` in the `RunContext`.

```python
from ticlNanoVal.modules.base import AnalysisModule
from ticlNanoVal.modules.registry import register_module

@register_module
class MyModule(AnalysisModule):
    name = "mymodule"
    requires = []                       # other modules whose columns you consume

    def book(self, rdf, ctx, reco_key): # return {name: lazy RResultPtr}
        ...
    def plot(self, results, metrics, output_dir, ctx, reco_key):
        ...
    # optional: define(self, rdf, ctx) and metrics(self, results, ctx, reco_key)
```

Modules are dependency-ordered via `requires`, so one module can consume another's
columns (e.g. a resolution module that reads matching results).

### Add a matching strategy

Every strategy returns the **same standardized columns**, so downstream modules
never care which algorithm produced them (see the contract at the top of
`ticlNanoVal/matching/base.py`):

```
sim2reco (per sim object):  match_{sim}_{reco}_simIdx / _simQuality / _simIsMatched
reco2sim (per reco object): match_{reco}_{sim}_recoIdx / _recoQuality / _recoIsFake
```

A strategy only describes *how good a single link is* and *how to compare/threshold
qualities*; the shared best-match loop produces the columns. Subclass
`MatchingStrategy` and implement four small C++ snippets:

```python
from ticlNanoVal.matching.base import MatchingStrategy
from ticlNanoVal.matching.registry import register_strategy

@register_strategy
class MyMatch(MatchingStrategy):
    name = "mymatch"
    def quality_expr(self):          return "shared / denom"   # vars: score, shared, denom
    def worst_quality(self):         return "-1.f"
    def is_better_expr(self):        return "q > best"
    def passes_expr(self, thr):      return f"best > {thr}f"
```

Built-in strategies: `shared_energy` (maximise shared energy fraction) and `score`
(minimise association score).

---

## Outputs

Single file (`ValidateFile`) or the final `PlotValidation`, under the output directory:

```
summary.json                       # scalar metrics per reco collection
<module>/<collection>/<plot>.{png,pdf}
```

`summary.json` is the machine-readable contract (e.g.
`ticlTrackstersCLUE3DHigh_cp_efficiency`).

### Multi-file workflow

```
ValidateFiles{Local,HTCondor}   one branch/file -> hists_<i>.root   (histograms only)
        │                                                            [parallel]
MergeHistograms                 TFileMerger sums all -> merged.root  [local]
        │
PlotValidation                  merged.root -> plots + summary.json  [local]
```

Each per-file job writes **only histograms** (`hists_<i>.root`); `MergeHistograms`
sums them (numerator and denominator separately) with ROOT's `TFileMerger`, and
`PlotValidation` derives the final efficiencies/plots from the **merged** histograms.
This is the statistically correct combination — averaging per-file efficiencies would
not be. Pick the producing workflow with `--workflow local|htcondor`.

---

## Tests

```bash
python3 -m pytest tests/ -q
```

Config/schema tests always run. The pipeline integration tests run only if the
sample ROOT files are found — point at them with `TICLNANOVAL_TEST_DIR` (defaults to
the repo's parent directory, where `step2.root` / `step4_inNANOAODSIM.root` live).
