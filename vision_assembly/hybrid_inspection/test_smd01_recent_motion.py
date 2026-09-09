from audit_smd01_recent_motion import peer_comparison


def report(values):
    return {'slots': [{'slot_id': key, 'stages': {'pose': {'measured': {'raw_offset_mm': value}}}}
                      for key, value in values.items()]}


def test_target_does_not_bias_peer_median():
    a = report({'smd_capacitor_01': [0, 0], 'a': [0, 0], 'b': [0, 0]})
    b = report({'smd_capacitor_01': [0, 10], 'a': [0, 1], 'b': [0, 1]})
    r = peer_comparison(a, b)
    assert r['peer_median_delta_mm'] == [0, 1]
    assert r['target_minus_peer_median_mm'] == [0, 9]


def test_no_peer_is_not_zero_uncertainty():
    r = report({'smd_capacitor_01': [0, 0]})
    assert peer_comparison(r, r)['peer_median_delta_mm'] is None
