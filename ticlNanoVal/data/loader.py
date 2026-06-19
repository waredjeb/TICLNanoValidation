"""Build an RDataFrame from one or more ROOT files, with implicit MT."""

from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import List, Set, Union

import ROOT

log = logging.getLogger(__name__)


class DataLoader:
    """Expand file patterns and create an RDataFrame over the ``Events`` tree."""

    def __init__(self, enable_mt: bool = True, threads: int = None):
        if enable_mt and not ROOT.IsImplicitMTEnabled():
            if threads:
                ROOT.EnableImplicitMT(int(threads))
            else:
                ROOT.EnableImplicitMT()
            log.info("Implicit MT enabled with %d threads", ROOT.GetThreadPoolSize())

    @staticmethod
    def expand(patterns: Union[str, List[str]]) -> List[str]:
        """Expand globs / comma-separated lists into a sorted unique file list."""
        if isinstance(patterns, str):
            patterns = [patterns]
        files: List[str] = []
        for pattern in patterns:
            for part in str(pattern).split(","):
                part = part.strip()
                if not part:
                    continue
                matches = glob.glob(part)
                if matches:
                    files.extend(matches)
                elif Path(part).exists():
                    files.append(part)
        return sorted(set(files))

    def build(
        self, patterns: Union[str, List[str]], tree_name: str = "Events"
    ) -> "ROOT.RDataFrame":
        files = self.expand(patterns)
        if not files:
            raise FileNotFoundError(f"No files match: {patterns}")
        log.info("Loading %d file(s) from tree '%s'", len(files), tree_name)
        if len(files) == 1:
            rdf = ROOT.RDataFrame(tree_name, files[0])
        else:
            chain = ROOT.TChain(tree_name)
            for f in files:
                chain.Add(f)
            rdf = ROOT.RDataFrame(chain)
        return rdf

    @staticmethod
    def columns(rdf: "ROOT.RDataFrame") -> Set[str]:
        """Set of available column (branch) names."""
        return set(str(c) for c in rdf.GetColumnNames())
