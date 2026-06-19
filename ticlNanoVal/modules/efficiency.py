"""Efficiency (sim2reco) and fake rate (reco2sim) from standardized match columns.

This module is a pure *consumer* of matching: it never re-implements matching, it
only reads the standardized ``MatchColumns`` placed in the context by the active
strategy. Fake rate is produced only for collections whose reco2sim association
exists in the file (e.g. HLT), and skipped otherwise (e.g. offline).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .base import AnalysisModule, Bookings, RunContext
from .registry import register_module

# (field, binning-axis, x-label) used for efficiency vs. observable
_OBS = [
    ("eta", "eta", r"$\eta$"),
    ("energy", "energy", "Raw energy [GeV]"),
    ("pt", "pt", r"$p_\mathrm{T}$ [GeV]"),
]


@register_module
class EfficiencyModule(AnalysisModule):
    name = "efficiency"

    def define(self, rdf, ctx: RunContext):
        # Define "passing" (matched / fake) kinematics by masking with the flag.
        for (direction, sim_key, reco_key), mc in ctx.match_map.items():
            if direction == "sim2reco":
                src_field = lambda f: self.schema.sim_field(sim_key, f)  # noqa: E731
                obs = ("eta", "energy", "pt")
            else:  # reco2sim -> fake numerator uses reco kinematics
                src_field = lambda f: self.schema.reco_field(reco_key, f)  # noqa: E731
                obs = ("eta",)
            for field in obs:
                branch = src_field(field)
                if branch not in ctx.columns:
                    continue
                col = self._pass_col(mc, field)
                rdf = rdf.Define(col, f"{branch}[{mc.flag} > 0]")
        return rdf

    @staticmethod
    def _pass_col(mc, field: str) -> str:
        return f"{mc.idx}__pass_{field}"

    def book(self, rdf, ctx: RunContext, reco_key: str) -> Bookings:
        out: Bookings = {}
        # -- efficiency: denominator = all sim, numerator = matched sim ------ #
        for sim_key in ctx.sims_for(reco_key, "sim2reco"):
            mc = ctx.match(reco_key, sim_key, "sim2reco")
            for field, axis_name, _ in _OBS:
                denom_branch = self.schema.sim_field(sim_key, field)
                if denom_branch not in ctx.columns:
                    continue
                ax = self.binning.axis(axis_name)
                tag = f"eff_{sim_key}_{field}"
                out[f"{tag}__total"] = rdf.Histo1D(
                    (f"{tag}_total", tag, ax.bins, ax.min, ax.max), denom_branch
                )
                out[f"{tag}__pass"] = rdf.Histo1D(
                    (f"{tag}_pass", tag, ax.bins, ax.min, ax.max),
                    self._pass_col(mc, field),
                )
        # -- fake rate: denominator = all reco, numerator = fake reco -------- #
        for sim_key in ctx.sims_for(reco_key, "reco2sim"):
            mc = ctx.match(reco_key, sim_key, "reco2sim")
            denom_branch = self.schema.reco_field(reco_key, "eta")
            if denom_branch not in ctx.columns:
                continue
            ax = self.binning.axis("eta")
            tag = f"fake_{sim_key}_eta"
            out[f"{tag}__total"] = rdf.Histo1D(
                (f"{tag}_total", tag, ax.bins, ax.min, ax.max), denom_branch
            )
            out[f"{tag}__pass"] = rdf.Histo1D(
                (f"{tag}_pass", tag, ax.bins, ax.min, ax.max),
                self._pass_col(mc, "eta"),
            )
        return out

    def metrics(self, results, ctx: RunContext, reco_key: str) -> Dict[str, float]:
        reco = self.schema.reco_name(reco_key)
        m: Dict[str, float] = {}
        # pair up *_total / *_pass and form ratios
        for key in results:
            if not key.endswith("__total"):
                continue
            tag = key[: -len("__total")]
            pass_key = f"{tag}__pass"
            if pass_key not in results:
                continue
            total = results[key].Integral()
            passed = results[pass_key].Integral()
            if total <= 0:
                continue
            kind = "efficiency" if tag.startswith("eff_") else "fake_rate"
            # tag like eff_cp_eta / fake_cp_eta -> sim key + observable
            _, sim_key, obs = tag.split("_", 2)
            if obs == "eta":  # report the overall (eta-integrated) number once
                m[f"{reco}_{sim_key}_{kind}"] = passed / total
        return m

    def plot(self, results, metrics, output_dir: Path, ctx: RunContext, reco_key: str):
        # Driven by the histogram dict (not ctx.match_map) so this works equally when
        # re-plotting from a merged ROOT file, where no matching context exists.
        reco = self.schema.reco_name(reco_key)
        out = Path(output_dir) / reco
        labels = {field: xlabel for field, _, xlabel in _OBS}
        for key in results:
            if not key.endswith("__total"):
                continue
            tag = key[: -len("__total")]
            if f"{tag}__pass" not in results:
                continue
            kind, sim_key, obs = tag.split("_", 2)  # eff|fake, sim key, observable
            if kind == "eff":
                name, ylabel = f"efficiency_{sim_key}_vs_{obs}", "Efficiency"
            else:
                name, ylabel = f"fake_rate_{sim_key}_vs_{obs}", "Fake rate"
            self.plotter.efficiency(
                results[f"{tag}__pass"],
                results[f"{tag}__total"],
                out,
                name,
                xlabel=labels.get(obs, obs),
                ylabel=ylabel,
            )
