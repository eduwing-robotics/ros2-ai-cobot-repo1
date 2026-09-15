"""Validate and fingerprint immutable execution-to-observation correspondence."""
import hashlib
import json

IDENTITY_FIELDS = ('source_id','tray_registration_id','source_observation_id',
                   'calibration_instance_index','source_identity_scope')
CORRELATION_FIELDS = ('job_id','part_id','source_index','slot_code','order')


def validate_source_bindings(payload):
    parts, slots = payload.get('parts'), payload.get('slots')
    if not isinstance(parts, list) or not parts or not isinstance(slots, list) or len(parts) != len(slots):
        raise ValueError('source binding requires complete part/slot correspondence')
    seen_source, seen_index, seen_slot, seen_calibration = set(), set(), set(), set()
    rows = []
    for row in parts:
        if any(not isinstance(row.get(k),str) or not row[k].strip()
               for k in ('source_id','tray_registration_id','source_observation_id','part_id','slot_code')):
            raise ValueError('source binding identity missing')
        if row.get('job_id') != payload.get('job_id') or type(row.get('source_index')) is not int or row['source_index'] < 1:
            raise ValueError('source binding job/index invalid')
        calibration_index = row.get('calibration_instance_index')
        if type(calibration_index) is not int or calibration_index < 1:
            raise ValueError('source binding calibration index missing')
        source = (row['tray_registration_id'], row['source_id'])
        index = (row['tray_registration_id'], row['source_observation_id'], row['part_id'], row['source_index'])
        calibration = (row['tray_registration_id'],row['source_observation_id'],row['part_id'],calibration_index)
        if source in seen_source or index in seen_index or row['slot_code'] in seen_slot or calibration in seen_calibration:
            raise ValueError('source binding is ambiguous or duplicated')
        seen_source.add(source);seen_index.add(index);seen_slot.add(row['slot_code']);seen_calibration.add(calibration)
        matches = [s for s in slots if s.get('slot_code') == row['slot_code']]
        if len(matches) != 1 or any(matches[0].get(k) != row.get(k) for k in IDENTITY_FIELDS + CORRELATION_FIELDS):
            raise ValueError('Pick/Place source binding mismatch')
        rows.append({k:row.get(k) for k in IDENTITY_FIELDS + CORRELATION_FIELDS})
    return hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['slot_code']),sort_keys=True).encode()).hexdigest()


def observation_source_id(registration_id, observation_id, part_type, calibration_index):
    if (any(not isinstance(v,str) or not v.strip() for v in (registration_id,observation_id,part_type))
            or type(calibration_index) is not int or calibration_index < 1):
        raise ValueError('cannot generate source ID without unique observation coordinates')
    token = json.dumps([registration_id,observation_id,part_type,calibration_index],separators=(',', ':'))
    return 'observation:' + hashlib.sha256(token.encode()).hexdigest()
