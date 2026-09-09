"""Small-sheet evidence card: registered pixels, locator and unambiguous status.

No inference, defect painting, synthetic detail or changes to the source report.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def render_overview(board, findings, geometry, destination, decision='UNKNOWN'):
    """Panel-free evidence photo fitted to the v2 worksheet picture aspect ratio."""
    canvas = Image.new('RGB', (1600, 1266), 'white')
    draw = ImageDraw.Draw(canvas)
    def text(x, y, value, size=30, color='#172235'):
        draw.text((x,y), str(value), font=ImageFont.truetype(FONT,size), fill=color)
    thumb = ImageOps.contain(board.convert('RGB'), canvas.size)
    x,y=(canvas.width-thumb.width)//2,(canvas.height-thumb.height)//2
    canvas.paste(thumb,(x,y))
    sx,sy=thumb.width/board.width,thumb.height/board.height
    rows=[]
    for index,f in enumerate(findings,1):
        confirmed=f.get('confirmed_defect') is True and f.get('authority')=='AUTHORITATIVE'
        color='#D52527' if confirmed else '#FFAB16'
        g=geometry.get(f['slot_id'])
        located=False
        if g is not None:
            cx,cy,w,h=map(float,g)
            if all(math.isfinite(v) for v in (cx,cy,w,h)) and w>0 and h>0 and 0<=cx<board.width and 0<=cy<board.height:
                box=(x+max(0,cx-w/2)*sx,y+max(0,cy-h/2)*sy,
                     x+min(board.width,cx+w/2)*sx,y+min(board.height,cy+h/2)*sy)
                draw.rectangle(box,outline='#111111',width=12)
                draw.rectangle(box,outline=color,width=8)
                # Label inside upper left of its own slot, never on a normal slot.
                bx,by=box[:2]
                draw.rounded_rectangle((bx,by,bx+48,by+43),radius=7,fill=color,outline='black',width=2)
                text(bx+5,by-1,index,29,'#111111')
                located=True
        names=list(dict.fromkeys(d['defect_name_ko'] for d in f.get('defect_codes',[]) if d.get('defect_name_ko')))
        label=' · '.join(names) or f.get('primary_defect_name_ko','검사 확인 필요')
        rows.append(dict(number=index,slot_code=f['slot_code'],located=located,
                         confirmed_defect=confirmed,defect_name_ko=label))
    destination=Path(destination);tmp=destination.with_suffix('.tmp')
    canvas.save(tmp,format='PNG')
    with tmp.open('rb') as stream: os.fsync(stream.fileno())
    os.replace(tmp,destination)
    return dict(layout='PANEL_FREE_WHOLE_BOARD',width=1600,height=1266,
                findings=rows,heatmap='NOT_SYNTHESIZED',decision=decision,
                legend={'red':'CONFIRMED_AUTHORITATIVE','amber':'UNVERIFIED_CANDIDATE'},
                worksheet_picture_emu=[2022282,1600200])


def render_card(board, geometry, finding, destination):
    cx,cy,w,h = map(float, geometry)
    if not all(math.isfinite(v) for v in (cx,cy,w,h)) or w<=0 or h<=0:
        raise ValueError('Invalid fixed-slot geometry')
    bw,bh=board.size
    if not (0<=cx-w/2<cx+w/2<=bw and 0<=cy-h/2<cy+h/2<=bh):
        raise ValueError('Fixed slot outside registered image')
    confirmed = finding.get('confirmed_defect') is True and finding.get('authority')=='AUTHORITATIVE'
    color = '#B42318' if confirmed else '#A15C00'
    canvas=Image.new('RGB',(1200,950),'white');draw=ImageDraw.Draw(canvas)
    def text(pos,value,size,fill='#142132'):
        draw.text(pos,value,font=ImageFont.truetype(FONT,size),fill=fill)
    draw.rectangle((0,0,1200,112),fill=color)
    text((28,12),finding['slot_code'],68,'white')
    text((560,23),'불량 확정' if confirmed else '미확정 후보',54,'white')
    # Explicit locator; its rectangle is nominal slot geometry, not a defect mask.
    thumb=ImageOps.contain(board.convert('RGB'),(316,565))
    tx,ty=20,190+(565-thumb.height)//2
    canvas.paste(thumb,(tx,ty)); sx=thumb.width/bw;sy=thumb.height/bh
    box=(tx+(cx-w/2)*sx,ty+(cy-h/2)*sy,tx+(cx+w/2)*sx,ty+(cy+h/2)*sy)
    draw.rectangle(box,outline='#FF3030',width=5)
    mx,my=tx+cx*sx,ty+cy*sy
    draw.line((mx+8,my,337,my),fill='#FF3030',width=5)
    text((24,123),'위치',42)
    text((380,123),'대상 부품 확대',42)
    margin=min(80.,max(w,h)*.40)
    crop_box=(max(0,int(cx-w/2-margin)),max(0,int(cy-h/2-margin)),
              min(bw,math.ceil(cx+w/2+margin)),min(bh,math.ceil(cy+h/2+margin)))
    crop=board.crop(crop_box).convert('RGB')
    zoom=ImageOps.contain(crop,(818,560),method=Image.Resampling.BICUBIC)
    zx=360+(818-zoom.width)//2;zy=190+(560-zoom.height)//2
    draw.rectangle((355,183,1182,757),outline='#CBD5E1',width=3)
    canvas.paste(zoom,(zx,zy))
    label=finding.get('primary_defect_name_ko','검사 확인 필요')
    suffix='' if confirmed else ' · 의심'
    text((28,774),label+suffix,58,color)
    text((28,865),'테두리: 검사 위치 | 확대: 원본 픽셀',35)
    destination=Path(destination)
    tmp=destination.with_suffix('.tmp')
    canvas.save(tmp,format='PNG')
    with tmp.open('rb') as stream: os.fsync(stream.fileno())
    os.replace(tmp,destination)
    return dict(crop_xyxy=list(crop_box),geometry_cxcywh=[cx,cy,w,h],
                confirmed_defect=confirmed,width=1200,height=950)


def prepare_views(report_path, package, payload, directory):
    """Use frozen package pixels; old reports need their saved geometry snapshot."""
    raw=json.loads((package/'raw/hybrid_report.json').read_text())
    registered=next((im for im in payload['images'] if im['role']=='registered_board'),None)
    if registered is None or not raw.get('registration',{}).get('alignment_valid'):
        return [], 'REGISTERED_IMAGE_UNAVAILABLE'
    board_path=package/registered['file']
    if hashlib.sha256(board_path.read_bytes()).hexdigest()!=registered['sha256']:
        raise ValueError('Registered image integrity error')
    geometry={s['slot_id']:s['fixed_slot_geometry'] for s in raw['slots'] if s.get('fixed_slot_geometry')}
    basis={sid:'SAVED_FIXED_SLOT' for sid in geometry}
    legacy=Path(report_path).parent/'geometry_reference.json'
    if not geometry and legacy.is_file():
        geometry=json.loads(legacy.read_text()).get('slots',{})
        basis={sid:'SAVED_GEOMETRY_SNAPSHOT' for sid in geometry}
    # Legacy reports lack ROI dimensions. A display window about the archived
    # expected center is NOT a reconstructed part/socket outline or measurement.
    for slot in raw['slots']:
        center=(slot.get('stages',{}).get('pose',{}).get('measured') or {}).get('expected_center_px')
        if slot['slot_id'] not in geometry and isinstance(center,list) and len(center)==2:
            geometry[slot['slot_id']]=[*center,128,128]
            basis[slot['slot_id']]='ARCHIVED_CENTER_DISPLAY_WINDOW_NOT_PART_OUTLINE'
    board=Image.open(board_path).convert('RGB');views=[]
    summary_name='countermeasure_ALL.png'
    summary_info=render_overview(board,payload['findings'],geometry,directory/summary_name,
                               payload.get('overall',{}).get('decision','UNKNOWN'))
    summary_blob=(directory/summary_name).read_bytes()
    views.append(dict(slot_code='ALL',filename=summary_name,ready=True,mime_type='image/png',
        sha256=hashlib.sha256(summary_blob).hexdigest(),size_bytes=len(summary_blob),
        path=f"/api/v1/inspections/{payload['inspection_id']}/image?view=countermeasure&slot=ALL",
        rendering=summary_info))
    for finding in payload['findings']:
        sid=finding['slot_id'];code=finding['slot_code']
        if sid not in geometry: continue
        if not re.fullmatch(r'[A-Z]+-\d{2}',code): raise ValueError('Invalid slot code')
        name=f'countermeasure_{code}.png'
        info=render_card(board,geometry[sid],finding,directory/name)
        info['geometry_basis']=basis[sid]
        blob=(directory/name).read_bytes()
        views.append(dict(slot_code=code,filename=name,ready=True,mime_type='image/png',
            sha256=hashlib.sha256(blob).hexdigest(),size_bytes=len(blob),
            path=f"/api/v1/inspections/{payload['inspection_id']}/image?view=countermeasure&slot={code}",
            rendering=info))
    return views, 'READY' if len(views)-1==len(payload['findings']) else 'SOME_SLOT_GEOMETRY_UNAVAILABLE'
