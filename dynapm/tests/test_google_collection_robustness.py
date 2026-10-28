"""V4F synthetic statistics tests; never read real e/g performance outcomes."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import ast,subprocess
import numpy as np
import pandas as pd
import pytest
from dynapm.core.provenance import (fingerprint,read_json,file_sha256,prepare_experiment,
    CohortEntity,CohortManifest,ExperimentConfigProvenance)
from dynapm.core.run_store import RunSession,OutputSpec,write_json,check_cache
from dynapm.data.manifests import build_dataset_manifest
from dynapm.experiments import google_collection_robustness as cr
from dynapm.experiments.google_staged_design import frozen_design
from dynapm.experiments.google_replication import google_config
from dynapm.experiments.confirmatory_execution import ENDPOINT_COLUMNS

REPO=Path(__file__).resolve().parents[2]

@pytest.fixture(scope='module')
def spec():return cr.frozen_spec(REPO)


def fixture_data(spec,cell='e'):
    cohort={'entities':[dict(cell=cell,collection_id=cid,instance_index=idx) for cid,n in [(10,3),(20,1),(30,2)] for idx in range(n)]}
    rows=[]
    for j,member in enumerate(cohort['entities']):
        for k,method in enumerate(spec['methods']):
            rows.append(dict(**member,vm_id=f"{member['collection_id']}:{member['instance_index']}",method_id=method,run_status='ok',
                cpu_class_accuracy=.2+.02*j+.01*k,memory_class_accuracy=.5-.01*j+.015*k,
                cpu_p95_mae=.5+.03*j-.02*k,mem_p95_mae=.3+.02*j-.01*k,n_refresh_events=k*(j+2)))
    data=pd.DataFrame(rows);primary=[]
    for family,contrasts in spec['comparison_families'].items():
        for contrast in contrasts:
            for endpoint in spec['endpoints']:
                col=ENDPOINT_COLUMNS.get(endpoint,endpoint);wide=data.pivot(index='vm_id',columns='method_id',values=col)
                d=wide[contrast['treatment']]-wide[contrast['control']]
                primary.append(dict(family=family,**contrast,endpoint=endpoint,mean=float(d.mean()),median=float(d.median()),
                    mean_ci_low=float(d.mean()-.1),mean_ci_high=float(d.mean()+.1),median_ci_low=float(d.median()-.1),
                    median_ci_high=float(d.median()+.1),wilcoxon_p=1.,holm_p=1.,n_pairs=len(d)))
    return data,pd.DataFrame(primary),cohort


def test_structure_metadata_counts_and_order_invariance():
    cohort={'entities':[dict(cell='e',collection_id=c,instance_index=i) for c,n in [(1,4),(2,1),(3,1)] for i in range(n)]}
    s=cr.collection_structure(cohort,'e');other=deepcopy(cohort);other['entities'].reverse()
    assert s==cr.collection_structure(other,'e')
    assert s['n_entities']==6 and s['n_collections']==3 and s['singleton_collections']==2
    assert s['entities_per_collection']['median']==1 and s['top_shares']['1']==4/6
    assert s['hhi']==pytest.approx((4/6)**2+2*(1/6)**2)
    assert s['inverse_hhi']==pytest.approx(2.)
    assert s['collection_inventory_sha256']==fingerprint(s['collection_inventory'])


def test_secondary_freeze_does_not_change_primary(spec):
    design=frozen_design(REPO)
    assert spec['parent_staged_design_sha256']=='dd857518fd7471a2e7c8cce94f6922f52aa278b637ff38f2656db807c322d33d'
    assert spec['stage_b_primary_config_sha256']==google_config('g',design).sha256=='c1d79eda67ce751d09d139df6fb95f76b133a0e93a2386e9a25a952d78392b32'
    assert spec['comparison_families']==design['comparison_families']
    assert spec['bootstrap']['repetitions']==10000 and spec['bootstrap']['seed']==20251022
    assert spec['bootstrap']['confidence_level']==.95
    assert not spec['inference']['secondary_pvalues'] and not spec['inference']['secondary_holm']
    assert spec['scopes']['e'].startswith('POST_HOC') and spec['scopes']['g'].startswith('PROSPECTIVE')


def test_aggregation_complete_pairs_and_primary_values_unchanged(spec):
    data,primary,cohort=fixture_data(spec);before=data.copy(deep=True);p_before=primary.copy(deep=True)
    clusters,summary=cr.analyze_collections(data,primary,cohort,'e',spec)
    assert len(clusters)==90 and len(summary)==30 and summary.n_entities.eq(6).all() and summary.n_collections.eq(3).all()
    for row in summary.to_dict('records'):
        original=primary.loc[(primary[cr.KEYS]==pd.Series({k:row[k] for k in cr.KEYS})).all(axis=1)].iloc[0]
        for field in cr.PRIMARY_FIELDS:assert row['primary_entity_'+field]==original[field]
        assert row['n_collection_positive']+row['n_collection_zero']+row['n_collection_negative']==3
    pd.testing.assert_frame_equal(data,before);pd.testing.assert_frame_equal(primary,p_before)
    assert not any(c in summary.columns for c in ['secondary_pvalue','secondary_holm_p','statistically_distinguishable'])


def test_shuffle_determinism(spec):
    d,p,c=fixture_data(spec)
    a,b=cr.analyze_collections(d,p,c,'e',spec)
    x,y=cr.analyze_collections(d.sample(frac=1,random_state=7),p.sample(frac=1,random_state=8),{'entities':c['entities'][::-1]},'e',spec)
    pd.testing.assert_frame_equal(a,x);pd.testing.assert_frame_equal(b,y)


def test_whole_cluster_bootstrap_matches_literal_repeated_member_resampling(spec):
    means=np.array([-.2,.7,.1]);sizes=np.array([7,1,3]);params=spec['bootstrap']
    result=cr.bootstrap_collections(means,sizes,params);rng=np.random.Generator(np.random.PCG64(params['seed']))
    entity=[];collection=[];median=[]
    for _ in range(params['repetitions']):
        draw=rng.integers(0,3,size=3)
        members=np.concatenate([np.repeat(means[c],sizes[c]) for c in draw])
        entity.append(members.mean());collection.append(means[draw].mean());median.append(np.median(means[draw]))
    for name,values in [('entity_mean',entity),('collection_mean',collection),('collection_median_of_means',median)]:
        np.testing.assert_allclose([result[name+'_cluster_ci_low'],result[name+'_cluster_ci_high']],np.quantile(values,[.025,.975]))
    assert result['entity_mean']==pytest.approx(np.average(means,weights=sizes))


def test_weighted_entity_and_equal_collection_estimands_can_differ(spec):
    r=cr.bootstrap_collections([-1.,4.],[9,1],spec['bootstrap'])
    assert r['entity_mean']==-.5 and r['collection_mean']==1.5
    assert cr.direction_pair(r['entity_mean'],r['collection_mean'])=='discordant_or_one_zero'


def test_singleton_members_are_retained_and_one_cluster_ci_unavailable(spec):
    r=cr.bootstrap_collections([.3],[1],spec['bootstrap'])
    assert r['cluster_ci_status']=='INSUFFICIENT_COLLECTIONS' and r['entity_mean']==.3
    assert all(v is None for k,v in r.items() if '_cluster_ci_' in k)
    s=cr.bootstrap_collections([0,0],[1,1],spec['bootstrap'])
    assert s['cluster_ci_status']=='COMPUTED' and s['entity_mean_cluster_ci_low']==s['entity_mean_cluster_ci_high']==0


@pytest.mark.parametrize('means,sizes',[([],[]),([np.nan],[1]),([np.inf],[2]),([1],[0]),([1],[1.5]),([1,2],[1])])
def test_invalid_cluster_summaries_rejected(means,sizes,spec):
    with pytest.raises(ValueError):cr.bootstrap_collections(means,sizes,spec['bootstrap'])


@pytest.mark.parametrize('mutation',['missing_method','missing_entity','duplicate','wrong_collection','mixed_cell','nonfinite','failed','missing_contrast','wrong_primary_mean'])
def test_no_silent_exclusions_or_wrong_parent(mutation,spec):
    d,p,c=fixture_data(spec)
    if mutation=='missing_method':d=d.iloc[:-1]
    if mutation=='missing_entity':d=d[d.vm_id.ne('10:0')]
    if mutation=='duplicate':d=pd.concat([d,d.iloc[[0]]])
    if mutation=='wrong_collection':d.loc[d.vm_id.eq('10:0'),'collection_id']=99
    if mutation=='mixed_cell':d.loc[0,'cell']='g'
    if mutation=='nonfinite':d.loc[0,'cpu_p95_mae']=np.nan
    if mutation=='failed':d.loc[0,'run_status']='failed'
    if mutation=='missing_contrast':p=p.iloc[:-1]
    if mutation=='wrong_primary_mean':p.loc[0,'mean']=1e6
    with pytest.raises(ValueError):cr.analyze_collections(d,p,c,'e',spec)


def test_cluster_sign_consistency_zero_and_endpoint_direction(spec):
    d,p,c=fixture_data(spec);clusters,summary=cr.analyze_collections(d,p,c,'e',spec)
    costs=summary[summary.endpoint.eq('n_refresh_events')]
    assert costs.n_collection_positive.eq(3).all() and costs.fraction_collection_positive.eq(1).all()
    assert set(costs.entity_vs_collection_direction)=={'same_positive'}
    assert cr.direction_pair(0,0)=='same_zero' and cr.direction_pair(0,1)=='discordant_or_one_zero'
    # Exact zero: no epsilon, significance or practical-benefit reinterpretation.
    assert cr.direction_pair(1e-30,1)=='same_positive'


def test_cross_cell_synthesis_separate_and_scoped(spec):
    d,p,c=fixture_data(spec,'e');_,e=cr.analyze_collections(d,p,c,'e',spec)
    d,p,c=fixture_data(spec,'g');_,g=cr.analyze_collections(d,p,c,'g',spec)
    joined=cr.cross_cell_synthesis(e,g,spec)
    assert len(joined)==30 and not joined.pooled_inference.any()
    assert joined.entity_mean_g_minus_e.eq(0).all()
    with pytest.raises(ValueError):cr.cross_cell_synthesis(e,g.iloc[:-1],spec)
    bad=g.copy();bad['analysis_scope']='POST_HOC'
    with pytest.raises(ValueError):cr.cross_cell_synthesis(e,bad,spec)
    bad=g.copy();bad['spec_sha256']='different'
    with pytest.raises(ValueError):cr.cross_cell_synthesis(e,bad,spec)


def test_no_cloud_or_policy_calls_and_safe_cli(monkeypatch,capsys,spec):
    tree=ast.parse(Path(cr.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith(('google.cloud','dynapm.methods'))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ['query','create_read_session','read_rows','step']
    from dynapm.scripts import task31_google_collection_robustness as cli
    monkeypatch.setattr('sys.argv',['task31','--cell','g'])
    monkeypatch.setattr(cli,'run_secondary',lambda *args:pytest.fail('default must not analyze'))
    cli.main();assert 'SECONDARY_SPEC_VERIFIED_NO_ANALYSIS' in capsys.readouterr().out


def test_frozen_spec_rejects_param_or_source_mutation(monkeypatch,spec):
    original=cr.spec_document
    def changed(repo):
        d=original(repo);d['bootstrap']['seed']=7;return d
    monkeypatch.setattr(cr,'spec_document',changed)
    with pytest.raises(ValueError,match='spec_or_source_mismatch'):cr.frozen_spec(REPO)


def test_managed_secondary_on_synthetic_parent_only(tmp_path,monkeypatch,spec):
    # Fake, sealed primary summaries, generated analytically; no real Google input.
    data,primary,cohort=fixture_data(spec)
    repo=tmp_path/'repo';repo.mkdir();(repo/'.gitignore').write_text('results/\n')
    (repo/'source.py').write_text('fixture=True\n')
    for args in [('init','-b','dynapm'),('add','.'),('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')]:
        subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
    raw=tmp_path/'raw';(raw/'e').mkdir(parents=True)
    for e in cohort['entities']:(raw/'e'/f"{e['collection_id']}_{e['instance_index']}.csv").write_text('synthetic\n1\n')
    config=google_config('e',frozen_design(REPO));dataset=build_dataset_manifest(raw,dataset_id=config.data.dataset_id,source_name='synthetic',trace_names=('e',),schema_identity='synthetic')
    members=cr.cohort_members(cohort,'e')
    cm=CohortManifest(dataset.dataset_id,dataset.sha256,'synthetic',{},tuple(CohortEntity('e',e.vm_id,True,None,1) for e in members.itertuples()),'synthetic')
    exp,env=prepare_experiment(repo,raw,config,dataset,cm,{'statistics':20251022})
    specs=[OutputSpec('outputs/per_entity_results.parquet','synthetic-primary-results'),OutputSpec('outputs/family_inference.parquet','synthetic-primary-inference'),OutputSpec('outputs/design_binding.json','synthetic-design-binding')]
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=raw,purpose='claim',required_outputs=specs) as parent:
        data.to_parquet(parent.path/'outputs/per_entity_results.parquet',index=False)
        primary.to_parquet(parent.path/'outputs/family_inference.parquet',index=False)
        write_json(parent.path/'outputs/design_binding.json',dict(design_fingerprint=spec['parent_staged_design_sha256']))
        parent.complete()
    before={p.relative_to(parent.path).as_posix():file_sha256(p) for p in parent.path.rglob('*') if p.is_file()}
    monkeypatch.setattr(cr,'frozen_spec',lambda root:spec)
    design=frozen_design(REPO);monkeypatch.setattr(cr,'frozen_design',lambda root:design)
    out=cr.run_secondary(repo,parent.path,'e');m=read_json(out/'manifest.json')
    assert m['status']=='SUCCESS' and check_cache(out,cr.experiment_from_dict(m['experiment']),'claim').reusable
    summary=pd.read_parquet(out/'outputs/side_by_side_estimates.parquet')
    assert len(summary)==30 and summary.analysis_scope.eq('POST_HOC_SENSITIVITY_AFTER_STAGE_A').all()
    assert before=={p.relative_to(parent.path).as_posix():file_sha256(p) for p in parent.path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='matching_cell_primary_required'):cr.run_secondary(repo,parent.path,'g')
    assert not subprocess.check_output(['git','-C',str(repo),'status','--short'])


def test_yaml_and_schema_guards(tmp_path,monkeypatch,spec):
    path=tmp_path/'bad.yaml';path.write_text('changed: true\n')
    monkeypatch.setattr(cr,'SPEC_YAML',str(path))
    with pytest.raises(ValueError,match='yaml_mismatch'):cr.frozen_spec(REPO)
    d,p,c=fixture_data(spec);bad=deepcopy(spec);bad['schema_version']='unsupported'
    with pytest.raises(ValueError,match='unsupported_collection_schema'):cr.analyze_collections(d,p,c,'e',bad)


@pytest.mark.parametrize('column,value',[('cpu_class_accuracy',1.1),('memory_class_accuracy',-.1),('cpu_p95_mae',-.1),('n_refresh_events',1.5)])
def test_primary_endpoint_ranges_preserved(column,value,spec):
    d,p,c=fixture_data(spec);d[column]=d[column].astype(float);d.loc[0,column]=value
    with pytest.raises(ValueError,match='endpoint_range'):cr.analyze_collections(d,p,c,'e',spec)


def test_one_collection_keeps_points_and_serializes_null_cis(spec):
    from dynapm.core.provenance import canonical_json
    d,p,c=fixture_data(spec);old=sorted(d.vm_id.unique());mapping={key:i for i,key in enumerate(old)}
    d['instance_index']=d.vm_id.map(mapping);d['collection_id']=99;d['vm_id']=[f'99:{i}' for i in d.instance_index]
    c={'entities':[dict(cell='e',collection_id=99,instance_index=i) for i in range(len(old))]}
    collection,summary=cr.analyze_collections(d,p,c,'e',spec)
    assert len(collection)==30 and summary.n_collections.eq(1).all()
    assert summary.cluster_ci_status.eq('INSUFFICIENT_COLLECTIONS').all()
    assert summary.entity_mean_cluster_ci_low.isna().all()
    assert 'null' in canonical_json(summary.to_dict('records'))
