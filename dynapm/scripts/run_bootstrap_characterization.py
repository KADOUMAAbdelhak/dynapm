#!/usr/bin/env python3
"""One-pass bootstrap characterization for all kept VMs -> parquet summary."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from dynapm.core.pattern import derive_burst_profile, derive_diurnal_pattern
from dynapm.data.bootstrap import compute_split
from dynapm.core.discretization import compute_thresholds
from dynapm.data.loader import load_vm_csv
from dynapm.data.provisioning import extract_provisioning

KEPT = REPO / "dynapm/data/kept_vms.json"
OUT = REPO / "dynapm/data/bootstrap_summary.parquet"
CPU_M = "CPU usage [%]"
MEM_M = "Memory usage [%]"


def main() -> int:
    with open(KEPT, encoding="utf-8") as f:
        kept = json.load(f)
    rows = []
    t0 = time.perf_counter()
    for item in kept:
        trace_name = item["trace"]
        vm_id = item["vm_id"]
        path = REPO / "data/raw" / trace_name / f"{vm_id}.csv"
        df = load_vm_csv(str(path))
        df_b, _, info = compute_split(df)
        prov = extract_provisioning(df)
        cpu_th = compute_thresholds(df_b, CPU_M)
        mem_th = compute_thresholds(df_b, MEM_M)
        boot_cpu = df_b[CPU_M]
        boot_mem = df_b[MEM_M]
        d_pat = derive_diurnal_pattern(boot_cpu)
        b_cpu = derive_burst_profile(boot_cpu, cpu_th["p95"])
        b_mem = derive_burst_profile(boot_mem, mem_th["p95"])
        rows.append(
            {
                "trace_name": trace_name,
                "vm_id": vm_id,
                "n_total": info["n_total"],
                "n_bootstrap": info["n_bootstrap"],
                "n_streaming": info["n_streaming"],
                "bootstrap_start": info["bootstrap_start"],
                "bootstrap_end": info["bootstrap_end"],
                "streaming_start": info["streaming_start"],
                "streaming_end": info["streaming_end"],
                "provisioned_cpu_cores": prov["provisioned_cpu_cores"],
                "provisioned_ram_gb": prov["provisioned_ram_gb"],
                "cpu_p20": cpu_th["p20"],
                "cpu_p40": cpu_th["p40"],
                "cpu_p60": cpu_th["p60"],
                "cpu_p80": cpu_th["p80"],
                "cpu_p95": cpu_th["p95"],
                "mem_p20": mem_th["p20"],
                "mem_p40": mem_th["p40"],
                "mem_p60": mem_th["p60"],
                "mem_p80": mem_th["p80"],
                "mem_p95": mem_th["p95"],
                "bootstrap_diurnal": d_pat,
                "bootstrap_burst_cpu": b_cpu,
                "bootstrap_burst_mem": b_mem,
            }
        )
    elapsed = time.perf_counter() - t0
    result = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUT, index=False)
    print(f"wrote {OUT} rows={len(result)} wall_s={elapsed:.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
