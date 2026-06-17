"""Base class for validation modules."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import ROOT


class ValidationModule(ABC):
    """
    Base class for all validation modules.

    Each module implements specific validation/analysis tasks and follows
    a standard interface for integration into the validation framework.
    """

    def __init__(self, config, name: Optional[str] = None):
        """
        Initialize the validation module.

        Args:
            config: ValidationConfig object with all settings
            name: Optional module name (defaults to class name)
        """
        self.config = config
        self.name = name or self.__class__.__name__.replace("Module", "").lower()
        self.dependencies = []  # List of module names this depends on
        self.histograms = {}
        self.metrics = {}

    @abstractmethod
    def define_columns(self, rdf: ROOT.RDataFrame) -> ROOT.RDataFrame:
        """
        Define new RDataFrame columns needed by this module.

        This is called once during setup and should return the modified RDataFrame
        with any additional columns defined via Define().

        Args:
            rdf: Input RDataFrame

        Returns:
            RDataFrame with additional columns defined
        """
        pass

    @abstractmethod
    def book_histograms(self, collection: str) -> Dict[str, Any]:
        """
        Return dictionary of histogram definitions for a collection.

        Each histogram definition should be a dict with:
        - 'name': histogram name
        - 'title': histogram title
        - 'bins': number of bins (or tuple for 2D)
        - 'xmin': x-axis minimum
        - 'xmax': x-axis maximum
        - 'ymin': y-axis minimum (for 2D)
        - 'ymax': y-axis maximum (for 2D)
        - 'variable': RDataFrame expression for variable to plot

        Args:
            collection: Name of the collection (e.g., "ticlTrackstersCLUE3DHigh")

        Returns:
            Dictionary mapping histogram keys to histogram definitions
        """
        pass

    @abstractmethod
    def fill_histograms(
        self,
        rdf: ROOT.RDataFrame,
        collection: str,
    ) -> Dict[str, ROOT.RDF.RResultPtr]:
        """
        Fill histograms using RDataFrame.

        Args:
            rdf: RDataFrame with data
            collection: Name of the collection to analyze

        Returns:
            Dictionary mapping histogram keys to RResultPtr objects
        """
        pass

    def compute_metrics(
        self,
        histograms: Dict[str, Any],
        collection: str
    ) -> Dict[str, float]:
        """
        Compute summary metrics from histograms.

        Override this method to extract numerical metrics from histograms.
        Default implementation returns empty dict.

        Args:
            histograms: Dictionary of filled histograms
            collection: Name of the collection

        Returns:
            Dictionary mapping metric names to values
        """
        return {}

    @abstractmethod
    def plot(
        self,
        histograms: Dict[str, Any],
        metrics: Dict[str, float],
        output_dir: Path,
        collection: str
    ):
        """
        Generate plots from histograms.

        Args:
            histograms: Dictionary of filled histograms
            metrics: Dictionary of computed metrics
            output_dir: Directory to save plots
            collection: Name of the collection
        """
        pass

    def get_dependencies(self) -> List[str]:
        """
        Get list of module names this module depends on.

        Returns:
            List of module names
        """
        return self.dependencies

    def can_run_standalone(self) -> bool:
        """
        Check if this module can run without dependencies.

        Returns:
            True if module has no dependencies
        """
        return len(self.dependencies) == 0

    def validate_inputs(self, rdf: ROOT.RDataFrame) -> bool:
        """
        Validate that required columns exist in the RDataFrame.

        Override this to check for required columns before running.

        Args:
            rdf: RDataFrame to validate

        Returns:
            True if all required inputs are present
        """
        return True

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"
