#!/usr/bin/env python3
"""V4B.6 streaming acquisition runner (zero-cost; no DynAPM outcomes)."""
from __future__ import annotations

import argparse
import os
import traceback
from pathlib import Path

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_streaming_execute import (
    acquire_cell,
    disk_safe_for_g_after_e,
    freeze_cohort,
    run_streaming_acquisition,
    streaming_preflight,
    write_acquisition_record,
)
from dynapm.experiments.google2019_acquisition import cumulative_executed_bytes, GIB
from dynapm.experiments.google2019_execute_acquisition import FROZEN_PLAN_FINGERPRINT
from dynapm.experiments.google2019_streaming import fingerprint, load_streaming_plan
from dynapm.experiments.replication_corpus import frozen_hashes as v4a_hashes
from dynapm.experiments.google2019_zero_cost_plan import CHOSEN_CELLS
from dynapm.core.provenance import utc_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--billing-project",
        default="project-b976bb08-5fbf-48ec-a44",
    )
    parser.add_argument(
        "--stage",
        choices=("all", "preflight", "cell-e", "cell-g", "cohort"),
        default="all",
    )
    args = parser.parse_args()
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    print(f"V4B.6 start stage={args.stage} pid={os.getpid()}", flush=True)
    try:
        if args.stage == "preflight":
            pf = streaming_preflight(billing_project=args.billing_project)
            print(canonical_json(pf), flush=True)
            return 0
        if args.stage == "cell-e":
            streaming_preflight(billing_project=args.billing_project)
            result = acquire_cell(billing_project=args.billing_project, cell="e")
            print(canonical_json({"ok": True, "cell": "e", **{
                k: result[k] for k in ("validation", "disk_gib")
            }}), flush=True)
            return 0
        if args.stage == "cell-g":
            gate = disk_safe_for_g_after_e()
            print("G_DISK_GATE", canonical_json(gate), flush=True)
            if not gate["safe"]:
                return 2
            result = acquire_cell(billing_project=args.billing_project, cell="g")
            print(canonical_json({"ok": True, "cell": "g", "validation": result["validation"]}), flush=True)
            return 0
        if args.stage == "cohort":
            cohort = freeze_cohort(("e", "g"))
            print(canonical_json(cohort), flush=True)
            return 0
        rec = run_streaming_acquisition(billing_project=args.billing_project)
        (log_dir / "v4b6_result.json").write_text(canonical_json(rec) + "\n")
        print("DONE", rec["disposition"], rec.get("blocker"), flush=True)
        return 0 if rec["disposition"] in ("GOOGLE_CORPUS_ACQUIRED", "ACQUISITION_PARTIAL") else 1
    except Exception as exc:  # noqa: BLE001
        (log_dir / "v4b6_error.txt").write_text(traceback.format_exc())
        print("FAILED", type(exc).__name__, exc, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
