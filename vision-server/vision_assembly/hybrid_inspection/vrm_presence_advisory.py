"""Frozen RGB context corroboration. Display evidence only; never a fusion vote."""
from pathlib import Path
import hashlib
import json
import math

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / 'runtime/inspection/vrm_presence_context_stress_20260905'


def summarize_presence_state(state, context):
    """Expose distinct model tasks without changing any fusion/candidate vote."""
    result = dict(status='UNKNOWN', authority='ADVISORY_ONLY',
                  presence_candidate='UNRESOLVED', state_candidate='UNRESOLVED',
                  conflict=False, scope='EXPLANATION_ONLY_NOT_A_FUSION_VOTE')
    state = state if isinstance(state, dict) else {}
    context = context if isinstance(context, dict) else {}
    try:
        p = context['present_probability']
        if (context.get('available') is True and context.get('authority') == 'ADVISORY_ONLY'
                and context.get('status') == 'UNKNOWN' and not isinstance(p, bool)
                and math.isfinite(p) and 0 <= p <= 1):
            result['present_probability'] = p
            result['presence_candidate'] = 'PRESENT' if p >= .90 else 'EMPTY' if p <= .10 else 'UNRESOLVED'
    except (KeyError, TypeError, ValueError):
        pass
    # Report only the already-gated state, never promote raw argmax.
    prediction = state.get('predicted_state')
    if prediction in ('EMPTY','CORRECT','ROTATED'):
        result['state_candidate'] = prediction
    raw = state.get('raw_predicted_state')
    result['raw_state_candidate'] = raw
    result['state_reason'] = state.get('reason')
    presence = result['presence_candidate']
    result['conflict'] = ((presence == 'PRESENT' and raw == 'EMPTY') or
                          (presence == 'EMPTY' and raw in ('CORRECT','ROTATED')))
    result['reason'] = ('PRESENCE_AND_STATE_DISAGREE' if result['conflict'] else
                        'PRESENCE_EVIDENCE_DOES_NOT_CONFIRM_POSE_OR_DIRECTION')
    return result


def corroborates_missing(presence, context):
    try:
        p = context['present_probability']
        confidence = presence['confidence']
        return bool(context.get('available') is True
                    and context.get('authority') == 'ADVISORY_ONLY'
                    and context.get('status') == 'UNKNOWN'
                    and presence.get('status') == 'UNKNOWN'
                    and presence.get('authority') == 'ADVISORY_ONLY'
                    and presence.get('reason') == 'VRM_STATE_LOW_CONFIDENCE:EMPTY'
                    and not isinstance(p, bool) and not isinstance(confidence, bool)
                    and math.isfinite(p) and 0 <= p <= .10
                    and math.isfinite(confidence) and .80 <= confidence < .90)
    except (KeyError, TypeError, ValueError):
        return False


def inspect_context(board, slots, alignment_valid):
    vrms = [s for s in slots if s.component_type == 'VRM']
    unavailable = lambda reason: {s.slot_id: dict(available=False, status='UNKNOWN',
                                                 authority='UNAVAILABLE', reason=reason) for s in vrms}
    if not alignment_valid:
        return unavailable('ALIGNMENT_INVALID')
    try:
        import torch
        from PIL import Image
        from torchvision import models, transforms
        metadata = json.loads((CANDIDATE / 'evaluation.json').read_text())
        if metadata['method'] != 'central55_context130_RGB_frozen_EfficientNetB0_logistic_C1':
            raise ValueError('feature contract mismatch')
        artifact = CANDIDATE / 'classifier_candidate.npz'
        with np.load(artifact, allow_pickle=False) as params:
            coef, intercept, classes = params['coef'], params['intercept'], params['classes']
        if (coef.shape != (1,2560) or intercept.shape != (1,) or classes.tolist() != [0,1]
                or not np.isfinite(coef).all() or not np.isfinite(intercept).all()):
            raise ValueError('invalid classifier')
        # Offline only: never download weights during inspection.
        weights = Path(torch.hub.get_dir()) / 'checkpoints/efficientnet_b0_rwightman-7f5810bc.pth'
        if not weights.is_file():
            raise FileNotFoundError('cached backbone unavailable')
        model = models.efficientnet_b0(weights=None)
        model.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True))
        model.classifier = torch.nn.Identity()
        model.eval()
        transform = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor(),
            transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
        batch = []
        for s in vrms:
            x,y,w,h = s.geometry
            for scale in (.55,1.30):
                crop = cv2.getRectSubPix(board, (max(8,round(w*scale)),max(8,round(h*scale))),
                                        (float(x),float(y)))
                batch.append(transform(Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB))))
        if not batch:
            return {}
        # Restore global thread settings; do not penalize other inspection providers.
        old_threads = torch.get_num_threads()
        try:
            torch.set_num_threads(min(old_threads,2))
            with torch.inference_mode():
                features = model(torch.stack(batch)).numpy().reshape(len(vrms),-1)
        finally:
            torch.set_num_threads(old_threads)
        logits = features @ coef.T + intercept
        probs = 1/(1+np.exp(-np.clip(logits[:,0],-50,50)))
        if not np.isfinite(probs).all():
            raise ValueError('nonfinite inference')
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        return {s.slot_id: dict(available=True, authority='ADVISORY_ONLY', status='UNKNOWN',
                               present_probability=float(p), candidate_sha256=digest,
                               reason='UNCALIBRATED_RGB_CONTEXT_PRESENCE',
                               scope='PRESENCE_ONLY_NOT_POSE', empty_display_gate=.10)
                for s,p in zip(vrms,probs)}
    except Exception as exc:
        return unavailable('CONTEXT_UNAVAILABLE:' + type(exc).__name__)
