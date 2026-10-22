"""Managed operational-origin disposition on the fixed 18 development VMs."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
import subprocess
import time
import numpy as np
import pandas as pd
from dynapm.core.discretization import compute_thresholds
from dynapm.core.ground_truth import derive_ground_truth_at_t
from dynapm.core.temporal import HORIZON, forward_observations
from dynapm.core.provenance import (SourceProvenance, experiment_from_dict,
    prepare_experiment, read_json, canonical_json, file_sha256)
from dynapm.core.run_store import RunSession, OutputSpec, check_cache, write_json
from dynapm.eval.replay import prepare_vm_inputs, CPU_T, MEM_T
from dynapm.experiments.pilot_design import guard_cohort
from dynapm.experiments.profile_prediction import DirectProfile
from dynapm.experiments.predictor_disposition import (VERSION, VALIDATION_FOLDS,
    operational_origins, bootstrap_origins, seasonal_profile, choose_content)

PARENT = ('6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/'
          '2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe')
METRICS = ['class_correct', 'p95_absolute_error', 'p95_bias']


def score(prediction, truth, resource):
    key = 'cpu' if resource == 'cpu' else 'mem'
    actual_class = truth['cpu_class' if resource == 'cpu' else 'memory_class']
    actual_p95 = truth[f'p95_{key}_next_24h']
    if prediction is None:
        return dict(available=False, predicted_class=None, predicted_mean=None,
                    predicted_p95=None, actual_class=actual_class, actual_p95=actual_p95,
                    class_correct=None, p95_absolute_error=None, p95_bias=None)
    if not np.isfinite([prediction['mean'], prediction['p95']]).all():
        raise ValueError('nonfinite content')
    return dict(available=True, predicted_class=prediction['class'],
        predicted_mean=prediction['mean'], predicted_p95=prediction['p95'],
        actual_class=actual_class, actual_p95=actual_p95,
        class_correct=float(prediction['class'] == actual_class),
        p95_absolute_error=abs(prediction['p95'] - actual_p95),
        p95_bias=prediction['p95'] - actual_p95)


def run_vm(task):
    repo, entity, origins = task
    trace, vm = entity['trace'], str(entity['vm_id'])
    inputs = prepare_vm_inputs(trace, vm, repo_root=repo, with_predictors=False)
    folds = bootstrap_origins(inputs.bootstrap)
    rows, validation, selections, eligibility, costs = [], [], [], [], []
    for resource, target, thresholds in [('cpu', CPU_T, inputs.cpu_thresholds),
                                         ('memory', MEM_T, inputs.mem_thresholds)]:
        fold_rows = []
        for fold, origin in enumerate(folds):
            prefix = inputs.bootstrap.loc[:origin]
            # Prefix-only thresholds keep rolling validation fully prequential;
            # final streaming thresholds are the usual full-bootstrap thresholds.
            cpu_th, mem_th = compute_thresholds(prefix, CPU_T), compute_thresholds(prefix, MEM_T)
            th = cpu_th if resource == 'cpu' else mem_th
            model = DirectProfile(target)
            start = time.perf_counter(); model.fit(prefix)
            costs.append(dict(trace=trace, vm_id=vm, resource=resource, scope='selector_fold_training',
                              fold=fold, seconds=time.perf_counter() - start))
            truth = derive_ground_truth_at_t(inputs.bootstrap, origin, cpu_thresholds=cpu_th, mem_thresholds=mem_th)
            if model.last_training_target > origin or origin + HORIZON > inputs.bootstrap.index[-1]:
                raise ValueError('rolling selection label leakage')
            for method, pred in [('rf_profile', model.predict_profile(prefix[target], origin, th)),
                                 ('seasonal', seasonal_profile(prefix[target], origin, th))]:
                if pred is None:
                    raise ValueError('unpaired bootstrap selector evidence')
                record = dict(trace=trace, vm_id=vm, resource=resource, fold=fold,
                    origin=origin, method=method, last_training_target=model.last_training_target,
                    validation_horizon_end=origin + HORIZON, bootstrap_end=inputs.bootstrap.index[-1],
                    training_rows=model.training_rows, thresholds=canonical_json(th),
                    **score(pred, truth, resource))
                fold_rows.append(record); validation.append(record)
        evidence = pd.DataFrame(fold_rows).groupby('method')[METRICS].mean()
        rf, sn = evidence.loc['rf_profile'], evidence.loc['seasonal']
        selected = choose_content(rf.class_correct, sn.class_correct, rf.p95_absolute_error, sn.p95_absolute_error)
        selections.append(dict(trace=trace, vm_id=vm, tier=entity['volatility_tier'], resource=resource,
            selected_method=selected, validation_origins=len(folds),
            rf_bootstrap_class=rf.class_correct, seasonal_bootstrap_class=sn.class_correct,
            rf_bootstrap_p95_mae=rf.p95_absolute_error, seasonal_bootstrap_p95_mae=sn.p95_absolute_error,
            selection_cutoff=inputs.bootstrap.index[-1]))
        final = DirectProfile(target)
        start = time.perf_counter(); final.fit(inputs.bootstrap)
        costs.append(dict(trace=trace, vm_id=vm, resource=resource, scope='final_bootstrap_training',
            seconds=time.perf_counter()-start, state_bytes_lower_bound=final.state_bytes()))
        for event in origins.to_dict('records'):
            origin = pd.Timestamp(event['origin'])
            if origin <= inputs.bootstrap.index[-1]:
                raise ValueError('non-streaming operational origin')
            try:
                truth = derive_ground_truth_at_t(inputs.frame, origin,
                    cpu_thresholds=inputs.cpu_thresholds, mem_thresholds=inputs.mem_thresholds)
            except ValueError as error:
                eligibility.append(dict(trace=trace, vm_id=vm, resource=resource,
                    origin=origin, origin_group=event['origin_group'], truth_available=False,
                    reason=str(error)))
                continue
            start = time.perf_counter()
            rf_pred = final.predict_profile(inputs.frame[target], origin, thresholds)
            costs.append(dict(trace=trace, vm_id=vm, resource=resource, scope='rf_operational_inference',
                origin=origin, seconds=time.perf_counter()-start))
            sn_pred = seasonal_profile(inputs.frame[target], origin, thresholds)
            eligibility.append(dict(trace=trace, vm_id=vm, resource=resource, origin=origin,
                origin_group=event['origin_group'], truth_available=True, seasonal_available=sn_pred is not None,
                rf_available=True, selector_available=(rf_pred if selected=='rf_profile' else sn_pred) is not None,
                reason='eligible' if sn_pred is not None else 'seasonal_source_below_200'))
            for method, pred in [('rf_profile', rf_pred), ('seasonal', sn_pred),
                                 ('selector', rf_pred if selected=='rf_profile' else sn_pred)]:
                rows.append(dict(trace=trace, vm_id=vm, tier=entity['volatility_tier'], resource=resource,
                    origin=origin, origin_group=event['origin_group'], method=method,
                    selected_method=selected if method=='selector' else method,
                    ground_truth_slots=len(forward_observations(inputs.frame, origin)),
                    **score(pred, truth, resource)))
    print(f'completed {trace}/{vm}', flush=True)
    return rows, validation, selections, eligibility, costs


def summarize(rows):
    # All scores are on common candidate availability; retain native coverage
    # separately instead of rewarding methods for scoring fewer origins.
    keys = ['trace','vm_id','resource','origin']
    common = rows.groupby(keys).available.transform('all')
    paired = rows.loc[common].copy()
    if not paired.groupby(keys).method.nunique().eq(3).all():
        raise ValueError('candidate alignment')
    for col in ['actual_class','actual_p95','ground_truth_slots']:
        if not paired.groupby(keys)[col].nunique().eq(1).all():
            raise ValueError('shared truth mismatch')
    expanded = pd.concat([paired, paired.assign(origin_group='all')], ignore_index=True)
    vm = expanded.groupby(['origin_group','resource','method','trace','vm_id','tier'])[METRICS].mean().reset_index()
    vm['n_origins'] = expanded.groupby(['origin_group','resource','method','trace','vm_id','tier']).size().to_numpy()
    macro = vm.groupby(['origin_group','resource','method'])[METRICS].mean().reset_index()
    tiers = vm.groupby(['origin_group','resource','method','tier'])[METRICS].mean().reset_index()
    wins = []
    for (group, resource), frame in vm.groupby(['origin_group','resource']):
        baseline=frame[frame.method.eq('seasonal')].set_index(['trace','vm_id'])
        for method in ['rf_profile','selector']:
            candidate=frame[frame.method.eq(method)].set_index(['trace','vm_id'])
            for metric, direction in [('class_correct',1),('p95_absolute_error',-1)]:
                delta=direction*(candidate[metric]-baseline[metric])
                wins.append(dict(origin_group=group, resource=resource, method=method, metric=metric,
                    wins=int(delta.gt(1e-12).sum()), losses=int(delta.lt(-1e-12).sum()),
                    ties=int(delta.abs().le(1e-12).sum()), n_vms=len(delta)))
    return vm, macro, tiers, wins


def execute(repo, workers=2):
    repo=Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:
        raise ValueError('clean committed source required')
    prior=repo/'results/runs'/PARENT
    old=experiment_from_dict(read_json(prior/'manifest.json')['experiment'])
    if not check_cache(prior,old,'pilot').reusable:
        raise ValueError('invalid managed origin dependency')
    changed=subprocess.check_output(['git','-C',str(repo),'diff','--name-only',old.source.commit,'HEAD','--',
        'dynapm/core','dynapm/data','dynapm/methods','dynapm/eval/replay.py',
        'dynapm/experiments/pilot_execution.py']).decode().strip()
    if changed:
        raise ValueError('operational origin producer changed: '+changed)
    selected=pd.DataFrame(old.cohort.filtering_config['selection_records']);guard_cohort(selected)
    events=pd.read_parquet(prior/'outputs/refresh_events.parquet')
    origins=operational_origins(events)
    if set(zip(origins.trace,origins.vm_id)) != set(zip(selected.trace,selected.vm_id.astype(str))):
        raise ValueError('development cohort mismatch')
    dependency=dict(fingerprint=old.fingerprint, refresh_events_sha256=file_sha256(prior/'outputs/refresh_events.parquet'),
                    output_manifest_sha256=file_sha256(prior/'output_manifest.json'))
    config=replace(old.config, policies=(), analysis=dict(study_version=VERSION,
        methods=['rf_profile','seasonal','bootstrap_selector'], managed_origin_dependency=dependency,
        origins='all-distinct-PP3-PP6-PP12-V3-budget-commits;PP6-and-drift-subgroups',
        selector=dict(folds=VALIDATION_FOLDS,grid='6h-from-bootstrap-start+72h',
            placement='evenly-indexed-eligible-origins', training='expanding-prefix-labels-fully-elapsed',
            thresholds='prefix-only-validation-full-bootstrap-streaming',
            rule='RF-iff-strictly-better-class-AND-strictly-lower-p95-MAE',fallback='none'),
        rf=dict(n_estimators=200,max_depth=20,max_features='sqrt',random_state=42,n_jobs=1),
        aggregation='paired-origin-then-equal-VM-macro;native-availability-separate',
        targets=['future_mean_class','future_p95'], purpose='exploratory-no-confirmatory-inference'))
    exp,env=prepare_experiment(repo,repo/'data/raw',config,old.dataset,old.cohort,{'model':42})
    if canonical_json(env.scientific)!=canonical_json(old.scientific_environment):
        raise ValueError('parent environment mismatch')
    names=['operational_origins','predictions','bootstrap_validation','selector_choices','availability',
           'costs','vm_metrics','macro_metrics','tier_metrics']
    start=time.perf_counter()
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=repo/'data/raw',purpose='pilot',
            required_outputs=[OutputSpec('outputs/'+n+'.parquet',n) for n in names]+[OutputSpec('outputs/summary.json','exploratory-disposition-evidence')]) as run:
        print(canonical_json(dict(run_path=str(run.path),fingerprint=exp.fingerprint)),flush=True)
        tasks=[(repo,e,origins[origins.trace.eq(e['trace']) & origins.vm_id.eq(str(e['vm_id']))]) for e in selected.to_dict('records')]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            answers=list(pool.map(run_vm,tasks))
        rows,validation,choices,availability,costs=[pd.DataFrame([r for a in answers for r in a[i]]) for i in range(5)]
        if len(choices)!=36 or len(validation)!=36*VALIDATION_FOLDS*2:
            raise ValueError('selector evidence incomplete')
        if len(availability)!=2*len(origins):
            raise ValueError('origin inventory incomplete')
        vm,macro,tiers,wins=summarize(rows)
        outputs=[origins,rows,validation,choices,availability,costs,vm,macro,tiers]
        for name,frame in zip(names,outputs):
            frame.to_parquet(run.path/'outputs'/f'{name}.parquet',index=False)
        summary=dict(purpose='pilot',source_commit=exp.source.commit,fingerprint=exp.fingerprint,
            run_id=run.manifest.run_id,cohort_sha256=old.cohort.sha256,dependency=dependency,
            origin_counts=origins.groupby('origin_group').size().to_dict(),
            availability_counts=availability.groupby('resource')[['truth_available','seasonal_available','rf_available','selector_available']].sum().reset_index().to_dict('records'),
            selector_counts=choices.groupby(['resource','selected_method']).size().reset_index(name='count').to_dict('records'),
            macro_vm=macro.to_dict('records'),wins_vs_seasonal=wins,
            wall_seconds=time.perf_counter()-start,no_confirmatory_outcomes=True,
            no_policy_or_residual_changes=True,selection_frozen_before_streaming=True,
            no_fallback=True,score_population='common origin availability; no effect-driven exclusions')
        write_json(run.path/'outputs/summary.json',summary);run.complete()
    assert check_cache(run.path,exp,'pilot').reusable
    print(canonical_json(dict(run_path=str(run.path),fingerprint=exp.fingerprint,
        output_manifest_sha256=read_json(run.path/'manifest.json')['output_manifest_sha256'])),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    args=parser.parse_args();execute(args.repo,args.workers)

if __name__=='__main__':
    main()
