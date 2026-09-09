"""Compare saved full-model reports and package a non-production replay viewer.

No camera, HTTP server, model fit, motion command or production IDs are used.
"""
import argparse
import json
from pathlib import Path
import shutil
import uuid

from archive_demo_case import archive
from inspection_api import prepare_result, IMAGE_NAME


def review(baseline, current, output):
    old, new = (json.loads(path.read_text()) for path in (baseline, current))
    if old['input_sha256'] != new['input_sha256']:
        raise ValueError('Cannot claim same-image replay with different sources')
    old_slots = {r['slot_id']: r for r in old['slots']}
    score_changes = {}
    for slot in new['slots']:
        before = old_slots[slot['slot_id']]['stages']['surface'].get('score')
        after = slot['stages']['surface'].get('score')
        score_changes[slot['slot_id']] = abs(before - after) if before is not None and after is not None else None
    def candidates(report):
        return {r['slot_id']: r['codes'] for r in report['advisory_candidates']['items']}
    result = dict(baseline=str(baseline.resolve()), current=str(current.resolve()),
                  source_sha256=new['input_sha256'], old_decision=old['status'], new_decision=new['status'],
                  old_candidates=candidates(old), new_candidates=candidates(new),
                  candidates_unchanged=candidates(old) == candidates(new),
                  surface_absolute_score_changes=score_changes,
                  capture_quality=new.get('capture_quality'), provider_health=new.get('provider_health'),
                  new_capture=False, independent_accuracy_test=False, model_training=False)
    output.mkdir(parents=True, exist_ok=False)
    (output/'comparison.json').write_text(json.dumps(result, indent=2))
    local_archive = output/'local_archive'
    local_archive.mkdir()
    request = dict(inspection_id=str(uuid.uuid4()), job_id=None, unit_id=None)
    compact, image = prepare_result(current, local_archive, request)
    image['path'] = None
    pair = output/'pair'
    pair.mkdir()
    shutil.copyfile(local_archive/IMAGE_NAME, pair/IMAGE_NAME)
    payload = dict(test_only=True, transport='MANUAL_FILE_PAIR', production_binding='UNBOUND',
                   capture_performed=False, saved_replay_source=str(current.resolve()),
                   data=dict(request, status='COMPLETED', result=compact, image=image))
    (pair/'inspection_result.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    viewer = archive(pair, output/'viewer')
    print(json.dumps(dict(candidates_unchanged=result['candidates_unchanged'],
                          all_surface_scores_available=all(v is not None for v in score_changes.values()),
                          decision=compact['decision'], viewer=str(viewer)), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    review(args.baseline, args.current, args.output)
