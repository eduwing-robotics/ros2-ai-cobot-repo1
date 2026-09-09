"""Freeze development-only candidate criteria before a fresh physical test."""
import json
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', type=Path, default=ROOT/'runtime/inspection/patchcore/inductor_appearance_candidate_20260906')
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    payload = json.loads((experiment/'comparison.json').read_text())
    comparison = payload['results']['candidate'] if 'results' in payload else payload
    destination = experiment/'calibration_dataset/inductor/test/good'
    destination.mkdir(parents=True, exist_ok=True)
    for split in ['test/good', 'holdout/normal', 'fresh/normal']:
        for source in (experiment/'dataset/inductor'/split).glob('*.png'):
            shutil.copy2(source, destination/source.name)
    low, high = comparison['normal_max'], comparison['defect_min']
    if not low < high:
        raise RuntimeError('Development normal/defect scores overlap')
    payload = {'components': {'inductor': {'pass_max': low, 'fail_min': (low+high)/2,
                'authority': 'ADVISORY_ONLY'}},
               'policy': 'DEVELOPMENT_ONLY_NOT_AUTOMATIC_ACCEPTANCE',
               'source': str(experiment/'comparison.json'),
               'warning': 'Previous recent holdout is now development calibration data, not independent validation. New physical captures required. No certified surface-crack performance.'}
    (experiment/'models/decision_thresholds.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
