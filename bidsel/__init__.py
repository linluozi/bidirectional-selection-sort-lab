"""Bidirectional selection sort, with the optimisations that actually pay.

This package exists because the popular "double-ended selection sort" write-up
gets the *reason* for its speed-up wrong. It claims the comparison count is
roughly halved. It is not: the comparison count is essentially unchanged
(measured 1.00x). What is halved is the number of inner-loop iterations, and
in CPython the loop control overhead is the expensive part.

See ``docs/CLAIMS.md`` for the measurements behind every claim in this README.

Public API
----------
``selection_sort``               baseline, one extremum per pass (upstream shape)
``selection_sort_bidirectional`` double-ended, no micro-optimisation
``selection_sort_fast``          double-ended + cached extrema + sorted precheck
``count_operations``             instrumentation used by the tests and benchmarks
"""

from __future__ import annotations

from .core import (
    Arms,
    OpCounts,
    count_operations,
    selection_sort,
    selection_sort_bidirectional,
    selection_sort_fast,
)

__version__ = "1.0.0"
__all__ = [
    "Arms",
    "OpCounts",
    "count_operations",
    "selection_sort",
    "selection_sort_bidirectional",
    "selection_sort_fast",
    "__version__",
]
