"""Orchestrates one analysis run: load -> match -> modules -> outputs.

This is the single place that contains the *physics flow*. LAW tasks call into the
functions here and nothing else; they never touch RDataFrame, matching or modules.

Two output paths share the same event loop:

* :func:`run` (and :func:`run_from_yaml`): book histograms, then immediately compute
  metrics + render plots + write ``summary.json`` for a single input. Used by the CLI
  and the single-file LAW task.
* :func:`run_histograms`: book histograms and persist them to a ROOT file (no plots).
  One per input file on the batch. :func:`plot_from_histograms` then reads the
  *merged* ROOT file once and produces the final, correctly-combined plots + summary.

Merging histograms (numerator/denominator separately) and re-deriving efficiencies
from the sum is the only statistically correct way to combine many files — averaging
per-file efficiencies would be wrong.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import ROOT

from .config.schema import RunConfig
from .data.collections import CollectionSchema
from .data.loader import DataLoader
from .matching import apply_matching, get_strategy
from .modules import RunContext, get_module, order_modules

log = logging.getLogger(__name__)

# (module_name, reco_key) -> {hist_key: TH1-like}
Realized = Dict[Tuple[str, str], Dict[str, object]]

# Marks a Realized key's collection slot as a sim key rather than a reco key.
SIM_KEY_PREFIX = "sim__"


def _make_plotter(output_config):
    """Construct a Plotter, or return None if plotting deps are unavailable.

    On batch workers the environment may lack matplotlib/mplhep; in that case we
    still want metrics + summary.json, just no plots.
    """
    try:
        from .plotting import Plotter

        return Plotter(output_config)
    except Exception as exc:  # pragma: no cover - environment dependent
        log.warning("Plotting unavailable (%s); plots will be skipped", exc)
        return None


# --------------------------------------------------------------------------- #
# Event loop (shared by run / run_histograms)
# --------------------------------------------------------------------------- #
def _run_event_loop(
    config: RunConfig, input_files: Union[str, List[str]]
) -> Tuple[CollectionSchema, RunContext, Dict[str, object], Realized]:
    """Load, match, book and trigger the event loop once.

    Returns ``(schema, ctx, modules, realized)`` where ``modules`` maps module name
    to its instance and ``realized`` maps ``(module, reco_key)`` to ``{hist_key: TH1}``.
    """
    schema = CollectionSchema(config.schema)

    loader = DataLoader(enable_mt=config.enable_mt, threads=config.threads)
    rdf = loader.build(input_files, tree_name=config.tree_name)
    columns = DataLoader.columns(rdf)

    reco_keys = schema.available_reco_keys(columns, config.reco_keys or None)
    sim_keys = config.matching.sim_keys or schema.sim_keys()
    log.info("schema=%s reco=%s sim=%s", schema.name, reco_keys, sim_keys)
    if not reco_keys:
        log.warning("No configured reco collections found in input; nothing to do.")

    strategy = get_strategy(config.matching.strategy)(config.matching)
    rdf, match_map = apply_matching(rdf, schema, strategy, columns, reco_keys, sim_keys)
    ctx = RunContext(schema=schema, config=config, columns=columns, match_map=match_map)

    modules: Dict[str, object] = {}
    for name in order_modules(list(config.modules)):
        mod = get_module(name)(config, schema)
        modules[name] = mod
        rdf = mod.define(rdf, ctx)

    sim_kine_keys = schema.available_sim_kinematics_keys(columns)

    bookings: Dict[Tuple[str, str], dict] = {}
    ptrs: List[ROOT.RDF.RResultPtr] = []
    for name, mod in modules.items():
        for reco_key in reco_keys:
            try:
                booked = mod.book(rdf, ctx, reco_key)
            except Exception:
                log.exception("book failed: module=%s reco=%s", name, reco_key)
                continue
            if booked:
                bookings[(name, reco_key)] = booked
                ptrs.extend(booked.values())
        if not mod.supports_sim:
            continue
        for sim_key in sim_kine_keys:
            try:
                booked = mod.book_sim(rdf, ctx, sim_key)
            except Exception:
                log.exception("book_sim failed: module=%s sim=%s", name, sim_key)
                continue
            if booked:
                bookings[(name, SIM_KEY_PREFIX + sim_key)] = booked
                ptrs.extend(booked.values())

    if ptrs:
        log.info("Triggering event loop over %d histograms ...", len(ptrs))
        ROOT.RDF.RunGraphs(ptrs)

    realized: Realized = {
        key: {hk: p.GetValue() for hk, p in booked.items()}
        for key, booked in bookings.items()
    }
    return schema, ctx, modules, realized


def _finalize(
    modules: Dict[str, object],
    realized: Realized,
    ctx: RunContext,
    output_dir: Path,
    plotter,
) -> Dict[str, Dict[str, float]]:
    """Compute metrics and (optionally) render plots from realized histograms."""
    summary: Dict[str, Dict[str, float]] = {}
    for (mod_name, key), results in realized.items():
        mod = modules[mod_name]
        mod.plotter = plotter
        is_sim = key.startswith(SIM_KEY_PREFIX)
        coll_key = key[len(SIM_KEY_PREFIX):] if is_sim else key
        try:
            metrics = (
                mod.metrics_sim(results, ctx, coll_key)
                if is_sim
                else mod.metrics(results, ctx, coll_key)
            )
        except Exception:
            log.exception("metrics failed: module=%s key=%s", mod_name, key)
            metrics = {}
        collection = (
            ctx.schema.sim(coll_key).tracksters if is_sim else ctx.schema.reco_name(coll_key)
        )
        summary.setdefault(collection, {}).update(metrics)
        if plotter is not None:
            try:
                if is_sim:
                    mod.plot_sim(results, metrics, Path(output_dir) / mod_name, ctx, coll_key)
                else:
                    mod.plot(results, metrics, Path(output_dir) / mod_name, ctx, coll_key)
            except Exception:
                log.exception("plot failed: module=%s key=%s", mod_name, key)
    return summary


def _write_summary(summary, config, output_dir: Path) -> None:
    if config.output.save_summary_json:
        summary_path = Path(output_dir) / "summary.json"
        with summary_path.open("w") as fh:
            json.dump(summary, fh, indent=2)
        log.info("Wrote %s", summary_path)


# --------------------------------------------------------------------------- #
# Histogram persistence (book -> ROOT file -> merge -> plot)
# --------------------------------------------------------------------------- #
def _write_hist_file(realized: Realized, hist_path: Union[str, Path]) -> None:
    """Persist realized histograms as ``<module>/<key>/<hist_key>`` in a TFile."""
    fh = ROOT.TFile(str(hist_path), "RECREATE")
    try:
        for (mod_name, key), results in realized.items():
            mdir = fh.GetDirectory(mod_name) or fh.mkdir(mod_name)
            sdir = mdir.GetDirectory(key) or mdir.mkdir(key)
            sdir.cd()
            for hist_key, obj in results.items():
                obj.SetName(hist_key)
                obj.Write(hist_key)
        fh.Write()
    finally:
        fh.Close()


def _read_hist_file(hist_path: Union[str, Path]) -> Realized:
    """Inverse of :func:`_write_hist_file`; detaches histograms from the file."""
    fh = ROOT.TFile.Open(str(hist_path))
    if not fh or fh.IsZombie():
        raise IOError(f"cannot open histogram file {hist_path}")
    realized: Realized = {}
    try:
        for mkey in fh.GetListOfKeys():
            mdir = fh.Get(mkey.GetName())
            if not isinstance(mdir, ROOT.TDirectory):
                continue
            for rkey in mdir.GetListOfKeys():
                sdir = mdir.Get(rkey.GetName())
                if not isinstance(sdir, ROOT.TDirectory):
                    continue
                results: Dict[str, object] = {}
                for hkey in sdir.GetListOfKeys():
                    obj = sdir.Get(hkey.GetName())
                    try:
                        obj.SetDirectory(0)  # survive file close
                    except AttributeError:
                        pass
                    results[hkey.GetName()] = obj
                if results:
                    realized[(mkey.GetName(), rkey.GetName())] = results
    finally:
        fh.Close()
    return realized


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def run(
    config: RunConfig,
    input_files: Union[str, List[str]],
    output_dir: Union[str, Path],
) -> Dict[str, Dict[str, float]]:
    """Run modules over ``input_files`` and write metrics + plots in one shot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _, ctx, modules, realized = _run_event_loop(config, input_files)
    plotter = _make_plotter(config.output)
    summary = _finalize(modules, realized, ctx, output_dir, plotter)
    _write_summary(summary, config, output_dir)
    return summary


def run_histograms(
    config: RunConfig,
    input_files: Union[str, List[str]],
    hist_path: Union[str, Path],
) -> str:
    """Book histograms for ``input_files`` and persist them to ``hist_path`` (no plots).

    This is what each per-file batch job runs; the per-file ROOT files are then summed
    by a merge step and plotted once by :func:`plot_from_histograms`.
    """
    _, _, _, realized = _run_event_loop(config, input_files)
    _write_hist_file(realized, hist_path)
    log.info("Wrote histograms to %s", hist_path)
    return str(hist_path)


def plot_from_histograms(
    config: RunConfig,
    hist_path: Union[str, Path],
    output_dir: Union[str, Path],
) -> Dict[str, Dict[str, float]]:
    """Produce final plots + summary from a (merged) histogram ROOT file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    schema = CollectionSchema(config.schema)
    realized = _read_hist_file(hist_path)
    modules = {
        name: get_module(name)(config, schema)
        for name in {mod_name for (mod_name, _) in realized}
    }
    # match_map / columns are not needed downstream: metrics() and plot() read only the
    # histogram dict and the schema.
    ctx = RunContext(schema=schema, config=config, columns=set(), match_map={})
    plotter = _make_plotter(config.output)
    summary = _finalize(modules, realized, ctx, output_dir, plotter)
    _write_summary(summary, config, output_dir)
    return summary


# --------------------------------------------------------------------------- #
# YAML convenience wrappers
# --------------------------------------------------------------------------- #
def _load(config_paths, overrides):
    from .config.loader import load_config

    return load_config(config_paths, overrides=overrides)


def run_from_yaml(
    config_paths: List[Union[str, Path]],
    input_files: Union[str, List[str]],
    output_dir: Union[str, Path],
    overrides: Optional[dict] = None,
) -> Dict[str, Dict[str, float]]:
    """Convenience wrapper: load YAML config(s) then :func:`run`."""
    return run(_load(config_paths, overrides), input_files, output_dir)


def run_histograms_from_yaml(
    config_paths: List[Union[str, Path]],
    input_files: Union[str, List[str]],
    hist_path: Union[str, Path],
    overrides: Optional[dict] = None,
) -> str:
    """Convenience wrapper: load YAML config(s) then :func:`run_histograms`."""
    return run_histograms(_load(config_paths, overrides), input_files, hist_path)


def plot_from_histograms_yaml(
    config_paths: List[Union[str, Path]],
    hist_path: Union[str, Path],
    output_dir: Union[str, Path],
    overrides: Optional[dict] = None,
) -> Dict[str, Dict[str, float]]:
    """Convenience wrapper: load YAML config(s) then :func:`plot_from_histograms`."""
    return plot_from_histograms(_load(config_paths, overrides), hist_path, output_dir)
