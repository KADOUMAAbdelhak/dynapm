"""V4D prospective e->g amendment. Never reads method outcomes."""
from pathlib import Path
from dynapm.core.provenance import read_json,fingerprint,file_sha256,canonical_json
from dynapm.core.run_store import write_json
from dynapm.experiments.confirmatory_design import emit_yaml,PRIMARY_METHODS,COMPARISON_FAMILIES,PRIMARY_FIDELITY_ENDPOINTS
from dynapm.experiments.google2019_availability_validation import validate_protocol_v2

DESIGN_PATH='configs/google2019_staged_replication_v1.json'
DESIGN_YAML='configs/google2019_staged_replication_v1.yaml'
SCHEMA='google2019-sequential-replication-design-v1'
E_BINDING='configs/google2019_stage_e_binding_v1.json'
G_BINDING='configs/google2019_stage_g_binding_v1.json'
E_COHORT_SHA='992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c'
E_MEMBERS_SHA='72509e63e07504d905e78d7c9ace6f70b66b9b6a0c4309a29d0c175471b00b6d'
RUNTIME_FILES=(
    'dynapm/experiments/google_staged_design.py','dynapm/experiments/google_replication.py',
    'dynapm/scripts/task30_google_replication.py','dynapm/data/google2019_clock.py',
    'dynapm/core/temporal.py','dynapm/core/features.py','dynapm/data/bootstrap.py','dynapm/core/discretization.py','dynapm/core/ground_truth.py',
    'dynapm/core/evaluation_clock.py','dynapm/core/forecasting.py','dynapm/core/schema.py',
    'dynapm/core/accounting.py','dynapm/methods/baselines_v2.py','dynapm/methods/factories.py',
    'dynapm/eval/replay.py','dynapm/eval/runner_v2.py','dynapm/core/provenance.py',
    'dynapm/core/run_store.py','dynapm/data/manifests.py',
    'dynapm/experiments/confirmatory_design.py','dynapm/experiments/confirmatory_execution.py','dynapm/experiments/confirmatory_estimation.py',
    'dynapm/experiments/google2019_protocol_validation.py','dynapm/experiments/google2019_requests.py')


def stage_e_binding(repo):
    repo=Path(repo);authority=read_json(repo/'configs/google2019_replication_cohort_v2.json')
    e=authority['e'];audit=read_json(repo/'configs/google2019_v4c1_validation_record.json')
    if e['cohort_sha256']!=E_COHORT_SHA or e['member_records_sha256']!=E_MEMBERS_SHA or e['selected']!=1000:
        raise ValueError('frozen_e_cohort_changed')
    generation='data/google2019/canonical/generations/'+e['canonical_generation']
    return dict(schema_version='google2019-stage-input-binding-v1',cell='e',status='AVAILABILITY_CONTRACT_READY',
        protocol_fingerprint=authority['protocol_fingerprint'],cohort_rule_sha256=authority['selection_rule_sha256'],
        canonical_path=generation,canonical_sha256=e['canonical_sha256'],
        canonical_manifest_sha256=file_sha256(repo/generation/'manifest.json'),
        clock_audit_path=audit['path'],clock_audit_manifest_sha256=audit['manifest_sha256'],
        cohort_path=e['manifest_path'],cohort_sha256=E_COHORT_SHA,member_records_sha256=E_MEMBERS_SHA,
        eligibility_path=authority['eligibility_manifest_path'],eligibility_sha256=authority['eligibility_manifest_sha256'])


def design_document(repo):
    repo=Path(repo);protocol=validate_protocol_v2(repo);authority=read_json(repo/'configs/google2019_replication_cohort_v2.json')
    binding=read_json(repo/E_BINDING)
    if canonical_json(binding)!=canonical_json(stage_e_binding(repo)):raise ValueError('e_binding_not_frozen')
    return dict(schema_version=SCHEMA,gate='V4D',amendment='prospective staged execution; replaces simultaneous two-cell execution prerequisite, not scientific protocol v2',
        status='FROZEN_BEFORE_ANY_GOOGLE_METHOD_OUTCOMES',protocol=protocol,
        stages=dict(A=dict(cell='e',role='first Google replication evidence',binding_path=E_BINDING,binding_sha256=file_sha256(repo/E_BINDING),
            exact_entities=1000,cohort_sha256=E_COHORT_SHA,member_records_sha256=E_MEMBERS_SHA),
            B=dict(cell='g',role='held-out within-corpus replication; not an independent corpus',binding_path=G_BINDING,
                maximum_entities=1000,required_regardless_of_e_direction=True,requires_validated_canonical_clock_and_cohort=True)),
        cohort_selection_rule=authority['selection_rule'],cohort_selection_rule_sha256=authority['selection_rule_sha256'],
        cohort_policy='apply identical rule independently; no cross-cell backfill; do not select by utilization, volatility, outcomes or expected effects',
        methods=list(PRIMARY_METHODS),comparison_families={k:[dict(treatment=a,control=b) for a,b in v] for k,v in COMPARISON_FAMILIES.items()},
        fidelity_endpoints=list(PRIMARY_FIDELITY_ENDPOINTS),primary_cost='n_refresh_events',
        secondary=['field writes','field value changes','trigger counters','profile age','bias','eligibility delays','verified read count','exposure'],
        statistics=dict(unit='entity',paired_mean_and_median=True,bootstrap_repetitions=10000,bootstrap_seed=20251022,
            confidence_level=.95,bootstrap_method='paired entity percentile bootstrap',wilcoxon_zero_method='wilcox',
            alternative='two-sided',all_ties='p=1, effect=0; standardized effect undefined when paired SD is zero',
            multiplicity='Holm independently within F1/F2/F3 across contrasts x four fidelity endpoints plus refresh cost, separately per cell',alpha=.05,
            practical_significance='NOT_DEFINED_AT_PROFILE_LEVEL'),
        protocol_execution=dict(bootstrap='Google nominal-time split, not observed-row Materna split',
            initialization='Static whole bootstrap; PW cadence-length bootstrap window; Full-Rewrite trailing 24h bootstrap window',
            runtime_window_hours=24,minimum_paired_slots=200,pw_history_slots=96,horizon_slots=288,evaluation_cadence_seconds=3600,
            predictor_or_detector_training=False,normalization='request-normalized ratios; no capacity inference, interpolation or clipping'),
        robustness=dict(primary=False,cell='separate-cell estimates',resource='CPU and memory reported separately',
            volatility='bootstrap CPU population std(ddof=0); within frozen selected cell cohort tertiles; <=q1 low, <=q2 medium, else high; never selection',
            no_additional_confirmatory_tests=True),
        cross_cell_synthesis=dict(rule='for each predeclared family/contrast/endpoint report e and g mean/median/CI side by side',
            direction_categories='same_positive, same_negative, same_zero, discordant_or_one_zero based on paired mean signs; descriptive only',
            heterogeneity='g-minus-e mean and median point effects, no new pooled inference or significance test',
            no_opportunistic_pooling=True,no_favorable_cell_selection=True,shared_collection_overlap='report metadata overlap, no post-outcome exclusions',
            global_superiority_claim=False),
        commitments=dict(g_must_be_analyzed_and_reported_even_if_e_null_or_negative=True,
            no_method_config_statistics_or_cohort_rule_changes_after_e=True,
            correctness_fix='versioned pre-g amendment + regression test + comparable e/g reruns; invalidate superseded outcomes; never patch results',
            acquisition_failure='report g unavailable; no favorable replacement cell or relaxed eligibility',
            google_errors_not_materna_capacity_errors=True,no_operational_or_edge_claim=True),
        artifact_policy='new managed generation per cell; no legacy cache reuse, complete frozen cohort x five methods, fail on any entity error',
        scientific_runtime_sha256={p:file_sha256(repo/p) for p in RUNTIME_FILES},
        execution_in_this_task='none; synthetic validation only')


def frozen_design(repo):
    repo=Path(repo);d=read_json(repo/DESIGN_PATH)
    if canonical_json(d)!=canonical_json(design_document(repo)):raise ValueError('frozen_staged_design_or_scientific_source_mismatch')
    if (repo/DESIGN_YAML).read_text()!='# V4D prospective sequential amendment; no outcomes used.\n'+emit_yaml(d):
        raise ValueError('staged_design_yaml_mismatch')
    return d


def write_design(repo):
    repo=Path(repo);write_json(repo/E_BINDING,stage_e_binding(repo));d=design_document(repo)
    write_json(repo/DESIGN_PATH,d)
    (repo/DESIGN_YAML).write_text('# V4D prospective sequential amendment; no outcomes used.\n'+emit_yaml(read_json(repo/DESIGN_PATH)))
    return fingerprint(frozen_design(repo))
