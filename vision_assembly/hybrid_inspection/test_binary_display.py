from copy import deepcopy

import numpy as np

import main


def test_operator_panels_are_binary_without_changing_raw_evidence(monkeypatch):
    texts = []
    original = main.cv2.putText

    def capture(image, text, *args, **kwargs):
        texts.append(text)
        return original(image, text, *args, **kwargs)

    monkeypatch.setattr(main.cv2, 'putText', capture)
    image = np.zeros((1266, 1600, 3), dtype=np.uint8)
    rows = [{'slot_id': str(i), 'status': 'UNKNOWN'} for i in range(25)]
    before = deepcopy(rows)
    policy = dict(mode='PROVISIONAL_BINARY_V1', validated=False, status='FAIL',
                  reasons=['DEFECT_CANDIDATE'])
    main._render_slot_diagnostic(image, [], rows, 'FAIL', .98, policy, [{'slot_id': '2'}])
    assert any('PASS 24   FAIL 1' in text for text in texts)
    main._render_evidence_report(image, image, image, [], [], 'UNKNOWN', .98,
                                {'vrm_01': {'codes': []}})
    assert all('UNKNOWN' not in text and 'UNCERTAIN' not in text for text in texts)
    assert rows == before
