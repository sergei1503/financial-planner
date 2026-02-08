"""
FPlan v2 Core Engine Package.

This package contains calculation engines and supporting infrastructure
for financial projections and analysis.

Modules:
    index_tracker: Index tracking for variable-rate loans (Prime, CPI)
"""

from fplan_v2.core.engine.index_tracker import IndexTracker

__all__ = ["IndexTracker"]

__version__ = "2.0.0"
__author__ = "FPlan Development Team"
