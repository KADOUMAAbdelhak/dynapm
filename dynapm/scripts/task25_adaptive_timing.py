"""Managed fixed-18 development comparison: same content, timing differences."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import time
import numpy as np
import pandas as pd
from dynapm.core.provenance import (SourceProvenance, experiment_from_dict,prepare_experiment,
    read_json,canonical_json)
from dynapm.core.run_store import RunSession, OutputSpec,check_cache,write_json
from dynapm.experiments.pilot_design import guard_cohort
from dynapm.experiments.adaptive_timing import study_config,validate_config,run_vm,METHODS
PARENT = ('6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/'
          '2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe')

FIELDS=['cpu_class_accuracy','memory_class_accuracy','cpu_p95_mae','mem_p95_mae',
        'cpu_p95_bias','mem_p95_bias','n_refresh_events','n_periodic_refreshes',
        'n_drift_refreshes','n_budget_extra_refreshes','n_field_writes','n_field_value_changes',
        'profile_age_mean_hours','profile_age_p95_hours']


def analyze(rows):
    deltas=[]
    for (trace,vm),g in rows.groupby(['trace','vm_id']):
        indexed=g.set_index('method_id');adaptive=indexed.loc['adaptive_residual']
        for ref in ['budget_matched','pw_6h']:
            baseline=indexed.loc[ref]
            deltas.append(dict(trace=trace,vm_id=vm,tier=adaptive.tier,reference=ref,
                **{name:float(adaptive[name]-baseline[name]) for name in FIELDS}))
    deltas=pd.DataFrame(deltas)
    effects=[]
    for reference,g in deltas.groupby('reference'):
        for name in FIELDS:
            x=g[name].to_numpy(float)
            effects.append(dict(reference=reference,metric=name,mean=float(x.mean()),
                median=float(np.median(x)),minimum=float(x.min()),maximum=float(x.max()),
                positive_delta_count=int((x>1e-12).sum()),
                negative_delta_count=int((x< -1e-12).sum()),
                ties=int((np.abs(x)<=1e-12).sum())))
    return deltas,effects


def execute(repo,workers=2):
    repo=Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:raise ValueError('clean committed source required')
    parent=repo/'results/runs'/PARENT
    old=experiment_from_dict(read_json(parent/'manifest.json')['experiment'])
    if not check_cache(parent,old,'pilot').reusable:raise ValueError('invalid managed cohort provenance')
    selected=pd.DataFrame(old.cohort.filtering_config['selection_records']);guard_cohort(selected)
    expected={'Materna-Trace-1':{'374','213','96','64','143','76'},
              'Materna-Trace-2':{'396','207','388','398','516','11'},
              'Materna-Trace-3':{'212','151','83','133','224','127'}}
    if {t:set(g.vm_id.astype(str)) for t,g in selected.groupby('trace')}!=expected:
        raise ValueError('only the fixed 18 development VMs may execute')
    config=study_config(old.config);validate_config(config)
    exp,env=prepare_experiment(repo,repo/'data/raw',config,old.dataset,old.cohort,{'model':42})
    outputs=['cohort.parquet','per_vm_results.parquet','refresh_events.parquet','evaluation_records.parquet',
        'budget_schedule.parquet','paired_effects.parquet','tier_metrics.parquet','diagnostics.json','summary.json']
    start=time.perf_counter()
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=repo/'data/raw',purpose='pilot',
        required_outputs=[OutputSpec('outputs/'+n,'exploratory-window-timing-'+n.split('.')[0]) for n in outputs]) as run:
        print(canonical_json(dict(run_path=str(run.path),fingerprint=exp.fingerprint)),flush=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            answers=list(pool.map(run_vm,[(repo,e,config) for e in selected.to_dict('records')]))
        rows,events,records,schedule=[pd.DataFrame([r for a in answers for r in a[i]]) for i in range(4)]
        diagnostics=[a[4] for a in answers]
        if len(rows)!=54 or not rows.groupby(['trace','vm_id']).method_id.nunique().eq(3).all():
            raise ValueError('exact 54 completed evaluations required')
        if not np.isfinite(rows[FIELDS].to_numpy(float)).all():raise ValueError('nonfinite metrics')
        deltas,effects=analyze(rows)
        tiers=rows.groupby(['tier','method_id'])[FIELDS].mean().reset_index()
        for name,frame in [('cohort',selected),('per_vm_results',rows),('refresh_events',events),
            ('evaluation_records',records),('budget_schedule',schedule),('paired_effects',deltas),('tier_metrics',tiers)]:
            frame.to_parquet(run.path/'outputs'/f'{name}.parquet',index=False)
        write_json(run.path/'outputs/diagnostics.json',diagnostics)
        summary=dict(purpose='pilot',source_commit=exp.source.commit,fingerprint=exp.fingerprint,
            run_id=run.manifest.run_id,cohort_sha256=old.cohort.sha256,methods=METHODS,
            attempted=54,completed=54,wall_seconds=time.perf_counter()-start,
            macro_vm=rows.groupby('method_id')[FIELDS].mean().reset_index().to_dict('records'),
            descriptive_paired_effects=effects,confirmed_equal_budgets=18,confirmed_identical_periodic_bases=18,
            confirmed_content_function='paired-observation-window-24h-v1',recursive_forecast_calls=0,
            numeric_causal_failures=0,no_confirmatory_outcomes=True,no_tuning=True,
            decision_scope='architectural exploratory disposition; no retrospective meaningful-margin or inference')
        write_json(run.path/'outputs/summary.json',summary);run.complete()
    assert check_cache(run.path,exp,'pilot').reusable
    print(canonical_json(dict(run_path=str(run.path),fingerprint=exp.fingerprint,
        output_manifest_sha256=read_json(run.path/'manifest.json')['output_manifest_sha256'])),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    args=parser.parse_args();execute(args.repo,args.workers)

if __name__=='__main__':main()
