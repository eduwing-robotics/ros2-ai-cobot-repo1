#!/usr/bin/env python3
"""One fresh two-phase cycle; no automatic recovery or historical target replay."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import selectors
import subprocess
import sys
import time
import threading
from uuid import UUID, uuid4
from datetime import datetime
from execution_safety import LAUNCHER_INTERRUPT_GRACE_SEC, LAUNCHER_TERMINATE_GRACE_SEC

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'vision_assembly/scripts'
BASELINE = ROOT / 'vision_assembly/checkpoints/full_cycle_success_20260906'
REVISION = ROOT / 'vision_assembly/config/assembly_launcher_revision.json'
NON_SMD = ['GPU-01'] + [f'HBM-{i:02}' for i in range(1, 9)] + [f'PM-{i:02}' for i in range(1, 5)] + [f'VRM-{i:02}' for i in range(1, 6)] + ['IND-01', 'IND-02']
SMD = [f'CAP-{i:02}' for i in range(1, 6)]
BASELINE_FILES = (
    'vision_assembly/config/part_gripper_recipes.json',
    'vision_assembly/config/assembly_slots_r1.json',
    'vision_assembly/config/assembly_board_holes.json',
    'vision_assembly/config/assembly_placecamera_residual.json',
    'vision_assembly/config/smd_section_view.json',
    'calibration/data/handeye_result.json',
)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def check_installation():
    revision = read(REVISION)
    if revision.get('schema') != 'fr5.assembly_launcher_revision/v1':
        raise RuntimeError('잘못된 런처 설정 검토 기록')
    approved = revision['reviewed_config_sha256']
    if set(approved) != {'vision_assembly/config/part_gripper_recipes.json'}:
        raise RuntimeError('런처 설정 변경 허용 범위 불일치')
    hashes = {}
    for relative in BASELINE_FILES:
        data = (ROOT / relative).read_bytes()
        expected = approved.get(relative, hashlib.sha256((BASELINE / 'files' / relative).read_bytes()).hexdigest())
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f'성공 기준과 설정이 다릅니다. 변경 검토 필요: {relative}')
        hashes[relative] = hashlib.sha256(data).hexdigest()
    for relative in (
        '.venv-vision/bin/python', 'vision_assembly/models/smd_obb/pilot_06/weights/best.pt',
        'vision_assembly/scripts/cycle_camera_stage.py',
        'vision_assembly/scripts/tray_capture_retry.py',
        'vision_assembly/scripts/capture_vrm_refinement.py',
        'vision_assembly/scripts/vrm_edge_refinement.py',
        'vision_assembly/scripts/pm_mask_selection.py',
        'vision_assembly/scripts/segmentation_scale_retry.py',
        'vision_assembly/scripts/full_cycle_plan.py',
        'vision_assembly/scripts/successful_gripper_directions.py',
        'vision_assembly/scripts/execute_full_fixed_cycle.py',
        'vision_assembly/scripts/capture_smd_close_target.py',
        'vision_assembly/scripts/capture_smd_with_retries.py',
        'vision_assembly/scripts/merge_smd_retry_captures.py',
        'vision_assembly/scripts/fixed_cycle_snapshot.py',
    ):
        if not (ROOT / relative).is_file():
            raise RuntimeError(f'필수 파일 없음: {relative}')
    return hashes


def workflow(directory):
    def py(name, *args):
        return [sys.executable, str(SCRIPTS / name), *map(str, args)]
    snapshot = directory / 'snapshot.json'
    steps = [('stack_check', ['bash', str(ROOT / 'run_fr5_assembly_stack.sh'), 'check'])]
    for point, phase in [('PlaceCamera', 'board'), ('TrayHome', 'tray')]:
        steps.append((f'capture_{phase}', py('cycle_camera_stage.py', point,
                     '--execute', '--directory', directory, *(['--defer-smd-to-close-view'] if phase == 'tray' else []))))
    steps.append(('refine_vrm', py('capture_vrm_refinement.py', '--directory', directory)))
    for phase in ('non-smd', 'smd'):
        if phase == 'smd':
            steps.extend([
                ('capture_smd_view', py('cycle_camera_stage.py', 'SMDView', '--execute', '--directory', directory)),
                ('measure_smd', py('capture_smd_with_retries.py', '--output', directory / 'smd_close.json')),
                ('merge_smd', py('fixed_cycle_snapshot.py', 'smd-close', '--output', snapshot,
                                '--smd-close-input', directory / 'smd_close.json')),
            ])
        plan = directory / f'{phase}_plan.json'
        common = ['--plan-file', plan, '--run-record', directory / f'{phase}_run.json']
        if phase == 'non-smd':
            common.append('--verify-tray-pick')
        steps.extend([
            (f'plan_{phase}', py('full_cycle_plan.py', '--phase', phase, '--snapshot', snapshot, '--output', plan)),
            (f'preflight_{phase}', py('execute_full_fixed_cycle.py', *common, '--dry-run')),
            (f'assemble_{phase}', py('execute_full_fixed_cycle.py', *common, '--execute', '--confirm-cycle')),
        ])
    return steps


def api_workflow(directory, profile='full'):
    from assembly_test_profiles import workflow as test_workflow
    original = workflow(directory) if profile == 'full' else test_workflow(directory, profile)
    steps=[]
    for name,command in original:
        if name.startswith('assemble_'):
            command=[sys.executable,str(SCRIPTS/'execute_cycle_steps_api.py'),
                '--directory',str(directory),'--phase',name.split('_',1)[1],
                '--job-id',os.environ.get('FR5_STEP_API_JOB_ID','<unit-execution-uuid>')]
        steps.append((name,command))
        if name=='stack_check':
            steps.append(('step_api_check',[sys.executable,str(SCRIPTS/'check_step_api.py')]))
    if profile=='full':
        steps.append(('after_photo',[sys.executable,str(SCRIPTS/'cycle_camera_stage.py'),
            'PlaceCamera','--execute','--photo-only','--directory',str(directory/'after')]))
    return steps


def frozen_api_recipe(profile='full'):
    import yaml
    from assembly_test_profiles import GROUPS
    reference=yaml.safe_load((ROOT/'assembly_integration/config/sequencer_recipe.current.yaml').read_text())
    slots=NON_SMD+SMD if profile=='full' else GROUPS[profile][1]
    recipe={'recipe_version':'fixed-fixture-step-api-20260908','frame':'base_link',
        'scope':'25_part_assembly_only' if profile=='full' else 'whole_part_group_test',
        'physical_api_cycle_verified':False,
        'motion':dict(approach_dz_mm=100.,retract_dz_mm=100.),
        'gripper':{'parts':reference['gripper']['parts']},
        'workflow':{'before_all':[], 'per_step':[{'robot.pick':'current_part'},{'robot.place':'current_slot'}], 'after_all':[]},
        'steps':[dict(order=i+1,part_id=slot.split('-')[0],slot_code=slot) for i,slot in enumerate(slots)]}
    return recipe


def verify_completion(directory, phase, expected_slots=None):
    record = read(directory / f'{phase}_run.json')
    plan_path = directory / f'{phase}_plan.json'
    plan = read(plan_path)
    expected = expected_slots if expected_slots is not None else NON_SMD if phase == 'non-smd' else SMD
    if (record.get('status') != 'motion_complete_awaiting_physical_verification'
            or record.get('motion_completed_slots') != expected
            or record.get('selected_slots') != expected
            or record.get('part_held_candidate') is not False or record.get('held_slot')
            or record.get('cycle_id') != plan.get('cycle_id')
            or record.get('plan_sha256') != hashlib.sha256(plan_path.read_bytes()).hexdigest()):
        raise RuntimeError(f'{phase}: 완료 기록 불일치. 다음 단계로 진행하지 않습니다.')


def verify_capture_ages(directory, phase, now=None, require_vrm=True):
    now = time.time() if now is None else now
    snapshot = read(directory / 'snapshot.json')
    keys = ['board_capture', 'tray_capture']
    if phase == 'smd':
        keys.append('smd_close_capture')
    elif require_vrm:
        keys.append('vrm_refinement_capture')
    for key in keys:
        age = now - float(snapshot.get(key, {}).get('captured_unix', math.nan))
        limit = 180.0 if key == 'vrm_refinement_capture' else 120.0 if key == 'smd_close_capture' else 1800.0
        if not math.isfinite(age) or not 0 <= age <= limit:
            raise RuntimeError(f'{key}: 촬영 유효시간 초과/누락. 새 촬영 필요.')


def stop_child(process, record_path, error):
    """Persist shutdown intent and distinguish graceful exit from escalation."""
    record = {'status': 'shutdown_requested', 'error': f'{type(error).__name__}: {error}',
              'pid': process.pid, 'signals': [], 'forced_termination': False,
              'forced_kill': False, 'physical_stop_verified': False}
    previous_sigint = None
    if threading.current_thread() is threading.main_thread():
        previous_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
    def persist():
        try:
            write(record_path, record)
        except Exception as exc:
            message = f'{type(exc).__name__}: {exc}'
            record.setdefault('record_write_errors', []).append(message)
            print('SHUTDOWN RECORD WRITE FAILED: ' + message, flush=True)
    try:
        persist()
        for signum, grace in ((signal.SIGINT, LAUNCHER_INTERRUPT_GRACE_SEC),
                              (signal.SIGTERM, LAUNCHER_TERMINATE_GRACE_SEC),
                              (signal.SIGKILL, None)):
            if process.poll() is not None:
                break
            entry = {'signal': signum.name, 'requested_unix': time.time(), 'grace_sec': grace}
            record['signals'].append(entry)
            record['forced_termination'] = signum != signal.SIGINT
            record['forced_kill'] = signum == signal.SIGKILL
            persist()
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                break
            entry['sent_unix'] = time.time()
            persist()
            try:
                process.wait(timeout=grace)
                break
            except subprocess.TimeoutExpired:
                entry['grace_expired_unix'] = time.time()
                persist()
        record.update(status='process_exited', returncode=process.poll(), finished_unix=time.time())
        persist()
    finally:
        if previous_sigint is not None:
            signal.signal(signal.SIGINT, previous_sigint)


def run_step(command, log_path, timeout=1800):
    # Separate process group allows SIGINT to reach the actual ROS executor.
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + timeout
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout)
                    for key, _ in selector.select(timeout=0.2):
                        data = os.read(key.fd, 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        log.write(data)
                        log.flush()
                        sys.stdout.write(data.decode('utf-8', errors='replace'))
                        sys.stdout.flush()
            code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
            if code:
                raise RuntimeError(f'단계 실패(exit {code}), 로그: {log_path}')
        except BaseException as exc:
            if process.poll() is None:
                stop_child(process, log_path.with_suffix('.shutdown.json'), exc)
            raise


def run_cycle(directory, hashes, runner=run_step, profile="full"):
    from assembly_test_profiles import GROUPS, workflow as test_workflow
    expected_slots = None if profile == "full" else GROUPS[profile][1]
    record = {'schema': 'fr5.assembly_cycle_launcher/v1', 'started_unix': time.time(),
              'status': 'running', 'baseline_hashes': hashes, 'steps': [],
              'physical_placement_verified': False, 'profile': profile}
    record_path = directory / 'cycle.json'
    write(record_path, record)
    try:
        steps = api_workflow(directory, profile)
        for index, (name, command) in enumerate(steps, 1):
            entry = {'name': name, 'command': command, 'status': 'running', 'started_unix': time.time()}
            record['steps'].append(entry)
            write(record_path, record)
            if check_installation() != hashes:
                raise RuntimeError('실행 도중 설정이 변경되었습니다.')
            if name.startswith(('preflight_', 'assemble_')):
                verify_capture_ages(directory, name.split('_', 1)[1], require_vrm=profile in ('full','VRM'))
            print(f'[{index}/{len(steps)}] {name} 시작 — {directory / (name + ".log")}', flush=True)
            runner(command, directory / f'{name}.log')
            if name.startswith('assemble_'):
                verify_completion(directory, name.split('_', 1)[1], expected_slots)
            entry.update(status='completed', completed_unix=time.time())
            write(record_path, record)
            print(f'[{index}/{len(steps)}] {name} 완료', flush=True)
        record['status'] = 'motion_complete_awaiting_physical_verification'
        print(f'{25 if expected_slots is None else len(expected_slots)}개 동작 완료. 실제 안착 결과를 확인하세요.', flush=True)
    except BaseException as exc:
        record.update(status='stopped_on_error', error=f'{type(exc).__name__}: {exc}')
        if record['steps'] and record['steps'][-1]['status'] == 'running':
            record['steps'][-1]['status'] = 'failed'
            shutdown_path = directory / (record['steps'][-1]['name'] + '.shutdown.json')
            if shutdown_path.exists():
                record['steps'][-1]['shutdown'] = read(shutdown_path)
        raise
    finally:
        record['finished_unix'] = time.time()
        write(record_path, record)


def main():
    parser = argparse.ArgumentParser(description='PlaceCamera → TrayHome → 일반20개 → SMDView → SMD5개')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true', help='현재 빈 그리퍼/빈 기판/트레이25개/고정 지그를 확인하고 전체 동작 시작')
    mode.add_argument('--check', action='store_true', help='설치 및 현재 로봇/티칭점/카메라 검사만 수행, 이동 없음')
    mode.add_argument('--dry-run', action='store_true', help='설정과 실행 순서 확인만, 로봇 접속/IK 검사 없음 (기본)')
    parser.add_argument("--profile", choices=["full","GPU","HBM","PM","VRM","IND","SMD"], default="full")
    parser.add_argument("--expected-revision", help="Reject API request if reviewed settings changed before launch")
    parser.add_argument("--run-id", type=lambda value: str(UUID(value)), help="API correlation UUID; new directory only")
    args = parser.parse_args()
    # Also cover direct Python launch; all cycle children inherit this setting.
    os.environ["FASTDDS_BUILTIN_TRANSPORTS"] = "UDPv4"
    hashes = check_installation()
    if args.expected_revision and read(REVISION)["revision"] != args.expected_revision:
        raise RuntimeError("API 요청 이후 레시피 revision이 변경되었습니다.")
    if not args.execute and not args.check:
        print('설정: PM -0.5mm / HBM -1.0mm / SMD 1번 -1.7mm / 2~5번 -2.4mm. PM2 배치 C180, 성공 방향 고정, Fast DDS UDPv4. SMD 검출 최대4회 / 파지 확인 최대3회.')
        print('실행 경로: 단계 API. GPU→HBM→PM→VRM→IND→SMD, 촬영 이동 포함. PCB 이송은 기존 성공 범위에 없음.')
        for i, (name, _) in enumerate(api_workflow(Path('<run-directory>'),args.profile), 1):
            print(f'{i:02}. {name}')
        print('이동 없음. 새 영상·실기 IK는 각 실행 단계에서 검사합니다.')
        return
    runtime = ROOT / 'runtime/assembly_cycles'
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / 'launcher.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('이미 조립 런처가 실행 중입니다.') from exc
        if args.check:
            subprocess.run(['bash', str(ROOT / 'run_fr5_assembly_stack.sh'), 'check'], check=True)
            subprocess.run([sys.executable, str(SCRIPTS / 'cycle_camera_stage.py'), 'check'], check=True)
            subprocess.run([sys.executable,str(SCRIPTS/'check_step_api.py')],check=True)
            return
        directory = runtime / (args.run_id or datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        directory.mkdir()
        (directory/'after').mkdir()
        job_id = args.run_id or str(uuid4())
        lease_path = runtime/'step_api_owner.json'
        if lease_path.exists():
            raise RuntimeError('이전 API 사이클 소유권 기록이 남아 있습니다. 상태/기록 복구가 먼저 필요합니다.')
        # Check the API before publishing a lease or making any camera move.
        subprocess.run([sys.executable,str(SCRIPTS/'check_step_api.py')],check=True)
        write(directory/'api_recipe.json',frozen_api_recipe(args.profile))
        lease=dict(job_id=job_id,pid=os.getpid(),
            process_start=Path(f'/proc/{os.getpid()}/stat').read_text().split()[21],
            directory=str(directory),created_unix=time.time())
        write(lease_path,lease)
        os.environ['FR5_STEP_API_JOB_ID']=job_id
        print(f'전체 API 실행 기록: {directory}', flush=True)
        try:
            run_cycle(directory, hashes, profile=args.profile)
        finally:
            # Release delegation only after independent API idle/empty/healthy
            # status. Unknown/held outcomes retain the lease for reconciliation.
            try:
                checked=subprocess.run([sys.executable,str(SCRIPTS/'check_step_api.py')],
                    capture_output=True,text=True,timeout=12)
                write(directory/'api_release_check.json',dict(returncode=checked.returncode,
                    stdout=checked.stdout,stderr=checked.stderr))
                if checked.returncode==0 and read(lease_path)==lease:
                    lease_path.unlink()
                else:print('API 결과/정지/보유 상태 확인 필요. 실행 소유권 기록을 보존합니다.',flush=True)
            except Exception as error:
                print(f'API 소유권 확인 미완료: {error}',flush=True)
            os.environ.pop('FR5_STEP_API_JOB_ID',None)


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'중단: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
