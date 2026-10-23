"""Guarded V4B/V4B.1 Google ClusterData 2019 acquisition utility.

No method outcomes. Dry-run is mandatory before any query execution.
Credentials, tokens, and billing secrets are never written to Git.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_acquisition import (
    AcquisitionBlocked,
    BudgetExceeded,
    DEFAULT_MAXIMUM_BYTES_BILLED,
    dry_run_all_query_classes,
    dry_run_query,
    execute_bounded_validation_extract,
    frozen_hashes,
    human_bootstrap_actions,
    inspect_access,
    load_query_sql,
    write_canonical_artifacts,
    write_query_provenance,
)
import pandas as pd


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-check", action="store_true")
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

    if args.access_check:
        status = inspect_access(billing_project=args.billing_project)
        print(
            canonical_json(
                {
                    **asdict(status),
                    "hashes": frozen_hashes(),
                    "human_bootstrap_actions": (
                        human_bootstrap_actions() if not status.dry_run_possible else []
                    ),
                }
            )
        )
        if not status.dry_run_possible:
            raise SystemExit(2)
        return

    if args.dry_run_all:
        if not args.billing_project:
            raise SystemExit("--billing-project is required for dry-run-all")
        try:
            records = dry_run_all_query_classes(
                billing_project=args.billing_project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                full_cell=args.cell or "a",
            )
            if args.output_dir is not None:
                write_query_provenance(records, output_dir=args.output_dir, kind="dry_run")
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
        print(canonical_json({"status": "DRY_RUN_COMPLETE", "records": records}))
        return

    if args.execute_bounded:
        if not args.billing_project:
            raise SystemExit("--billing-project is required for execute-bounded")
        try:
            result = execute_bounded_validation_extract(
                billing_project=args.billing_project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                output_dir=args.output_dir,
            )
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
        # Drop any non-serializable leftovers.
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
                    "method_outcomes_computed": False,
                }
            )
        )
        return

    if args.dry_run_query:
        if not args.billing_project:
            raise SystemExit("--billing-project is required for dry-run")
        try:
            sql = load_query_sql(args.dry_run_query, cell=args.cell)
            result = dry_run_query(
                sql,
                billing_project=args.billing_project,
                maximum_bytes_billed=args.maximum_bytes_billed,
                query_name=args.dry_run_query,
            )
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
        "choose --access-check, --bootstrap-instructions, --dry-run-all, "
        "--dry-run-query, --execute-bounded, or --canonicalize-input"
    )


if __name__ == "__main__":
    main()
