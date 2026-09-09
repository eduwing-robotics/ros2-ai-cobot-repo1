"""Replay advisory nomination only; historical evidence is not fresh inference."""
import json
from pathlib import Path
import main as pipeline


def run():
    root = Path(__file__).resolve().parents[2]
    predicate = pipeline.vrm05_conflicting_pose
    changes = []
    count = 0
    for path in sorted((root / 'runtime/inspection').glob('**/hybrid_report.json')):
        data = json.loads(path.read_text())
        rows = data.get('slots', [])
        if not rows:
            continue
        count += 1
        try:
            pipeline.vrm05_conflicting_pose = lambda row: False
            before = pipeline.build_advisory_candidates(rows)
            pipeline.vrm05_conflicting_pose = predicate
            after = pipeline.build_advisory_candidates(rows)
        finally:
            pipeline.vrm05_conflicting_pose = predicate
        if before != after:
            changes.append(dict(report=str(path), image=data.get('input_image'),
                before=before, after=after))
    out = root / 'runtime/inspection/vrm05_abstention_history_20260907.json'
    out.write_text(json.dumps(dict(reports=count, changes=changes,
        limitation='Historical stage evidence, mixed model versions and repeated images. Not fresh inference or independent labelled sensitivity.'), indent=2))
    images = sorted({r['image'] for r in changes if r['image']})
    print(json.dumps(dict(reports=count, changed_reports=len(changes),
                         changed_images=images, artifact=str(out)), indent=2))


if __name__ == '__main__':
    run()
