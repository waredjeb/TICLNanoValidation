"""Orchestrates one analysis run: load -> match -> modules -> outputs.

This is the single place that contains the *physics flow*. LAW tasks call
:func:`run` and nothing else; they never touch RDataFrame, matching or modules.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import ROOT

from .config.schema import RunConfig
from .data.collections import CollectionSchema
from .data.loader import DataLoader
from .matching import apply_matching, get_strategy
from .modules import RunContext, get_module, order_modules

log = logging.getLogger(__name__)


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


def run(
    config: RunConfig,
    input_files: Union[str, List[str]],
    output_dir: Union[str, Path],
) -> Dict[str, Dict[str, float]]:
    """Run the configured modules over ``input_files`` and write outputs.

    Returns the metrics dict (also written to ``<output_dir>/summary.json``).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    schema = CollectionSchema(config.schema)

    # 1. Load -------------------------------------------------------------- #
    loader = DataLoader(enable_mt=config.enable_mt, threads=config.threads)
    rdf = loader.build(input_files, tree_name=config.tree_name)
    columns = DataLoader.columns(rdf)

    reco_keys = schema.available_reco_keys(columns, config.reco_keys or None)
    sim_keys = config.matching.sim_keys or schema.sim_keys()
    log.info("schema=%s reco=%s sim=%s", schema.name, reco_keys, sim_keys)
    if not reco_keys:
        log.warning("No configured reco collections found in input; nothing to do.")

    # 2. Match (pipeline phase, standardized columns) ---------------------- #
    strategy = get_strategy(config.matching.strategy)(config.matching)
    rdf, match_map = apply_matching(
        rdf, schema, strategy, columns, reco_keys, sim_keys
    )
    ctx = RunContext(schema=schema, config=config, columns=columns, match_map=match_map)

    # 3. Instantiate modules (dependency-ordered) -------------------------- #
    plotter = _make_plotter(config.output)
    module_names = order_modules(list(config.modules))
    modules = []
    for name in module_names:
        mod = get_module(name)(config, schema)
        mod.plotter = plotter
        modules.append(mod)
        rdf = mod.define(rdf, ctx)

    # 4. Book everything lazily, trigger once ------------------------------ #
    bookings: Dict[tuple, dict] = {}
    ptrs: List[ROOT.RDF.RResultPtr] = []
    for mod in modules:
        for reco_key in reco_keys:
            try:
                booked = mod.book(rdf, ctx, reco_key)
            except Exception:
                log.exception("book failed: module=%s reco=%s", mod.name, reco_key)
                continue
            if booked:
                bookings[(mod.name, reco_key)] = (mod, booked)
                ptrs.extend(booked.values())

    if ptrs:
        log.info("Triggering event loop over %d histograms ...", len(ptrs))
        ROOT.RDF.RunGraphs(ptrs)

    # 5. Realize -> metrics -> plots --------------------------------------- #
    summary: Dict[str, Dict[str, float]] = {}
    for (mod_name, reco_key), (mod, booked) in bookings.items():
        realized = {k: p.GetValue() for k, p in booked.items()}
        try:
            metrics = mod.metrics(realized, ctx, reco_key)
        except Exception:
            log.exception("metrics failed: module=%s reco=%s", mod_name, reco_key)
            metrics = {}
        reco = schema.reco_name(reco_key)
        summary.setdefault(reco, {}).update(metrics)
        if mod.plotter is not None:
            try:
                mod.plot(realized, metrics, output_dir / mod_name, ctx, reco_key)
            except Exception:
                log.exception("plot failed: module=%s reco=%s", mod_name, reco_key)

    # 6. Summary ----------------------------------------------------------- #
    if config.output.save_summary_json:
        summary_path = output_dir / "summary.json"
        with summary_path.open("w") as fh:
            json.dump(summary, fh, indent=2)
        log.info("Wrote %s", summary_path)
    return summary


def run_from_yaml(
    config_paths: List[Union[str, Path]],
    input_files: Union[str, List[str]],
    output_dir: Union[str, Path],
    overrides: Optional[dict] = None,
) -> Dict[str, Dict[str, float]]:
    """Convenience wrapper: load YAML config(s) then :func:`run`."""
    from .config.loader import load_config

    config = load_config(config_paths, overrides=overrides)
    return run(config, input_files, output_dir)
