"""Archive an unchanged JSON/PNG inspection pair for a recorded-case demo."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from string import Template


def escape(value):
    return html.escape(str(value if value is not None else '미기록'))


def render(payload):
    """Presentation only: display supplied decisions, never derive a verdict."""
    data = payload['data']
    result = data['result']
    findings = result.get('findings', [])
    slots = result.get('slots', [])
    summary = result.get('summary', {})
    rows = []
    for finding in findings:
        slot = escape(finding.get('slot_code', '미기록'))
        part = escape(finding.get('part_name') or finding.get('part_type', '미기록'))
        name = escape(finding.get('primary_defect_name_ko', '미분류'))
        decision = escape(finding.get('decision', 'UNKNOWN'))
        authority = escape(finding.get('authority', '미기록'))
        confirmed = '확정' if finding.get('confirmed_defect') is True else '미확정'
        details = ''.join(f'<li>{escape(line)}</li>' for line in finding.get('details', []))
        measurements = ''.join(f'<dt>{escape(key)}</dt><dd>{escape(value)}</dd>'
                               for key, value in finding.get('measurements', {}).items() if value is not None)
        rows.append(f'''<tr class="finding"><td><strong>{slot}</strong><span class="sub">{part}</span></td>
<td>{name}<span class="sub">{confirmed} · {authority}</span></td><td><span class="pill">{decision}</span></td>
<td><details><summary>근거 보기</summary><ul>{details or '<li>기록된 상세 근거 없음</li>'}</ul>
<dl>{measurements}</dl><small>원본 측정값입니다. 표시 자체가 측정 정확도 보증은 아닙니다.</small></details></td></tr>''')
    badges = ''.join(f'<div class="slot"><strong>{escape(s.get("slot_code"))}</strong>'
                     f'<span>{escape(s.get("decision", "UNKNOWN"))}</span></div>' for s in slots)
    binding = '미연결 · 저장 사례' if payload.get('production_binding') == 'UNBOUND' else '원본 JSON 참조'
    diagnostics = result.get('diagnostics') or {}
    quality = diagnostics.get('capture_quality') or {}
    audit = diagnostics.get('evidence_audit') or {}
    health = diagnostics.get('provider_health') or {}
    unavailable_rows = ''.join(f'<li>{escape(r.get("slot_id"))} / {escape(r.get("stage"))}: '
                               f'{escape(r.get("reason"))}</li>' for r in health.get('unavailable', []))
    quality_label = {
        'NO_GROSS_ISSUE_DETECTED': '심한 화질 저하 신호 없음 · 검사 품질 보증 아님',
        'RECAPTURE_RECOMMENDED': '촬영 품질 의심 · 재촬영 권장 · 부품 불량 아님',
        'NOT_EVALUATED': '촬영 품질 평가 불가',
    }.get(quality.get('status'), '촬영 품질 미평가 · 기존 저장 결과')
    diagnostic_rows = ''.join(
        f'<tr><td>{escape(row.get("slot_id"))}</td><td>{escape(row.get("stage"))}</td>'
        f'<td>{escape(row.get("raw_status"))} / {escape(row.get("authority"))}</td>'
        f'<td>{escape(row.get("reason"))}</td></tr>'
        for row in audit.get('items', []) if not row.get('displayed_as_candidate'))
    template_dir = Path(__file__).with_name('demo_assets')
    template = Template((template_dir/'page.html').read_text(encoding='utf-8'))
    return template.substitute(
        css=(template_dir/'style.css').read_text(encoding='utf-8'),
        js=(template_dir/'viewer.js').read_text(encoding='utf-8'),
        decision=escape(result['decision']), inspection_id=escape(data['inspection_id']),
        captured_at=escape(result.get('captured_at')), inspected_at=escape(result.get('inspected_at')),
        binding=binding, expected=escape(summary.get('expected_slots', len(slots) if slots else '미기록')),
        confirmed=escape(summary.get('confirmed_defect_count', '미기록')),
        advisory=escape(summary.get('advisory_candidate_count', '미기록')),
        unknown=escape(summary.get('slot_decisions', {}).get('UNKNOWN', '미기록')),
        findings=''.join(rows), finding_count=str(len(findings)), slots=badges,
        no_findings='' if findings else '현재 결과에 기록된 검출 항목이 없습니다. 이것만으로 PASS를 뜻하지 않습니다.',
        quality_label=escape(quality_label), quality_flags=escape(', '.join(quality.get('flags', []))),
        diagnostic_rows=diagnostic_rows, undisplayed=escape(audit.get('undisplayed_count', '미기록')),
        unavailable=escape(health.get('unavailable_count', '미기록')), unavailable_rows=unavailable_rows,
    )


def archive(source: Path, output: Path):
    raw=(source/'inspection_result.json').read_bytes()
    payload=json.loads(raw)
    data=payload['data']
    if data['status']!='COMPLETED':
        raise ValueError('Only completed inspection results can be archived')
    metadata=data['image']
    if metadata.get('ready') is not True or metadata['filename']!='02_annotated_report.png' or metadata['mime_type']!='image/png':
        raise ValueError('Unexpected image contract')
    image=(source/'02_annotated_report.png').read_bytes()
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid PNG signature')
    if len(image)!=metadata['size_bytes'] or hashlib.sha256(image).hexdigest()!=metadata['sha256']:
        raise ValueError('Image does not match result JSON')
    result=data['result']
    if result['decision'] not in ('PASS','FAIL','UNKNOWN'):
        raise ValueError('Unknown decision value')
    page=render(payload)
    output.mkdir(parents=True,exist_ok=False)
    (output/'inspection_result.json').write_bytes(raw)
    (output/'02_annotated_report.png').write_bytes(image)
    (output/'index.html').write_text(page,encoding='utf-8')
    (output/'provenance.json').write_text(json.dumps(dict(source=str(source.resolve()),
        inspection_id=data['inspection_id'],decision=result['decision'],recorded_example=True,
        json_sha256=hashlib.sha256(raw).hexdigest(),image_sha256=metadata['sha256'],
        presentation_version=2,result_modified=False,live_capture_performed=False,network_delivery_performed=False),indent=2))
    return output/'index.html'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(archive(a.source,a.output))
