"""Sequential saved-image replay with source identity and bounded subprocess execution.

Never captures, operates equipment, promotes labels, or grants release authority.
"""
import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


class BatchCancelled(RuntimeError):
    pass


def handle_termination(signum, frame):
    raise BatchCancelled('Batch terminated; owned inference will be cleaned up')


def execute_owned(command, log, timeout):
    proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        return proc.wait(timeout=timeout)
    finally:
        # Kill only this owned process group, including provider workers on timeout.
        try:
            os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_cases(manifest, root=ROOT):
    cases = manifest.get('cases')
    if not isinstance(cases,list) or not 1 <= len(cases) <= 20:
        raise ValueError('Expected 1..20 explicit saved-image cases')
    result, seen = [],set()
    for row in cases:
        requested = root/row['image']
        if requested.is_symlink() or 'latest' in requested.name:
            raise ValueError('Mutable image alias is not a validation case')
        path = requested.resolve()
        if not path.is_relative_to(root.resolve()) or 'latest' in path.name or path.suffix.lower() not in ('.png','.jpg','.jpeg'):
            raise ValueError('Expected immutable workspace image path')
        expected = row['sha256']
        if digest(path) != expected:
            raise ValueError('Input hash mismatch')
        if expected in seen:
            raise ValueError('Duplicate image; combine its slot labels into one case')
        seen.add(expected)
        result.append(dict(image=str(path), sha256=expected, labels=row.get('labels',{}),
                           label_provenance=row.get('label_provenance'),
                           split=row.get('split','UNSPECIFIED_NOT_INDEPENDENT')))
    return result


def source_fingerprint():
    # Records local code/config, NOT a claim to identify every loaded model weight.
    paths = sorted((ROOT/'vision_assembly/hybrid_inspection').glob('*.py'))
    paths += sorted((ROOT/'vision_assembly/config').glob('*.json'))
    return {str(p.relative_to(ROOT)):digest(p) for p in paths}


def run(manifest, output, timeout=240):
    cases = validate_cases(manifest)
    output = output.resolve()
    if not output.is_relative_to((ROOT/'runtime/inspection').resolve()):
        raise ValueError('Output must be a new inspection artifact directory')
    output.mkdir(parents=True,exist_ok=False)
    initial = source_fingerprint()
    rows=[]
    for index,case in enumerate(cases):
        item=output/f'case_{index:02}'
        item.mkdir()
        started=time.monotonic()
        state='EXECUTION_FAILED'
        detail=None
        try:
            if digest(Path(case['image'])) != case['sha256']:
                raise ValueError('Source changed before replay')
            with (item/'execution.log').open('w') as log:
                returncode=execute_owned([str(ROOT/'vision_assembly/run_hybrid_fixed_slot_inspection.sh'),
                    '--image',case['image'],'--output',str(item/'replay')],
                    log,timeout)
            reports=list((item/'replay').glob('*/hybrid_report.json'))
            if returncode or len(reports)!=1:
                raise ValueError('Replay failed or unique report missing')
            report=json.loads(reports[0].read_text())
            if report.get('input_sha256') != case['sha256'] or digest(Path(case['image'])) != case['sha256']:
                raise ValueError('Source changed or report source mismatch')
            state='REPLAY_COMPLETED'
            detail=dict(report=str(reports[0]), report_sha256=digest(reports[0]),
                        production_decision=report.get('status'),
                        candidates=report.get('advisory_candidates'),
                        note='Completion is not model accuracy or label agreement')
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired,BatchCancelled) as exc:
            detail=dict(error=type(exc).__name__,message=str(exc))
        rows.append(dict(**case,state=state,elapsed_seconds=time.monotonic()-started,detail=detail))
        # Persist partial progress for interruption/failure without touching source reports.
        (output/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
        if state!='REPLAY_COMPLETED':
            break
    final=source_fingerprint()
    result=dict(cases=rows,requested_cases=len(cases),code_config_before=initial,code_config_after=final,
                code_config_unchanged=initial==final,
                inference_asset_identity_complete=False,
                limitation='Code/config hashes do not include all model files or imported third-party libraries. No independent release certification.',
                fresh_capture=False,robot_command_sent=False,conveyor_command_sent=False)
    (output/'batch.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    previous=signal.signal(signal.SIGTERM,handle_termination)
    try:
        r=run(json.loads(args.manifest.read_text()),args.output)
    finally:
        signal.signal(signal.SIGTERM,previous)
    print(json.dumps(dict(output=str(args.output),completed=sum(c['state']=='REPLAY_COMPLETED' for c in r['cases']),
                          requested=r['requested_cases'],code_config_unchanged=r['code_config_unchanged'])))
    if len(r['cases']) != r['requested_cases'] or not r['code_config_unchanged'] or any(
            c['state'] != 'REPLAY_COMPLETED' for c in r['cases']):
        raise SystemExit(1)


if __name__=='__main__':
    main()
