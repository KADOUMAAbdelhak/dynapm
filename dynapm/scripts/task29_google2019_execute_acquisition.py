"""V4B.4 execute frozen zero-cost Google 2019 acquisition.

Default: preflight only. Use --execute only after preflight authorizes.
Use --record-blocked to persist a tracked blocked-acquisition summary.
No method outcomes. No BigQuery destination tables.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dynapm.core.provenance import canonical_json, read_json
from dynapm.experiments.google2019_acquisition import resolve_quota_project
from dynapm.experiments.google2019_execute_acquisition import (
    EXECUTION_ORDER,
    AcquisitionExecutionBlocked,
    MANAGED_ROOT,
    RAW_ROOT,
    assess_disk_for_cells,
    preflight,
    stream_query_to_parquet,
    write_blocked_acquisition_record,
)
from dynapm.experiments.google2019_zero_cost_plan import CHOSEN_CELLS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--billing-project")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute frozen scans after a passing preflight.",
    )
    parser.add_argument(
        "--record-blocked",
        action="store_true",
        help="Write tracked ACQUISITION_BLOCKED record when preflight refuses.",
    )
    args = parser.parse_args(argv)
    project = resolve_quota_project(args.billing_project)
    if not project:
        raise SystemExit("--billing-project or ADC quota_project_id is required")

    try:
        payload = preflight(billing_project=project, cells=CHOSEN_CELLS)
    except AcquisitionExecutionBlocked as exc:
        disk = assess_disk_for_cells(CHOSEN_CELLS)
        preflight_path = MANAGED_ROOT / "v4b4_preflight.json"
        pre = read_json(preflight_path) if preflight_path.is_file() else {
            "blocker": str(exc),
            "disk": {
                "free_gib": disk.free_gib,
                "required_gib": disk.required_gib,
                "safe": disk.safe,
            },
        }
        failure = {
            "status": "ACQUISITION_BLOCKED",
            "blocker": str(exc),
            "disk": {
                "free_gib": disk.free_gib,
                "required_gib": disk.required_gib,
                "safe": disk.safe,
            },
        }
        if args.record_blocked or not args.execute:
            record = write_blocked_acquisition_record(
                str(exc), preflight_payload=pre
            )
            failure["record"] = {
                "path": record["path"],
                "sha256": record["record_sha256"],
            }
        print(canonical_json(failure))
        raise SystemExit(2) from exc

    print(canonical_json({"status": "PREFLIGHT_OK", **payload}))
    if not args.execute:
        return

    manifests = []
    for cell, tmpl in EXECUTION_ORDER:
        out = RAW_ROOT / cell / f"{Path(tmpl).stem}.parquet"
        manifests.append(
            stream_query_to_parquet(
                billing_project=project,
                cell=cell,
                template=tmpl,
                output_path=out,
            )
        )
        print(canonical_json({"status": "QUERY_COMPLETE", "manifest": manifests[-1]}))
    print(canonical_json({"status": "RAW_EXTRACT_COMPLETE", "manifests": manifests}))


if __name__ == "__main__":
    main()
