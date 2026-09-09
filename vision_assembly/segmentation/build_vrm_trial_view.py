"""Self-contained comparison of observed masks, never a clearance verdict."""
import base64
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    output=base/'placement_comparison.html'
    if output.exists():
        raise FileExistsError(output)
    records=[];sections=[]
    for stamp,label in [('153918','왼쪽 배치 기준'),('155131','오른쪽 배치'),('161036','대략 중앙 배치 — 정확한 중앙 아님')]:
        folder=base/f'fresh_s22_inspection_roi_20260906_{stamp}_last'
        report=json.loads((folder/'report.json').read_text())
        if report['weights_sha256']!='98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc':
            raise ValueError('Checkpoint mismatch')
        records.append({r['slot']:r['primary'] for r in report['rows']})
        image=base64.b64encode((folder/f's22_inspection_roi_20260906_{stamp}.jpg').read_bytes()).decode()
        sections.append(f'<section><h2>{html.escape(label)} · {stamp}</h2><img alt="원본과 외곽 후보 비교" src="data:image/jpeg;base64,{image}"></section>')
    table=[]
    for slot,a in records[0].items():
        values=[]
        for record in records[1:]:
            b=record[slot]
            values.append(f'{b["center_px"][0]-a["center_px"][0]:+.2f} px' if a and b else '측정 없음')
        table.append(f'<tr><td>{html.escape(slot)}</td><td>{values[0]}</td><td>{values[1]}</td><td>UNKNOWN</td></tr>')
    document='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VRM 배치 비교</title>
<style>body{background:#10151e;color:#e9eef5;font:16px sans-serif;margin:24px auto;padding:0 20px;max-width:1500px}h1{font-size:26px}h2{font-size:17px}section{background:#1b2432;padding:16px;margin:16px 0;border-radius:10px}img{width:100%;height:auto}table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid #374355}.notice{color:#ffd486;line-height:1.6}</style>
<h1>VRM 위치 변화 비교 · 검증용</h1><p class="notice">자동 정상·불량 판정 아님. 표는 왼쪽 기준 대비 영상 중심의 수평 변화량이며, 슬롯 여유(mm)가 아닙니다.<br>중앙 배치는 사용자가 대략 놓은 사례입니다. 정확한 0.75mm 정답이나 정상 학습 데이터로 사용하지 않습니다.</p>
<table><tr><th>슬롯</th><th>오른쪽 배치 변화</th><th>중간 배치 변화</th><th>1mm 충족 판정</th></tr>'''+''.join(table)+'</table>'+''.join(sections)+'''<p>동일한 고정 가중치와 confidence 0.25 사용. 재학습·임계값 변경·로봇 이동 없음. 실제 벽 위치, 높이 차이, 측정 불확실성이 검증되지 않아 1mm 판정은 보류합니다.</p></html>'''
    output.write_text(document,encoding='utf-8')
    assert document.count('data:image/jpeg;base64,')==3
    print(output)


if __name__=='__main__':
    main()
