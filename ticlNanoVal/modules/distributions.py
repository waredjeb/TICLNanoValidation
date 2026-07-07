"""Basic kinematic distributions per collection (eta, phi, energy, pt, n).

Runs over both reco and sim collections (e.g. SimTracksters), since a sim
trackster collection is just another named set of branches under the schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from .base import AnalysisModule, Bookings, RunContext
from .registry import register_module

# (field, binning-axis, x-label)
_OBSERVABLES = [
    ("eta", "eta", r"$\eta$"),
    ("phi", "phi", r"$\phi$"),
    ("energy", "energy", "Raw energy [GeV]"),
    ("pt", "pt", r"$p_\mathrm{T}$ [GeV]"),
]


@register_module
class DistributionsModule(AnalysisModule):
    name = "distributions"
    supports_sim = True

    # -- shared implementation, parameterized by physical collection name --- #
    def _book(
        self, rdf, columns, collection: str, field: Callable[[str], str], size: str
    ) -> Bookings:
        out: Bookings = {}
        for fname, axis_name, _ in _OBSERVABLES:
            branch = field(fname)
            if branch not in columns:
                continue
            ax = self.binning.axis(axis_name)
            model = (f"{collection}_{fname}", f"{collection} {fname}", ax.bins, ax.min, ax.max)
            out[fname] = rdf.Histo1D(model, branch)
        if size in columns:
            out["multiplicity"] = rdf.Histo1D(
                (f"{collection}_n", f"{collection} multiplicity", 50, 0, 50), size
            )
        return out

    def _metrics(self, results, collection: str) -> Dict[str, float]:
        m: Dict[str, float] = {}
        for key, h in results.items():
            m[f"{collection}_{key}_mean"] = h.GetMean()
            m[f"{collection}_{key}_rms"] = h.GetRMS()
        return m

    def _plot(self, results, output_dir: Path, collection: str):
        out = Path(output_dir) / collection
        labels = {f: lbl for f, _, lbl in _OBSERVABLES}
        labels["multiplicity"] = "Multiplicity"
        for key, h in results.items():
            self.plotter.hist1d(
                h, out, key, xlabel=labels.get(key, key), ylabel="Entries"
            )

    # -- reco collections ---------------------------------------------------- #
    def book(self, rdf, ctx: RunContext, reco_key: str) -> Bookings:
        reco = self.schema.reco_name(reco_key)
        return self._book(
            rdf, ctx.columns, reco,
            lambda fname: self.schema.field(reco, fname),
            self.schema.size(reco),
        )

    def metrics(self, results, ctx: RunContext, reco_key: str) -> Dict[str, float]:
        return self._metrics(results, self.schema.reco_name(reco_key))

    def plot(self, results, metrics, output_dir: Path, ctx: RunContext, reco_key: str):
        self._plot(results, output_dir, self.schema.reco_name(reco_key))

    # -- sim collections ------------------------------------------------------ #
    def book_sim(self, rdf, ctx: RunContext, sim_key: str) -> Bookings:
        sim = self.schema.sim(sim_key).tracksters
        return self._book(
            rdf, ctx.columns, sim,
            lambda fname: self.schema.field(sim, fname),
            self.schema.size(sim),
        )

    def metrics_sim(self, results, ctx: RunContext, sim_key: str) -> Dict[str, float]:
        return self._metrics(results, self.schema.sim(sim_key).tracksters)

    def plot_sim(self, results, metrics, output_dir: Path, ctx: RunContext, sim_key: str):
        self._plot(results, output_dir, self.schema.sim(sim_key).tracksters)
