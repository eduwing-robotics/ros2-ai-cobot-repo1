"""Leave-scene-out descriptive edge envelopes, never production tolerances."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def evidence(current, references):
    refs = np.asarray(references, dtype=float)
    low, high = refs.min(axis=0), refs.max(axis=0)
    p = np.asarray(current, dtype=float)
    signed = np.where(p < low, p-low, np.where(p > high, p-high, 0))
    # Both opposing edges must move outside the observed range in the same direction.
    pair = []
    for a, b in ((0, 2), (1, 3)):
        pair.append(float(min(abs(signed[a]), abs(signed[b])))
                    if signed[a]*signed[b] > 0 else 0.)
    return dict(low=low.tolist(), high=high.tolist(), signed_excess_px=signed.tolist(),
                paired_excess_xy_px=pair, paired_excess_px=max(pair))


def main():
    directory = ROOT/'runtime/inspection/vrm_edge_profiles_regression_160027'
    source = json.loads((directory/'report.json').read_text())['rows']
    results = []
    for row in source:
        refs = [r for r in source if r['slot'] == row['slot'] and
                r['stamp'] != row['stamp'] and r['expected'] == 'PASS']
        if len(refs) < 3:
            continue
        positions = lambda r: [e['position'] for e in r['raw']]
        result = dict(stamp=row['stamp'], slot=row['slot'], expected=row['expected'],
            status='UNKNOWN', reference_stamps=[r['stamp'] for r in refs],
            **evidence(positions(row), [positions(r) for r in refs]))
        results.append(result)
    normals = [r['paired_excess_px'] for r in results if r['expected'] == 'PASS']
    defects = [r['paired_excess_px'] for r in results if r['expected'] == 'FAIL']
    report = dict(authority='ADVISORY_ONLY', runtime_enabled=False,
        note='Development-only leave-scene-out statistics. Reserved validation is not fitted into any deployable artifact. No threshold selected. Presence and rotation not assessed.',
        normal_max_excess_px=max(normals), defect_min_excess_px=min(defects),
        normal_count=len(normals), defect_count=len(defects),
        robot_command_sent=False, conveyor_command_sent=False, rows=results)
    (directory/'slot_envelopes.json').write_text(json.dumps(report, indent=2))
    print('normal max', max(normals), 'defect min', min(defects))
    for r in results:
        if r['expected']=='FAIL' or r['paired_excess_px']>0:
            print(r['stamp'],r['slot'],r['expected'],r['paired_excess_xy_px'])


if __name__ == '__main__':
    main()
