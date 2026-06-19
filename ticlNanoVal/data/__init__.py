"""Data layer: RDataFrame loading and the collection/alias schema."""

from .collections import Association, CollectionSchema
from .loader import DataLoader

__all__ = ["Association", "CollectionSchema", "DataLoader"]
