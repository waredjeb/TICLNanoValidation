"""LAW tasks for TICL NanoAOD validation.

Tasks are deliberately thin: they expand inputs, build a RunConfig from YAML +
overrides, call ``ticlNanoVal.pipeline.run``, and stage the resulting directory as
a single ``.tgz`` target. ROOT is imported lazily (inside ``run``) so that
scheduling/indexing the tasks does not require the analysis environment.

Tasks
-----
* ``ValidateFile``         : one input file, run locally.
* ``ValidateFilesLocal``   : many files, one local branch per file.
* ``ValidateFilesHTCondor``: many files, one HTCondor job per file (lxplus).
* ``MergeSummaries``       : merge per-file summary.json into one summary.

The local and HTCondor multi-file tasks share ``ValidateFilesBase``; the only
difference is the workflow mix-in and the default storage backend.
"""

from __future__ import annotations

import glob
import os
import tarfile
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
    input_files = luigi.Parameter(description="input file path or glob")
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

    def run_pipeline(self, input_files, dest_dir):
        """Run the analysis pipeline into ``dest_dir`` (imports ROOT lazily)."""
        from ticlNanoVal.pipeline import run_from_yaml

        return run_from_yaml(
            config_paths=self.config_paths(),
            input_files=input_files,
            output_dir=dest_dir,
            overrides=self.overrides(),
        )


def _tar_dir(src_dir: str, tar_path: str):
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(src_dir, arcname=".")


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
# Single file (local)
# --------------------------------------------------------------------------- #
class ValidateFile(BaseParams):
    """Run validation on a single input file (local)."""

    def output(self):
        return law.LocalFileTarget(os.path.join(self.output_dir, "summary.json"))

    def run(self):
        out = self.output()
        out.parent.touch()
        self.run_pipeline(self.input_files, os.path.dirname(out.path) or ".")


# --------------------------------------------------------------------------- #
# Many files (workflow): one branch per file
# --------------------------------------------------------------------------- #
class ValidateFilesBase(BaseParams, law.BaseWorkflow):
    """One branch per input file; each branch stages a results tarball."""

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
        return f"file_{self.branch}_{stem}.tgz"

    def output(self):
        rel = self._branch_rel()
        if str(self.store) == "wlcg":
            # base path comes from the default wlcg_fs in law.cfg
            return law.wlcg.WLCGFileTarget(os.path.join(self.output_dir, rel))
        return law.LocalFileTarget(os.path.join(self.output_dir, rel))

    def run(self):
        # Run into a local scratch dir, tar it, then stage the tarball to the target.
        with tempfile.TemporaryDirectory() as scratch:
            results_dir = os.path.join(scratch, "results")
            os.makedirs(results_dir, exist_ok=True)
            self.run_pipeline(self.branch_data, results_dir)

            tar_path = os.path.join(scratch, "results.tgz")
            _tar_dir(results_dir, tar_path)

            out = self.output()
            out.parent.touch()
            out.copy_from_local(tar_path)


class ValidateFilesLocal(ValidateFilesBase, law.LocalWorkflow):
    """Run all files locally, one branch per file (parallel via --workers)."""


class ValidateFilesHTCondor(ValidateFilesBase, HTCondorWorkflow):
    """Submit one HTCondor job per file (lxplus). Defaults to EOS (wlcg) output."""

    store = luigi.Parameter(default="wlcg", description="output store: local|wlcg")


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
class MergeSummaries(BaseParams):
    """Merge the per-file summaries produced by a local validation workflow."""

    max_files = luigi.IntParameter(default=-1)

    def requires(self):
        return ValidateFilesLocal(
            configs=self.configs,
            input_files=self.input_files,
            output_dir=self.output_dir,
            modules=self.modules,
            strategy=self.strategy,
            threads=self.threads,
            max_files=self.max_files,
        )

    def output(self):
        return law.LocalFileTarget(os.path.join(self.output_dir, "merged_summary.json"))

    def run(self):
        import json

        agg = {}
        n = 0
        # self.input() is the workflow's (possibly nested) target collection.
        targets = [t for t in _collect_file_targets(self.input()) if t.path.endswith(".tgz")]
        for target in targets:
            with tarfile.open(target.path, "r:gz") as tar:
                member = tar.extractfile("./summary.json")
                if member is None:
                    continue
                data = json.load(member)
            n += 1
            for collection, metrics in data.items():
                bucket = agg.setdefault(collection, {})
                for name, value in metrics.items():
                    bucket.setdefault(name, []).append(value)

        merged = {
            collection: {
                name: {
                    "mean": sum(vals) / len(vals),
                    "min": min(vals),
                    "max": max(vals),
                    "n_files": len(vals),
                }
                for name, vals in metrics.items()
            }
            for collection, metrics in agg.items()
        }
        merged["_metadata"] = {"n_files": n, "input": str(self.input_files)}

        out = self.output()
        out.parent.touch()
        out.dump(merged, indent=2)
