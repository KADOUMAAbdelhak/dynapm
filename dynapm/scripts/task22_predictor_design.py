"""Managed four-candidate development investigation; fixed 18 VMs/eight origins."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
import time
import numpy as np
import pandas as pd
from dynapm.core.provenance import SourceProvenance, experiment_from_dict, prepare_experiment,read_json,canonical_json
from dynapm.core.run_store import RunSession,OutputSpec,check_cache,write_json
from dynapm.core.predictor import VMPredictor,forecast_at_origin
from dynapm.core.discretization import classify_value
from dynapm.core.temporal import forecast_targets, history_valid
from dynapm.eval.replay import prepare_vm_inputs,CPU_T,MEM_T
from dynapm.experiments.pilot_design import guard_cohort
from dynapm.experiments.forecast_design import DirectHorizonRF,tree_state_bytes,DESIGN_VERSION
from dynapm.scripts.task21_predictor_diagnosis import choose_origins,LEADS

PREVIOUS=('d62c95d22722a7d42f43a61766bae0e7de1c31fcb8d02337b46f0e066f9dbd13/'
          '2026-10-21T144944.993961Z-d62c95d22722-bedfa37c')
METHODS=('rf_recursive','persistence','seasonal_naive_24h','rf_direct_joint')


class TimedRF(VMPredictor):
    def fit(self,frame):
        start=time.perf_counter();super().fit(frame)
        self.training_seconds=time.perf_counter()-start


def design_vm(args):
    repo,entity,expected_origins=args
    trace,vm=entity['trace'],str(entity['vm_id'])
    inputs=prepare_vm_inputs(trace,vm,repo_root=repo,predictor_factory=TimedRF,
        with_predictors=True,with_residuals=False)
    eligible=[t for t in inputs.ground_truth.index if t in inputs.frame.index and
        all(history_valid(inputs.frame[target],t) for target in (CPU_T,MEM_T))]
    origins=choose_origins(eligible)
    if list(origins)!=list(pd.DatetimeIndex(expected_origins)):raise ValueError('development origins changed')
    rows,metrics,costs=[],[],[]
    for resource,target,recursive,thresholds in zip(('cpu','memory'),(CPU_T,MEM_T),inputs.predictors,
            (inputs.cpu_thresholds,inputs.mem_thresholds)):
        direct=DirectHorizonRF(target)
        start=time.perf_counter();direct.fit(inputs.bootstrap);direct_fit=time.perf_counter()-start
        for method,model,train_s,n_train in (
            ('rf_recursive',recursive,recursive.training_seconds,recursive.training_diagnostics['valid_feature_rows']),
            ('rf_direct_joint',direct,direct_fit,direct.training_rows)):
            costs.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,
                'cost_kind':'training','seconds':train_s,'training_rows':n_train,
                'tree_array_bytes_lower_bound':tree_state_bytes(model)})
        for origin in origins:
            targets=forecast_targets(origin);series=inputs.frame[target];forecasts={}
            for method,model in [('rf_recursive',recursive),('rf_direct_joint',direct)]:
                start=time.perf_counter();pred=forecast_at_origin(model,series,origin)
                seconds=time.perf_counter()-start
                forecasts[method]=pred
                costs.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,
                    'cost_kind':'inference','origin':origin,'seconds':seconds})
            # Time each nonlearned forecast separately; no caching from the past diagnosis.
            for method in ('persistence','seasonal_naive_24h'):
                start=time.perf_counter()
                past=series.loc[series.index<=origin]
                pred=(pd.Series(float(past.loc[origin]),index=targets) if method=='persistence' else
                    pd.Series(past.reindex(targets-pd.Timedelta(days=1)).to_numpy(),index=targets))
                forecasts[method]=pred
                costs.append({'trace':trace,'vm_id':vm,'resource':resource,'method':method,
                    'cost_kind':'inference','origin':origin,'seconds':time.perf_counter()-start})
            actual=series.reindex(targets).to_numpy(dtype=float)
            common=np.isfinite(actual)
            for pred in forecasts.values():
                if not pred.index.equals(targets):raise ValueError('target mismatch')
                common &= np.isfinite(pred.to_numpy())
            if common.sum()<200:raise ValueError('insufficient common targets for comparison')
            for method,pred in forecasts.items():
                values=pred.to_numpy(dtype=float);err=values[common]-actual[common]
                correct=np.array([classify_value(p,thresholds)==classify_value(a,thresholds)
                                  for p,a in zip(values[common],actual[common])])
                metrics.append({'trace':trace,'vm_id':vm,'tier':entity['volatility_tier'],
                    'resource':resource,'origin':origin,'method':method,'paired_slots':int(common.sum()),
                    'available_forecast_slots':int(np.isfinite(values).sum()),
                    'mae':float(np.abs(err).mean()),'bias':float(err.mean()),
                    'p95_absolute_error':float(np.quantile(np.abs(err),.95)),
                    'point_class_correctness':float(correct.mean()),
                    'mean_class_correct':classify_value(float(values[common].mean()),thresholds)==classify_value(float(actual[common].mean()),thresholds),
                    'profile_p95_absolute_error':float(abs(np.quantile(values[common],.95)-np.quantile(actual[common],.95))),
                    'mean_adjacent_prediction_jump':float(np.nanmean(np.abs(np.diff(values)))),
                    'mean_adjacent_actual_jump':float(np.nanmean(np.abs(np.diff(actual))))})
                for i in range(288):
                    rows.append({'trace':trace,'vm_id':vm,'resource':resource,'origin':origin,
                        'target_time':targets[i],'lead':i+1,'method':method,
                        'prediction':float(values[i]) if np.isfinite(values[i]) else None,
                        'actual':float(actual[i]) if np.isfinite(actual[i]) else None,
                        'common_valid':bool(common[i]),
                        'error':float(values[i]-actual[i]) if common[i] else None,
                        'absolute_error':float(abs(values[i]-actual[i])) if common[i] else None,
                        'class_correct':bool(classify_value(values[i],thresholds)==classify_value(actual[i],thresholds)) if common[i] else None})
        del direct
    print(f'completed {trace}/{vm}',flush=True)
    return rows,metrics,costs


def execute(repo,workers=2):
    repo=Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:raise ValueError('clean committed source required')
    if workers not in (1,2):raise ValueError('at most two bounded VM workers')
    prior=repo/'results/runs'/PREVIOUS
    old=experiment_from_dict(read_json(prior/'manifest.json')['experiment'])
    if not check_cache(prior,old,'pilot').reusable:raise ValueError('invalid development diagnosis provenance')
    records=old.cohort.filtering_config['selection_records'];selected=pd.DataFrame(records);guard_cohort(selected)
    point_origins=pd.read_parquet(prior/'outputs/lead_errors.parquet')
    expected={(trace,str(vm)):g.origin.drop_duplicates().sort_values().tolist()
        for (trace,vm),g in point_origins.groupby(['trace','vm_id'])}
    config=replace(old.config,analysis={'design_version':DESIGN_VERSION,'methods':METHODS,
        'origin_rule':'same-eight-as-validated-v2.4','full_horizon_steps':288,'selected_leads':LEADS,
        'direct_rf':{'outputs':288,'n_estimators':200,'max_depth':20,'max_features':'sqrt',
            'random_state':42,'n_jobs':1,'labels':'complete-future-bootstrap-only'},
        'comparison':'common-actual-and-forecast-slots-all-four-methods',
        'selection_rule':'learned-candidate-must-beat-seasonal-full-MAE-both-resources-majority-VMs-and-no-worse-absolute-bias',
        'inference':'fixed-origin-no-feedback-except-current-recursive-control',
        'purpose':'development-forecast-quality-only-no-policy-selection-or-confirmatory-inference'})
    exp,env=prepare_experiment(repo,repo/'data/raw',config,old.dataset,old.cohort,{'model':42})
    names={'forecasts.parquet':'all-horizon-paired-fixed-origin-forecasts',
        'origin_metrics.parquet':'direct-forecast-quality-and-consistency',
        'costs.parquet':'same-run-training-and-inference-cost-observations',
        'lead_curves.parquet':'macro-vm-error-by-all-288-leads',
        'vm_metrics.parquet':'per-vm-forecast-errors',
        'summary.json':'exploratory-design-comparison'}
    started=time.perf_counter()
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=repo/'data/raw',purpose='pilot',
            required_outputs=[OutputSpec('outputs/'+n,role) for n,role in names.items()]) as run:
        print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint}),flush=True)
        tasks=[(repo,r,expected[(r['trace'],str(r['vm_id']))]) for r in records]
        with ProcessPoolExecutor(max_workers=workers) as pool:answers=list(pool.map(design_vm,tasks))
        points,metrics,costs=[pd.DataFrame([row for a in answers for row in a[i]]) for i in range(3)]
        for frame,name in [(points,'forecasts'),(metrics,'origin_metrics'),(costs,'costs')]:
            frame.to_parquet(run.path/'outputs'/f'{name}.parquet',index=False)
        keys=['trace','vm_id','resource','origin']
        if not metrics.groupby(keys).method.nunique().eq(4).all() or len(metrics)!=1152:raise ValueError('origin alignment failed')
        if not metrics.groupby(keys).paired_slots.nunique().eq(1).all():raise ValueError('target alignment failed')
        if not np.isfinite(metrics[['mae','bias','p95_absolute_error']].to_numpy()).all():raise ValueError('nonfinite metrics')
        vm=metrics.groupby(['resource','method','trace','vm_id'])[['mae','bias','p95_absolute_error','point_class_correctness','mean_class_correct','profile_p95_absolute_error','mean_adjacent_prediction_jump','mean_adjacent_actual_jump']].mean().reset_index()
        vm.to_parquet(run.path/'outputs/vm_metrics.parquet',index=False)
        leads=points[points.common_valid].groupby(['resource','method','lead','trace','vm_id']).agg(mae=('absolute_error','mean'),bias=('error','mean'),class_correctness=('class_correct','mean')).reset_index()
        curves=leads.groupby(['resource','method','lead'])[['mae','bias','class_correctness']].mean().reset_index()
        curves.to_parquet(run.path/'outputs/lead_curves.parquet',index=False)
        wins=[]
        for resource,g in vm.groupby('resource'):
            seasonal=g[g.method.eq('seasonal_naive_24h')].set_index(['trace','vm_id'])
            for method,h in g.groupby('method'):
                h=h.set_index(['trace','vm_id']);delta=h.mae-seasonal.mae
                wins.append({'resource':resource,'method':method,'wins_vs_seasonal':int(delta.lt(-1e-12).sum()),
                    'losses_vs_seasonal':int(delta.gt(1e-12).sum()),'ties_vs_seasonal':int(delta.abs().le(1e-12).sum())})
        summary={'purpose':'pilot','label':'EXPLORATORY DEVELOPMENT ONLY',
            'source_commit':exp.source.commit,'fingerprint':exp.fingerprint,'run_id':run.manifest.run_id,
            'cohort_sha256':old.cohort.sha256,'vm_count':18,'origins_per_vm':8,
            'wall_seconds':time.perf_counter()-started,'workers':workers,
            'identical_origins_and_common_targets':True,'methods':METHODS,
            'full_horizon_macro_vm':vm.groupby(['resource','method'])[['mae','bias','p95_absolute_error','point_class_correctness','mean_class_correct','profile_p95_absolute_error','mean_adjacent_prediction_jump','mean_adjacent_actual_jump']].mean().reset_index().to_dict('records'),
            'lead_summary':curves[curves.lead.isin(LEADS)].to_dict('records'),'vm_wins_vs_seasonal':wins,
            'cost_summary':costs.groupby(['resource','method','cost_kind']).seconds.agg(['mean','median','min','max']).reset_index().to_dict('records')}
        write_json(run.path/'outputs/summary.json',summary);run.complete()
    assert check_cache(run.path,exp,'pilot').reusable
    print(canonical_json({'run_path':str(run.path),'fingerprint':exp.fingerprint,
        'output_manifest_sha256':read_json(run.path/'manifest.json')['output_manifest_sha256']}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--workers',type=int,choices=(1,2),default=2)
    a=p.parse_args();execute(a.repo,a.workers)

if __name__=='__main__':main()
