"""Guarded V4B Google ClusterData 2019 acquisition utility.

No method outcomes. Dry-run is mandatory before any future query execution.
This command currently records an access blocker when credentials/billing are absent.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from dynapm.core.provenance import canonical_json
from dynapm.experiments.google2019_acquisition import (
    AcquisitionBlocked,
    DEFAULT_MAXIMUM_BYTES_BILLED,
    QUERY_ROOT,
    dry_run_query,
    frozen_hashes,
    inspect_access,
    render_cell_query,
    write_canonical_artifacts,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-check", action="store_true")
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

    if args.access_check:
        print(canonical_json({**asdict(inspect_access()), "hashes": frozen_hashes()}))
        return

    if args.dry_run_query:
        if not args.billing_project:
            raise SystemExit("--billing-project is required for dry-run")
        if args.dry_run_query.startswith(("04_", "05_")):
            if not args.cell:
                raise SystemExit("--cell is required for cell-template query")
            sql = render_cell_query(args.dry_run_query, args.cell)
        else:
            sql = (QUERY_ROOT / args.dry_run_query).read_text(encoding="utf-8")
        try:
            result = dry_run_query(
                sql,
                billing_project=args.billing_project,
                maximum_bytes_billed=args.maximum_bytes_billed,
            )
        except AcquisitionBlocked as exc:
            print(canonical_json({"status": "ACQUISITION_BLOCKED", "blocker": str(exc)}))
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

    parser.error("choose --access-check, --dry-run-query, or --canonicalize-input")


if __name__ == "__main__":
    main()
