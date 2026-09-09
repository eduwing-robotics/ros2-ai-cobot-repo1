"""Check two saved integration results against disclosed development labels.

This is a regression check, not independent accuracy or release qualification.
"""
import argparse
import json
from pathlib import Path


def check(normal, defect):
    errors=[]
    expected_hashes=('259fb0581874edfe405fe1fa11d1937cf781811304c9f5dde15d526d4c6803d3',
                     '3b6cd3507b6a12e5a7aed5a447ab509774da878da1f435ba64d1e33b4d89b98e')
    for name,report,digest in zip(('normal','defect'),(normal,defect),expected_hashes):
        if report.get('input_sha256')!=digest:
            errors.append(name+': wrong source image')
        if report.get('providers',{}).get('yolo',{}).get('status')!='ADVISORY_ONLY':
            errors.append(name+': auxiliary YOLO unavailable or authority changed')
        if report.get('status')!='UNKNOWN':
            errors.append(name+': unexpected final authority')
        if len(report.get('slots',[]))!=25:
            errors.append(name+': missing slot results')
    if normal.get('advisory_candidates',{}).get('count')!=0:
        errors.append('normal: unexpected displayed candidate')
    actual={i['slot_id']:set(i['codes']) for i in defect.get('advisory_candidates',{}).get('items',[])}
    expected={'hbm_01':{'PINS?'},'hbm_04':{'PINS?'},'hbm_07':{'PINS?'},'power_module_04':{'POSE?'}}
    if actual!=expected:
        errors.append('defect: expected candidates changed (including false HBM4 direction)')
    return {'regression_passed':not errors,'errors':errors,'release_qualified':False,
            'scope':'Two development sources; all final decisions must remain UNKNOWN'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal',required=True,type=Path)
    parser.add_argument('--defect',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=check(json.loads(args.normal.read_text()),json.loads(args.defect.read_text()))
    result['reports']=[str(args.normal),str(args.defect)]
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['regression_passed'] else 1)


if __name__=='__main__':
    main()
