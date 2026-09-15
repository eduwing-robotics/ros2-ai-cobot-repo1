#!/usr/bin/env python3
"""Sequence one prepared phase as individual Pick and Place API requests."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

from assembly_cycle_launcher import ROOT,read,write


def phase_recipe(template, slots):
    recipe=deepcopy(template)
    # Keep the full frozen recipe order/correlation; execute only the named
    # phase's rows, after its explicit fresh vision stage has completed.
    lookup={s['slot_code']:s for s in recipe['steps']}
    if len(slots)!=len(set(slots)) or any(s not in lookup for s in slots):
        raise ValueError('invalid phase slot scope')
    return recipe,[lookup[s] for s in slots]


def execute_phase(session, steps, record, path):
    for step in steps:
        part,slot=step['part_id'],step['slot_code']
        pick=session.call(session.client.pickItem,part,slot)
        record.setdefault('pick_results',[]).append(pick);record['part_held_candidate']=True
        record['held_slot']=slot;write(path,record)
        place=session.call(session.client.placeItem,part,slot)
        record.setdefault('place_results',[]).append(place)
        record['motion_completed_slots'].append(slot)
        record['part_held_candidate']=False;record.pop('held_slot',None);write(path,record)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--phase',choices=['non-smd','smd'],required=True)
    parser.add_argument('--job-id',type=lambda x:str(UUID(x)),required=True)
    args=parser.parse_args()
    import rclpy
    from execute_full_fixed_cycle import validate_plan
    from fr5_process_sequences.real_vision_adapter import build_target_payload
    from step_api_transport import StepApiSession
    plan_path=args.directory/f'{args.phase}_plan.json';plan=read(plan_path)
    selection=plan['plan_selection'];validation={}
    if selection['mode']=='explicit_slots':validation['requested_selected_slots']=selection['selected_slots']
    if selection['mode']=='single_slot':validation['requested_only_slot']=selection['requested_only_slot']
    items=validate_plan(plan,1800,**validation)
    slots=[i['slot_code'] for i in items]
    frozen=read(args.directory/'api_recipe.json')
    recipe,steps=phase_recipe(frozen,slots)
    # Adapter source_index is per-kind occurrence. Pass all preceding recipe
    # rows of requested kinds: phases/groups always contain each entire kind.
    kinds={s['part_id'] for s in steps}
    target_steps=[s for s in recipe['steps'] if s['part_id'] in kinds]
    payload=build_target_payload(snapshot=read(args.directory/'snapshot.json'),
        recipes=read(ROOT/'vision_assembly/config/part_gripper_recipes.json'),
        slots=read(ROOT/'vision_assembly/config/assembly_slots_r1.json'),steps=target_steps,
        job_id=args.job_id,plan_builder=lambda *a,**k:plan,frozen_unit=True)
    write(args.directory/f'{args.phase}_api_targets.json',payload)
    record=dict(status='running',cycle_id=plan['cycle_id'],selected_slots=slots,
        motion_completed_slots=[],part_held_candidate=False,job_id=args.job_id,
        plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),execution_backend='single_step_api')
    path=args.directory/f'{args.phase}_run.json'
    if path.exists():raise RuntimeError('phase already has a run record; no automatic replay')
    write(path,record)
    rclpy.init();node=rclpy.create_node('cycle_step_api_client')
    try:
        session=StepApiSession(node,args.job_id,args.directory/f'{args.phase}_api',recipe)
        session.ready();session.publish_targets(payload)
        execute_phase(session,steps,record,path)
        record['status']='motion_complete_awaiting_physical_verification'
    except BaseException as error:
        record.update(status='stopped_on_error',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        write(path,record);node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':
    import signal
    def interrupted(*_):raise KeyboardInterrupt('launcher interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    main()
