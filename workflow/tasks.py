"""LAW tasks for TICL NanoAOD validation.

Tasks are deliberately thin: they expand inputs, build overrides from parameters,
and call into ``ticlNanoVal.pipeline``. ROOT is imported lazily (inside ``run``) so
that scheduling/indexing the tasks does not require the analysis environment.

Workflow
--------
The heavy per-file event loop runs in parallel (locally or on HTCondor); merging the
resulting histograms and producing the final plots run **locally** and cheaply:

    ValidateFiles{Local,HTCondor}   one branch per file -> hists_<i>.root   [parallel]
            |                        (histograms only, no plots)
    MergeHistograms                  TFileMerger sums all hists -> merged.root   [local]
            |
    PlotValidation                   merged.root -> final plots + summary.json   [local]

Combining at the *histogram* level (summing numerator/denominator, then re-deriving
efficiencies) is the only correct way to merge many files.

Tasks
-----
* ``ValidateFile``         : one input file, run locally, full plots + summary.
* ``ValidateFilesLocal``   : many files, one local branch per file (histograms).
* ``ValidateFilesHTCondor``: many files, one HTCondor job per file (histograms).
* ``MergeHistograms``      : sum per-file histograms into one ROOT file.
* ``PlotValidation``       : final, correctly-combined plots + summary from the merge.
"""

from __future__ import annotations

import glob
import os
import tempfile
from pathlib import Path

import law
import luigi

from .framework import REPO_DIR, HTCondorWorkflow

law.contrib.load("wlcg")


# --------------------------------------------------------------------------- #
# Shared parameters / helpers
# --------------------------------------------------------------------------- #
class BaseParams(law.Task):
    """Parameters common to all validation tasks."""

    configs = luigi.Parameter(
        description="comma-separated YAML config files (layered in order), "
        "e.g. configs/base.yaml,configs/offline.yaml",
    )
    input_files = luigi.Parameter(
        default="", description="input file path or glob (not needed for merge/plot "
        "from an explicit --hists glob)"
    )
    output_dir = luigi.Parameter(
        default="validation_output", description="base output directory"
    )
    modules = luigi.Parameter(default="", description="override modules (comma-sep)")
    strategy = luigi.Parameter(default="", description="override matching strategy")
    threads = luigi.IntParameter(default=4, description="RDataFrame threads")

    def config_paths(self):
        paths = []
        for c in str(self.configs).split(","):
            c = c.strip()
            if not c:
                continue
            paths.append(c if os.path.isabs(c) else os.path.join(REPO_DIR, c))
        return paths

    def overrides(self):
        run = {"threads": int(self.threads)}
        if self.modules:
            run["modules"] = [m.strip() for m in str(self.modules).split(",") if m.strip()]
        ov = {"run": run}
        if self.strategy:
            ov["matching"] = {"strategy": str(self.strategy)}
        return ov


def _collect_file_targets(obj):
    """Flatten nested dicts / lists / law TargetCollections into file targets."""
    out, stack = [], [obj]
    while stack:
        x = stack.pop()
        if hasattr(x, "path"):
            out.append(x)
        elif hasattr(x, "targets"):  # law TargetCollection
            t = x.targets
            stack.extend(t.values() if isinstance(t, dict) else t)
        elif isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, (list, tuple)):
            stack.extend(x)
    return out


# --------------------------------------------------------------------------- #
# Single file (local): full run with plots + summary
# --------------------------------------------------------------------------- #
class ValidateFile(BaseParams):
    """Run validation on a single input file (local): plots + summary in output_dir."""

    def output(self):
        return law.LocalFileTarget(os.path.join(self.output_dir, "summary.json"))

    def run(self):
        from ticlNanoVal.pipeline import run_from_yaml

        out = self.output()
        out.parent.touch()
        run_from_yaml(
            config_paths=self.config_paths(),
            input_files=self.input_files,
            output_dir=os.path.dirname(out.path) or ".",
            overrides=self.overrides(),
        )


# --------------------------------------------------------------------------- #
# Many files (workflow): one branch per file -> per-file histogram ROOT file
# --------------------------------------------------------------------------- #
class ValidateFilesBase(BaseParams, law.BaseWorkflow):
    """One branch per input file; each branch stages a histogram ROOT file."""

    exclude_index = True  # abstract base, not directly runnable

    max_files = luigi.IntParameter(default=-1, description="limit number of files (-1=all)")

    #: storage backend for branch outputs: "local" or "wlcg" (EOS via law.cfg)
    store = luigi.Parameter(default="local", description="output store: local|wlcg")

    def create_branch_map(self):
        files = sorted(glob.glob(str(self.input_files)))
        if self.max_files and self.max_files > 0:
            files = files[: self.max_files]
        return {i: f for i, f in enumerate(files)}

    def _branch_rel(self):
        stem = Path(self.branch_data).stem
        return f"hists_{self.branch}_{stem}.root"

    def output(self):
        rel = self._branch_rel()
        if str(self.store) == "wlcg":
            return law.wlcg.WLCGFileTarget(os.path.join(self.output_dir, rel))
        return law.LocalFileTarget(os.path.join(self.output_dir, rel))

    def run(self):
        from ticlNanoVal.pipeline import run_histograms_from_yaml

        # Book histograms into a local scratch file, then stage it to the target.
        with tempfile.TemporaryDirectory() as scratch:
            hist_path = os.path.join(scratch, "hists.root")
            run_histograms_from_yaml(
                config_paths=self.config_paths(),
                input_files=self.branch_data,
                hist_path=hist_path,
                overrides=self.overrides(),
            )
            out = self.output()
            out.parent.touch()
            out.copy_from_local(hist_path)


class ValidateFilesLocal(ValidateFilesBase, law.LocalWorkflow):
    """Run all files locally, one branch per file (parallel via --workers)."""


class ValidateFilesHTCondor(ValidateFilesBase, HTCondorWorkflow):
    """Submit one HTCondor job per file (lxplus). Defaults to EOS (wlcg) output."""

    store = luigi.Parameter(default="wlcg", description="output store: local|wlcg")


# --------------------------------------------------------------------------- #
# Merge (local): sum per-file histograms
# --------------------------------------------------------------------------- #
class MergeHistograms(BaseParams):
    """Sum the per-file histograms (numerator/denominator separately) into one file."""

    workflow = luigi.ChoiceParameter(
        default="htcondor",
        choices=("local", "htcondor"),
        description="which validation workflow produced the per-file histograms",
    )
    max_files = luigi.IntParameter(default=-1)
    store = luigi.Parameter(default="wlcg", description="store used by the workflow: local|wlcg")
    hists = luigi.Parameter(
        default="",
        description="glob of existing per-file histogram files to merge directly "
        "(e.g. '.../hists_*.root'); when set, the upstream workflow is NOT required",
    )

    def _workflow_cls(self):
        return ValidateFilesHTCondor if str(self.workflow) == "htcondor" else ValidateFilesLocal

    def requires(self):
        # Standalone merge: depend on nothing, just merge the given files.
        if str(self.hists):
            return []
        return self._workflow_cls()(
            configs=self.configs,
            input_files=self.input_files,
            output_dir=self.output_dir,
            modules=self.modules,
            strategy=self.strategy,
            threads=self.threads,
            max_files=self.max_files,
            store=self.store,
        )

    def output(self):
        return law.LocalFileTarget(os.path.join(self.output_dir, "merged.root"))

    def _input_paths(self):
        """Local paths of the per-file histogram files to merge."""
        merged = self.output().path
        if str(self.hists):
            return [
                p for p in sorted(glob.glob(str(self.hists)))
                if p.endswith(".root") and os.path.abspath(p) != os.path.abspath(merged)
            ]
        return [t.path for t in _collect_file_targets(self.input()) if t.path.endswith(".root")]

    def run(self):
        import ROOT

        paths = self._input_paths()
        if not paths:
            raise RuntimeError("no per-file histogram files found to merge")

        with tempfile.TemporaryDirectory() as scratch:
            # In workflow mode the inputs are law targets (may be remote); in --hists
            # mode they are plain paths. Build targets so both go through copy_to_local.
            if str(self.hists):
                targets = [law.LocalFileTarget(p) for p in paths]
            else:
                targets = [t for t in _collect_file_targets(self.input()) if t.path.endswith(".root")]

            local_files = []
            for i, target in enumerate(targets):
                dst = os.path.join(scratch, f"h{i}.root")
                target.copy_to_local(dst)
                local_files.append(dst)

            merged = os.path.join(scratch, "merged.root")
            merger = ROOT.TFileMerger(False)
            if not merger.OutputFile(merged):
                raise RuntimeError("could not open merge output file")
            for lf in local_files:
                merger.AddFile(lf)
            if not merger.Merge():
                raise RuntimeError("histogram merge failed")

            out = self.output()
            out.parent.touch()
            out.copy_from_local(merged)


# --------------------------------------------------------------------------- #
# Plot (local): final combined plots + summary from the merged histograms
# --------------------------------------------------------------------------- #
class PlotValidation(BaseParams):
    """Produce the final, correctly-combined plots + summary.json from the merge."""

    workflow = luigi.ChoiceParameter(default="htcondor", choices=("local", "htcondor"))
    max_files = luigi.IntParameter(default=-1)
    store = luigi.Parameter(default="wlcg", description="store used by the workflow: local|wlcg")
    hists = luigi.Parameter(
        default="",
        description="glob of existing per-file histogram files (passed to MergeHistograms); "
        "when set, merge + plot run standalone without the upstream workflow",
    )

    def requires(self):
        return MergeHistograms(
            configs=self.configs,
            input_files=self.input_files,
            output_dir=self.output_dir,
            modules=self.modules,
            strategy=self.strategy,
            threads=self.threads,
            workflow=self.workflow,
            max_files=self.max_files,
            store=self.store,
            hists=self.hists,
        )

    def output(self):
        return law.LocalFileTarget(os.path.join(self.output_dir, "summary.json"))

    def run(self):
        from ticlNanoVal.pipeline import plot_from_histograms_yaml

        out = self.output()
        out.parent.touch()
        plot_from_histograms_yaml(
            config_paths=self.config_paths(),
            hist_path=self.input().path,
            output_dir=os.path.dirname(out.path) or ".",
            overrides=self.overrides(),
        )
