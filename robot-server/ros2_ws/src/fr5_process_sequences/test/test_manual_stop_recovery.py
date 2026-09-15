import json
import threading
from types import SimpleNamespace as NS
import pytest
from fr5_process_sequences import manual_stop_recovery as m
from fr5_process_sequences.real_backend import BackendFailure

@pytest.fixture
def setup(tmp_path,monkeypatch):
 d=tmp_path/'runtime/robot_operations';d.mkdir(parents=True)
 row=dict(status='terminal',request={'job_id':'execution'},event={'event':'OPERATION_FAILED'},fingerprint='original',held_candidate=True,recovery_required=True)
 path=d/'op.json';path.write_text(json.dumps(row))
 def write(p,r):p.write_text(json.dumps(r))
 store=NS(directory=d,_write=write,restore=lambda:({},False))
 state=NS(abnormal_stop=1,robot_mode=0,robot_motion_done=1,tool_num=1,work_num=0,gripper_feedback_valid=True,gripperfaultnum=0,grippererro=0)
 calls=[]
 port=NS(_state_sequence=1,_fresh_state=lambda:state,_enabled=True,_assert_health=lambda s:None)
 def service(cmd,code):
  calls.append(cmd);state.abnormal_stop=0;port._state_sequence+=1;return '0'
 def fresh():
  port._state_sequence+=1
  return state
 port._fresh_state=fresh
 port._service=service
 backend=NS(_active=None,held_part=NS(job_id='execution'),_held=object(),_operation_store=store,_state_lock=threading.Lock(),_recovery_required=True,_paused=threading.Event())
 control=NS(worker=None,blocked=threading.Event(),pause_anchor=object())
 bridge=NS(node=NS(_backend=backend,_robot_port=port),controller=NS(root=tmp_path),production=NS(control=control))
 monkeypatch.setattr(m,'verify_stationary',lambda p,allow_abnormal=False:dict(abnormal_stop=int(state.abnormal_stop),samples=20))
 return bridge,path,row,calls,state

def test_manual_stop_recovers_without_motion_and_preserves_event(setup):
 b,p,old,calls,state=setup
 m.reconcile(b,'execution',{'operator_id':'operator'})
 new=json.loads(p.read_text())
 assert not new['held_candidate'] and not new['recovery_required']
 assert new['event']==old['event'] and new['fingerprint']==old['fingerprint']
 assert calls==['ResetAllError()']
 assert b.node._backend._held is None and not b.node._backend._recovery_required
 assert list((b.controller.root/'runtime/manual_stop_recovery').glob('*.json'))

@pytest.mark.parametrize('cause',['active','other_held','other_journal','intent','other_lease','reset_failure','unsafe'])
def test_recovery_refuses_without_clearing_records(setup,monkeypatch,cause):
 b,p,old,calls,state=setup
 if cause=='active':b.node._backend._active=object()
 if cause=='other_held':b.node._backend.held_part.job_id='other'
 if cause in ('other_journal','intent'):
  if cause=='other_journal':old['request']['job_id']='other'
  else:old['status']='intent'
  p.write_text(json.dumps(old))
 if cause=='other_lease':
  lease=b.controller.root/'runtime/assembly_cycles/step_api_owner.json';lease.parent.mkdir(parents=True)
  lease.write_text(json.dumps(dict(job_id='other',pid=-1,process_start='0')))
 def fail(*args,**kwargs):raise BackendFailure('SAFETY_STOP','blocked')
 if cause=='reset_failure':b.node._robot_port._service=fail
 if cause=='unsafe':monkeypatch.setattr(m,'verify_stationary',fail)
 with pytest.raises(BackendFailure):m.reconcile(b,'execution',{})
 assert json.loads(p.read_text())==old and b.node._backend._recovery_required

@pytest.mark.parametrize('field',['robot_motion_done','gripper_feedback_valid','robot_mode'])
def test_bad_robot_state_rejected(setup,field):
 b,p,old,calls,state=setup
 setattr(state,field,1 if field=='robot_mode' else 0)
 with pytest.raises(BackendFailure):m.check_state(b.node._robot_port,state,True)
