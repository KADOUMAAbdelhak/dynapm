"""V4F secondary postprocessing; primary Google policies/statistics stay untouched."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from collections import Counter
from numbers import Integral
import numpy as np
import pandas as pd
from dynapm.core.provenance import (read_json,canonical_json,fingerprint,file_sha256,
    experiment_from_dict,prepare_experiment,SourceProvenance)
from dynapm.core.run_store import RunSession,OutputSpec,check_cache,write_json
from dynapm.experiments.google_staged_design import frozen_design
from dynapm.experiments.google_replication import google_config
from dynapm.experiments.confirmatory_design import emit_yaml
from dynapm.experiments.confirmatory_execution import ENDPOINT_COLUMNS

SCHEMA='google2019-collection-robustness-v1'
SPEC_PATH='configs/google2019_collection_robustness_v1.json'
SPEC_YAML='configs/google2019_collection_robustness_v1.yaml'
RUNTIME=('dynapm/experiments/google_collection_robustness.py',
         'dynapm/scripts/task31_google_collection_robustness.py')
KEYS=['family','treatment','control','endpoint']
PRIMARY_FIELDS=['mean','median','mean_ci_low','mean_ci_high','median_ci_low','median_ci_high',
                'wilcoxon_p','holm_p','n_pairs']


def spec_document(repo):
    repo=Path(repo);d=frozen_design(repo)
    return dict(schema_version=SCHEMA,role='SECONDARY_SENSITIVITY_NOT_PRIMARY',
        parent_staged_design_sha256=fingerprint(d),google_protocol_sha256=d['protocol']['protocol_fingerprint'],
        stage_b_primary_config_sha256=google_config('g',d).sha256,
        stage_b_spec_sha256=fingerprint(d['stages']['B']),cohort_rule_sha256=d['cohort_selection_rule_sha256'],
        methods=d['methods'],comparison_families=d['comparison_families'],
        endpoints=[*d['fidelity_endpoints'],d['primary_cost']],
        scopes=dict(e='POST_HOC_SENSITIVITY_AFTER_STAGE_A',g='PROSPECTIVE_SECONDARY_FROZEN_BEFORE_G_OUTCOMES'),
        clusters='(cell, collection_id); analyze exactly one cell at a time; retain singleton and all larger represented collections',
        inclusion='exact complete primary cohort; no minimum collection size, outcome exclusion, reweighting by exposure or backfill',
        estimands=dict(entity_mean='sum(n_c * mean_delta_c) / sum(n_c), same entity weighting as primary',
            entity_median='original primary median and original entity-bootstrap CI, displayed unchanged; no secondary entity-median CI',
            collection_mean='unweighted mean of within-collection entity paired means',
            collection_median_of_means='unweighted median of within-collection entity paired means',
            represented_population='represented collections and selected members only; not unseen entities/collections'),
        bootstrap=dict(repetitions=d['statistics']['bootstrap_repetitions'],seed=d['statistics']['bootstrap_seed'],
            confidence_level=d['statistics']['confidence_level'],method='percentile',
            sampling='draw C collection IDs uniformly with replacement; keep every selected member of each drawn collection, including multiplicity',
            within_collection_resampling=False,resample_size='C original represented collections',
            entity_mean_replicate='sum(n_drawn * mean_drawn) / sum(n_drawn); denominator can vary',
            collection_replicates='mean and median of the C drawn collection means, equal collection weight',
            ordering='collection_id ascending numerically; entity_id canonical string ascending; same PCG64 seeded draws for every contrast/endpoint',
            fewer_than_two_collections='retain point estimates and signs; CI=null, status=INSUFFICIENT_COLLECTIONS; never drop cohort or use entity bootstrap instead'),
        direction=dict(zero='exact zero, no epsilon/margin tuning',
            counts='unweighted positive/zero/negative collection-mean counts and fractions, all C including zero',
            agreement='fraction of collection means whose sign equals primary entity-mean sign; zero primary mean matches zero only',
            estimand_alignment='same_positive, same_negative, same_zero, discordant_or_one_zero',
            cost='raw more/same/fewer refresh directions; no automatic benefit label'),
        inference=dict(secondary_pvalues=False,secondary_holm=False,primary_holm_unchanged=True,
            practical_significance='NOT_DEFINED_AT_PROFILE_LEVEL',
            interpretation='nominal marginal cluster CIs and descriptive signs only; no significance/pass/fail upgrade of primary claims'),
        assumptions='collections treated as resampling units; between-collection/provider/month dependence and sparse membership remain limitations; inverse HHI is concentration, not inferential sample size',
        cross_cell=dict(separate_first=True,required_cells=['e','g'],no_naive_pooled_entities=True,no_favorable_cell_selection=True,
            report='all 30 fixed contrasts/endpoints: original primary + cluster-adjusted entity mean + equal-collection mean/median with each cell CI',
            direction='apply same_positive/same_negative/same_zero/discordant_or_one_zero separately to entity mean, collection mean and collection median-of-means',
            heterogeneity='g-minus-e point differences only; no pooled CI/pvalue/global superiority rule',
            shared_ids='report shared collection-ID count when g exists; no post-outcome exclusions or pooling'),
        provenance='separate managed derived generation; bind this spec, parent experiment/output manifest and cohort hashes; never overwrite parent results',
        scientific_runtime_sha256={p:file_sha256(repo/p) for p in RUNTIME})


def write_spec(repo):
    repo=Path(repo);d=spec_document(repo);write_json(repo/SPEC_PATH,d)
    (repo/SPEC_YAML).write_text('# V4F secondary supplement; frozen primary contract unchanged.\n'+emit_yaml(read_json(repo/SPEC_PATH)))
    return fingerprint(d)


def frozen_spec(repo):
    repo=Path(repo);d=read_json(repo/SPEC_PATH)
    if canonical_json(d)!=canonical_json(spec_document(repo)):raise ValueError('collection_spec_or_source_mismatch')
    if (repo/SPEC_YAML).read_text()!='# V4F secondary supplement; frozen primary contract unchanged.\n'+emit_yaml(d):
        raise ValueError('collection_spec_yaml_mismatch')
    return d


def cohort_members(cohort,cell):
    if cell not in ('e','g'):raise ValueError('explicit_cell_required')
    rows=[]
    for e in cohort['entities']:
        if 'collection_id' in e:
            c=e['cell'];cid=e['collection_id'];idx=e['instance_index']
        else:
            if not e['included']:raise ValueError('secondary_cannot_exclude_primary_members')
            c=e['trace'];parts=e['entity_id'].split(':')
            if len(parts)!=2:raise ValueError('invalid_entity_identity')
            cid,idx=map(int,parts)
            if e['entity_id']!=f'{cid}:{idx}':raise ValueError('noncanonical_entity_identity')
        if c!=cell or not isinstance(cid,Integral) or isinstance(cid,bool) or not isinstance(idx,Integral) or isinstance(idx,bool) or cid<0 or idx<0:
            raise ValueError('cohort_cell_or_identity_mismatch')
        rows.append(dict(cell=cell,collection_id=int(cid),instance_index=int(idx),vm_id=f'{cid}:{idx}'))
    out=pd.DataFrame(rows)
    if not 1<=len(out)<=1000 or out.duplicated(['cell','vm_id']).any():raise ValueError('invalid_or_unbounded_primary_cohort')
    return out.sort_values('vm_id',kind='stable').reset_index(drop=True)


def collection_structure(cohort,cell):
    """Identity-only metadata. Never accepts or reads a performance table."""
    members=cohort_members(cohort,cell)
    counts=members.groupby('collection_id',sort=True).size();a=counts.to_numpy(dtype=np.int64);n=int(a.sum())
    ranked=sorted(counts.items(),key=lambda x:(-x[1],x[0]));hhi=float(np.sum((a/n)**2))
    inventory=[dict(cell=cell,collection_id=int(cid),n_entities=int(k)) for cid,k in counts.items()]
    return dict(schema_version='google2019-collection-structure-v1',cell=cell,n_entities=n,n_collections=len(a),
        entities_per_collection=dict(min=int(a.min()),median=float(np.median(a)),mean=float(a.mean()),
            p75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.90)),p95=float(np.quantile(a,.95)),max=int(a.max())),
        size_histogram={str(k):int(v) for k,v in sorted(Counter(a.tolist()).items())},
        singleton_collections=int((a==1).sum()),multi_entity_collections=int((a>=2).sum()),
        collections_ge5=int((a>=5).sum()),collections_ge10=int((a>=10).sum()),
        top_shares={str(k):float(sum(x[1] for x in ranked[:k])/n) for k in (1,3,5,10,20)},
        top_collections=[dict(collection_id=int(cid),n_entities=int(k),entity_share=float(k/n)) for cid,k in ranked[:20]],
        hhi=hhi,inverse_hhi=1/hhi,concentration_is_not_inferential_sample_size=True,
        collection_inventory=inventory,collection_inventory_sha256=fingerprint(inventory))


def bootstrap_collections(means,sizes,bootstrap):
    """Whole-cluster resampling: retain cluster multiplicity, pairing and sizes."""
    means=np.asarray(means,dtype=float);sizes=np.asarray(sizes,dtype=float)
    if means.ndim!=1 or sizes.shape!=means.shape or not len(means) or not np.isfinite(means).all() or not np.isfinite(sizes).all() or np.any(sizes<1) or np.any(sizes!=np.floor(sizes)):
        raise ValueError('invalid_collection_summaries')
    c=len(means);b=bootstrap['repetitions'];seed=bootstrap['seed'];level=bootstrap['confidence_level']
    if type(b) is not int or b<1 or type(seed) is not int or not 0<level<1:raise ValueError('invalid_bootstrap_configuration')
    result=dict(entity_mean=float(np.average(means,weights=sizes)),collection_mean=float(means.mean()),
        collection_median_of_means=float(np.median(means)),cluster_ci_status='COMPUTED' if c>=2 else 'INSUFFICIENT_COLLECTIONS')
    names=['entity_mean','collection_mean','collection_median_of_means']
    if c<2:
        return {**result,**{f'{name}_cluster_ci_{side}':None for name in names for side in ('low','high')}}
    rng=np.random.Generator(np.random.PCG64(seed));estimates={k:[] for k in names}
    for start in range(0,b,256):
        draw=rng.integers(0,c,size=(min(256,b-start),c));values=means[draw];counts=sizes[draw]
        estimates['entity_mean'].extend(np.sum(values*counts,axis=1)/np.sum(counts,axis=1))
        estimates['collection_mean'].extend(values.mean(axis=1))
        estimates['collection_median_of_means'].extend(np.median(values,axis=1))
    alpha=(1-level)/2
    for name,values in estimates.items():
        low,high=np.quantile(values,[alpha,1-alpha],method='linear')
        result[f'{name}_cluster_ci_low']=float(low);result[f'{name}_cluster_ci_high']=float(high)
    return result


def direction_pair(a,b):
    a,b=np.sign(a),np.sign(b)
    return 'same_positive' if a==b==1 else 'same_negative' if a==b==-1 else 'same_zero' if a==b==0 else 'discordant_or_one_zero'


def _planned_keys(spec):
    return {(family,contrast['treatment'],contrast['control'],endpoint)
        for family,contrasts in spec['comparison_families'].items() for contrast in contrasts for endpoint in spec['endpoints']}


def analyze_collections(per_entity,primary_inference,cohort,cell,spec):
    """Pure compute API; real output execution must use run_secondary below."""
    if spec.get('schema_version')!=SCHEMA:raise ValueError('unsupported_collection_schema')
    members=cohort_members(cohort,cell);n=len(members);methods=set(spec['methods'])
    data=per_entity.copy()
    if set(data.cell)!={cell} or not data.run_status.eq('ok').all():raise ValueError('one_complete_cell_required')
    if data.duplicated(['vm_id','method_id']).any() or len(data)!=n*len(methods) or set(data.method_id)!=methods:
        raise ValueError('incomplete_or_duplicate_primary_matrix')
    actual=data[['cell','collection_id','instance_index','vm_id']].drop_duplicates().sort_values('vm_id').reset_index(drop=True)
    if canonical_json(actual.to_dict('records'))!=canonical_json(members.to_dict('records')):raise ValueError('primary_cohort_identity_mismatch')
    if not data.groupby('vm_id').method_id.nunique().eq(len(methods)).all():raise ValueError('missing_primary_method')
    columns=[ENDPOINT_COLUMNS.get(k,k) for k in spec['endpoints']]
    if not np.isfinite(data[columns].to_numpy(float)).all():raise ValueError('nonfinite_primary_endpoint_no_silent_exclusions')
    if not data[['cpu_class_accuracy','memory_class_accuracy']].ge(0).all().all() or not data[['cpu_class_accuracy','memory_class_accuracy']].le(1).all().all() or not data[['cpu_p95_mae','mem_p95_mae','n_refresh_events']].ge(0).all().all() or not np.equal(data.n_refresh_events,np.floor(data.n_refresh_events)).all():
        raise ValueError('invalid_primary_endpoint_range')
    primary=primary_inference.copy()
    if primary.duplicated(KEYS).any() or set(map(tuple,primary[KEYS].itertuples(index=False,name=None)))!=_planned_keys(spec):raise ValueError('primary_family_matrix_mismatch')
    if not primary.n_pairs.eq(n).all() or not np.isfinite(primary[PRIMARY_FIELDS].to_numpy(float)).all():raise ValueError('primary_inference_coverage_or_numeric_mismatch')
    primary=primary.set_index(KEYS);summaries=[];collections=[]
    for family,contrasts in spec['comparison_families'].items():
        for contrast in contrasts:
            treatment,control=contrast['treatment'],contrast['control']
            for endpoint in spec['endpoints']:
                column=ENDPOINT_COLUMNS.get(endpoint,endpoint)
                wide=data.pivot(index='vm_id',columns='method_id',values=column).sort_index()
                delta=wide[treatment]-wide[control]
                joined=members.set_index('vm_id').join(delta.rename('delta'),validate='one_to_one')
                rows=[]
                for cid,g in joined.groupby('collection_id',sort=True):
                    values=g.sort_index().delta.to_numpy(float)
                    row=dict(cell=cell,family=family,treatment=treatment,control=control,endpoint=endpoint,
                        collection_id=int(cid),n_entities=len(values),mean_delta=float(values.mean()),
                        n_entity_positive=int((values>0).sum()),n_entity_zero=int((values==0).sum()),n_entity_negative=int((values<0).sum()))
                    rows.append(row);collections.append(row)
                means=np.array([r['mean_delta'] for r in rows]);sizes=np.array([r['n_entities'] for r in rows])
                boot=bootstrap_collections(means,sizes,spec['bootstrap'])
                original=primary.loc[(family,treatment,control,endpoint)]
                if not np.isclose(original['mean'],delta.mean(),rtol=1e-12,atol=1e-12) or not np.isclose(original['median'],delta.median(),rtol=1e-12,atol=1e-12):raise ValueError('primary_point_estimate_mismatch')
                # Display original primary estimates byte-for-value, not recomputed alternatives.
                boot['entity_mean']=float(original['mean']);signs=np.sign(means);primary_sign=float(np.sign(original['mean']))
                summaries.append(dict(cell=cell,family=family,treatment=treatment,control=control,endpoint=endpoint,
                    analysis_role='SECONDARY',analysis_scope=spec['scopes'][cell],spec_sha256=fingerprint(spec),
                    n_entities=n,n_collections=len(rows),**boot,
                    **{'primary_entity_'+k:int(original[k]) if k=='n_pairs' else float(original[k]) for k in PRIMARY_FIELDS},
                    n_collection_positive=int((signs>0).sum()),n_collection_zero=int((signs==0).sum()),n_collection_negative=int((signs<0).sum()),
                    fraction_collection_positive=float((signs>0).mean()),fraction_collection_zero=float((signs==0).mean()),fraction_collection_negative=float((signs<0).mean()),
                    collection_sign_agreement_with_primary_mean=float((signs==primary_sign).mean()),
                    entity_vs_collection_direction=direction_pair(original['mean'],boot['collection_mean'])))
    return pd.DataFrame(collections),pd.DataFrame(summaries)


def cross_cell_synthesis(e,g,spec):
    for frame,cell in ((e,'e'),(g,'g')):
        if set(frame.cell)!={cell} or not frame.spec_sha256.eq(fingerprint(spec)).all() or not frame.analysis_scope.eq(spec['scopes'][cell]).all():raise ValueError('cell_or_secondary_spec_mismatch')
        if frame.duplicated(KEYS).any() or set(map(tuple,frame[KEYS].itertuples(index=False,name=None)))!=_planned_keys(spec):raise ValueError('cross_cell_contrast_matrix_mismatch')
    out=e.merge(g,on=KEYS,suffixes=('_e','_g'),validate='one_to_one')
    for name in ['entity_mean','collection_mean','collection_median_of_means']:
        out[name+'_cross_cell_direction']=[direction_pair(a,b) for a,b in zip(out[name+'_e'],out[name+'_g'])]
        out[name+'_g_minus_e']=out[name+'_g']-out[name+'_e']
    return out.assign(pooled_inference=False)


def run_secondary(repo,primary_path,cell):
    """Separate managed read-only derivation; never runs policies or changes parent."""
    repo=Path(repo).resolve();parent=Path(primary_path).resolve();spec=frozen_spec(repo)
    if SourceProvenance.capture(repo).dirty:raise ValueError('clean_committed_secondary_source_required')
    manifest=read_json(parent/'manifest.json');original=experiment_from_dict(manifest['experiment'])
    if original.config.data.dataset_id!=f'google_clusterdata_2019_{cell}' or manifest['purpose']!='claim' or not manifest['claim_eligible']:
        raise ValueError('canonical_matching_cell_primary_required')
    decision=check_cache(parent,original,'claim')
    if not decision.reusable:raise ValueError('invalid_primary:'+','.join(decision.reasons))
    base=google_config(cell,frozen_design(repo))
    if (canonical_json(replace(original.config,preprocessing=base.preprocessing))!=canonical_json(base) or
        any(canonical_json(original.config.preprocessing.get(k))!=canonical_json(v) for k,v in base.preprocessing.items())):
        raise ValueError('primary_execution_contract_mismatch')
    binding=read_json(parent/'outputs/design_binding.json')
    if binding['design_fingerprint']!=spec['parent_staged_design_sha256']:raise ValueError('unsupported_primary_staged_design')
    members=read_json(parent/'cohort_manifest.json')
    parent_hashes={p:file_sha256(parent/p) for p in ['manifest.json','output_manifest.json','cohort_manifest.json',
        'outputs/per_entity_results.parquet','outputs/family_inference.parquet']}
    config=replace(original.config,analysis={**original.config.analysis,'collection_robustness':dict(
        spec_sha256=fingerprint(spec),spec=spec,parent_experiment_fingerprint=original.fingerprint,
        parent_hashes=parent_hashes,analysis_scope=spec['scopes'][cell],role='SECONDARY_NOT_PRIMARY')})
    dataset_root=Path(manifest['execution_locations']['dataset_root'])
    exp,env=prepare_experiment(repo,dataset_root,config,original.dataset,original.cohort,{'collection_bootstrap':spec['bootstrap']['seed']})
    specs=[OutputSpec('outputs/collection_effects.parquet','within-collection-paired-means'),
        OutputSpec('outputs/side_by_side_estimates.parquet','unchanged-primary-and-secondary-collection-estimates'),
        OutputSpec('outputs/secondary_design.json','frozen-secondary-spec-and-parent-binding'),
        OutputSpec('outputs/diagnostics.json','secondary-coverage-and-nonreplacement-boundary')]
    with RunSession(repo/'results/google2019_collection_robustness',exp,env,repo=repo,dataset_root=dataset_root,purpose='claim',required_outputs=specs) as run:
        collection,summary=analyze_collections(pd.read_parquet(parent/'outputs/per_entity_results.parquet'),
            pd.read_parquet(parent/'outputs/family_inference.parquet'),members,cell,spec)
        collection.to_parquet(run.path/'outputs/collection_effects.parquet',index=False,compression='zstd')
        summary.to_parquet(run.path/'outputs/side_by_side_estimates.parquet',index=False,compression='zstd')
        write_json(run.path/'outputs/secondary_design.json',dict(spec=spec,parent_hashes=parent_hashes,parent_run_id=manifest['run_id']))
        write_json(run.path/'outputs/diagnostics.json',dict(cell=cell,scope=spec['scopes'][cell],role='SECONDARY',
            n_entities=len(cohort_members(members,cell)),n_collections=int(summary.n_collections.iloc[0]),
            comparisons=len(summary),primary_changed=False,secondary_pvalues=False,query_bytes=0))
        if frozen_spec(repo)!=spec or any(file_sha256(parent/p)!=sha for p,sha in parent_hashes.items()):raise ValueError('secondary_spec_or_parent_changed_during_run')
        if not check_cache(parent,original,'claim').reusable:raise ValueError('parent_integrity_changed')
        run.complete();return run.path
