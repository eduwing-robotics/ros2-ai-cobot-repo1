"""Isolated full-report replay; never installs the candidate into active models."""
import json
import argparse
from pathlib import Path
import sys
from unittest.mock import patch
import torch
from evaluate_vrm_texture_presence import ROOT

sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
import main as hybrid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,
                        default=ROOT/'runtime/inspection/s22_inspection_roi_20260905_165914.png')
    parser.add_argument('--skip-patchcore',action='store_true',
                        help='Geometry diagnostic only; surface stage remains unavailable.')
    args=parser.parse_args()
    torch.set_num_threads(2)
    bridge=ROOT/'runtime/inspection/vrm_multiscale_seating_plus_165057/integration_bridge'
    metadata=json.loads((bridge/'vrm_seating.json').read_text())
    assert metadata['runtime_enabled'] is False
    original=hybrid.VrmSeatingClassifier
    def factory(model_root):
        provider=original(model_root,device='cpu')
        provider.model=torch.jit.load(str(bridge/'vrm_seating.torchscript.pt')).eval()
        provider.model_path=bridge/'vrm_seating.torchscript.pt'
        provider.metadata_path=bridge/'vrm_seating.json'
        provider.metadata={**metadata,'runtime_enabled':True,'seating_min_probability':.5}
        return provider
    with patch.object(hybrid,'VrmSeatingClassifier',factory):
        result=hybrid.inspect_pcb(
            args.image,
            run_patchcore=not args.skip_patchcore,
            output_root=ROOT/'runtime/inspection/vrm_bridge_full_report_test')
    assert json.loads((bridge/'vrm_seating.json').read_text())['runtime_enabled'] is False
    print('Isolated report completed; active model untouched.')


if __name__=='__main__':
    main()
