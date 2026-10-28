"""Outcome-independent deterministic offered-load traces, with open-loop arrivals."""
import concurrent.futures,json,threading,time,urllib.request


def workload_state(scenario,elapsed,design):
    c=design['scenarios'][scenario]
    if scenario=='stable':return c['rps'],c['memory_mib']
    if scenario=='periodic':high=(elapsed%c['period_seconds'])>=c['period_seconds']/2
    elif scenario=='burst':high=(elapsed-c['first_burst_seconds'])%c['period_seconds']<c['burst_seconds'] and elapsed>=c['first_burst_seconds']
    elif scenario=='abrupt_regime_shift':high=elapsed>=c['shift_seconds']
    else:raise ValueError('unknown_scenario')
    return (c['high_rps'],c['high_memory_mib']) if high else (c['low_rps'],c['low_memory_mib'])


def offered_trace(scenario,duration,design,*,smoke=False):
    if duration<=0:raise ValueError('positive_duration_required')
    trace=[];elapsed=0.;seed=design['workload']['seed']
    while elapsed<duration:
        rate,memory=(design['smoke']['rps'],design['smoke']['memory_mib']) if smoke else workload_state(scenario,elapsed,design)
        trace.append(dict(offset_seconds=elapsed,iterations=design['smoke']['iterations'] if smoke else design['workload']['iterations'],memory_mib=memory,seed=seed))
        elapsed+=1/rate
    return trace


def run_load(url,trace,start_wall,*,timeout=5.,concurrency=32,stop_event=None):
    """Bounded concurrency; overload is recorded as dropped offered work, never hidden."""
    records=[];lock=threading.Lock();slots=threading.BoundedSemaphore(concurrency)
    start_mono=time.monotonic()+start_wall-time.time()  # Preserve a late generator start in arrival-to-completion latency.
    def send(index,event):
        scheduled=start_wall+event['offset_seconds'];sent=time.time();due=start_mono+event['offset_seconds']
        try:
            query=f"iterations={event['iterations']}&memory_mib={event['memory_mib']}&seed={event['seed']}"
            with urllib.request.urlopen(url+'/work?'+query,timeout=timeout) as response:
                status=response.status;success=status==200;response.read()
            error=None
        except Exception as e:status=None;success=False;error=type(e).__name__
        end=time.time()
        with lock:records.append(dict(request_id=index,scheduled_at=scheduled,sent_at=sent,completed_at=end,
            latency_seconds=time.monotonic()-due,success=success,http_status=status,error=error,dropped=False))
        slots.release()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i,event in enumerate(trace):
            scheduled=start_wall+event['offset_seconds'];wait=max(0,start_mono+event['offset_seconds']-time.monotonic())
            if stop_event is not None:
                if stop_event.wait(wait):break
            else:time.sleep(wait)
            if not slots.acquire(blocking=False):
                records.append(dict(request_id=i,scheduled_at=scheduled,sent_at=None,completed_at=time.time(),latency_seconds=None,success=False,http_status=None,error='generator_capacity',dropped=True))
            else:pool.submit(send,i,event)
    return sorted(records,key=lambda x:x['request_id'])
