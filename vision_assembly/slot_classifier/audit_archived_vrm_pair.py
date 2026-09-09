"""Check exported/native seating parity and score ordering on a held-out pair."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    directory = ROOT / 'runtime/inspection/vrm_seating_pairs'
    exported = json.loads((directory / 'frozen_pair_check.json').read_text())['rows']
    reports = [json.loads((directory / name).read_text()) for name in
               ('normal_spatial_check.json', 'lip_spatial_check.json')]
    errors = []
    for original, native in zip(exported, reports):
        assert original['scene']['image_sha256'] == native['image_sha256']
        score = next(r['seating_score'] for r in native['candidates'][0]['rows']
                     if r['slot'] == 'vrm_05')
        errors.append(abs(score - original['result']['probabilities']['SEATING']))
    assert max(errors) < 1e-5, 'Export/input-path discrepancy requires investigation'
    candidates = []
    for normal, lip in zip(*(report['candidates'] for report in reports)):
        assert normal['sha256'] == lip['sha256']
        scores = [next(r['seating_score'] for r in c['rows'] if r['slot'] == 'vrm_05')
                  for c in (normal, lip)]
        candidates.append(dict(model=normal['candidate'], sha256=normal['sha256'],
            flat_score=scores[0], lip_score=scores[1], correct_order=scores[1] > scores[0],
            high_score_threshold_can_separate_pair=scores[1] > scores[0]))
    result = dict(export_native_max_error=max(errors), candidates=candidates,
        conclusion='Both frozen candidates reverse this pair; export mismatch is not supported. '
                   'Feature/training generalization remains unresolved; no fitted threshold.',
        limitation='Two user-labelled scenes only; not proof of physical height or a unique root cause.',
        training_performed=False, runtime_changed=False,
        robot_command_sent=False, conveyor_command_sent=False)
    (directory / 'pair_failure_audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
