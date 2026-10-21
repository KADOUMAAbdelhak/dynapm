"""Exploratory fixed-development-cohort diagnostics; never runs policies or confirmation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
import time
import numpy as np
import pandas as pd
from dynapm.core.provenance import (SourceProvenance, experiment_from_dict, prepare_experiment,
    fingerprint, read_json, canonical_json)
from dynapm.core.run_store import RunSession, OutputSpec, check_cache, write_json
from dynapm.core.predictor import forecast_at_origin
from dynapm.core.temporal import forecast_targets, history_valid
from dynapm.core.discretization import classify_value
from dynapm.eval.replay import prepare_vm_inputs, CPU_T, MEM_T
from dynapm.experiments.pilot_design import guard_cohort

VERSION = 'predictor-diagnosis-v1'
ORIGINS = 8
LEADS = (1,12,72,144,288)
PILOT = ('6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/'
         '2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe')


def choose_origins(index, count=ORIGINS):
    """Equal spacing over ordered input-eligible origins; no error/outcome input."""
    index = pd.DatetimeIndex(index).sort_values()
    if len(index) < count:
        raise ValueError('insufficient eligible development origins')
    return index[np.linspace(0,len(index)-1,count,dtype=int)]


def diagnostic_controls(series, origin):
    targets = forecast_targets(origin)
    past = series.loc[series.index <= origin]
    return {'persistence': pd.Series(float(past.loc[origin]), index=targets),
            'seasonal_naive_24h': pd.Series(past.reindex(targets-pd.Timedelta(days=1)).to_numpy(), index=targets)}


def diagnose_vm(args):
    repo, selected = args
    trace, vm = selected['trace'], str(selected['vm_id'])
    inputs = prepare_vm_inputs(trace, vm, repo_root=repo, with_predictors=True, with_residuals=False)
    eligible = [t for t in inputs.ground_truth.index if t in inputs.frame.index and
        all(history_valid(inputs.frame[target],t) for target in (CPU_T,MEM_T))]
    origins = choose_origins(eligible)
    points, profiles, metadata = [], [], []
    for resource,target,predictor,thresholds in zip(('cpu','memory'),(CPU_T,MEM_T),inputs.predictors,
            (inputs.cpu_thresholds,inputs.mem_thresholds)):
        series = inputs.frame[target]
        # Diagnostic with actual intervening history: NOT a fixed-origin deployable forecast.
        one_step = predictor.predict_streaming(inputs.frame).y_pred
        gates = np.array([thresholds[k] for k in ('p20','p40','p60','p80')])
        boot = inputs.bootstrap[target]
        metadata.append({'trace':trace,'vm_id':vm,'resource':resource,
            'eligible_origins':len(eligible),'selected_origins':len(origins),
            'candidate_origins':len(inputs.ground_truth),'thresholds':canonical_json(thresholds),
            'bootstrap_mean':float(boot.mean()),'stream_mean':float(inputs.stream[target].mean()),
            'bootstrap_min':float(boot.min()),'bootstrap_max':float(boot.max()),
            'stream_outside_bootstrap_range_fraction':float(((inputs.stream[target]<boot.min())|(inputs.stream[target]>boot.max())).mean()),
            **predictor.training_diagnostics})
        for origin in origins:
            targets = forecast_targets(origin)
            forecasts = {'rf_recursive':forecast_at_origin(predictor,series,origin),
                         **diagnostic_controls(series,origin),
                         'rf_one_step_actual_history_DIAGNOSTIC':one_step.reindex(targets)}
            actual = series.reindex(targets)
            future_missing = int(actual.isna().sum())
            for method,predicted in forecasts.items():
                mask = np.isfinite(actual.to_numpy()) & np.isfinite(predicted.to_numpy())
                for lead in LEADS:
                    i = lead-1
                    if not mask[i]: continue
                    y,p = float(actual.iloc[i]),float(predicted.iloc[i])
                    margin = float(np.abs(gates-y).min())
                    points.append({'trace':trace,'vm_id':vm,'tier':selected['volatility_tier'],
                        'resource':resource,'origin':origin,'target_time':targets[i],'lead':lead,'method':method,
                        'actual':y,'prediction':p,'error':p-y,'absolute_error':abs(p-y),
                        'class_error':classify_value(p,thresholds)!=classify_value(y,thresholds),
                        'boundary_margin':margin,'near_boundary_0_1pp':margin<=.1,
                        'future_missing_slots':future_missing})
                if mask.sum()>=200:
                    y95,p95 = float(np.quantile(actual.to_numpy()[mask],.95)),float(np.quantile(predicted.to_numpy()[mask],.95))
                    profiles.append({'trace':trace,'vm_id':vm,'resource':resource,'origin':origin,'method':method,
                        'paired_slots':int(mask.sum()),'actual_p95':y95,'predicted_p95':p95,
                        'p95_error':p95-y95,'p95_absolute_error':abs(p95-y95),
                        'p95_class_error':classify_value(p95,thresholds)!=classify_value(y95,thresholds),
                        'p95_boundary_margin':float(np.abs(gates-y95).min()),
                        'actual_mean':float(actual.to_numpy()[mask].mean()),
                        'predicted_mean':float(predicted.to_numpy()[mask].mean()),
                        'mean_class_error':classify_value(float(predicted.to_numpy()[mask].mean()),thresholds)!=classify_value(float(actual.to_numpy()[mask].mean()),thresholds),
                        'mean_boundary_margin':float(np.abs(gates-actual.to_numpy()[mask].mean()).min()),
                        'actual_std':float(actual.to_numpy()[mask].std()),
                        'predicted_std':float(predicted.to_numpy()[mask].std()),
                        'future_missing_slots':future_missing})
    print(f'completed {trace}/{vm}',flush=True)
    return points,profiles,metadata


def execute(repo,workers=4):
    repo = Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty: raise ValueError('clean committed source required')
    prior = repo/'results/runs'/PILOT
    old = experiment_from_dict(read_json(prior/'manifest.json')['experiment'])
    decision = check_cache(prior,old,'pilot')
    if not decision.reusable: raise ValueError(decision.reasons)
    selected = pd.read_parquet(prior/'outputs/pilot_cohort.parquet')
    guard_cohort(selected)
    if {(r.trace,str(r.vm_id)) for r in selected.itertuples()} != {(e.trace,e.entity_id) for e in old.cohort.entities if e.included}:
        raise ValueError('fixed development cohort mismatch')
    config = replace(old.config, policies=(), analysis={'diagnostic_version':VERSION,
        'origins_per_vm':ORIGINS,'origin_selection':'equal-index-spacing-over-valid-observed-hourly-origins-v1',
        'leads':LEADS,'controls':['persistence','seasonal_naive_24h'],
        'one_step_comparator':'actual-intervening-history-diagnostic-not-fixed-origin-forecast',
        'boundary_tolerance_percentage_points':.1,'profile_class_statistic':'arithmetic-mean-as-production','purpose':'exploratory-no-confirmatory-inference'})
    exp,env = prepare_experiment(repo,repo/'data/raw',config,old.dataset,old.cohort,{'model':42})
    required = [OutputSpec('outputs/'+name,role) for name,role in (
        ('lead_errors.parquet','paired-lead-error-observations'),('profile_errors.parquet','origin-p95-class-errors'),
        ('vm_diagnostics.parquet','input-training-origin-diagnostics'),('summary.json','exploratory-macro-vm-summary'))]
    started = time.perf_counter()
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=repo/'data/raw',purpose='pilot',required_outputs=required) as run:
        print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint}),flush=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            answers = list(pool.map(diagnose_vm,[(repo,r) for r in selected.to_dict('records')]))
        frames = [pd.DataFrame([row for answer in answers for row in answer[i]]) for i in range(3)]
        for frame,name in zip(frames,('lead_errors','profile_errors','vm_diagnostics')):
            frame.to_parquet(run.path/'outputs'/f'{name}.parquet',index=False)
        points,profiles,meta = frames
        if len(meta)!=36 or meta.selected_origins.ne(ORIGINS).any(): raise ValueError('cohort execution incomplete')
        numeric = points[['actual','prediction','error','absolute_error','boundary_margin']].to_numpy()
        if not np.isfinite(numeric).all(): raise ValueError('nonfinite diagnostics')
        # Common matched target sets for three deployable controls, and teacher-forced diagnosis separately.
        keys=['trace','vm_id','resource','origin','lead']
        matched = points.groupby(keys).method.nunique()
        paired = points.merge(matched[matched.eq(4)].rename('n_methods').reset_index(),on=keys)
        vm_means = paired.groupby(['resource','lead','method','trace','vm_id']).agg(
            mae=('absolute_error','mean'),bias=('error','mean'),class_error=('class_error','mean')).reset_index()
        aggregate = vm_means.groupby(['resource','lead','method']).agg(
            mae=('mae','mean'),bias=('bias','mean'),class_error=('class_error','mean'),
            min_vm_mae=('mae','min'),max_vm_mae=('mae','max'),n_vms=('vm_id','size')).reset_index()
        summary={'label':'DEVELOPMENT EXPLORATORY DIAGNOSIS; NOT CLAIM EVIDENCE',
            'source_commit':exp.source.commit,'fingerprint':exp.fingerprint,'run_id':run.manifest.run_id,
            'cohort_sha256':old.cohort.sha256,'vm_count':18,'origins_per_vm':ORIGINS,
            'wall_seconds':time.perf_counter()-started,'common_four_method_lead_rows':len(paired),
            'lead_summary':aggregate.to_dict('records'),
            'profile_summary':profiles.groupby(['resource','method']).agg(
                mae=('p95_absolute_error','mean'),bias=('p95_error','mean'),mean_class_error=('mean_class_error','mean'),p95_class_error=('p95_class_error','mean'),n=('vm_id','size')).reset_index().to_dict('records')}
        write_json(run.path/'outputs/summary.json',summary)
        run.complete()
    assert check_cache(run.path,exp,'pilot').reusable
    print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint,
        'output_manifest_sha256':read_json(run.path/'manifest.json')['output_manifest_sha256']}),flush=True)
    return run.path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    args=parser.parse_args()
    execute(args.repo,args.workers)

if __name__=='__main__': main()
