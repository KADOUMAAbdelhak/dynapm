"""Provenance tooling only: hashing, inspection and validation, never training."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from dynapm.core.provenance import (SourceProvenance, EnvironmentProvenance,
    ExperimentConfigProvenance, ExperimentManifest, DataConfig, ModelConfig, PolicyConfig,
    config_from_dict, cohort_from_dict, dataset_from_dict, experiment_from_dict, read_json,
    canonical_json, prepare_experiment)
from dynapm.core.run_store import check_cache, write_json
from dynapm.data.manifests import materna_manifest, materna_cohort, check_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("manifest-dataset", help="hash the three local Materna traces")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("check-dataset")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p = commands.add_parser("manifest-cohort", help="read timestamps/row counts only")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--minimum-observations", type=int, default=2000)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("config-template")
    p.add_argument("--dataset-id", default="materna")
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("prepare-experiment", help="capture source/environment; no execution")
    for name in ("config", "dataset", "cohort", "repo", "dataset-root", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p = commands.add_parser("fingerprint")
    p.add_argument("--experiment", type=Path, required=True)
    for name in ("validate-run", "explain-cache"):
        p = commands.add_parser(name)
        p.add_argument("--run", type=Path, required=True)
        p.add_argument("--experiment", type=Path, required=True)
        p.add_argument("--purpose", choices=("smoke", "pilot", "claim"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "manifest-dataset":
            d = materna_manifest(args.root)
            write_json(args.output, d)
            print(canonical_json({"dataset_manifest_sha256": d.sha256, "file_count": d.file_count,
                "raw_entity_files": sum(f.role == "raw_entity" for f in d.files)}))
        elif args.command == "check-dataset":
            d = dataset_from_dict(read_json(args.manifest))
            check_dataset(args.root, d)
            print(canonical_json({"status": "VALID", "dataset_manifest_sha256": d.sha256}))
        elif args.command == "manifest-cohort":
            d = dataset_from_dict(read_json(args.dataset))
            c = materna_cohort(args.root, d, args.minimum_observations)
            write_json(args.output, c)
            print(canonical_json({"cohort_sha256": c.sha256,
                "included": sum(e.included for e in c.entities), "entities": len(c.entities)}))
        elif args.command == "config-template":
            config = ExperimentConfigProvenance(DataConfig(args.dataset_id), ModelConfig(),
                tuple(PolicyConfig(name, periodic_interval_hours=6.0 if "periodic" in name or "dynapm" in name else None)
                    for name in ("static_v2", "periodic_6h_v2", "reactive_v2", "full_rewrite_v2",
                                 "periodic_predictor_6h_v2", "dynapm_v3_v2")))
            write_json(args.output, config)
            print(canonical_json({"config_sha256": config.sha256, "execution": "NOT STARTED"}))
        elif args.command == "prepare-experiment":
            config = config_from_dict(read_json(args.config))
            exp, env = prepare_experiment(args.repo, args.dataset_root, config,
                dataset_from_dict(read_json(args.dataset)), cohort_from_dict(read_json(args.cohort)),
                {"model": config.model.random_state, "bootstrap": config.statistics.bootstrap_seed})
            write_json(args.output, exp)
            write_json(args.output.with_name(args.output.stem + "-environment.json"), env)
            print(canonical_json({"experiment_fingerprint": exp.fingerprint, "dirty": exp.source.dirty}))
        elif args.command == "fingerprint":
            exp = experiment_from_dict(read_json(args.experiment))
            print(canonical_json({"experiment_fingerprint": exp.fingerprint, "identity": exp.identity()}))
        else:
            exp = experiment_from_dict(read_json(args.experiment))
            decision = check_cache(args.run, exp, args.purpose)
            print(canonical_json(asdict(decision)))
            return 0 if decision.reusable else 2
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
