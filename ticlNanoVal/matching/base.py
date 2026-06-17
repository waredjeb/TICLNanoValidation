"""Matching strategy interface + standardized output schema.

Standardized output (the contract every strategy fulfils), per (sim, reco, dir):

    sim2reco (efficiency view, one entry per *sim* object):
        match_{sim}_{reco}_simIdx        RVec<int>    best reco index, -1 if none
        match_{sim}_{reco}_simQuality    RVec<float>  quality of the best match
        match_{sim}_{reco}_simIsMatched  RVec<int>    1 if matched above threshold

    reco2sim (fake view, one entry per *reco* object):
        match_{reco}_{sim}_recoIdx       RVec<int>    best sim index, -1 if none
        match_{reco}_{sim}_recoQuality   RVec<float>
        match_{reco}_{sim}_recoIsFake    RVec<int>    1 if NOT matched (fake)

A strategy only has to describe *how good a single link is* and *how to compare /
threshold qualities*; the generic best-match loop below is shared. This keeps new
strategies to a few lines while guaranteeing the same output columns.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Set, Tuple

import ROOT

from ..config.schema import MatchingConfig
from ..data.collections import CollectionSchema

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatchColumns:
    """Names of the standardized columns for one (sim, reco, direction) match."""

    idx: str
    quality: str
    flag: str  # is_matched (sim2reco) or is_fake (reco2sim)
    direction: str
    sim_key: str
    reco_key: str

    @staticmethod
    def make(
        schema: CollectionSchema, sim_key: str, reco_key: str, direction: str
    ) -> "MatchColumns":
        sim_token = schema.sim(sim_key).token
        reco = schema.reco_name(reco_key)
        if direction == "sim2reco":
            base = f"match_{sim_token}_{reco}"
            return MatchColumns(
                idx=f"{base}_simIdx",
                quality=f"{base}_simQuality",
                flag=f"{base}_simIsMatched",
                direction=direction,
                sim_key=sim_key,
                reco_key=reco_key,
            )
        elif direction == "reco2sim":
            base = f"match_{reco}_{sim_token}"
            return MatchColumns(
                idx=f"{base}_recoIdx",
                quality=f"{base}_recoQuality",
                flag=f"{base}_recoIsFake",
                direction=direction,
                sim_key=sim_key,
                reco_key=reco_key,
            )
        raise ValueError(f"bad direction {direction!r}")


class MatchingStrategy(ABC):
    """Base class for matching strategies. Subclasses register via the registry.

    Subclasses implement small C++ snippets describing per-link quality and how
    qualities are ordered/thresholded. The shared best-match loop in
    :meth:`define` turns those into the standardized output columns.
    """

    name: str = "base"

    def __init__(self, config: MatchingConfig):
        self.config = config

    # -- pieces a strategy must provide ----------------------------------- #
    @abstractmethod
    def quality_expr(self) -> str:
        """C++ expression for a single link's quality.

        Available variables: ``score`` (float), ``shared`` (float),
        ``denom`` (float, source object's raw energy).
        """

    @abstractmethod
    def worst_quality(self) -> str:
        """C++ literal used to initialise the running best (e.g. ``-1.f``)."""

    @abstractmethod
    def is_better_expr(self) -> str:
        """C++ bool: is candidate ``q`` better than ``best``? (e.g. ``q > best``)."""

    @abstractmethod
    def passes_expr(self, threshold: float) -> str:
        """C++ bool: does ``best`` pass ``threshold``? (e.g. ``best > 0.5``)."""

    # -- shared best-match loop ------------------------------------------- #
    def define(
        self,
        rdf: "ROOT.RDataFrame",
        schema: CollectionSchema,
        sim_key: str,
        reco_key: str,
        direction: str,
    ) -> Tuple["ROOT.RDataFrame", MatchColumns]:
        """Add the standardized match columns for one (sim, reco, direction)."""
        cols = MatchColumns.make(schema, sim_key, reco_key, direction)
        assoc = schema.association(sim_key, reco_key, direction)

        # The number of source objects comes from the collection counter branch
        # (nXxx), NOT from the association's per-object link-count array: when a
        # reco collection is empty the ntuplizer may write an empty association,
        # and we still want one match entry per source object so the output stays
        # aligned with the kinematics arrays.
        if direction == "sim2reco":
            denom = schema.sim_field(sim_key, "energy")
            nobj_branch = schema.sim_size(sim_key)
            flag_expr = "best_idx >= 0 ? 1 : 0"  # is_matched
        else:
            denom = schema.reco_field(reco_key, "energy")
            nobj_branch = schema.reco_size(reco_key)
            flag_expr = "best_idx < 0 ? 1 : 0"  # is_fake

        threshold = self.config.threshold(direction)
        tuple_col = f"{cols.idx}__tuple"

        loop = f"""
        const auto& cnt   = {assoc.count};
        const auto& lidx  = {assoc.index};
        const auto& lscore= {assoc.score};
        const auto& lshare= {assoc.shared};
        const auto& edenom= {denom};
        const int nobj = (int){nobj_branch};
        const int ncnt = (int)cnt.size();
        ROOT::VecOps::RVec<int>   out_idx;
        ROOT::VecOps::RVec<float> out_q;
        ROOT::VecOps::RVec<int>   out_flag;
        out_idx.reserve(nobj); out_q.reserve(nobj); out_flag.reserve(nobj);
        int offset = 0;
        for (int i = 0; i < nobj; ++i) {{
            const int c = (i < ncnt) ? (int)cnt[i] : 0;
            int   best_idx = -1;
            float best     = {self.worst_quality()};
            const float denom = (i < (int)edenom.size()) ? edenom[i] : 0.f;
            for (int j = 0; j < c; ++j) {{
                const int   l      = offset + j;
                const float score  = lscore[l];
                const float shared = lshare[l];
                const float q      = {self.quality_expr()};
                if ({self.is_better_expr()}) {{ best = q; best_idx = lidx[l]; }}
            }}
            const float best_q = best;
            if (!({self.passes_expr(threshold)})) best_idx = -1;
            out_idx.push_back(best_idx);
            out_q.push_back(best_q);
            out_flag.push_back({flag_expr});
            offset += c;
        }}
        return std::make_tuple(out_idx, out_q, out_flag);
        """

        rdf = (
            rdf.Define(tuple_col, loop)
            .Define(cols.idx, f"std::get<0>({tuple_col})")
            .Define(cols.quality, f"std::get<1>({tuple_col})")
            .Define(cols.flag, f"std::get<2>({tuple_col})")
        )
        return rdf, cols


def apply_matching(
    rdf: "ROOT.RDataFrame",
    schema: CollectionSchema,
    strategy: MatchingStrategy,
    columns: Set[str],
    reco_keys: List[str],
    sim_keys: List[str],
):
    """Apply ``strategy`` to every existing (sim, reco, direction) association.

    Returns ``(rdf, match_map)`` where ``match_map[(direction, sim, reco)]`` is the
    :class:`MatchColumns` describing the standardized columns that were defined.
    Associations that don't exist in the file are skipped (e.g. reco2sim in offline).
    """
    match_map = {}
    for reco_key in reco_keys:
        for direction in ("sim2reco", "reco2sim"):
            for sim_key in sim_keys:
                assoc = schema.association(sim_key, reco_key, direction)
                if not assoc.exists(columns):
                    continue
                rdf, cols = strategy.define(rdf, schema, sim_key, reco_key, direction)
                match_map[(direction, sim_key, reco_key)] = cols
                log.info(
                    "matched %s %s->%s (%s)", direction, sim_key, reco_key, strategy.name
                )
    return rdf, match_map
