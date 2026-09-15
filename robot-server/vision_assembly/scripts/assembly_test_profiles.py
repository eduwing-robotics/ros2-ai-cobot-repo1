"""Named whole-group physical tests using the normal capture/planner/executor."""
import argparse
from pathlib import Path
import sys

GROUPS = {
    'GPU': ('gpu', ['GPU-01']),
    'HBM': ('hbm', [f'HBM-{i:02}' for i in range(1, 9)]),
    'PM': ('long_orange', [f'PM-{i:02}' for i in range(1, 5)]),
    'VRM': ('black_block', [f'VRM-{i:02}' for i in range(1, 6)]),
    'IND': ('marked_white', ['IND-01', 'IND-02']),
    'SMD': ('right_white_brown', [f'CAP-{i:02}' for i in range(1, 6)]),
}


def workflow(directory, profile):
    from assembly_cycle_launcher import ROOT, SCRIPTS
    kind, slots = GROUPS[profile]
    def py(name, *args):
        return [sys.executable, str(SCRIPTS/name), *map(str, args)]
    phase = 'smd' if profile == 'SMD' else 'non-smd'
    steps = [('stack_check', ['bash', str(ROOT/'run_fr5_assembly_stack.sh'), 'check']),
        ('capture_board', py('cycle_camera_stage.py', 'PlaceCamera', '--execute', '--directory', directory)),
        ('capture_tray', py('cycle_camera_stage.py', 'TrayHome', '--execute', '--directory', directory,
                           '--part-group', kind, *(['--defer-smd-to-close-view'] if profile == 'SMD' else [])))]
    if profile == 'VRM':
        steps.append(('refine_vrm', py('capture_vrm_refinement.py', '--directory', directory)))
    if profile == 'SMD':
        steps.extend([
            ('capture_smd_view', py('cycle_camera_stage.py', 'SMDView', '--execute', '--directory', directory)),
            ('measure_smd', py('capture_smd_with_retries.py', '--output', directory/'smd_close.json')),
            ('merge_smd', py('fixed_cycle_snapshot.py', 'smd-close', '--output', directory/'snapshot.json',
                             '--smd-close-input', directory/'smd_close.json'))])
    plan = directory/f'{phase}_plan.json'
    common = ['--plan-file', plan, '--run-record', directory/f'{phase}_run.json']
    if profile != 'SMD':
        common += ['--selected-slots', *slots, '--verify-tray-pick']
    steps.extend([
        (f'plan_{phase}', py('assembly_test_profiles.py', '--profile', profile, '--directory', directory)),
        (f'preflight_{phase}', py('execute_full_fixed_cycle.py', *common, '--dry-run')),
        (f'assemble_{phase}', py('execute_full_fixed_cycle.py', *common, '--execute', '--confirm-cycle')),
        ('after_photo', py('cycle_camera_stage.py', 'PlaceCamera', '--execute', '--photo-only', '--directory', directory/'after'))])
    return steps


def build(directory, profile):
    from assembly_cycle_launcher import ROOT, read, write
    from full_cycle_plan import build_plan
    from execute_full_fixed_cycle import validate_plan
    kind, slots = GROUPS[profile]
    snapshot = read(directory/'snapshot.json')
    if snapshot['tray_capture']['capture_scope']['selected_part_types'] != [kind]:
        raise RuntimeError('test capture scope does not match requested group')
    if profile != 'SMD':
        snapshot['authorized_selected_slots'] = slots
        write(directory/'snapshot.json', snapshot)
    recipes = read(ROOT/'vision_assembly/config/part_gripper_recipes.json')
    slot_config = read(ROOT/'vision_assembly/config/assembly_slots_r1.json')
    kwargs = {'phase': 'smd'} if profile == 'SMD' else {'selected_slots': slots}
    plan = build_plan(snapshot, recipes, slot_config, snapshot_path=directory/'snapshot.json', **kwargs)
    validate_plan(plan, 1800, **({'requested_selected_slots': slots} if profile != 'SMD' else {}))
    if [item['slot_code'] for item in plan['plan']] != slots:
        raise RuntimeError('unexpected test plan scope')
    phase = 'smd' if profile == 'SMD' else 'non-smd'
    write(directory/f'{phase}_plan.json', plan)
    (directory/'after').mkdir(exist_ok=True)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=list(GROUPS), required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    build(args.directory, args.profile)
