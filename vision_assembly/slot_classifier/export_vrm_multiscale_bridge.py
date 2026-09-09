"""Export a disabled TorchScript bridge; never replace the active provider."""
import hashlib
import json
import argparse
from pathlib import Path

import numpy as np
import torch
from torchvision import models
from vrm_seating_common import VRM_SEATING_CROP_PIPELINE
from evaluate_vrm_texture_presence import ROOT


class Bridge(torch.nn.Module):
    def __init__(self, coef, intercept):
        super().__init__()
        backbone=models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1).features
        self.early=backbone[:6]
        self.late=backbone[6:]
        self.register_buffer('coef',torch.tensor(coef,dtype=torch.float32))
        self.register_buffer('intercept',torch.tensor(intercept,dtype=torch.float32))

    def forward(self,x):
        early=self.early(x)
        late=self.late(early)
        vector=torch.cat([torch.nn.functional.adaptive_avg_pool2d(f,(4,4)).flatten(1) for f in (early,late)],dim=1)
        z=vector@self.coef.t()+self.intercept
        return torch.cat([torch.zeros_like(z),z],dim=1)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT/'runtime/inspection/vrm_multiscale_seating_plus_165057')
    args=parser.parse_args()
    torch.set_num_threads(2)
    torch.manual_seed(0)
    source=args.source.resolve()
    output=source/'integration_bridge'
    if output.exists():
        raise ValueError('Refusing to overwrite bridge')
    metadata=json.loads((source/'evaluation.json').read_text())
    if metadata['method']!='frozen_B0_layer5_final_spatial4x4_logistic_C1':
        raise ValueError('Unexpected feature contract')
    with np.load(source/'candidate.npz',allow_pickle=False) as head:
        if not np.array_equal(head['classes'],[0,1]):
            raise ValueError('Unexpected class order')
        model=Bridge(head['coef'],head['intercept']).eval()
    example=torch.zeros(1,3,224,224)
    traced=torch.jit.trace(model,example)
    with torch.inference_mode():
        check=torch.randn(2,3,224,224)
        error=float((model(check)-traced(check)).abs().max())
    if error>1e-5:
        raise ValueError('Trace parity failure')
    output.mkdir()
    traced.save(str(output/'vrm_seating.torchscript.pt'))
    report=dict(runtime_enabled=False,validated=False,authority='ADVISORY_ONLY',
        class_order=['FLAT','SEATING'],input_size=224,crop_pipeline=VRM_SEATING_CROP_PIPELINE,
        flat_max_seating_probability=0.0,seating_min_probability=1.0,
        source_sha256=hashlib.sha256((source/'candidate.npz').read_bytes()).hexdigest(),
        trace_max_logit_error=error,candidate_status='BRIDGE_ONLY_NOT_PROMOTED',
        promotion_blocker='Uncalibrated thresholds; historical holdout miss; real-crop export parity and integrated presence gating require verification.',
        note='Sentinel thresholds disable decisions. Do not copy to active model path or enable without further verification.',
        robot_command_sent=False,conveyor_command_sent=False)
    (output/'vrm_seating.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
