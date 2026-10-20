"""Shared matplotlib bootstrap for tests/scripts in sandboxed environments."""
from __future__ import annotations

import os
from pathlib import Path


def configure_matplotlib() -> None:
    root = Path(__file__).resolve().parent.parent
    cache_dir = root / ".matplotlib_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache_dir)

    import matplotlib

    matplotlib.use("Agg", force=True)


configure_matplotlib()
