"""Compare saved raw offsets and peer drift; never correct production coordinates."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    'normal': 'smd01_fresh_validation_20260908_131643/20260908_131741_747610',
    'lip': 'smd01_lip_validation_20260908_132035/20260908_132108_768224',
    'restored': 'smd01_recovery_20260908_132402/20260908_132425_543863',
}


def peer_comparison(before, after, target='smd_capacitor_01'):
    def offsets(report):
        out = {}
        for row in report['slots']:
            raw = row.get('stages', {}).get('pose', {}).get('measured', {}).get('raw_offset_mm')
            if raw is not None and len(raw) == 2:
                import math
                if all(isinstance(v, (int, float)) and math.isfinite(v) for v in raw):
                    out[row['slot_id']] = raw
        return out
    a, b = offsets(before), offsets(after)
    target_delta = [b[target][i]-a[target][i] for i in range(2)]
    peers = {sid: [b[sid][i]-a[sid][i] for i in range(2)]
             for sid in sorted(a.keys() & b.keys()) if sid != target}
    drift = [median(v[i] for v in peers.values()) for i in range(2)] if peers else None
    return dict(target_delta_mm=target_delta, peer_count=len(peers), peer_deltas_mm=peers,
                peer_median_delta_mm=drift,
                target_minus_peer_median_mm=([target_delta[i]-drift[i] for i in range(2)]
                                            if drift else None))


def run(output):
    reports, provenance = {}, {}
    for key, relative in CASES.items():
        path = ROOT / 'runtime/inspection' / relative / 'hybrid_report.json'
        blob = path.read_bytes()
        report = json.loads(blob)
        source = Path(report['input_image'])
        if not source.is_absolute():
            source = ROOT / source
        if hashlib.sha256(source.read_bytes()).hexdigest() != report['input_sha256']:
            raise ValueError('Image hash mismatch')
        reports[key] = report
        row = next(s for s in report['slots'] if s['slot_id'] == 'smd_capacitor_01')
        provenance[key] = dict(report=str(path), report_sha256=hashlib.sha256(blob).hexdigest(),
                               image_sha256=report['input_sha256'],
                               measured=row['stages']['pose']['measured'])
    result = dict(inputs=provenance,
                  normal_to_lip=peer_comparison(reports['normal'], reports['lip']),
                  normal_to_restored=peer_comparison(reports['normal'], reports['restored']),
                  limitations=['Peer immobility is assumed, not measured.',
                               'Median drift mixes registration, segmentation and physical movement.',
                               'Algorithm mm is not a calibrated physical height measurement.',
                               'No peer correction applied to runtime; defects must not be normalized away.'],
                  runtime_changed=False, authority='ADVISORY_ONLY')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: {a: b for a, b in v.items() if a != 'peer_deltas_mm'}
                      for k, v in result.items() if k.startswith('normal_to_')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)
