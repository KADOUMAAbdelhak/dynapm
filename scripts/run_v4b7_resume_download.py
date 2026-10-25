#!/usr/bin/env python3
"""Resume V4B.7 Storage Read from existing e-usage job (no new query)."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Force line-buffered logs even under nohup.
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_v4b7_recover_e import resume_existing_usage_job


def main() -> int:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-b976bb08-5fbf-48ec-a44")
    streams = int(os.environ.get("V4B7_MAX_STREAMS", "8"))
    print(f"V4B.7 resume-download pid={os.getpid()} streams={streams}", flush=True)
    try:
        rec = resume_existing_usage_job(billing_project=project, max_streams=streams)
        Path("logs").mkdir(exist_ok=True)
        Path("logs/v4b7_result.json").write_text(canonical_json(rec) + "\n")
        print("DONE", rec["disposition"], flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        Path("logs").mkdir(exist_ok=True)
        Path("logs/v4b7_error.txt").write_text(traceback.format_exc())
        print("FAILED", type(exc).__name__, exc, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
