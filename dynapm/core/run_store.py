"""A small run store: immutable identity, explicit completion, one cache validator."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from enum import Enum
import csv
import os
from pathlib import Path
import sys
import tempfile
import traceback
import uuid

from dynapm.core.provenance import (PROVENANCE_SCHEMA, CONFIG_SCHEMA, DATASET_SCHEMA,
    COHORT_SCHEMA, OUTPUT_SCHEMA, TEMPORAL_PROTOCOL, ACCOUNTING_SCHEMA,
    ExperimentManifest, SourceProvenance, EnvironmentProvenance, canonical_json,
    file_sha256, fingerprint, read_json, relative_path, utc_now, experiment_from_dict, current_environment_like)
from dynapm.data.manifests import check_dataset


class RunPurpose(str, Enum):
    SMOKE = "smoke"
    PILOT = "pilot"
    CLAIM = "claim"


@dataclass(frozen=True)
class OutputSpec:
    path: str
    semantic_role: str


@dataclass(frozen=True)
class OutputFile:
    path: str
    size_bytes: int
    sha256: str
    semantic_role: str
    row_count: int | None = None
    table_schema: tuple | None = None


@dataclass(frozen=True)
class OutputManifest:
    files: tuple[OutputFile, ...]
    schema_version: str = OUTPUT_SCHEMA

    @property
    def sha256(self):
        return fingerprint(self)


@dataclass
class RunManifest:
    run_id: str
    experiment_fingerprint: str
    experiment: dict
    purpose: str
    allow_dirty: bool
    claim_eligible: bool
    status: str
    started_at: str
    command: list[str]
    output_path: str
    required_outputs: list[dict]
    metadata_sha256: dict[str, str]
    ended_at: str | None = None
    output_manifest_sha256: str | None = None
    error: dict | None = None
    failures: list | None = None
    exclusions: list | None = None
    classification: str = "DEVELOPMENT_NONCANONICAL"
    execution_locations: dict | None = None
    schema_version: str = PROVENANCE_SCHEMA


@dataclass(frozen=True)
class CacheDecision:
    reusable: bool
    reasons: tuple[str, ...]


def write_json(path, value):
    """Atomic, canonical JSON. A failed serialization cannot create a SUCCESS."""
    data = canonical_json(value).encode("utf-8")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, p)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _safe_file(root, rel):
    rel = relative_path(rel)
    p = Path(root) / rel
    if ".git" in Path(rel).parts:
        raise ValueError("Git content is not an output")
    for parent in [p, *p.parents]:
        if parent.is_symlink():
            raise ValueError("symlink in run file path")
        if parent == Path(root):
            break
    if not p.is_file():
        raise ValueError("missing regular run file")
    return p


def _output_paths(root):
    paths = []
    for name in ("outputs", "logs"):
        base = Path(root) / name
        if base.is_symlink():
            raise ValueError("symlink output directory")
        for p in base.rglob("*"):
            if p.is_symlink() or p.name == ".git":
                raise ValueError("symlink/Git output")
            if p.is_file():
                paths.append(p.relative_to(root).as_posix())
    return sorted(paths)


def build_output_manifest(root, specs):
    specs = tuple(OutputSpec(relative_path(s.path), s.semantic_role) for s in specs)
    paths = [relative_path(s.path) for s in specs]
    if not specs or len(paths) != len(set(paths)) or any(not s.semantic_role for s in specs):
        raise ValueError("nonempty unique required outputs and roles are mandatory")
    if any(Path(p).parts[0] not in {"outputs", "logs"} for p in paths):
        raise ValueError("outputs must be within outputs/ or logs/")
    if sorted(paths) != _output_paths(root):
        raise ValueError("required_output_inventory_mismatch")
    files = []
    for spec in sorted(specs, key=lambda s: s.path):
        p = _safe_file(root, spec.path)
        count, schema = None, None
        if p.suffix == ".json":
            read_json(p)
        elif p.suffix == ".csv":
            with p.open(newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                count = 0
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError("malformed CSV output")
                    count += 1
                schema = tuple(header)
        elif p.suffix == ".parquet":
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(p)
            count = pf.metadata.num_rows
            schema = tuple((f.name, str(f.type)) for f in pf.schema_arrow)
        files.append(OutputFile(relative_path(spec.path), p.stat().st_size,
            file_sha256(p), spec.semantic_role, count, schema))
    return OutputManifest(tuple(files))


def _supported(exp):
    return (exp.schema_version == PROVENANCE_SCHEMA and exp.config.schema_version == CONFIG_SCHEMA
        and exp.dataset.schema_version == DATASET_SCHEMA and exp.cohort.schema_version == COHORT_SCHEMA
        and exp.protocol_version == TEMPORAL_PROTOCOL and exp.accounting_schema == ACCOUNTING_SCHEMA)


class RunSession:
    """Arbitrary experiment callers write only declared outputs, then complete().

    This manages provenance, not algorithms or corpus scheduling. The caller must
    declare all required entity/method outputs; partial coverage cannot be hidden
    by omitting files after execution.
    """
    def __init__(self, result_root, experiment: ExperimentManifest, environment: EnvironmentProvenance,
                 *, repo, dataset_root, purpose, required_outputs, allow_dirty=False, command=None):
        self.experiment = deepcopy(experiment)
        exp = self.experiment
        self.repo, self.dataset_root = Path(repo), Path(dataset_root)
        self.purpose = RunPurpose(purpose)
        if not _supported(exp):
            raise ValueError("unsupported_manifest_schema_or_protocol")
        if canonical_json(environment.scientific) != canonical_json(exp.scientific_environment) or canonical_json(current_environment_like(exp.scientific_environment).scientific) != canonical_json(exp.scientific_environment):
            raise ValueError("environment_mismatch")
        current = SourceProvenance.capture(self.repo, exp.source.scientific_paths)
        if fingerprint(current.identity()) != fingerprint(exp.source.identity()):
            raise ValueError("source_state_mismatch")
        if exp.source.dirty and self.purpose != RunPurpose.SMOKE and not allow_dirty:
            raise ValueError("dirty_source: --allow-dirty is required; override is DEVELOPMENT only")
        check_dataset(dataset_root, exp.dataset)
        self.specs = tuple(OutputSpec(relative_path(s.path), s.semantic_role) for s in required_outputs)
        if not self.specs or len({relative_path(s.path) for s in self.specs}) != len(self.specs):
            raise ValueError("required outputs must be explicit and unique")
        run_id = utc_now().replace(":", "").replace("+0000", "Z") + "-" + exp.fingerprint[:12] + "-" + uuid.uuid4().hex[:8]
        self.path = Path(result_root) / "runs" / exp.fingerprint / run_id
        self.path.mkdir(parents=True, exist_ok=False)
        for name in ("outputs", "logs"):
            (self.path / name).mkdir()
        snapshots = {"config.json": exp.config, "environment.json": environment,
                     "dataset_manifest.json": exp.dataset, "cohort_manifest.json": exp.cohort}
        for name, data in snapshots.items():
            write_json(self.path / name, data)
        self.manifest = RunManifest(run_id, exp.fingerprint, asdict(exp), self.purpose.value,
            allow_dirty, self.purpose == RunPurpose.CLAIM and not exp.source.dirty and not allow_dirty,
            "INCOMPLETE", utc_now(), list(sys.argv if command is None else command), str(self.path.resolve()),
            [asdict(s) for s in self.specs], {n: file_sha256(self.path / n) for n in snapshots})
        self.manifest.classification = "CANONICAL_CLAIM" if self.manifest.claim_eligible else "DEVELOPMENT_NONCANONICAL"
        self.manifest.execution_locations = {"repository": str(self.repo.resolve()),
                                             "dataset_root": str(self.dataset_root.resolve())}
        self.manifest.failures = []
        self.manifest.exclusions = [{"trace": e.trace, "entity_id": e.entity_id,
            "reason": e.exclusion_reason} for e in exp.cohort.entities if not e.included]
        write_json(self.path / "manifest.json", self.manifest)

    def __enter__(self):
        return self

    def complete(self, *, failures=(), exclusions=()):
        if self.manifest.status != "INCOMPLETE":
            raise ValueError("run already finalized")
        current = SourceProvenance.capture(self.repo, self.experiment.source.scientific_paths)
        if fingerprint(current.identity()) != fingerprint(self.experiment.source.identity()):
            raise ValueError("source_changed_during_run")
        if canonical_json(current_environment_like(self.experiment.scientific_environment).scientific) != canonical_json(self.experiment.scientific_environment):
            raise ValueError("environment_changed_during_run")
        check_dataset(self.dataset_root, self.experiment.dataset)
        self.manifest.failures = list(failures)
        self.manifest.exclusions.extend(exclusions)
        outputs = build_output_manifest(self.path, self.specs)
        write_json(self.path / "output_manifest.json", outputs)
        assert fingerprint(read_json(self.path / "output_manifest.json")) == outputs.sha256
        self.manifest.output_manifest_sha256 = outputs.sha256
        self.manifest.status = "SUCCESS"
        self.manifest.ended_at = utc_now()
        write_json(self.path / "manifest.json", self.manifest)
        write_json(self.path / "SUCCESS", {"manifest_sha256": file_sha256(self.path / "manifest.json"),
                   "output_manifest_sha256": outputs.sha256, "run_id": self.manifest.run_id})
        decision = check_cache(self.path, self.experiment, self.purpose)
        development_only = (self.manifest.classification == "DEVELOPMENT_NONCANONICAL"
                            and set(decision.reasons) <= {"dirty_source", "noncanonical_run"})
        if not decision.reusable and not development_only:
            (self.path / "SUCCESS").unlink(missing_ok=True)
            raise ValueError("completion_integrity_failure: " + ",".join(decision.reasons))
        return self.path

    def fail(self, error):
        (self.path / "SUCCESS").unlink(missing_ok=True)
        self.manifest.status = "FAILED"
        self.manifest.ended_at = utc_now()
        self.manifest.error = {"type": type(error).__name__, "message": str(error),
                               "traceback": "".join(traceback.format_exception(error))}
        write_json(self.path / "manifest.json", self.manifest)
        write_json(self.path / "FAILED", self.manifest.error)

    def __exit__(self, typ, error, tb):
        if error is not None:
            self.fail(error)
        elif self.manifest.status != "SUCCESS":
            error = RuntimeError("incomplete_run: complete() was not called")
            self.fail(error)
            raise error
        return False


def check_cache(run_dir, expected: ExperimentManifest, requested_purpose):
    """The sole reuse decision. No fallbacks, filename heuristics or migration."""
    reasons = []
    def reject(reason):
        if reason not in reasons:
            reasons.append(reason)
    purpose = RunPurpose(requested_purpose)
    canonical_required = purpose == RunPurpose.CLAIM
    root = Path(run_dir)
    try:
        manifest = read_json(_safe_file(root, "manifest.json"))
        if canonical_json(current_environment_like(expected.scientific_environment).scientific) != canonical_json(expected.scientific_environment):
            reject("environment_mismatch")
        if manifest.get("schema_version") != PROVENANCE_SCHEMA:
            return CacheDecision(False, ("unsupported_manifest_schema",))
        RunManifest(**manifest)  # Reject missing/extra schema fields, not just a version string.
        exp = experiment_from_dict(manifest["experiment"])
        expected_names = {"manifest.json", "config.json", "environment.json", "dataset_manifest.json",
                          "cohort_manifest.json", "output_manifest.json", "SUCCESS", "outputs", "logs"}
        if {p.name for p in root.iterdir()} != expected_names:
            reject("run_inventory_mismatch")
        if not _supported(exp) or not _supported(expected):
            reject("unsupported_manifest_schema")
        cached, want = exp.identity(), expected.identity()
        dimensions = [("source", "source_state_mismatch"), ("protocol_version", "protocol_mismatch"),
            ("accounting_schema", "accounting_schema_mismatch"), ("config_sha256", "config_mismatch"),
            ("dataset_manifest_sha256", "dataset_mismatch"), ("cohort_sha256", "cohort_mismatch"),
            ("scientific_environment", "environment_mismatch"), ("seeds", "seed_mismatch")]
        if exp.source.commit != expected.source.commit:
            reject("source_commit_mismatch")
        for key, reason in dimensions:
            if canonical_json(cached[key]) != canonical_json(want[key]):
                reject(reason)
        if manifest.get("experiment_fingerprint") != exp.fingerprint or exp.fingerprint != expected.fingerprint:
            reject("experiment_fingerprint_mismatch")
        if manifest.get("purpose") != purpose.value:
            reject("run_purpose_mismatch")
        if canonical_required:
            if exp.source.dirty:
                reject("dirty_source")
            if not manifest.get("claim_eligible") or manifest.get("purpose") != RunPurpose.CLAIM.value or manifest.get("allow_dirty") or manifest.get("classification") != "CANONICAL_CLAIM":
                reject("noncanonical_run")
        if manifest.get("status") != "SUCCESS" or not (root / "SUCCESS").is_file() or (root / "FAILED").exists():
            reject("incomplete_run")
        else:
            marker = read_json(_safe_file(root, "SUCCESS"))
            if marker.get("manifest_sha256") != file_sha256(root / "manifest.json") or marker.get("run_id") != manifest["run_id"]:
                reject("completion_marker_mismatch")
        for name, recorded in manifest["metadata_sha256"].items():
            if file_sha256(_safe_file(root, name)) != recorded:
                reject("metadata_hash_mismatch")
        if set(manifest["metadata_sha256"]) != {"config.json", "environment.json", "dataset_manifest.json", "cohort_manifest.json"}:
            reject("metadata_inventory_mismatch")
        # Snapshot data and embedded identity must agree, not merely be independently hashable.
        snapshots = {"config.json": exp.config, "dataset_manifest.json": exp.dataset,
                     "cohort_manifest.json": exp.cohort}
        for name, value in snapshots.items():
            if canonical_json(read_json(root / name)) != canonical_json(value):
                reject("metadata_identity_mismatch")
        if read_json(root / "environment.json")["scientific"] != exp.scientific_environment:
            reject("environment_mismatch")
        outputs = read_json(_safe_file(root, "output_manifest.json"))
        if outputs.get("schema_version") != OUTPUT_SCHEMA:
            reject("unsupported_manifest_schema")
        output_hash = fingerprint(outputs)
        if manifest.get("output_manifest_sha256") != output_hash:
            reject("output_manifest_mismatch")
        if (root / "SUCCESS").is_file() and read_json(root / "SUCCESS").get("output_manifest_sha256") != output_hash:
            reject("completion_marker_mismatch")
        try:
            actual = build_output_manifest(root, [OutputSpec(**s) for s in manifest["required_outputs"]])
            if canonical_json(actual) != canonical_json(outputs):
                reject("output_hash_mismatch")
        except (OSError, ValueError, StopIteration):
            reject("output_hash_mismatch")
    except RuntimeError:
        reject("environment_unresolved")
    except FileNotFoundError:
        reject("incomplete_run")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, StopIteration) as error:
        reject("unsupported_manifest_schema" if str(error) == "unsupported_manifest_schema" else "invalid_or_unversioned_run")
    return CacheDecision(not reasons, tuple(reasons))


def load_verified_output(run_dir, expected, purpose, relative_output):
    decision = check_cache(run_dir, expected, purpose)
    if not decision.reusable:
        raise ValueError("cache_rejected: " + ",".join(decision.reasons))
    names = {f["path"] for f in read_json(Path(run_dir) / "output_manifest.json")["files"]}
    if relative_path(relative_output) not in names:
        raise ValueError("output_not_in_manifest")
    return _safe_file(Path(run_dir), relative_output)


def refuse_unmanaged_workflow():
    """Legacy directory-based corpus/report entry points cannot establish provenance."""
    raise ValueError("unversioned_workflow_rejected: use an explicit ExperimentManifest and RunSession; legacy outputs are never upgraded or reused")
