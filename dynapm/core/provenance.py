"""Deterministic scientific identities, separate from physical execution metadata."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import importlib
from importlib import metadata
import json
import math
import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import platform
import socket
import subprocess
import sys
import time
from typing import Any

from dynapm.core.accounting import ACCOUNTING_SCHEMA
from dynapm.core.temporal import TEMPORAL_PROTOCOL, HORIZON_STEPS, MIN_OBSERVATIONS
from dynapm.core.features import LAGS, ROLL_WINDOWS, MAX_CONTEXT, VALID_TARGETS
from dynapm.data.bootstrap import LOCKED_BOOTSTRAP_FRACTION

PROVENANCE_SCHEMA = "provenance-schema-v1"
CONFIG_SCHEMA = "experiment-config-v1"
DATASET_SCHEMA = "dataset-manifest-v1"
COHORT_SCHEMA = "cohort-manifest-v1"
OUTPUT_SCHEMA = "output-manifest-v1"
SCIENTIFIC_PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "river", "joblib",
                       "pyarrow", "python-dateutil", "matplotlib")
SOURCE_PATHS = ("dynapm", "tests", "configs", "requirements.txt", "pyproject.toml",
                "pytest.ini", ".gitignore", "src", "scripts", "requirements", "setup.cfg",
                "setup.py", "uv.lock", "poetry.lock", "environment.yml")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalized(value):
    if is_dataclass(value) and not isinstance(value, type):
        return normalized(asdict(value))
    if isinstance(value, Enum):
        return normalized(value.value)
    if isinstance(value, PurePath):
        return value.as_posix()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return value
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise TypeError("JSON object keys must be strings")
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalized(v) for v in value]
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value) -> str:
    return json.dumps(normalized(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def invalid(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate JSON key: {k}")
            out[k] = v
        return out
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=invalid,
                      object_pairs_hook=unique)


def relative_path(value) -> str:
    s = str(value).replace("\\", "/")
    p = PurePosixPath(s)
    if not s or p.is_absolute() or bool(PureWindowsPath(s).drive) or ".." in p.parts:
        raise ValueError("scientific file paths must be relative, without parent traversal")
    return p.as_posix()


def reject_absolute_values(value):
    value = normalized(value)
    if isinstance(value, str) and (value.startswith("/") or PureWindowsPath(value).is_absolute()):
        raise ValueError("absolute filesystem locations are execution metadata, not configuration identity")
    if isinstance(value, dict):
        for v in value.values():
            reject_absolute_values(v)
    if isinstance(value, list):
        for v in value:
            reject_absolute_values(v)


@dataclass(frozen=True)
class SourceFile:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SourceProvenance:
    commit: str
    branch: str
    git_tree_status: tuple[str, ...]
    dirty: bool
    tracked_diff_sha256: str | None
    scientific_diff_sha256: str | None
    untracked_scientific_files: tuple[SourceFile, ...]
    source_root: str = "."
    scientific_paths: tuple[str, ...] = SOURCE_PATHS

    @classmethod
    def capture(cls, repo: Path, scientific_paths=SOURCE_PATHS):
        repo = Path(repo).resolve()
        def git(*args):
            return subprocess.check_output(["git", "--no-optional-locks", "-C", str(repo), *args])
        top = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        if top != repo:
            raise ValueError("source root must be the Git repository root")
        roots = tuple(sorted(relative_path(p) for p in scientific_paths))
        status = tuple(sorted(git("status", "--porcelain=v1", "--untracked-files=all").decode().splitlines()))
        diff_options = ("diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv",
            "--no-renames", "--diff-algorithm=myers", "--no-color", "--full-index",
            "--src-prefix=a/", "--dst-prefix=b/", "--unified=3", "--inter-hunk-context=0")
        diff = git(*diff_options)
        # Canonical HEAD-to-working-file delta includes untracked additions and
        # is independent of staging, rename detection and textual diff options.
        head = {}
        for row in git("ls-tree", "-rz", "HEAD", "--", *roots).decode().split("\0"):
            if row:
                meta, rel = row.split("\t", 1)
                mode, kind, blob = meta.split()
                if kind != "blob":
                    raise ValueError("scientific source submodules are unsupported")
                head[rel] = (mode, blob)
        current_paths = {p for p in git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *roots).decode().split("\0") if p}
        object_format = git("rev-parse", "--show-object-format").decode().strip()
        changes = []
        for rel in sorted(set(head) | current_paths):
            p = repo / rel
            old_mode, old_blob = head.get(rel, (None, None))
            if p.is_symlink() or p.is_dir():
                raise ValueError("scientific source symlinks/submodules are unsupported")
            data = p.read_bytes() if p.exists() else None
            mode = ("100755" if p.stat().st_mode & 0o111 else "100644") if data is not None else None
            blob = hashlib.new(object_format, b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() if data is not None else None
            if (mode, blob) != (old_mode, old_blob):
                changes.append({"path": relative_path(rel), "head_mode": old_mode,
                    "head_blob": old_blob, "working_mode": mode,
                    "working_sha256": hashlib.sha256(data).hexdigest() if data is not None else None})
        for rel in git("ls-files", "-z", "--", *roots).decode().split("\0"):
            if rel and ((repo / rel).is_symlink() or (repo / rel).is_dir()):
                raise ValueError("scientific source symlinks/submodules are unsupported")
        paths = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
        inventory = []
        for rel in sorted(p for p in paths if p):
            if not any(rel == r or rel.startswith(r + "/") for r in roots):
                continue
            p = repo / rel
            if p.is_symlink() or not p.is_file():
                raise ValueError("untracked scientific inputs must be regular files")
            inventory.append(SourceFile(relative_path(rel), p.stat().st_size, file_sha256(p)))
        branch = git("symbolic-ref", "--short", "-q", "HEAD").decode().strip() if git("rev-parse", "--abbrev-ref", "HEAD").strip() != b"HEAD" else "DETACHED"
        return cls(git("rev-parse", "HEAD").decode().strip(), branch, status, bool(status),
                   hashlib.sha256(diff).hexdigest() if status else None,
                   fingerprint(changes) if status else None,
                   tuple(inventory), ".", roots)

    def identity(self):
        return {"commit": self.commit, "dirty": self.dirty,
                "scientific_diff_sha256": self.scientific_diff_sha256,
                "source_root": relative_path(self.source_root),
                "scientific_paths": self.scientific_paths}


@dataclass(frozen=True)
class DatasetFile:
    path: str
    size_bytes: int
    sha256: str
    trace: str
    entity_id: str | None
    role: str


@dataclass(frozen=True)
class DatasetProvenance:
    dataset_id: str
    source_name: str
    trace_names: tuple[str, ...]
    schema_identity: str
    expected_cadence_seconds: int
    files: tuple[DatasetFile, ...]
    generated_at: str
    schema_version: str = DATASET_SCHEMA
    selection: str = "all-regular-files-v1"
    ancillary_files: tuple[DatasetFile, ...] = ()

    total_file_count: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "total_file_count", len(self.files))
        paths = [f.path for f in self.files]
        if not paths or len(paths) != len(set(paths)) or paths != sorted(paths):
            raise ValueError("dataset file inventory must be nonempty, unique and sorted")
        for f in self.files:
            if relative_path(f.path) != f.path or f.size_bytes < 0 or len(f.sha256) != 64 or f.trace not in self.trace_names:
                raise ValueError("invalid dataset file identity")
        if self.trace_names != tuple(sorted(set(self.trace_names))):
            raise ValueError("trace inventory must be sorted and unique")

    def identity(self):
        # Ancillary backups are inventoried, but never loaded by the dataset adapter.
        return {k: v for k, v in asdict(self).items() if k not in {"generated_at", "ancillary_files"}}

    @property
    def sha256(self):
        return fingerprint(self.identity())

    @property
    def file_count(self):
        return len(self.files)


@dataclass(frozen=True)
class CohortEntity:
    trace: str
    entity_id: str
    included: bool
    exclusion_reason: str | None
    observation_count: int
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    temporal_characterization: dict | None = None


@dataclass(frozen=True)
class CohortManifest:
    dataset_id: str
    dataset_manifest_sha256: str
    filtering_rule_version: str
    filtering_config: dict
    entities: tuple[CohortEntity, ...]
    generated_at: str
    schema_version: str = COHORT_SCHEMA

    def __post_init__(self):
        keys = [(e.trace, e.entity_id) for e in self.entities]
        if not keys or keys != sorted(set(keys)):
            raise ValueError("cohort entities must be nonempty, unique and sorted")
        if any(e.observation_count < 0 or e.included == bool(e.exclusion_reason) for e in self.entities):
            raise ValueError("cohort inclusion/reason/count mismatch")
        reject_absolute_values(self.filtering_config)

    def identity(self):
        return {k: v for k, v in asdict(self).items() if k != "generated_at"}

    @property
    def sha256(self):
        return fingerprint(self.identity())


@dataclass(frozen=True)
class DataConfig:
    dataset_id: str
    bootstrap_fraction: float = LOCKED_BOOTSTRAP_FRACTION
    minimum_observations: int = 2000
    forecast_horizon_steps: int = HORIZON_STEPS
    sampling_cadence_seconds: int = 300
    evaluation_cadence_seconds: int = 43200
    minimum_ground_truth_paired_slots: int = MIN_OBSERVATIONS
    lag_semantics: str = "observed-row"


@dataclass(frozen=True)
class ModelConfig:
    family: str = "RandomForestRegressor"
    n_estimators: int = 200
    max_depth: int | None = 20
    max_features: str | float = "sqrt"
    random_state: int = 42
    n_jobs: int = 1
    targets: tuple[str, ...] = VALID_TARGETS
    feature_specification: dict = field(default_factory=lambda: {
        "lags": LAGS, "rolling_windows": ROLL_WINDOWS, "max_context": MAX_CONTEXT,
        "rolling_ddof": 0, "past_only": True, "differences": (1, 12),
        "calendar": ("hour_sin", "hour_cos", "dow_sin", "dow_cos")})


@dataclass(frozen=True)
class PolicyConfig:
    method_id: str
    periodic_interval_hours: float | None = None
    observation_window_steps: int = 288
    observation_window_hours: float | None = None
    reactive_window_hours: float = 6.0
    adwin_delta: float = 0.002
    detector_settings: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StatisticsConfig:
    bootstrap_repetitions: int = 1000
    bootstrap_seed: int = 42
    confidence_level: float = 0.95
    test_specification: dict = field(default_factory=lambda: {
        "paired_unit": "VM", "test": "wilcoxon", "zero_method": "wilcox"})


@dataclass(frozen=True)
class ExperimentConfigProvenance:
    data: DataConfig
    model: ModelConfig
    policies: tuple[PolicyConfig, ...]
    statistics: StatisticsConfig = field(default_factory=StatisticsConfig)
    preprocessing: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    schema_version: str = CONFIG_SCHEMA

    @property
    def sha256(self):
        reject_absolute_values(self)
        return fingerprint(self)


@dataclass(frozen=True)
class EnvironmentProvenance:
    scientific: dict
    execution: dict
    packages: dict[str, str]

    @classmethod
    def capture(cls, scientific_packages=SCIENTIFIC_PACKAGES, execution_compatibility_keys=()):
        if not set(SCIENTIFIC_PACKAGES) <= set(scientific_packages):
            raise ValueError("required scientific package compatibility cannot be disabled")
        allowed = {"platform", "architecture", "cpu_model", "logical_cpus", "physical_cpus", "memory_bytes"}
        if not set(execution_compatibility_keys) <= allowed:
            raise ValueError("hostname/time/location cannot be scientific execution keys")
        packages = {}
        for d in metadata.distributions():
            name = d.metadata.get("Name")
            version = d.version
            if not name or not version:
                raise RuntimeError("unresolved package metadata")
            key = name.lower().replace("_", "-").replace(".", "-")
            if key in packages and packages[key] != version:
                raise RuntimeError(f"ambiguous installed package resolution: {key}")
            packages[key] = version
        versions = {}
        for name in sorted(set(scientific_packages)):
            try:
                versions[name] = metadata.version(name)
            except metadata.PackageNotFoundError as e:
                raise RuntimeError(f"required scientific package unresolved: {name}") from e
        package_locations = {}
        for name, module in {"scikit-learn": "sklearn", "python-dateutil": "dateutil",
                             **{n: n for n in SCIENTIFIC_PACKAGES if n not in {"scikit-learn", "python-dateutil"}}}.items():
            try:
                imported = importlib.import_module(module)
            except ImportError as error:
                raise RuntimeError(f"required scientific package import failed: {name}") from error
            if getattr(imported, "__version__", None) != versions[name]:
                raise RuntimeError(f"installed/imported package resolution differs: {name}")
            location = getattr(imported, "__file__", None)
            distribution_root = Path(metadata.distribution(name).locate_file("")).resolve()
            if location is None or not Path(location).resolve().is_relative_to(distribution_root):
                raise RuntimeError(f"scientific import shadows installed distribution: {name}")
            package_locations[name] = str(Path(location).resolve())
        def sysctl(name):
            try:
                return subprocess.check_output(["/usr/sbin/sysctl", "-n", name], stderr=subprocess.DEVNULL).decode().strip()
            except (OSError, subprocess.CalledProcessError):
                return None
        physical = sysctl("hw.physicalcpu")
        memory = sysctl("hw.memsize")
        cpu = sysctl("machdep.cpu.brand_string") or platform.processor() or None
        if platform.system() == "Linux":
            try:
                info = Path("/proc/cpuinfo").read_text()
                records = [dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
                           for block in info.split("\n\n") if block.strip()]
                records = [{k.strip(): v.strip() for k, v in r.items()} for r in records]
                cores = {(r.get("physical id"), r.get("core id")) for r in records
                         if "physical id" in r and "core id" in r}
                physical = str(len(cores)) if cores else None
                cpu = next((r.get("model name") for r in records if r.get("model name")), cpu)
                mem = Path("/proc/meminfo").read_text().split("MemTotal:", 1)[1].split()[0]
                memory = str(int(mem) * 1024)
            except (OSError, IndexError, ValueError):
                pass  # Unavailable hardware fields remain explicitly null, not invented.
        execution = {"python_executable": sys.executable, "platform": platform.platform(),
            "architecture": platform.machine(), "hostname": socket.gethostname(),
            "timezone": time.tzname, "package_locations": package_locations,
            "cpu_model": cpu, "logical_cpus": os.cpu_count(),
            "physical_cpus": int(physical) if physical else None,
            "memory_bytes": int(memory) if memory else None}
        if any(execution[k] is None for k in execution_compatibility_keys):
            raise RuntimeError("required scientific hardware field unavailable")
        scientific = {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "architecture": platform.machine(), "platform": platform.platform(), "packages": versions,
            "numeric_thread_settings": {k: os.environ.get(k) for k in (
                "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "PYTHONHASHSEED")},
            "execution_compatibility_keys": tuple(sorted(execution_compatibility_keys)),
            "execution_compatibility": {k: execution[k] for k in sorted(execution_compatibility_keys)}}
        return cls(scientific, execution, dict(sorted(packages.items())))


def current_environment_like(scientific):
    return EnvironmentProvenance.capture(tuple(scientific["packages"]),
        tuple(scientific["execution_compatibility_keys"]))



@dataclass(frozen=True)
class ExperimentManifest:
    source: SourceProvenance
    config: ExperimentConfigProvenance
    dataset: DatasetProvenance
    cohort: CohortManifest
    scientific_environment: dict
    seeds: dict[str, int]
    protocol_version: str = TEMPORAL_PROTOCOL
    accounting_schema: str = ACCOUNTING_SCHEMA
    schema_version: str = PROVENANCE_SCHEMA

    def identity(self):
        if self.config.data.dataset_id != self.dataset.dataset_id or self.cohort.dataset_id != self.dataset.dataset_id:
            raise ValueError("dataset/config/cohort IDs differ")
        threshold = self.cohort.filtering_config.get("minimum_observations")
        if threshold is not None and threshold != self.config.data.minimum_observations:
            raise ValueError("configuration/cohort filtering thresholds differ")
        if not self.scientific_environment or not self.seeds:
            raise ValueError("explicit scientific environment and seeds are required")
        if self.cohort.dataset_manifest_sha256 != self.dataset.sha256:
            raise ValueError("cohort does not describe this dataset")
        return {"schema_version": self.schema_version, "source": self.source.identity(),
                "protocol_version": self.protocol_version, "accounting_schema": self.accounting_schema,
                "config_sha256": self.config.sha256, "dataset_manifest_sha256": self.dataset.sha256,
                "cohort_sha256": self.cohort.sha256, "scientific_environment": self.scientific_environment,
                "seeds": self.seeds}

    @property
    def fingerprint(self):
        return fingerprint(self.identity())


def dataset_from_dict(d):
    d = dict(d)
    if d.get("schema_version") != DATASET_SCHEMA:
        raise ValueError("unsupported_manifest_schema")
    count = d.pop("total_file_count")
    if count != len(d["files"]):
        raise ValueError("dataset file count mismatch")
    d["files"] = tuple(DatasetFile(**f) for f in d["files"])
    d["trace_names"] = tuple(d["trace_names"])
    d["ancillary_files"] = tuple(DatasetFile(**f) for f in d["ancillary_files"])
    return DatasetProvenance(**d)


def cohort_from_dict(d):
    d = dict(d)
    if d.get("schema_version") != COHORT_SCHEMA:
        raise ValueError("unsupported_manifest_schema")
    d["entities"] = tuple(CohortEntity(**e) for e in d["entities"])
    return CohortManifest(**d)


def config_from_dict(d):
    d = dict(d)
    if d.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported_manifest_schema")
    d["data"] = DataConfig(**d["data"])
    d["model"] = ModelConfig(**d["model"])
    d["policies"] = tuple(PolicyConfig(**p) for p in d["policies"])
    d["statistics"] = StatisticsConfig(**d["statistics"])
    return ExperimentConfigProvenance(**d)


def experiment_from_dict(d):
    d = dict(d)
    if d.get("schema_version") != PROVENANCE_SCHEMA:
        raise ValueError("unsupported_manifest_schema")
    src = dict(d["source"])
    src["untracked_scientific_files"] = tuple(SourceFile(**f) for f in src["untracked_scientific_files"])
    src["git_tree_status"] = tuple(src["git_tree_status"])
    src["scientific_paths"] = tuple(src["scientific_paths"])
    d.update(source=SourceProvenance(**src), config=config_from_dict(d["config"]),
             dataset=dataset_from_dict(d["dataset"]), cohort=cohort_from_dict(d["cohort"]))
    result = ExperimentManifest(**d)
    result.fingerprint  # Validate cross-manifest identities and canonical types now.
    return result


def prepare_experiment(repo, dataset_root, config, dataset, cohort, seeds, *,
                       scientific_packages=SCIENTIFIC_PACKAGES, execution_compatibility_keys=()):
    """Capture fresh source/environment and verify a supplied raw-input manifest."""
    from dynapm.data.manifests import check_dataset
    check_dataset(dataset_root, dataset)
    env = EnvironmentProvenance.capture(scientific_packages, execution_compatibility_keys)
    experiment = ExperimentManifest(SourceProvenance.capture(repo), config, dataset, cohort,
                                    env.scientific, seeds)
    experiment.fingerprint
    return experiment, env
