"""Bounded JSON-only sidecar; never executes providers or promotes authority."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runtime/inspection/parallel_release_20260908/presence_direction/summary.json'
MAX_BYTES = 4 * 1024 * 1024
MAX_REPORTS = 64


def read_json(path):
    if path.suffix != '.json':
        raise ValueError('JSON only')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError(f'JSON byte bound exceeded: {path}')
    return json.loads(raw), dict(path=str(path.relative_to(ROOT)),
                                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def outcome(truth, status):
    if truth not in {'NORMAL', 'DEFECT', 'PRESENT', 'EMPTY'}:
        return 'UNLABELLED'
    if status not in {'PASS', 'FAIL'}:
        return 'ABSTAIN'
    defect = truth in {'DEFECT', 'EMPTY'}
    return ('TP' if defect else 'FP') if status == 'FAIL' else ('FN' if defect else 'TN')


def counts(rows):
    c = Counter(r['outcome'] for r in rows)
    return dict(total=len(rows), **{k: c[k] for k in
                ('TP', 'TN', 'FP', 'FN', 'ABSTAIN', 'UNLABELLED')},
                unique_inputs=len({r['input_sha256'] for r in rows}),
                unit='slot-observations, not independent captures')


def build_summary():
    provenance = []

    def load(path):
        data, prov = read_json(path)
        provenance.append(prov)
        return data

    contract = load(ROOT / 'vision_assembly/config/inspection_fusion_contract.json')
    base = ROOT / 'runtime/inspection'
    confirmed = base / 'confirmed_controls_20260908'
    vrm = base / 'vrm_controls_20260908'
    a = load(confirmed / 'audit.json')
    b = load(vrm / 'audit.json')
    extended = load(vrm / 'extended_normal_summary.json')
    labels = {}
    archived = []
    for r in a['rows']:
        if r['track'] != 'direction':
            continue
        key = (r['input_sha256'], r['slot'], 'direction')
        labels[key] = (r['truth'], r['provenance'])
        archived.append(dict(input_sha256=key[0], slot=key[1], track=key[2],
                             truth=r['truth'], status=r['archived_status'],
                             outcome=outcome(r['truth'], r['archived_status']),
                             report=r['report'], report_sha256=r['report_sha256'],
                             provenance=r['provenance']))
    for r in b['rows']:
        labels[(r['source_hash'], r['slot'], 'presence')] = (r['presence_truth'], r['label_source'])
    for r in extended['rows']:
        labels[(r['input_sha256'], r['slot'], 'presence')] = (r['truth'], r['provenance'])

    paths = sorted([*confirmed.glob('*/*/hybrid_report.json'),
                    *vrm.glob('*/*/hybrid_report.json')])
    if len(paths) > MAX_REPORTS:
        raise ValueError('report count bound exceeded')
    current = []
    status_inventory = Counter()
    authority_inventory = Counter()
    # Read the two audit families concurrently, bounded to four JSON readers.
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(read_json, paths))
    for report, prov in reports:
        provenance.append(prov)
        digest = report.get('input_sha256')
        for slot in report['slots']:
            for track, stage_key in [('presence', 'presence'), ('direction', 'orientation')]:
                stage = slot.get('stages', {}).get(stage_key, {})
                status = stage.get('status', 'UNKNOWN')
                authority = stage.get('authority', 'UNAVAILABLE')
                status_inventory[f'{track}:{status}'] += 1
                authority_inventory[f'{track}:{authority}'] += 1
                key = (digest, slot['slot_id'], track)
                if key not in labels:
                    continue
                truth, label_source = labels[key]
                current.append(dict(input_sha256=digest, slot=key[1], track=track,
                                    truth=truth, status=status, authority=authority,
                                    reason=stage.get('reason'), outcome=outcome(truth, status),
                                    report=prov['path'], report_sha256=prov['sha256'],
                                    provenance=label_source, board_status=report.get('status'),
                                    split='reused_development_control'))

    model_dir = ROOT / 'vision_assembly/slot_classifier/models'
    metadata_paths = [model_dir / 'vrm_state.json',
                      *sorted((model_dir / 'component_presence_candidate').glob('*_presence.json')),
                      base / 'vrm_presence_context_stress_20260905/evaluation.json']
    metadata = []
    for path in metadata_paths:
        d = load(path)
        metadata.append(dict(path=str(path.relative_to(ROOT)),
                             authority=d.get('authority'), validated=d.get('validated'),
                             validation_policy=d.get('validation_policy', d.get('validation')),
                             session_role=d.get('session_role'),
                             deployment_promotion=d.get('deployment_promotion'),
                             independent_validated_authority_evidence=False,
                             reason='No verified independent release-validation artifact in this bounded audit; metadata metrics are not authority.'))
    grouped = {}
    for mode, rows in [('archived_provider', archived), ('saved_newer_replay', current)]:
        grouped[mode] = {track: counts([r for r in rows if r['track'] == track])
                         for track in ('presence', 'direction')}
    covered = {(r['input_sha256'], r['slot'], r['track']) for r in current}
    return dict(schema_version=1, contract_id=contract['contract_id'],
                release_readiness='NOT_READY', independent_validated_authority_evidence=False,
                authority_conclusion_scope='Only the bounded saved audits, replay stages and listed current metadata; not a repository-wide proof of absence.',
                development_reuse=True, independent_accuracy_claim=False,
                current_provider_execution=False, current_runtime_equivalence_verified=False,
                counts=grouped, archived_rows=archived, saved_newer_replay_rows=current,
                missing_labelled_replays=[list(k) for k in sorted(set(labels) - covered)],
                saved_replay_inventory=dict(reports=len(reports), statuses=dict(status_inventory),
                                            authorities=dict(authority_inventory)),
                current_provider_metadata=metadata, provenance=provenance,
                limits=dict(max_json_bytes=MAX_BYTES, max_reports=MAX_REPORTS),
                limitations=[
                    'Newer means saved 20260908 replay, not execution of current checkout; no code/model identity proof.',
                    'Repeated replays of the same input/slot are repeated observations, not independent samples.',
                    'Input image hashes and historical label provenance are inherited, not rehashed or relabelled.',
                    'Only explicitly labelled controls enter confusion counts; other slots are status inventory only.',
                    'VRM rotation/position pose FAIL is not independent orientation validation and is excluded from direction counts.',
                    'Non-VRM presence and GPU/HBM direction lack labelled controls in these audit families.',
                    'No model scores, display codes, holdout metrics or control success grant PASS/FAIL authority.'],
                runtime_changed=False, robot_command_sent=False, conveyor_command_sent=False,
                fresh_capture=False, network_used=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(OUT.parent.resolve()):
        parser.error('output must stay in owned presence_direction artifacts directory')
    summary = build_summary()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(release_readiness=summary['release_readiness'], counts=summary['counts'],
                          output=str(args.output))))


if __name__ == '__main__':
    main()
