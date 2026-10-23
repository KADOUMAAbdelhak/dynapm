"""Guarded V4B/V4B.2 Google ClusterData 2019 acquisition utility.

Zero cloud spend: billingEnabled must be false before any dry-run/execute.
No method outcomes. Credentials/tokens/secrets are never written to Git.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_acquisition import (
    AcquisitionBlocked,
    BillingEnabledBlocked,
    BudgetExceeded,
    DEFAULT_MAXIMUM_BYTES_BILLED,
    cumulative_executed_bytes,
    dry_run_all_query_classes,
    dry_run_query,
    execute_bounded_validation_extract,
    frozen_hashes,
    human_bootstrap_actions,
    inspect_access,
    inspect_billing_state,
    load_byte_ledger,
    load_query_sql,
    resolve_quota_project,
    write_canonical_artifacts,
    write_query_provenance,
)


def _project(args) -> str | None:
    return resolve_quota_project(args.billing_project)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-check", action="store_true")
    parser.add_argument("--billing-check", action="store_true")
    parser.add_argument("--bootstrap-instructions", action="store_true")
    parser.add_argument("--dry-run-all", action="store_true")
    parser.add_argument("--execute-bounded", action="store_true")
    parser.add_argument("--dry-run-query", choices=[
        "01_schema_probe.sql",
        "02_bounded_population.sql",
        "03_bounded_validation_extract.sql",
        "04_full_cell_population.sql",
        "05_full_cell_extract.sql",
    ])
    parser.add_argument("--cell", choices=list("abcdefgh"))
    parser.add_argument("--billing-project")
    parser.add_argument(
        "--maximum-bytes-billed",
        type=int,
        default=DEFAULT_MAXIMUM_BYTES_BILLED,
    )
    parser.add_argument("--canonicalize-input", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--query-name",
        default="03_bounded_validation_extract.sql",
    )
    args = parser.parse_args(argv)

    if args.bootstrap_instructions:
        print(canonical_json({"human_bootstrap_actions": human_bootstrap_actions()}))
        return

    if args.billing_check or args.access_check:
        project = _project(args)
        status = inspect_access(billing_project=project)
        payload: dict = {**asdict(status), "hashes": frozen_hashes()}
        if project:
            try:
                billing = inspect_billing_state(project)
                payload["billing"] = asdict(billing)
            except AcquisitionBlocked as exc:
                payload["billing"] = {
                    "blocker_code": str(exc),
                    "zero_spend_guaranteed": False,
                }
        else:
            payload["billing"] = None
        payload["byte_ledger"] = {
            "cumulative_executed_bytes": cumulative_executed_bytes(),
            "prior_monthly_usage_verified": load_byte_ledger().get(
                "prior_monthly_usage_verified"
            ),
        }
        if not status.dry_run_possible:
            payload["human_bootstrap_actions"] = human_bootstrap_actions()
            print(canonical_json(payload))
            raise SystemExit(2)
        billing = payload.get("billing") or {}
        if billing.get("billing_enabled"):
            print(canonical_json(payload))
            raise SystemExit(4)
        if args.billing_check and not billing.get("zero_spend_guaranteed"):
            print(canonical_json(payload))
            raise SystemExit(2)
        print(canonical_json(payload))
        return

    if args.dry_run_all:
        project = _project(args)
        if not project:
            raise SystemExit("--billing-project or ADC quota_project_id is required")
        try:
            records = dry_run_all_query_classes(
                billing_project=project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                full_cell=args.cell or "a",
            )
            if args.output_dir is not None:
                write_query_provenance(
                    records, output_dir=args.output_dir, kind="dry_run"
                )
        except BillingEnabledBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED",
                        "blocker": str(exc),
                    }
                )
            )
            raise SystemExit(4) from exc
        except AcquisitionBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "ACQUISITION_BLOCKED",
                        "blocker": str(exc),
                        "human_bootstrap_actions": human_bootstrap_actions(),
                    }
                )
            )
            raise SystemExit(2) from exc
        print(
            canonical_json(
                {
                    "status": "DRY_RUN_COMPLETE",
                    "quota_project": project,
                    "cumulative_executed_bytes": cumulative_executed_bytes(),
                    "records": records,
                }
            )
        )
        return

    if args.execute_bounded:
        project = _project(args)
        if not project:
            raise SystemExit("--billing-project or ADC quota_project_id is required")
        try:
            result = execute_bounded_validation_extract(
                billing_project=project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                output_dir=args.output_dir,
            )
        except BillingEnabledBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED",
                        "blocker": str(exc),
                        "executed": False,
                    }
                )
            )
            raise SystemExit(4) from exc
        except BudgetExceeded as exc:
            print(
                canonical_json(
                    {
                        "status": "BUDGET_EXCEEDED",
                        "blocker": str(exc),
                        "executed": False,
                    }
                )
            )
            raise SystemExit(3) from exc
        except AcquisitionBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "ACQUISITION_BLOCKED",
                        "blocker": str(exc),
                        "human_bootstrap_actions": human_bootstrap_actions(),
                    }
                )
            )
            raise SystemExit(2) from exc
        print(
            canonical_json(
                {
                    "status": "BOUNDED_EXTRACT_COMPLETE",
                    "execution": result["execution"],
                    "manifest_sha256": result["manifest"]["manifest_sha256"],
                    "row_count": result["manifest"]["row_count"],
                    "entity_count": result["manifest"]["entity_count"],
                    "cells": result["manifest"]["cells"],
                    "output_root": result["output_root"],
                    "cumulative_executed_bytes": cumulative_executed_bytes(),
                    "method_outcomes_computed": False,
                }
            )
        )
        return

    if args.dry_run_query:
        project = _project(args)
        if not project:
            raise SystemExit("--billing-project or ADC quota_project_id is required")
        try:
            sql = load_query_sql(args.dry_run_query, cell=args.cell)
            result = dry_run_query(
                sql,
                billing_project=project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                query_name=args.dry_run_query,
            )
        except BillingEnabledBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED",
                        "blocker": str(exc),
                    }
                )
            )
            raise SystemExit(4) from exc
        except AcquisitionBlocked as exc:
            print(
                canonical_json(
                    {
                        "status": "ACQUISITION_BLOCKED",
                        "blocker": str(exc),
                        "human_bootstrap_actions": human_bootstrap_actions(),
                    }
                )
            )
            raise SystemExit(2) from exc
        print(canonical_json(result))
        return

    if args.canonicalize_input:
        if args.output_dir is None:
            raise SystemExit("--output-dir is required with --canonicalize-input")
        source = args.canonicalize_input
        if source.suffix == ".parquet":
            frame = pd.read_parquet(source)
        elif source.suffix == ".csv":
            frame = pd.read_csv(source)
        else:
            raise SystemExit("input must be .parquet or .csv")
        result = write_canonical_artifacts(
            frame,
            args.output_dir,
            query_name=args.query_name,
        )
        print(canonical_json(result))
        return

    parser.error(
        "choose --access-check, --billing-check, --bootstrap-instructions, "
        "--dry-run-all, --dry-run-query, --execute-bounded, or --canonicalize-input"
    )


if __name__ == "__main__":
    main()
