"""Profile schema dataclasses for DynAPM."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


CPU_CLASSES = ("idle", "low", "medium", "high", "burst")
MEMORY_CLASSES = ("idle", "low", "medium", "high", "burst")

@dataclass(frozen=True)
class StaticFields:
    vm_id: str
    trace_name: str
    provisioned_cpu_cores: int
    provisioned_ram_gb: float
    bootstrap_start: pd.Timestamp
    bootstrap_end: pd.Timestamp
    n_total_timesteps: int


@dataclass(frozen=False)
class DynamicFields:
    cpu_class: str
    memory_class: str
    predicted_cpu_p95_next_24h: float
    predicted_mem_p95_next_24h: float


@dataclass
class ProfileInstance:
    static: StaticFields
    dynamic: DynamicFields
    last_updated: dict[str, pd.Timestamp]
    version: int = 1

    def to_json(self) -> dict[str, Any]:
        def ts_obj(x: pd.Timestamp) -> str:
            if hasattr(x, "isoformat"):
                return pd.Timestamp(x).isoformat()
            return str(x)

        dyn = self.dynamic
        st = self.static
        out: dict[str, Any] = {
            "static": {
                "vm_id": st.vm_id,
                "trace_name": st.trace_name,
                "provisioned_cpu_cores": st.provisioned_cpu_cores,
                "provisioned_ram_gb": st.provisioned_ram_gb,
                "bootstrap_start": ts_obj(st.bootstrap_start),
                "bootstrap_end": ts_obj(st.bootstrap_end),
                "n_total_timesteps": st.n_total_timesteps,
            },
            "dynamic": {
                "cpu_class": dyn.cpu_class,
                "memory_class": dyn.memory_class,
                "predicted_cpu_p95_next_24h": dyn.predicted_cpu_p95_next_24h,
                "predicted_mem_p95_next_24h": dyn.predicted_mem_p95_next_24h,
            },
            "last_updated": {k: ts_obj(v) for k, v in self.last_updated.items()},
            "version": self.version,
        }
        return out
