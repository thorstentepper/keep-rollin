"""Shared pytest configuration.

Pin matplotlib's non-interactive backend before any test module imports
pyplot. Both the CLI and the dashboard import it, and Streamlit's AppTest
renders figures on a worker thread; with an interactive backend such as TkAgg
that is a hard interpreter crash ("Tcl_AsyncDelete: async handler deleted by
the wrong thread"), not a catchable test failure.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg", force=True)
