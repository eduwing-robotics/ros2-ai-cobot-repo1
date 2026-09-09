"""Offline one-pixel guard against quantized mask-boundary nomination."""
import json
from pathlib import Path
from vrm_boundary_advisory import BASE, LEFT, measure


def main():
    references = {}
    for stamp in LEFT:
        data = json.loads((BASE/f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json').read_text())
        for row in data['rows']:
            value = measure(row['primary']['polygon'], row['crop_origin_px'])
            references.setdefault(row['slot'],[]).append(value['position'])
    margins = [max(max(p[i] for p in v)-min(p[i] for p in v) for v in references.values()) for i in range(3)]
    source = json.loads((BASE/'placement_uncertainty_replay.json').read_text())
    results = []
    for item in source['rows']:
        if item['intent'] not in ('LEFT_SEATED','RIGHT_SHIFT'):
            continue
        stamp, sid = item['capture'], item['slot']
        data = json.loads((BASE/f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json').read_text())
        row = next(r for r in data['rows'] if r['slot']==sid)
        value = measure(row['primary']['polygon'],row['crop_origin_px'])
        excess = [value['position'][i]-max(p[i] for p in references[sid])-margins[i] for i in (0,2)]
        results.append(dict(capture=stamp,slot=sid,intent=item['intent'],excess_px=excess,
                            old=all(e>0 for e in excess),guarded=all(e>1 for e in excess)))
    out = Path(__file__).resolve().parents[2]/'runtime/inspection/vrm_boundary_pixel_guard_20260907.json'
    out.write_text(json.dumps(dict(rows=results,
        limitation='Offline development replay using frozen deployed references, including normal references. Not leave-one-out or physical1mm certification; one-pixel guard not deployed.'),indent=2))
    print(json.dumps({label:dict(count=sum(r['intent']==label for r in results),
        guarded=sum(r['guarded'] for r in results if r['intent']==label)) for label in ('LEFT_SEATED','RIGHT_SHIFT')}))


if __name__=='__main__':
    main()
