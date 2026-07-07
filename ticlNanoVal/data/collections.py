"""Resolve logical collection names to physical NanoAOD branch names.

This is the abstraction that lets the *same* analysis code run on HLT and offline
files. Modules ask for, e.g., ``schema.reco_field("clue3d", "energy")`` and get back
``ticlTrackstersCLUE3DHigh_raw_energy`` (offline) or
``hltTiclTrackstersCLUE3DHigh_raw_energy`` (HLT) depending only on which YAML schema
was loaded.

The HLT/offline naming is *not* a simple prefix (``ticlTrackstersCLUE3DHigh`` ->
``hltTiclTrackstersCLUE3DHigh``), and the association token (``SimCP``) differs from
the kinematics collection (``ticlSimTrackstersfromCPs``), so every physical name is
listed explicitly in the schema rather than derived by a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

from ..config.schema import SchemaConfig, SimCollection


@dataclass(frozen=True)
class Association:
    """The set of branches describing one (sim, reco, direction) association.

    Branch layout produced by the TICL ntuplizer, e.g. for the head
    ``SimCP2ticlTrackstersCLUE3DHighByHits``:

    * ``count``  : per-object number of links (length == n source objects)
    * ``index``  : flat per-link target index
    * ``score``  : flat per-link score
    * ``shared`` : flat per-link shared energy
    """

    head: str
    count: str
    index: str
    score: str
    shared: str

    def branches(self) -> List[str]:
        return [self.count, self.index, self.score, self.shared]

    def exists(self, columns: Set[str]) -> bool:
        return all(b in columns for b in self.branches())


class CollectionSchema:
    """Pure name resolver built from a :class:`SchemaConfig` (no ROOT needed)."""

    def __init__(self, cfg: SchemaConfig):
        self.cfg = cfg

    # -- identity ---------------------------------------------------------- #
    @property
    def name(self) -> str:
        return self.cfg.name

    # -- reco collections -------------------------------------------------- #
    def reco_keys(self) -> List[str]:
        return list(self.cfg.reco.keys())

    def reco_name(self, key: str) -> str:
        """Physical reco collection name for a logical key (e.g. ``clue3d``)."""
        try:
            return self.cfg.reco[key]
        except KeyError as exc:
            raise KeyError(
                f"Unknown reco key '{key}'. Known: {sorted(self.cfg.reco)}"
            ) from exc

    # -- sim collections --------------------------------------------------- #
    def sim_keys(self) -> List[str]:
        return list(self.cfg.sim.keys())

    def sim(self, key: str) -> SimCollection:
        try:
            return self.cfg.sim[key]
        except KeyError as exc:
            raise KeyError(
                f"Unknown sim key '{key}'. Known: {sorted(self.cfg.sim)}"
            ) from exc

    # -- field branches ---------------------------------------------------- #
    def field(self, collection: str, field: str) -> str:
        """Resolve a field template (e.g. ``eta``) for a physical collection."""
        try:
            template = self.cfg.fields[field]
        except KeyError as exc:
            raise KeyError(
                f"Unknown field '{field}'. Known: {sorted(self.cfg.fields)}"
            ) from exc
        return template.format(coll=collection)

    def reco_field(self, key: str, field: str) -> str:
        return self.field(self.reco_name(key), field)

    def sim_field(self, key: str, field: str) -> str:
        return self.field(self.sim(key).tracksters, field)

    @staticmethod
    def size(collection: str) -> str:
        """NanoAOD counter branch for a collection (``nXxx``)."""
        return f"n{collection}"

    def reco_size(self, key: str) -> str:
        return self.size(self.reco_name(key))

    def sim_size(self, key: str) -> str:
        return self.size(self.sim(key).tracksters)

    # -- associations ------------------------------------------------------ #
    def association(self, sim_key: str, reco_key: str, direction: str) -> Association:
        """Build the :class:`Association` for a (sim, reco) pair and direction.

        ``direction`` is ``"sim2reco"`` (efficiency view, one entry per sim object)
        or ``"reco2sim"`` (fake view, one entry per reco object).
        """
        sim = self.sim(sim_key)
        reco = self.reco_name(reco_key)
        if direction == "sim2reco":
            head = self.cfg.assoc_sim2reco.format(sim=sim.token, reco=reco)
        elif direction == "reco2sim":
            head = self.cfg.assoc_reco2sim.format(sim=sim.token, reco=reco)
        else:
            raise ValueError(
                f"direction must be 'sim2reco' or 'reco2sim', got {direction!r}"
            )
        return Association(
            head=head,
            count=f"{head}_n{head}Links",
            index=f"{head}Links_index",
            score=f"{head}Links_score",
            shared=f"{head}Links_sharedEnergy",
        )

    # -- runtime discovery ------------------------------------------------- #
    def available_reco_keys(
        self, columns: Set[str], wanted: Optional[Iterable[str]] = None
    ) -> List[str]:
        """Reco keys whose collection is actually present in the file."""
        keys = list(wanted) if wanted else self.reco_keys()
        return [k for k in keys if self.reco_size(k) in columns]

    def available_sim_keys(
        self,
        columns: Set[str],
        reco_key: str,
        direction: str,
        wanted: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """Sim keys that have an existing association with ``reco_key``."""
        keys = list(wanted) if wanted else self.sim_keys()
        out = []
        for sim_key in keys:
            if self.association(sim_key, reco_key, direction).exists(columns):
                out.append(sim_key)
        return out

    def available_sim_kinematics_keys(
        self, columns: Set[str], wanted: Optional[Iterable[str]] = None
    ) -> List[str]:
        """Sim keys whose trackster collection is present, independent of matching."""
        keys = list(wanted) if wanted else self.sim_keys()
        return [k for k in keys if self.sim_size(k) in columns]
