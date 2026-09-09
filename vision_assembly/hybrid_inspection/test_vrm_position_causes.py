from audit_vrm_position_causes import describe


def test_pixel_reference_does_not_become_measured_clearance():
    r = describe({'measured': {'position_error_mm': 1.02}},
                 {'right_excess_px': [12,14], 'codes':['RIGHT?']})
    assert r['required_right_wall_clearance_mm'] == 1.0
    assert r['measured_right_wall_clearance_mm'] is None
    assert r['clearance_status'] == 'UNKNOWN'


def test_no_warning_does_not_prove_clearance():
    assert describe({}, {})['clearance_status'] == 'UNKNOWN'
