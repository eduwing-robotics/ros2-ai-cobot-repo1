from copy import deepcopy
import hashlib
import sys
from pathlib import Path
from PIL import Image
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from countermeasure_image import render_card, render_overview


def test_overview_multiple_findings_preserves_evidence(tmp_path):
    board=Image.new('RGB',(1600,1266),(33,44,55));before=board.tobytes()
    findings=[dict(finding(),slot_id='smd_capacitor_01'),
              dict(finding(),slot_id='vrm_03',slot_code='VRM-03',
                   confirmed_defect=True,authority='AUTHORITATIVE')]
    original=deepcopy(findings)
    info=render_overview(board,findings,{'smd_capacitor_01':[1200,500,60,100],
        'vrm_03':[100,700,100,140]},tmp_path/'overview.png')
    assert Image.open(tmp_path/'overview.png').size==(1600,1266)
    assert info['layout']=='PANEL_FREE_WHOLE_BOARD'
    assert [r['number'] for r in info['findings']]==[1,2]
    assert [r['confirmed_defect'] for r in info['findings']]==[False,True]
    assert all(r['located'] for r in info['findings'])
    assert findings==original and board.tobytes()==before


def test_overview_no_candidates_not_pass_and_missing_geometry(tmp_path):
    board=Image.new('RGB',(1600,1266))
    info=render_overview(board,[],{},tmp_path/'empty.png')
    assert info['decision']=='UNKNOWN' and info['findings']==[]
    info=render_overview(board,[dict(finding(),slot_id='missing')],{},tmp_path/'missing.png')
    assert info['findings'][0]['located'] is False


def finding():
    return dict(slot_code='CAP-01',primary_defect_name_ko='위치 오류',
                confirmed_defect=False,authority='ADVISORY_ONLY')


def test_card_is_readable_derivative_not_new_verdict(tmp_path):
    board=Image.new('RGB',(1600,1266),(33,44,55));before=board.tobytes()
    f=finding();old=deepcopy(f)
    output=tmp_path/'card.png'
    info=render_card(board,[1270,1080,60,40],f,output)
    assert Image.open(output).size==(1200,950)
    assert info['confirmed_defect'] is False
    assert board.tobytes()==before and f==old
    assert output.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'


@pytest.mark.parametrize('geometry',[[0,0,10,10],[20,20,-1,2],[float('nan'),50,10,10]])
def test_invalid_crop_fails_closed(tmp_path,geometry):
    with pytest.raises(ValueError):
        render_card(Image.new('RGB',(100,100)),geometry,finding(),tmp_path/'no.png')
    assert not (tmp_path/'no.png').exists()


def test_claim_alone_cannot_color_as_confirmed(tmp_path):
    f=finding();f['confirmed_defect']=True
    assert not render_card(Image.new('RGB',(200,200)),[100,100,20,20],f,tmp_path/'a.png')['confirmed_defect']


def test_http_countermeasure_roundtrip(tmp_path):
    import threading, urllib.request, urllib.error, uuid
    import inspection_api as api
    iid=str(uuid.uuid4());directory=tmp_path/iid;directory.mkdir()
    original=b'original';detail=b'detail'
    (directory/api.IMAGE_NAME).write_bytes(original)
    (directory/'countermeasure_CAP-01.png').write_bytes(detail)
    store=api.Store(tmp_path,lambda:False,None)
    store.records[iid]=dict(inspection_id=iid,status='COMPLETED',image=dict(ready=True,
        sha256=hashlib.sha256(original).hexdigest(),countermeasure_views=[dict(slot_code='CAP-01',
        filename='countermeasure_CAP-01.png',sha256=hashlib.sha256(detail).hexdigest()),
        dict(slot_code='ALL',filename='countermeasure_CAP-01.png',sha256=hashlib.sha256(detail).hexdigest())]))
    token='test-only-token'*4
    server=api.ThreadingHTTPServer(('127.0.0.1',0),api.handler(store,token))
    thread=threading.Thread(target=server.serve_forever);thread.start()
    base=f'http://127.0.0.1:{server.server_port}/api/v1/inspections/{iid}/image'
    def fetch(query='',auth=True):
        return urllib.request.urlopen(urllib.request.Request(base+query,
            headers={'Authorization':'Bearer '+token} if auth else {}),timeout=3)
    try:
        with fetch() as response: assert response.read()==original
        with fetch('?view=countermeasure&slot=CAP-01') as response: assert response.read()==detail
        with fetch('?view=countermeasure&slot=ALL') as response: assert response.read()==detail
        for query,code in [('?view=countermeasure&slot=CAP-02',404),
                           ('?view=countermeasure&slot=CAP-01&slot=CAP-02',400),
                           ('?view=countermeasure&slot=../../secret',404)]:
            with pytest.raises(urllib.error.HTTPError) as exc: fetch(query)
            assert exc.value.code==code
        with pytest.raises(urllib.error.HTTPError) as exc: fetch('?view=countermeasure&slot=CAP-01',False)
        assert exc.value.code==401
        (directory/'countermeasure_CAP-01.png').write_bytes(b'changed')
        with pytest.raises(urllib.error.HTTPError) as exc: fetch('?view=countermeasure&slot=CAP-01')
        assert exc.value.code==409
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
