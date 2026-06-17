"""Data loading utilities using RDataFrame."""

import ROOT
from pathlib import Path
from typing import List, Union
import glob


class DataLoader:
    """Handles RDataFrame setup and file loading."""

    def __init__(self, config):
        """
        Initialize data loader.

        Args:
            config: ValidationConfig object
        """
        self.config = config
        self._setup_multithreading()

    def _setup_multithreading(self):
        """Enable ROOT's implicit multi-threading if configured."""
        if self.config.enable_mt:
            if not ROOT.IsImplicitMTEnabled():
                if self.config.num_threads:
                    ROOT.EnableImplicitMT(self.config.num_threads)
                else:
                    ROOT.EnableImplicitMT()
                print(f"Multi-threading enabled with {ROOT.GetThreadPoolSize()} threads")

    def load_files(
        self,
        file_pattern: Union[str, List[str]],
        tree_name: str = "Events"
    ) -> ROOT.RDataFrame:
        """
        Load ROOT files into an RDataFrame.

        Args:
            file_pattern: Single file path, glob pattern, or list of file paths
            tree_name: Name of the TTree to load (default: "Events")

        Returns:
            RDataFrame with loaded data

        Raises:
            FileNotFoundError: If no files match the pattern
            RuntimeError: If RDataFrame creation fails
        """
        # Expand file pattern(s) to list of files
        files = self._expand_file_patterns(file_pattern)

        if not files:
            raise FileNotFoundError(f"No files found matching pattern: {file_pattern}")

        print(f"Loading {len(files)} file(s):")
        for f in files[:5]:  # Show first 5
            print(f"  - {f}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")

        # Create RDataFrame
        try:
            if len(files) == 1:
                rdf = ROOT.RDataFrame(tree_name, files[0])
            else:
                # Use TChain for multiple files
                chain = ROOT.TChain(tree_name)
                for f in files:
                    chain.Add(f)
                rdf = ROOT.RDataFrame(chain)

            # Print event count
            n_events = rdf.Count().GetValue()
            print(f"Total events: {n_events}")

            return rdf

        except Exception as e:
            raise RuntimeError(f"Failed to create RDataFrame: {e}")

    def _expand_file_patterns(
        self,
        patterns: Union[str, List[str]]
    ) -> List[str]:
        """
        Expand file patterns with glob support.

        Args:
            patterns: Single pattern or list of patterns

        Returns:
            List of expanded file paths
        """
        if isinstance(patterns, str):
            patterns = [patterns]

        files = []
        for pattern in patterns:
            # Expand glob pattern
            matches = glob.glob(pattern)
            if matches:
                files.extend(matches)
            else:
                # Not a glob pattern, treat as literal path
                if Path(pattern).exists():
                    files.append(pattern)

        # Remove duplicates and sort
        files = sorted(set(files))

        return files

    def check_branches(
        self,
        rdf: ROOT.RDataFrame,
        required_branches: List[str]
    ) -> dict:
        """
        Check which branches exist in the RDataFrame.

        Args:
            rdf: RDataFrame to check
            required_branches: List of branch names to check

        Returns:
            Dictionary mapping branch names to bool (exists or not)
        """
        available = set(rdf.GetColumnNames())
        return {branch: branch in available for branch in required_branches}

    def get_collection_size_branch(self, collection: str) -> str:
        """
        Get the name of the branch containing the collection size.

        Args:
            collection: Collection name (e.g., "ticlTrackstersCLUE3DHigh")

        Returns:
            Size branch name (e.g., "nticlTrackstersCLUE3DHigh")
        """
        return f"n{collection}"

    def collection_exists(self, rdf: ROOT.RDataFrame, collection: str) -> bool:
        """
        Check if a collection exists in the RDataFrame.

        Args:
            rdf: RDataFrame to check
            collection: Collection name

        Returns:
            True if the collection's size branch exists
        """
        size_branch = self.get_collection_size_branch(collection)
        return size_branch in rdf.GetColumnNames()
