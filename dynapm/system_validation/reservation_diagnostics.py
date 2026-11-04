"""Bounded V7C.13 transport adapter; engineering only; frozen v2 model unchanged."""
from pathlib import Path
import os,sys,json,time,uuid,subprocess,tempfile,threading,concurrent.futures,traceback,shutil
from urllib.request import urlopen
from collections import Counter
from copy import deepcopy
from dynapm.core.provenance import canonical_json,file_sha256,fingerprint,utc_now,read_json
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.reservation_protocol import Target,ActuationLedger,read_protocol,reservation_resources,enforcement_check,application_window,resources_match
from dynapm.system_validation.neutral_characterization import qualification,ARTIFACT,QUALIFICATION,initialize_profile
from dynapm.system_validation.shared_bootstrap import StartupEvidence
from dynapm.system_validation.host_power import power_state,ManagedPowerGuard
from dynapm.system_validation.smoke import Commands,Kube,environment,guard_local_endpoint,guard_local_api,free_port,wait_http,http
from dynapm.system_validation.calibration_runner import require_isolated_engine,local_host_diagnostics
from dynapm.system_validation.clock_observations import ObservationClock,receive_observation,validate_clock_evidence
from dynapm.system_validation.timing_probes import distribution
from dynapm.system_validation.receipt_derivation import _inventory
REPO=Path('/Users/fgtek002/dynapm');HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
MODE=sys.argv[1] if len(sys.argv)>1 else 'external_only'
assert MODE in ('external_only','application_exec')
from dynapm.system_validation.outcome_taxonomy import OutcomeLedger,observation_window,control_enforcement,SCHEMA as TAXONOMY
# Explicit engineering stimuli, never policy outcomes or comparative exposures.
CASES=[('cpu_down',250,512),('cpu_up',1000,512),('memory_down',1000,64),('memory_up',1000,256),('simultaneous',500,128),('noop',500,128),('queue_inflight',1000,512),('cycle_down_1',100,64),('cycle_up_1',1000,512),('cycle_down_2',100,64),('cycle_up_2',1000,512),('cycle_down_3',100,64),('cycle_up_3',1000,512),('final_noop',1000,512)]
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(canonical_json(v))
def append(p,v):
 with p.open('a') as f:f.write(canonical_json(v)+'\n');f.flush()
def source_clean():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==HEAD
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True).strip()
def main():
 source_clean();design=frozen_spec(REPO);protocol=read_protocol(REPO);artifact,q=qualification(REPO);power_state()
 assert shutil.disk_usage(REPO).free>20*2**30
 endpoint=os.environ.get('DOCKER_HOST') or subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip();guard_local_endpoint(endpoint)
 runid=utc_now().replace(':','').replace('.','-')+'-'+uuid.uuid4().hex[:8]
 root=REPO/'results/resource_semantics/v7c13'/runid;out=root/'outputs';logs=root/'logs'
 root.mkdir(parents=True,exist_ok=False);out.mkdir();logs.mkdir()
 script=root/'execution.py';shutil.copyfile(__file__,script)
 protected={str(p.relative_to(REPO)):file_sha256(p) for base in ['configs','results/shared_bootstrap','results/neutral_characterization'] for p in (REPO/base).rglob('*') if p.is_file() and not p.is_symlink()}
 write(root/'protected-before.json',protected)
 config=dict(schema_version='v7c13-bounded-reservation-verification-v1',taxonomy=TAXONOMY,diagnostic_mode=MODE,taxonomy_sha256=file_sha256(REPO/'dynapm/system_validation/outcome_taxonomy.py'),node_poll_seconds=1,node_max_gap_seconds=10,first_low_seconds=45,later_low_seconds=15,source_commit=HEAD,adapter_sha256=file_sha256(script),protocol_sha256=file_sha256(REPO/'configs/system_resource_actuation_v2.json'),artifact_sha256=ARTIFACT,qualification_sha256=QUALIFICATION,cases=CASES,max_active_seconds=300,watchdog_seconds=60,physical_bucket_seconds=300,comparative=False,claim_generating=False,statistically_settled=None)
 fp=fingerprint(config);context=dict(run_id=runid,source_commit=HEAD,experiment_fingerprint=fp)
 write(root/'manifest.json',dict(**context,config=config,status='RUNNING',started_at=utc_now()))
 print(canonical_json(dict(stage='PREFLIGHT',run_id=runid,fingerprint=fp,path=str(root))),flush=True)
 processes=[];handles=[];created=False;cluster=design['kubernetes']['cluster']+'-reservation-'+uuid.uuid4().hex[:8]
 stop=threading.Event();gen=None;clock=None;ledger=OutcomeLedger();timings=[];operation_results=[];failed=None;guard=None
 request_lock=threading.Lock();records=[];inflight={};sent_ids=set();load_errors=[];load_started_ns=None;node_binding={};sampler_stop=threading.Event();sampler=None;sampler_errors=[];diagnostics=[];diag_threads=[]
 with tempfile.TemporaryDirectory(prefix='dynapm-reservation-private-') as tmp:
  private=Path(tmp);private.chmod(0o700);dc=private/'docker';dc.mkdir();write(dc/'config.json',{'auths':{}})
  env={**os.environ,'DOCKER_HOST':endpoint,'DOCKER_CONFIG':str(dc),'KUBECONFIG':str(private/'kubeconfig'),'PATH':str(REPO/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1'}
  commands=Commands(env,REPO);kube=Kube(commands,private/'kubeconfig',cluster,design)
  def spawn(args,name):
   h=(logs/name).open('a');handles.append(h);p=subprocess.Popen(args,env=env,cwd=REPO,stdout=h,stderr=subprocess.STDOUT);processes.append(p);return p
  def collect():
   guard.raise_if_failed();begin=time.monotonic_ns();e=receive_observation(app_url+'/clock-observation')
   with (out/'telemetry.jsonl').open('a') as f:s=clock.accept(e,f)
   timings.append(dict(kind='telemetry_seconds',value=(time.monotonic_ns()-begin)/1e9));return s
  def cg_read():
   if not node_binding:
    pod=kube.pod();cs=next(c for c in pod['status']['containerStatuses'] if c['name']=='workload');cid=cs['containerID'].split('://')[1];node=pod['spec']['nodeName']
    inspect=json.loads(commands.run(['docker','exec',node,'crictl','inspect',cid],timeout=10));pid=str(inspect['info']['pid']);assert pid.isdigit()
    group=commands.run(['docker','exec',node,'cat','/proc/'+pid+'/cgroup'],timeout=10).strip().split('::')[1]
    import re
    assert re.fullmatch(r'/[a-zA-Z0-9_./:-]+',group)
    node_binding.update(node=node,container_id=cid,pid=pid,cgroup='/sys/fs/cgroup'+group)
    write(out/'node_binding.json',node_binding)
   shell='for name in cpu.max cpu.weight cpu.stat memory.max memory.current memory.stat memory.events memory.min memory.low memory.swap.max memory.swap.current; do echo FILE:$name; cat "$1/$name"; done; echo FILE:uptime; cat /proc/uptime; echo FILE:boot; cat /proc/sys/kernel/random/boot_id'
   start=time.monotonic_ns();raw=commands.run(['docker','exec',node_binding['node'],'sh','-c',shell,'reader',node_binding['cgroup']],timeout=10);end=time.monotonic_ns()
   values={};key=None
   for line in raw.splitlines():
    if line.startswith('FILE:'):key=line[5:];values[key]=''
    else:values[key]+=line+'\n'
   values={k:v.strip() for k,v in values.items()}
   with request_lock:backlog=len(inflight)
   v=dict(start_monotonic_ns=start,end_monotonic_ns=end,values=values,client_inflight=backlog,binding=node_binding)
   append(out/'cgroup_observations.jsonl',v);return v
  def observation(target,generation,ack_ns):
   guard.raise_if_failed()
   if sampler_errors:raise ValueError('lost_control_telemetry:'+str(sampler_errors))
   start=time.monotonic_ns();p=kube.pod();receipt=time.monotonic_ns();node=cg_read();now=time.monotonic_ns()
   check=control_enforcement(p,node,target,pod_uid=uid,generation=generation,ack_ns=ack_ns,pod_received_ns=receipt,now_ns=now)
   append(out/'pod_observations.jsonl',dict(start_monotonic_ns=start,receipt_monotonic_ns=receipt,pod=p,node=node,target=vars(target),check=check))
   return check,p,node
  def sample_loop():
   previous=None;boot=None
   try:
    while not sampler_stop.is_set():
     sample=cg_read();now=sample['end_monotonic_ns']
     if previous is not None and now-previous>10*10**9:raise ValueError('independent_node_telemetry_gap')
     if boot is not None and sample['values']['boot']!=boot:raise ValueError('node_boot_discontinuity')
     previous=now;boot=sample['values']['boot']
     sampler_stop.wait(1)
   except Exception as ex:sampler_errors.append(repr(ex))
  def diagnostic(index):
   if index:time.sleep(5)
   start=time.monotonic_ns()
   try:
    code="import json,pathlib; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({n:(p/n).read_text().strip() for n in ['cpu.max','cpu.stat','memory.current','memory.max','memory.events']}))"
    value=json.loads(kube.call(['exec','application','-c','workload','--','python','-c',code],timeout=30))
    row=dict(index=index,start_monotonic_ns=start,end_monotonic_ns=time.monotonic_ns(),success=True,value=value)
   except Exception as ex:row=dict(index=index,start_monotonic_ns=start,end_monotonic_ns=time.monotonic_ns(),success=False,error=repr(ex),latency_seconds=None,category='CONTROL_PLANE_DIAGNOSTIC_FAILURE')
   diagnostics.append(row);append(out/'application_diagnostics.jsonl',row)
  try:
   require_isolated_engine(commands);details=environment(commands,design)
   expected=read_json(artifact/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']['image_ids']
   details['image_ids']={}
   for image in [design['kubernetes'][k] for k in ['application_image','prometheus_local_image','node_image']]:
    val=json.loads(commands.run(['docker','image','inspect',image]))[0]['Id'];details['image_ids'][image]=val
    if image in expected:assert val==expected[image],'qualified_image_changed'
   write(out/'host_before.json',local_host_diagnostics())
   with ManagedPowerGuard(root,context) as guard:
    try:
     created=True;commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(private/'kubeconfig'),'--wait','120s'],log=logs/'kind.log',timeout=300)
     guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
     details['version']=json.loads(kube.call(['version','-o','json']));assert details['version']['serverVersion']['gitVersion']=='v1.35.8'
     details['nodes']=json.loads(kube.call(['get','nodes','-o','json']));details['kubelet_config']={}
     for node in (cluster+'-control-plane',cluster+'-worker'):
      conf=commands.run(['docker','exec',node,'cat','/var/lib/kubelet/config.yaml']);details['kubelet_config'][node]=conf
      assert 'MemoryQoS: true' not in conf,'MemoryQoS_must_be_off'
     for image in [design['kubernetes'][k] for k in ['application_image','prometheus_local_image']]:commands.run(['kind','load','docker-image',image,'--name',cluster],log=logs/'kind.log')
     objects=reservation_resources(design);write(out/'resources.json',objects);kube.call(['apply','-f',str(out/'resources.json')],log=logs/'kind.log')
     kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],log=logs/'kind.log',timeout=150)
     write(out/'runtime_environment.json',details);guard.raise_if_failed()
     app_port,profile_port=free_port(),free_port();app_url=f'http://127.0.0.1:{app_port}';profile_url=f'http://127.0.0.1:{profile_port}'
     spawn(['kubectl','--kubeconfig',str(private/'kubeconfig'),'--context','kind-'+cluster,'-n',design['kubernetes']['namespace'],'port-forward','service/application',f'{app_port}:8080','--address','127.0.0.1'],'portforward.log');wait_http(app_url+'/healthz')
     clock=ObservationClock(root,context);sample=collect();pod=kube.pod();uid=pod['metadata']['uid'];instance=sample['instance_id']
     initial_cg=cg_read()['values'];assert initial_cg['memory.max']==str(1024*2**20) and initial_cg['memory.swap.max']=='0' and initial_cg['memory.swap.current']=='0'
     assert initial_cg['memory.min']=='0' and initial_cg['memory.low']=='0','unexpected_memory_protection'
     plan=dict(repo=str(REPO),design=design,**context);write(out/'plan.json',plan)
     spawn([sys.executable,'-u','-m','dynapm.system_validation.neutral_characterization','worker','profile','--plan',str(out/'plan.json'),'--root',str(root),'--port',str(profile_port)],'profile.log');wait_http(profile_url+'/healthz')
     h=http(profile_url+'/healthz');startup=StartupEvidence(uuid.uuid4().hex,uid,instance,h['profile_instance_id'],uuid.uuid4().hex,uuid.uuid4().hex,0,0,0,False)
     init=initialize_profile(profile_url+'/initialize',dict(profile_instance_id=h['profile_instance_id'],startup=vars(startup)));assert init['snapshot']['runtime_refresh_count']==0 if 'runtime_refresh_count' in init['snapshot'] else True
     rate=design['scenarios']['stable']['rps'];work=design['scenarios']['stable']['memory_mib'];sem=threading.BoundedSemaphore(design['workload']['max_concurrency'])
     def send(i):
      with request_lock:
       sent=time.monotonic_ns();inflight[i]=sent;sent_ids.add(i)
       append(out/'request_registry.jsonl',dict(event='STARTED',request_id=i,monotonic_ns=sent))
      try:
       with urlopen(app_url+f"/work?iterations={design['workload']['iterations']}&memory_mib={work}&seed={design['workload']['seed']}",timeout=design['workload']['timeout_seconds']) as response:
        body=json.loads(response.read());complete=time.monotonic_ns();status=response.status
       verified=body['iterations']==design['workload']['iterations'] and body['memory_mib']==work
       row=dict(request_id=i,sent_monotonic_ns=sent,completed_monotonic_ns=complete,success=status==200 and verified,work_verified=verified,response=body)
      except Exception as ex:row=dict(request_id=i,sent_monotonic_ns=sent,completed_monotonic_ns=time.monotonic_ns(),success=False,work_verified=False,error=repr(ex))
      with request_lock:
       records.append(row);append(out/'requests.jsonl',row);inflight.pop(i);append(out/'request_registry.jsonl',dict(event='COMPLETED',request_id=i,monotonic_ns=row['completed_monotonic_ns']))
      sem.release()
     def generator():
      nonlocal load_started_ns
      load_started_ns=time.monotonic_ns()
      try:
       with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        i=0
        while not stop.is_set() and time.monotonic_ns()-load_started_ns<300*10**9:
         if stop.wait(max(0,(load_started_ns+i*10**9/rate-time.monotonic_ns())/1e9)):break
         if sem.acquire(blocking=False):pool.submit(send,i)
         else:raise ValueError('request_generator_capacity_drop')
         i+=1
      except Exception as ex:load_errors.append(repr(ex))
     gen=threading.Thread(target=generator,name='fixed-rps-load');gen.start();sampler=threading.Thread(target=sample_loop,name='independent-node-observer');sampler.start();time.sleep(3)
     # All decisions remain explicit actuator stimuli. A single PW6 profile is initialized from block1.
     def execute(case,target,already_active=False):
      if time.monotonic_ns()-load_started_ns>270*10**9:raise ValueError('bounded_240s_active_limit')
      assert not load_errors
      if not already_active:assert ledger.intend(case,target)==target
      begin=ledger.active['issued_ns'];p=kube.pod();before=next(c['resources'] for c in p['spec']['containers'] if c['name']=='workload')
      append(out/'recommendations.jsonl',dict(decision_id=case,target=vars(target),role='ENGINEERING_STIMULUS_NOT_TREATMENT_OUTCOME',profile_recommendation_recorded_separately=True))
      if resources_match(before,target):
       check,_,_=observation(target,p['metadata']['generation'],begin);assert check['complete'];ledger.no_op(check);ack_ns=begin;no_op=True
      else:
       payload=ledger.patch(p);submitted=ledger.active['submitted_ns'];api_started=threading.Event()
       def patch():
        args=['kubectl','--kubeconfig',str(private/'kubeconfig'),'--context','kind-'+cluster,'-n',design['kubernetes']['namespace'],'--as','system:serviceaccount:'+design['kubernetes']['namespace']+':profile-consumer','patch','pod','application','--subresource=resize','--type=strategic','-p',canonical_json(payload),'-o','json']
        proc=subprocess.Popen(args,env=env,cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);api_started.set()
        try:stdout,stderr=proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:proc.kill();proc.communicate();raise ValueError('patch_ack_unknown_censored')
        receipt=time.monotonic_ns()
        if proc.returncode:raise ValueError('patch_explicit_rejection:'+stderr)
        return json.loads(stdout),receipt
       with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(patch);assert api_started.wait(5)
        if case=='queue_inflight':
         assert ledger.intend('queued_stale',Target(250,128)) is None
         assert ledger.intend('queued_latest',Target(500,256)) is None
         queued_at=time.monotonic_ns()
        ack,ack_ns=future.result(timeout=61)
       if case=='queue_inflight':assert queued_at<ack_ns,'queued_opportunity_must_precede_physical_ack_receipt'
       append(out/'patches.jsonl',dict(decision_id=case,payload=payload,submitted_monotonic_ns=submitted,ack_receipt_monotonic_ns=ack_ns,ack=ack))
       ledger.acknowledged(ack['metadata']['generation']);no_op=False
       while True:
        if ledger.watchdog():raise ValueError('censored_actuation')
        check,p,s=observation(target,ack['metadata']['generation'],ack_ns)
        if ledger.observe(check):break
        if check['resize_conditions']:ledger.deferred(check)
        time.sleep(.15)
       enf=ledger.active['enforced_ns'];timings.extend([dict(kind='patch_ack_seconds',value=(ack_ns-submitted)/1e9),dict(kind='ack_to_enforcement_seconds',value=(enf-ack_ns)/1e9),dict(kind='decision_to_enforcement_seconds',value=(enf-begin)/1e9)])
      enforced=ledger.active['enforced_ns']
      with request_lock:
       ids=sorted(set(inflight)|{r['request_id'] for r in records if r['sent_monotonic_ns']<enforced<=r['completed_monotonic_ns']});append(out/'request_registry.jsonl',dict(event='ENFORCEMENT_CAPTURE',decision_id=case,enforced_monotonic_ns=enforced,captured_monotonic_ns=time.monotonic_ns(),inflight_ids=ids))
      # Registry includes actual-boundary inflight plus any conservatively captured later requests.
      if case=='cycle_down_1' and MODE=='application_exec':
       for index in range(2):
        thread=threading.Thread(target=diagnostic,args=(index,),name='observational-app-exec');diag_threads.append(thread);thread.start()
      cg=cg_read()['values'];assert cg['memory.max']==str(1024*2**20) and cg['memory.swap.current']=='0'
      quota,period=map(int,cg['cpu.max'].split());assert abs(quota/period*1000-target.cpu_millicores)<1e-6
      assert cg['memory.min']=='0' and cg['memory.low']=='0'
      while True:
       if ledger.watchdog():raise ValueError('censored_application_window')
       guard.raise_if_failed()
       if sampler_errors:raise ValueError('lost_control_telemetry:'+str(sampler_errors))
       with request_lock:window=observation_window(deepcopy(records),ids,enforced,time.monotonic_ns())
       dwell=45 if case=='cycle_down_1' else 15 if case.startswith('cycle_down_') else 5
       if window['observation_complete'] and time.monotonic_ns()-enforced>=dwell*10**9:break
       time.sleep(.2)
      # Reconcile identities/spec/status/cgroup again at the next decision boundary.
      check,p,s=observation(target,p['metadata']['generation'],ack_ns);assert check['complete'],'hidden_pending_or_regression'
      final_cg=cg_read()['values'];assert final_cg['memory.max']==str(1024*2**20)
      quota,period=map(int,final_cg['cpu.max'].split());assert abs(quota/period*1000-target.cpu_millicores)<1e-6
      timings.append(dict(kind='enforcement_to_mechanical_window_seconds',value=(time.monotonic_ns()-enforced)/1e9))
      with request_lock:
       window=observation_window(deepcopy(records),ids,enforced,time.monotonic_ns())
       assert ledger.finish_window(window)
      row=dict(case=case,target=vars(target),no_op=no_op,enforced_monotonic_ns=enforced,window=window,cgroup_initial=cg,cgroup_final=final_cg,final_gates=check)
      operation_results.append(row);append(out/'operations.jsonl',row)
      print(canonical_json(dict(stage='OPERATION_COMPLETE',case=case,no_op=no_op,post_completions=window['post_response_count'])),flush=True)
      queued=ledger.next_queued()
      if queued is not None:execute(ledger.active['id'],queued,already_active=True)
     for name,cpu,mem in CASES:execute(name,Target(cpu,mem))
     for thread in diag_threads:thread.join(timeout=35)
     assert not any(t.is_alive() for t in diag_threads) and not sampler_errors
     assert ledger.active is None and ledger.queued is None and not ledger.terminal
     write(out/'profile_final.json',http(profile_url+'/snapshot'))
     power_state();require_isolated_engine(commands,cluster)
    finally:
     stop.set();sampler_stop.set()
     if sampler is not None:sampler.join(timeout=12)
     for thread in diag_threads:thread.join(timeout=35)
     if gen is not None:gen.join(timeout=15)
     if clock is not None:clock.finalize()
     for p in processes:
      if p.poll() is None:p.terminate()
      try:p.wait(timeout=10)
      except subprocess.TimeoutExpired:p.kill();p.wait()
     for h in handles:h.close()
     if created:
      try:(logs/'application.log').write_text(kube.call(['logs','application']))
      finally:commands.run(['kind','delete','cluster','--name',cluster],log=logs/'kind.log',timeout=120)
   validate_clock_evidence(root,context)
   assert not load_errors and not inflight and len(records)==len(sent_ids) and not sampler_errors
  except BaseException as ex:
   failed=dict(type=type(ex).__name__,message=str(ex),traceback=traceback.format_exc())
   if ledger.active is not None and not ledger.terminal:ledger.fail('ENGINEERING_VERIFICATION_FAILED',failed)
  finally:
   write(out/'ledger.json',dict(events=ledger.events,active=None if ledger.active is None else {k:vars(v) if isinstance(v,Target) else v for k,v in ledger.active.items()},queued=None if ledger.queued is None else {k:vars(v) if isinstance(v,Target) else v for k,v in ledger.queued.items()},terminal=ledger.terminal))
   write(out/'timings.json',timings);write(out/'host_after.json',local_host_diagnostics())
   mismatches=[n for n,h in protected.items() if not (REPO/n).is_file() or file_sha256(REPO/n)!=h]
   if mismatches:failed=dict(type='ProtectedEvidenceChanged',paths=mismatches)
   source_clean()
   counts=Counter(e['event'] for e in ledger.events)
   summary=dict(status='BLOCKED' if failed else 'PASS',disposition='RESERVATION_SEMANTICS_BLOCKED' if failed else 'RESERVATION_SEMANTICS_VERIFIED',failure=failed,context=context,event_counts=dict(counts),operations=operation_results,diagnostic_mode=MODE,application_diagnostics=diagnostics,node_sampler_errors=sampler_errors,requests=len(records),request_failures=sum(not x['success'] for x in records),inflight_remaining=list(inflight),generator_errors=load_errors,protected_files=len(protected),protected_mismatches=mismatches,timing_distributions={k:distribution([x['value'] for x in timings if x['kind']==k]) for k in sorted({x['kind'] for x in timings})},statistically_settled=None,comparative=False,claim_generating=False,physical_bucket_seconds=300)
   write(out/'summary.json',summary)
   manifest=read_json(root/'manifest.json');manifest.update(status=summary['status'],ended_at=utc_now());write(root/'manifest.json',manifest)
   inventory={str(p.relative_to(root)):file_sha256(p) for p in root.rglob('*') if p.is_file()};write(root/'output_manifest.json',inventory)
   write(root/'COMPLETE',dict(status=summary['status'],output_manifest_sha256=file_sha256(root/'output_manifest.json'),summary_sha256=file_sha256(out/'summary.json')))
   print(canonical_json(dict(stage='TERMINAL',status=summary['status'],failure=failed,path=str(root),summary_sha256=file_sha256(out/'summary.json'))),flush=True)
 return 1 if failed else 0
if __name__=='__main__':sys.exit(main())
