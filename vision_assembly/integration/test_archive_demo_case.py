import hashlib
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from archive_demo_case import archive


def source(tmp_path):
    folder=tmp_path/'source'; folder.mkdir()
    blob=b'\x89PNG\r\n\x1a\nexample-png'
    (folder/'02_annotated_report.png').write_bytes(blob)
    payload={'data':{'inspection_id':'demo','status':'COMPLETED',
        'result':{'decision':'UNKNOWN','findings':[]},
        'image':{'ready':True,'filename':'02_annotated_report.png','mime_type':'image/png','size_bytes':len(blob),
                 'sha256':hashlib.sha256(blob).hexdigest()}}}
    (folder/'inspection_result.json').write_text(json.dumps(payload))
    return folder


def test_preserve_unknown_and_original_bytes(tmp_path):
    src=source(tmp_path); out=tmp_path/'out'; archive(src,out)
    assert (src/'inspection_result.json').read_bytes()==(out/'inspection_result.json').read_bytes()
    assert (src/'02_annotated_report.png').read_bytes()==(out/'02_annotated_report.png').read_bytes()
    assert 'UNKNOWN' in (out/'index.html').read_text()
    with pytest.raises(FileExistsError): archive(src,out)


def test_corrupt_image_rejected(tmp_path):
    src=source(tmp_path); (src/'02_annotated_report.png').write_bytes(b'\x89PNG\r\n\x1a\nbad')
    with pytest.raises(ValueError,match='match'): archive(src,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def edit_payload(src, change):
    path=src/'inspection_result.json'
    payload=json.loads(path.read_text())
    change(payload['data'])
    path.write_text(json.dumps(payload))


def test_no_findings_does_not_become_pass(tmp_path):
    src=source(tmp_path); out=tmp_path/'out'
    archive(src,out)
    page=(out/'index.html').read_text()
    assert '기록된 검출 항목이 없습니다' in page
    assert '원본 최종 판정</span><strong>UNKNOWN</strong>' in page
    assert '실시간 화면 아님' in page
    assert '서버 전달 성공을 증명하지 않습니다' in page


def test_result_content_is_escaped(tmp_path):
    src=source(tmp_path); out=tmp_path/'out'
    malicious='<script>alert("oops")</script>'
    def change(data):
        data['inspection_id']=malicious
        data['result']['findings']=[dict(slot_code=malicious, primary_defect_name_ko='방향 오류',
            decision='UNKNOWN', authority='ADVISORY_ONLY', confirmed_defect=False,
            details=[malicious], measurements={'<key>':'<value>'})]
    edit_payload(src,change)
    archive(src,out)
    page=(out/'index.html').read_text()
    assert malicious not in page
    assert '&lt;script&gt;' in page
    assert '미확정' in page
    assert '<summary>근거 보기</summary>' in page


@pytest.mark.parametrize('status',['ACCEPTED','RUNNING','FAILED'])
def test_incomplete_results_rejected(tmp_path,status):
    src=source(tmp_path)
    edit_payload(src,lambda d:d.update(status=status))
    with pytest.raises(ValueError,match='completed'): archive(src,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_ready_flag_required(tmp_path):
    src=source(tmp_path)
    edit_payload(src,lambda d:d['image'].update(ready=False))
    with pytest.raises(ValueError,match='contract'): archive(src,tmp_path/'out')


def test_png_signature_checked_even_when_hash_matches(tmp_path):
    src=source(tmp_path); blob=b'not-an-image'
    (src/'02_annotated_report.png').write_bytes(blob)
    edit_payload(src,lambda d:d['image'].update(size_bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
    with pytest.raises(ValueError,match='PNG'): archive(src,tmp_path/'out')


def test_header_summary_uses_supplied_counts(tmp_path):
    src=source(tmp_path); out=tmp_path/'out'
    edit_payload(src,lambda d:d['result'].update(summary=dict(expected_slots=25,confirmed_defect_count=0,
        advisory_candidate_count=4,slot_decisions={'UNKNOWN':25})))
    archive(src,out)
    page=(out/'index.html').read_text()
    assert '확정 불량 항목</span><strong>0</strong>' in page
    assert '의심 후보 항목</span><strong>4</strong>' in page
    assert 'UNKNOWN 슬롯</span><strong>25</strong>' in page


def test_quality_and_hidden_signals_shown_without_promotion(tmp_path):
    src = source(tmp_path)
    def change(data):
        data['result']['diagnostics'] = {
            'capture_quality': {'status': 'RECAPTURE_RECOMMENDED', 'flags': ['GROSS_BLUR_OR_TEXTURE_LOSS']},
            'evidence_audit': {'undisplayed_count': 1, 'items': [dict(
                slot_id='hbm_01', stage='pose', raw_status='FAIL', authority='ADVISORY_ONLY',
                reason='<unverified>', displayed_as_candidate=False)]}}
        data['result']['diagnostics']['provider_health'] = {
            'unavailable_count': 1, 'unavailable': [dict(slot_id='ai_gpu', stage='surface', reason='GPU_UNAVAILABLE')]}
    edit_payload(src, change)
    archive(src, tmp_path/'out')
    page = (tmp_path/'out/index.html').read_text()
    assert '촬영 품질 의심' in page and 'hbm_01' in page and '&lt;unverified&gt;' in page
    assert 'GPU_UNAVAILABLE' in page and '실행 불가 검사 1개' in page
    assert '원본 최종 판정</span><strong>UNKNOWN</strong>' in page
