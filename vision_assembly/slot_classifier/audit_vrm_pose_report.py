"""Read-only pose arithmetic audit. Counterfactuals never change decisions."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def audit(path):
    data = path.read_bytes()
    report = json.loads(data)
    rows = []
    for slot in report['slots']:
        measured = slot['stages']['pose'].get('measured', {})
        if slot['component_type'] != 'VRM' or 'raw_offset_mm' not in measured:
            continue
        raw = np.asarray(measured['raw_offset_mm'])
        common = np.asarray(measured['common_bias_correction_mm'])
        reference = np.asarray(measured['slot_reference_correction_mm'])
        residual = raw - common - reference
        assert np.allclose(residual, measured['offset_mm'])
        assert np.isclose(np.linalg.norm(residual), measured['position_error_mm'])
        rows.append({'slot_id': slot['slot_id'], 'raw_offset_mm': raw.tolist(),
                     'reference_offset_mm': reference.tolist(),
                     'reported_error_mm': float(np.linalg.norm(residual)),
                     'without_reference_error_mm': float(np.linalg.norm(raw-common))})
    return {'source': str(path.resolve()), 'source_sha256': hashlib.sha256(data).hexdigest(),
            'common_bias': report['providers']['yolo']['common_projection_bias'],
            'rows': rows, 'arithmetic_verified': True,
            'restriction': 'Without-reference values are diagnostics, not revised decisions. '
                           'No evidence here establishes physical displacement or permits '
                           'lowering the minimum common-bias support.',
            'runtime_changed': False, 'robot_command_sent': False, 'conveyor_command_sent': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.report), indent=2))
