"""Clock probe orchestration guards; no Kubernetes starts in these tests."""
from pathlib import Path
import inspect
from dynapm.system_validation.clock_probe import SECONDS,POLL_SECONDS,probe
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.smoke import Kube


def test_probe_uses_managed_local_cluster_prefix_and_no_workload():
    d=frozen_spec(Path(__file__).parents[2])
    # Exercise Kube's actual isolation guard, without making any calls.
    k=Kube(None,Path('/UNIT/config'),d['kubernetes']['cluster']+'-clock-UNIT',d)
    assert k is not None
    source=inspect.getsource(probe)
    assert "cluster=d['kubernetes']['cluster']+'-clock-'" in source
    assert 'kube.pod()' not in source  # No controller service account exists in clock-only deployment.
    assert '/work' not in source and '/initialize' not in source
    assert SECONDS==900 and POLL_SECONDS==1


def test_probe_configuration_binds_actual_collection_cadence():
    from dynapm.system_validation.clock_probe import probe_config
    c=probe_config('UNIT',{'duration_seconds':SECONDS,'poll_seconds':POLL_SECONDS})
    assert c.data.sampling_cadence_seconds==c.data.evaluation_cadence_seconds==POLL_SECONDS
    assert c.preprocessing['poll_seconds']==POLL_SECONDS
    assert not c.policies
