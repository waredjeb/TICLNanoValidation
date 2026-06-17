"""Basic kinematic distributions per reco collection (eta, phi, energy, pt, n)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

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

    def book(self, rdf, ctx: RunContext, reco_key: str) -> Bookings:
        reco = self.schema.reco_name(reco_key)
        out: Bookings = {}
        for field, axis_name, _ in _OBSERVABLES:
            branch = self.schema.field(reco, field)
            if branch not in ctx.columns:
                continue
            ax = self.binning.axis(axis_name)
            model = (f"{reco}_{field}", f"{reco} {field}", ax.bins, ax.min, ax.max)
            out[field] = rdf.Histo1D(model, branch)
        # multiplicity (per-event count)
        size = self.schema.size(reco)
        if size in ctx.columns:
            out["multiplicity"] = rdf.Histo1D(
                (f"{reco}_n", f"{reco} multiplicity", 50, 0, 50), size
            )
        return out

    def metrics(self, results, ctx: RunContext, reco_key: str) -> Dict[str, float]:
        reco = self.schema.reco_name(reco_key)
        m: Dict[str, float] = {}
        for key, h in results.items():
            m[f"{reco}_{key}_mean"] = h.GetMean()
            m[f"{reco}_{key}_rms"] = h.GetRMS()
        return m

    def plot(self, results, metrics, output_dir: Path, ctx: RunContext, reco_key: str):
        reco = self.schema.reco_name(reco_key)
        out = Path(output_dir) / reco
        labels = {f: lbl for f, _, lbl in _OBSERVABLES}
        labels["multiplicity"] = "Multiplicity"
        for key, h in results.items():
            self.plotter.hist1d(
                h, out, key, xlabel=labels.get(key, key), ylabel="Entries"
            )
