#!/usr/bin/env python3
"""V4B.7 recover cell e (Storage Read); never queries cell g."""
from __future__ import annotations

import os
import traceback
from pathlib import Path

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_v4b7_recover_e import run_v4b7_recover_e


def main() -> int:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-b976bb08-5fbf-48ec-a44")
    print(f"V4B.7 recover-e start pid={os.getpid()}", flush=True)
    try:
        rec = run_v4b7_recover_e(billing_project=project)
        Path("logs").mkdir(exist_ok=True)
        Path("logs/v4b7_result.json").write_text(canonical_json(rec) + "\n")
        print("DONE", rec["disposition"], rec["google_side_processed_bytes"]["cumulative_gib"], flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        Path("logs").mkdir(exist_ok=True)
        Path("logs/v4b7_error.txt").write_text(traceback.format_exc())
        print("FAILED", type(exc).__name__, exc, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
