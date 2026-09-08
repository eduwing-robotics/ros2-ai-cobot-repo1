import json
from dataclasses import replace
from fr5_process_sequences.real_contract import Event, parse_operation
from test_real_backend import backend, pick, place


def test_attachment_callbacks_preserve_original_identity_and_world_ownership_order():
    real, *_ = backend(); p=parse_operation(pick()); q=parse_operation(place())
    row=dict(source_id='actual-original-id',tray_registration_id='registration-7',source_observation_id='frame-23')
    for op in (p,q):real.event_context.bind(op,{'source_cycle_id':'cycle-9','plan_sha256':'hash'},row)
    def emit(op,phase,event,feedback=None):
        e=real._event(op,phase=phase,event=event,feedback=feedback);real._emit(e);return e
    start=emit(p,'APPROACH',Event.PHASE_STARTED)
    assert real.event_context.snapshot()['attachments'][0]['state']=='reserved'
    emit(p,'PREOPEN',Event.PHASE_COMPLETED,{'continuous_feedback_verified':True})
    assert real.event_context.snapshot()['attachments'][0]['state']=='reserved'
    grasp=emit(p,'GRASP',Event.PHASE_COMPLETED,{'continuous_feedback_verified':True,'state_sequence':12})
    assert real.event_context.snapshot()['attachments'][0]['state']=='attached'
    release=emit(q,'RELEASE',Event.PHASE_COMPLETED,{'continuous_feedback_verified':True,'state_sequence':19})
    assert real.event_context.snapshot()['attachments'][0]['state']=='placed'
    real._emit(grasp)  # late replay cannot reattach
    assert real.event_context.snapshot()['attachments'][0]['state']=='placed'
    messages=[json.loads(e.message) for e in (start,grasp,release)]
    assert [m['event_sequence'] for m in messages]==sorted(m['event_sequence'] for m in messages)
    assert all(m['source_id']=='actual-original-id' for m in messages)
    assert all('production_job_id' not in m for m in messages)


def test_unbound_or_unverified_grasp_never_creates_attachment():
    real,*_=backend();op=parse_operation(pick())
    e=real._event(op,phase='GRASP',event=Event.PHASE_COMPLETED)
    real._emit(e)
    assert not json.loads(e.message)['attachment_binding_valid']
    assert real.event_context.snapshot()['attachments']==[]


def test_failure_preserves_parent_state_and_marks_uncertainty():
    real,*_=backend();op=parse_operation(pick())
    real.event_context.bind(op,{},dict(source_id='part',tray_registration_id='reg',source_observation_id='obs'))
    for phase,event,fb in [('APPROACH',Event.PHASE_STARTED,None),('GRASP',Event.PHASE_COMPLETED,{'continuous_feedback_verified':True}),('LIFT',Event.OPERATION_FAILED,None)]:
        real._emit(real._event(op,phase=phase,event=event,message='original fault',feedback=fb))
    item=real.event_context.snapshot()['attachments'][0]
    assert item['state']=='attached' and item['uncertain']
    assert item['reason']=='original fault' and not item['physical_holding_verified']


def test_control_overtaking_grasp_does_not_drop_attachment_or_terminal():
    real,*_=backend();op=parse_operation(pick())
    real.event_context.bind(op,{},dict(source_id='part',tray_registration_id='reg',source_observation_id='obs'))
    real._emit(real._event(op,phase='APPROACH',event=Event.PHASE_STARTED))
    grasp=real._event(op,phase='GRASP',event=Event.PHASE_COMPLETED,feedback={'continuous_feedback_verified':True})
    terminal=real._event(op,phase='LIFT',event=Event.OPERATION_COMPLETED)
    real._emit(real._event(op,phase='CONTROL',event=Event.PAUSE_CONFIRMED))
    real._emit(grasp)
    real._emit(terminal)
    snapshot=real.event_context.snapshot()
    assert snapshot['attachments'][0]['state']=='attached'
    assert len(snapshot['terminal_operations'])==1
    assert snapshot['last_event']['event']=='PAUSE_CONFIRMED'
