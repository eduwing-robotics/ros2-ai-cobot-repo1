"""Prepare a non-production JSON/PNG pair from a completed manual capture event."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from inspection_api import ROOT, IMAGE_NAME, prepare_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True, type=Path)
    args = parser.parse_args()
    event = json.loads(args.event.read_text())
    if event['pipeline_status'] != 'COMPLETED':
        raise RuntimeError('Capture and inspection must finish first')
    request = dict(inspection_id=str(uuid.uuid4()), job_id=None, unit_id=None)
    staging = ROOT/'runtime/inspection/manual_handoff_archive'/request['inspection_id']
    staging.mkdir(parents=True, exist_ok=False)
    result, image = prepare_result(event['report'], staging, request)
    # This pair has no registered API request or fabricated production identity.
    image['path'] = None
    output = ROOT/'runtime/inspection/team_json_png'/request['inspection_id']
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(staging/IMAGE_NAME, output/IMAGE_NAME)
    for view in image.get('countermeasure_views', []):
        shutil.copyfile(staging/view['filename'], output/view['filename'])
        view['path'] = None  # This manual package has no registered API request.
    if hashlib.sha256((output/IMAGE_NAME).read_bytes()).hexdigest() != image['sha256']:
        raise RuntimeError('Copied image integrity mismatch')
    response = dict(test_only=True, transport='MANUAL_FILE_PAIR',
        production_binding='UNBOUND',
        data=dict(request, status='COMPLETED', result=result, image=image))
    (output/'inspection_result.json').write_text(
        json.dumps(response, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(output)
    print(json.dumps(dict(decision=result['decision'], summary=result['summary']), ensure_ascii=False))


if __name__ == '__main__':
    main()
