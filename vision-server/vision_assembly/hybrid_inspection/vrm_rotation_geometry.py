"""Conservative advisory rotation from two same-mask axes, not two sensors."""
import math


def strong_boundary_rotation(row):
    """High-confidence presence plus consistent boundary axes, advisory only.

    The two axes share one mask. This can nominate rotation but cannot prove
    socket containment, height or a final FAIL. No classifier CORRECT veto.
    """
    try:
        if row.get('component_type') != 'VRM':
            return False
        context = row['vrm_presence_context']
        boundary = row['stages']['vrm_boundary']
        if context.get('available') is not True:
            return False
        if any(s.get('authority') != 'ADVISORY_ONLY' for s in (context, boundary)):
            return False
        if 'UNAVAILABLE' in boundary.get('reason', ''):
            return False
        measured = boundary['measured']
        if len(measured['axes']) != 2:
            return False
        a, b = [float(v) for v in measured['axes']]
        confidence = float(measured['confidence'])
        present = float(context['present_probability'])
        limits = row['stages']['pose']['limits']
        tolerance = float(limits['angle_tolerance_deg'])
        expected = float(limits['expected_axis_angle_deg'])
        probs = [float(row['vrm_state_evidence']['probabilities'][k])
                 for k in ('EMPTY', 'CORRECT', 'ROTATED')]
        if not all(math.isfinite(v) for v in (a,b,confidence,present,tolerance,expected,*probs)):
            return False
        if not (all(0 <= p <= 1 for p in probs) and abs(sum(probs)-1) < 1e-5 and probs[0] <= .05):
            return False
        if not (.97 <= confidence <= 1 and .99 <= present <= 1 and tolerance >= 0):
            return False
        axial = lambda v: (v+90) % 180-90
        if abs(axial(expected-90)) > 1e-4:
            return False
        a,b = axial(a),axial(b)
        return a*b > 0 and abs(a-b) <= 2 and min(abs(a),abs(b)) >= max(5., tolerance+2.)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return False


def multi_axis_rotation(row):
    """Advisory-only three-axis corroboration; never an independent sensor vote.

    Require the auxiliary axis and both boundary axes to agree. The median
    retains the eight-degree nomination floor without requiring the noisier
    boundary PCA estimate to cross that floor alone.
    """
    try:
        if row.get('component_type') != 'VRM':
            return False
        boundary = row['stages']['vrm_boundary']
        pose = row['stages']['pose']
        if any(s.get('authority') != 'ADVISORY_ONLY' for s in (boundary, pose)):
            return False
        if 'UNAVAILABLE' in boundary.get('reason', ''):
            return False
        b, p = boundary['measured'], pose['measured']
        if p.get('axis_angle_checked') is not True or len(b['axes']) != 2:
            return False
        probabilities = row['vrm_state_evidence']['probabilities']
        probs = [float(probabilities[k]) for k in ('EMPTY', 'CORRECT', 'ROTATED')]
        bc, pc = float(b['confidence']), float(pose['confidence'])
        expected = float(pose['limits']['expected_axis_angle_deg'])
        actual = float(p['axis_angle_deg'])
        axes = [float(v) for v in b['axes']]
        centers = [float(v) for v in p['center_px']]
        other = [float(v) for v in b['position'][:2]]
        values = [*probs, bc, pc, expected, actual, *axes, *centers, *other]
        if not all(math.isfinite(v) for v in values):
            return False
        if len(centers) != 2 or len(other) != 2:
            return False
        if not (all(0 <= v <= 1 for v in probs) and abs(sum(probs)-1) < 1e-5):
            return False
        if not (probs[0] <= .05 and .95 <= bc <= 1 and .25 <= pc <= 1):
            return False
        axial = lambda x: (x+90) % 180-90
        if abs(axial(expected-90)) > 1e-4 or math.dist(centers, other) > 5:
            return False
        angles = [axial(v) for v in axes] + [axial(actual-expected)]
        # Consistent sign and <=2deg spread; no cancellation of opposing axes.
        if not (all(v > 0 for v in angles) or all(v < 0 for v in angles)):
            return False
        magnitude = sorted(abs(v) for v in angles)
        return magnitude[1] >= 8 and magnitude[2]-magnitude[0] <= 2
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return False


def corroborated_rotation(row):
    if row.get('component_type')!='VRM':
        return False
    stages=row.get('stages',{})
    boundary=stages.get('vrm_boundary') or {}
    if boundary.get('authority')!='ADVISORY_ONLY' or 'UNAVAILABLE' in boundary.get('reason',''):
        return False
    measured=boundary.get('measured') or {}
    try:
        axes=measured['axes']
        if len(axes)!=2:
            return False
        a,b=(float(x) for x in axes)
        confidence=float(measured['confidence'])
        empty=float(row['vrm_state_evidence']['probabilities']['EMPTY'])
        if not all(math.isfinite(x) for x in (a,b,confidence,empty)):
            return False
        a,b=((x+90)%180-90 for x in (a,b))
        difference=abs((a-b+90)%180-90)
        # Keep the original gate. A second, stricter-boundary route marginalizes
        # CORRECT+ROTATED as presence instead of requiring either orientation
        # class to win. This is candidate tuning, NEVER release authority.
        presence_supported = 0<=empty<=0.05 and 0.90<=confidence<=1
        if not presence_supported and 0<=empty<=0.10 and 0.95<=confidence<=1:
            probabilities=row['vrm_state_evidence']['probabilities']
            correct=float(probabilities['CORRECT'])
            rotated=float(probabilities['ROTATED'])
            presence_supported=(all(math.isfinite(v) and 0<=v<=1 for v in (correct,rotated))
                                and abs(empty+correct+rotated-1)<=1e-5
                                and correct+rotated>=0.90)
        return (presence_supported and min(abs(a),abs(b))>=8 and difference<=2)
    except (KeyError,TypeError,ValueError,OverflowError):
        return False
