"""Managed task-aligned profile study on fixed development origins only."""
import argparse,subprocess,time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from dynapm.core.provenance import (SourceProvenance,experiment_from_dict,prepare_experiment,
    read_json,canonical_json,file_sha256)
from dynapm.core.run_store import RunSession,OutputSpec,check_cache,write_json
from dynapm.core.ground_truth import derive_ground_truth_at_t
from dynapm.core.temporal import forward_observations,forecast_targets
from dynapm.core.discretization import classify_value
from dynapm.core.forecasting import forecast_class_from_window,forecast_p95_from_window
from dynapm.eval.replay import prepare_vm_inputs,CPU_T,MEM_T
from dynapm.experiments.pilot_design import guard_cohort
from dynapm.experiments.profile_prediction import DirectProfile,timestamp_availability,VERSION

PARENT=('62f5727e20e29e0d0cbb620b9391c6d2909dd978549120dddd09bd7b3e470948/'
        '2026-10-22T004212.427895Z-62f5727e20e2-905e675d')
METHODS=('rf_recursive','rf_direct_joint','persistence','seasonal_naive_24h','rf_profile','ridge_profile')


def profile_vm(task):
    repo,entity,points=task;trace,vm=entity['trace'],str(entity['vm_id'])
    inputs=prepare_vm_inputs(trace,vm,repo_root=repo,with_predictors=False)
    origins=pd.DatetimeIndex(sorted(points.origin.unique()))
    if len(origins)!=8:raise ValueError('exact fixed origins required')
    rows,costs,training=[],[],[]
    for resource,target,thresholds in [('cpu',CPU_T,inputs.cpu_thresholds),('memory',MEM_T,inputs.mem_thresholds)]:
        fitted={}
        for method in ('rf_profile','ridge_profile'):
            model=DirectProfile(target,method);start=time.perf_counter();model.fit(inputs.bootstrap)
            costs.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,'cost_kind':'training',
                'seconds':time.perf_counter()-start,'state_array_bytes_lower_bound':model.state_bytes()})
            training.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,
                'training_rows':model.training_rows,'minimum_label_slots':model.label_slots_min,
                'maximum_label_slots':model.label_slots_max,'last_training_target':model.last_training_target,
                'bootstrap_last_observation':inputs.bootstrap.index[-1]})
            fitted[method]=model
        for origin in origins:
            w=forward_observations(inputs.frame,origin)
            truth=derive_ground_truth_at_t(inputs.frame,origin,cpu_thresholds=inputs.cpu_thresholds,mem_thresholds=inputs.mem_thresholds)
            actual_mean=float(w[target].mean());actual_p95=truth['p95_cpu_next_24h' if resource=='cpu' else 'p95_mem_next_24h']
            actual_class=truth['cpu_class' if resource=='cpu' else 'memory_class']
            for method in METHODS:
                start=time.perf_counter()
                if method in fitted:
                    pred=fitted[method].predict_profile(inputs.frame[target],origin,thresholds);available_slots=288
                else:
                    g=points[(points.resource==resource)&points.origin.eq(origin)&points.method.eq(method)].sort_values('lead')
                    if len(g)!=288 or not pd.DatetimeIndex(g.target_time).equals(forecast_targets(origin)):raise ValueError('parent forecast alignment')
                    # NO future observation mask may influence profile construction.
                    available=g.prediction.dropna().to_numpy(dtype=float);available_slots=len(available)
                    if available_slots<200:raise ValueError('baseline profile unavailable at fixed origin')
                    pred={'mean':float(available.mean()),'p95':forecast_p95_from_window(available),
                        'class':forecast_class_from_window(available,thresholds)}
                costs.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,
                    'cost_kind':'profile_prediction_or_aggregation','origin':origin,'seconds':time.perf_counter()-start,
                    'cost_scope':'full-direct-inference' if method in fitted else 'parent-forecast-aggregation-only'})
                rows.append({'trace':trace,'vm_id':vm,'tier':entity['volatility_tier'],'resource':resource,
                    'origin':origin,'method':method,'predicted_mean':pred['mean'],'predicted_p95':pred['p95'],
                    'predicted_class':pred['class'],'actual_mean':actual_mean,'actual_p95':actual_p95,
                    'actual_class':actual_class,'class_correct':pred['class']==actual_class,
                    'p95_absolute_error':abs(pred['p95']-actual_p95),'p95_bias':pred['p95']-actual_p95,
                    'mean_absolute_error':abs(pred['mean']-actual_mean),'mean_bias':pred['mean']-actual_mean,
                    'ground_truth_slots':len(w),'available_source_slots':available_slots,
                    'negative_mean':pred['mean']<0,'negative_p95':pred['p95']<0})
    print(f'completed {trace}/{vm}',flush=True)
    return rows,costs,training


def execute(repo,workers=2):
    repo=Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:raise ValueError('clean committed source required')
    prior=repo/'results/runs'/PARENT
    old=experiment_from_dict(read_json(prior/'manifest.json')['experiment'])
    if not check_cache(prior,old,'pilot').reusable:raise ValueError('incompatible parent')
    # Explicit managed dependency reuse, not pretending old outputs were generated
    # by the new source. Reject reuse if the producing scientific paths changed.
    changed=subprocess.check_output(['git','-C',str(repo),'diff','--name-only',old.source.commit,'HEAD','--',
        'dynapm/core','dynapm/data','dynapm/eval/replay.py','dynapm/experiments/forecast_design.py',
        'dynapm/scripts/task22_predictor_design.py']).decode().strip()
    if changed:raise ValueError('parent producing source changed: '+changed)
    selected=pd.DataFrame(old.cohort.filtering_config['selection_records']);guard_cohort(selected)
    dependency={'fingerprint':old.fingerprint,'run_id':read_json(prior/'manifest.json')['run_id'],
        'output_manifest_sha256':file_sha256(prior/'output_manifest.json'),
        'forecasts_sha256':file_sha256(prior/'outputs/forecasts.parquet')}
    config=replace(old.config,analysis={'study_version':VERSION,'methods':METHODS,'parent_managed_dependency':dependency,
        'origins':'same-eight-fixed-development-v2.4B','targets':['future_mean','future_p95'],
        'class_rule':'frozen-bootstrap-class-of-mean','profile_mask':'all-origin-available-predictions-no-future-mask',
        'label_rule':'canonical-paired-finite-200-of-288-bootstrap-only-full-elapsed-horizon',
        'rf_profile':{'trees':200,'max_depth':20,'max_features':'sqrt','seed':42,'n_jobs':1},
        'ridge_profile':{'alpha':1.0,'standard_scaler':True,'clip':False},
        'decision_rule':'compare-class-and-p95-against-seasonal-both-resources-no-posthoc-hybrid',
        'timestamp_audit':'all-retained-1576-no-resource-values-complete288-and-density200',
        'purpose':'exploratory-no-policy-evaluation-or-confirmatory-inference'})
    exp,env=prepare_experiment(repo,repo/'data/raw',config,old.dataset,old.cohort,{'model':42})
    if canonical_json(env.scientific)!=canonical_json(old.scientific_environment):raise ValueError('parent scientific environment mismatch')
    names={'profile_predictions.parquet':'origin-profile-field-predictions-and-canonical-truth',
        'training_labels_audit.parquet':'bootstrap-label-boundary-and-density-evidence',
        'costs.parquet':'direct-training-inference-and-baseline-aggregation-cost',
        'parent_costs.parquet':'explicit-parent-managed-point-model-cost-evidence',
        'seasonal_availability.parquet':'1576-vm-timestamp-only-availability',
        'vm_metrics.parquet':'per-vm-task-aligned-profile-errors',
        'tier_metrics.parquet':'descriptive-volatility-tier-profile-errors',
        'summary.json':'exploratory-profile-design-and-seasonal-availability-summary'}
    start=time.perf_counter()
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=repo/'data/raw',purpose='pilot',
            required_outputs=[OutputSpec('outputs/'+n,role) for n,role in names.items()]) as run:
        print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint}),flush=True)
        availability=[]
        for entry in old.dataset.files:
            if entry.role!='raw_entity':continue
            f=pd.read_csv(repo/'data/raw'/entry.path,sep=';',usecols=['Timestamp'],dtype=str)
            if len(f)<2000:continue
            idx=pd.DatetimeIndex(pd.to_datetime(f.Timestamp,format='%d.%m.%Y %H:%M:%S'))
            availability.append(timestamp_availability(idx,entry.trace,entry.entity_id))
        audit=pd.DataFrame(availability)
        if len(audit)!=1576:raise ValueError('timestamp-only retained cohort changed')
        audit.to_parquet(run.path/'outputs/seasonal_availability.parquet',index=False)
        points=pd.read_parquet(prior/'outputs/forecasts.parquet')
        tasks=[(repo,row,points[(points.trace==row['trace'])&points.vm_id.eq(str(row['vm_id']))]) for row in selected.to_dict('records')]
        with ProcessPoolExecutor(max_workers=workers) as pool:answers=list(pool.map(profile_vm,tasks))
        rows,costs,training=[pd.DataFrame([r for a in answers for r in a[i]]) for i in range(3)]
        if len(rows)!=1728 or not rows.groupby(['trace','vm_id','resource','origin']).method.nunique().eq(6).all():raise ValueError('candidate alignment')
        for col in ('actual_mean','actual_p95','actual_class','ground_truth_slots'):
            if not rows.groupby(['trace','vm_id','resource','origin'])[col].nunique().eq(1).all():raise ValueError('truth mismatch')
        if not np.isfinite(rows[['predicted_mean','predicted_p95']].to_numpy()).all():raise ValueError('nonfinite profiles')
        rows.to_parquet(run.path/'outputs/profile_predictions.parquet',index=False)
        costs.to_parquet(run.path/'outputs/costs.parquet',index=False)
        training.to_parquet(run.path/'outputs/training_labels_audit.parquet',index=False)
        # Byte-preserving dependency copy, declared in both config and output manifest.
        (run.path/'outputs/parent_costs.parquet').write_bytes((prior/'outputs/costs.parquet').read_bytes())
        fields=['class_correct','p95_absolute_error','p95_bias','mean_absolute_error','mean_bias','negative_mean','negative_p95']
        vm=rows.groupby(['resource','method','trace','vm_id','tier'])[fields].mean().reset_index()
        vm.to_parquet(run.path/'outputs/vm_metrics.parquet',index=False)
        tiers=vm.groupby(['resource','method','tier'])[fields].mean().reset_index()
        tiers.to_parquet(run.path/'outputs/tier_metrics.parquet',index=False)
        wins=[]
        for resource,g in vm.groupby('resource'):
            reference=g[g.method.eq('seasonal_naive_24h')].set_index(['trace','vm_id'])
            for method,h in g.groupby('method'):
                h=h.set_index(['trace','vm_id']);delta=h.p95_absolute_error-reference.p95_absolute_error
                dclass=h.class_correct-reference.class_correct
                wins.append({'resource':resource,'method':method,'p95_wins':int(delta.lt(-1e-12).sum()),
                    'p95_losses':int(delta.gt(1e-12).sum()),'p95_ties':int(delta.abs().le(1e-12).sum()),
                    'class_wins':int(dclass.gt(1e-12).sum()),'class_losses':int(dclass.lt(-1e-12).sum()),
                    'class_ties':int(dclass.abs().le(1e-12).sum())})
        counts=audit.select_dtypes('number').sum().to_dict()
        summary={'purpose':'pilot','source_commit':exp.source.commit,'fingerprint':exp.fingerprint,
            'run_id':run.manifest.run_id,'cohort_sha256':old.cohort.sha256,'parent_dependency':dependency,
            'profile_rows':len(rows),'wall_seconds':time.perf_counter()-start,
            'macro_vm':vm.groupby(['resource','method'])[fields].mean().reset_index().to_dict('records'),
            'wins_vs_seasonal':wins,'timestamp_availability_counts':counts,
            'availability_scope':'timestamp-only upper bound on finite-value eligibility; no utilization values inspected',
            'no_policy_parameter_changes':True,'no_confirmatory_outcomes':True}
        write_json(run.path/'outputs/summary.json',summary);run.complete()
    assert check_cache(run.path,exp,'pilot').reusable
    print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint,
        'output_manifest_sha256':read_json(run.path/'manifest.json')['output_manifest_sha256']}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--workers',type=int,choices=(1,2),default=2)
    a=p.parse_args();execute(a.repo,a.workers)

if __name__=='__main__':main()
