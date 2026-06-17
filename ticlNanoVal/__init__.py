"""ticlNanoVal: a small, flexible RDataFrame + LAW framework for TICL NanoAOD validation.

The package is split into two clearly separated layers:

* The *analysis layer* (``ticlNanoVal``) knows nothing about LAW/luigi. It loads
  ROOT files with RDataFrame, applies a pluggable matching strategy that emits a
  *standardized* set of columns, and runs analysis modules that consume them.
* The *workflow layer* (``workflow/``) is thin: it only orchestrates and schedules
  pipeline runs locally or on HTCondor.

Collection names (HLT vs offline) are never hardcoded in analysis code; they are
resolved through :class:`ticlNanoVal.data.collections.CollectionSchema`, which is
populated from YAML.
"""

__version__ = "0.1.0"
