"""Smoke tests for ticlNanoVal.

The pure-config/schema tests always run (no ROOT needed). The pipeline tests run
only if the local sample files are available; point at them with the env var
``TICLNANOVAL_TEST_DIR`` (defaults to the repo's parent directory).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONFIGS = REPO / "configs"
SAMPLE_DIR = Path(os.environ.get("TICLNANOVAL_TEST_DIR", REPO.parent))
OFFLINE = SAMPLE_DIR / "step4_inNANOAODSIM.root"
HLT = SAMPLE_DIR / "step2.root"


# --------------------------------------------------------------------------- #
# Config + schema (no ROOT)
# --------------------------------------------------------------------------- #
def test_config_loads_and_layers():
    from ticlNanoVal.config import load_config

    cfg = load_config([CONFIGS / "base.yaml", CONFIGS / "offline.yaml"])
    assert cfg.schema.name == "offline"
    assert cfg.matching.strategy == "shared_energy"
    assert cfg.matching.threshold("sim2reco") == 0.5
    assert cfg.binning.axis("eta").bins == 50


def test_overrides_win():
    from ticlNanoVal.config import load_config

    cfg = load_config(
        [CONFIGS / "base.yaml", CONFIGS / "offline.yaml"],
        overrides={"run": {"modules": ["distributions"]}, "matching": {"strategy": "score"}},
    )
    assert cfg.modules == ["distributions"]
    assert cfg.matching.strategy == "score"


def test_schema_resolves_offline_vs_hlt_names():
    from ticlNanoVal.config import load_config
    from ticlNanoVal.data import CollectionSchema

    off = CollectionSchema(load_config([CONFIGS / "base.yaml", CONFIGS / "offline.yaml"]).schema)
    hlt = CollectionSchema(load_config([CONFIGS / "base.yaml", CONFIGS / "hlt.yaml"]).schema)

    assert off.reco_field("clue3d", "energy") == "ticlTrackstersCLUE3DHigh_raw_energy"
    assert hlt.reco_field("clue3d", "energy") == "hltTiclTrackstersCLUE3DHigh_raw_energy"
    # association heads
    assert off.association("cp", "clue3d", "sim2reco").head == "SimCP2ticlTrackstersCLUE3DHighByHits"
    assert hlt.association("cp", "clue3d", "reco2sim").head == "RecohltTiclTrackstersCLUE3DHigh2SimCPByHits"


def test_registries_populated():
    from ticlNanoVal.matching import available_strategies
    from ticlNanoVal.modules import available_modules, order_modules

    assert {"shared_energy", "score"} <= set(available_strategies())
    assert {"distributions", "efficiency"} <= set(available_modules())
    # ordering is stable and includes all requested
    assert set(order_modules(["efficiency", "distributions"])) == {"efficiency", "distributions"}


# --------------------------------------------------------------------------- #
# Pipeline integration (needs ROOT + sample files)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not OFFLINE.exists(), reason="offline sample not available")
def test_pipeline_offline(tmp_path):
    pytest.importorskip("ROOT")
    from ticlNanoVal.pipeline import run_from_yaml

    summary = run_from_yaml(
        [CONFIGS / "base.yaml", CONFIGS / "offline.yaml"],
        str(OFFLINE),
        tmp_path,
        overrides={"run": {"threads": 1}},
    )
    clue3d = summary["ticlTrackstersCLUE3DHigh"]
    # efficiency present, fake rate absent (offline has no reco2sim)
    assert clue3d["ticlTrackstersCLUE3DHigh_cp_efficiency"] == pytest.approx(0.55, abs=1e-6)
    assert not any("fake_rate" in k for k in clue3d)
    assert (tmp_path / "summary.json").exists()


@pytest.mark.skipif(not HLT.exists(), reason="HLT sample not available")
def test_pipeline_hlt_has_fake_rate(tmp_path):
    pytest.importorskip("ROOT")
    from ticlNanoVal.pipeline import run_from_yaml

    summary = run_from_yaml(
        [CONFIGS / "base.yaml", CONFIGS / "hlt.yaml"],
        str(HLT),
        tmp_path,
        overrides={"run": {"threads": 1}},
    )
    clue3d = summary["hltTiclTrackstersCLUE3DHigh"]
    # HLT has both directions
    assert any("efficiency" in k for k in clue3d)
    assert any("fake_rate" in k for k in clue3d)
