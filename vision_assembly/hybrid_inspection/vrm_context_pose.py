"""Advisory pose evidence despite ambiguous fixed-slot presence. No height claim."""
import math


def context_pose_codes(row):
    try:
        if row.get('component_type')!='VRM': return []
        context=row.get('vrm_presence_context') or {}
        stages=row['stages']; pose=stages['pose']; boundary=stages['vrm_boundary']
        if context.get('available') is not True or context.get('authority')!='ADVISORY_ONLY': return []
        if pose.get('authority')!='ADVISORY_ONLY' or boundary.get('authority')!='ADVISORY_ONLY': return []
        # A state-classifier CORRECT vote is not a veto on independent pose
        # evidence. Preserve that raw advisory vote; do not grant final FAIL.
        presence=stages['presence']
        present_advisory=(presence.get('status')=='PASS'
                          and presence.get('authority')=='ADVISORY_ONLY'
                          and presence.get('predicted_state') in ('CORRECT','PRESENT'))
        if presence.get('status')!='UNKNOWN' and not present_advisory: return []
        p=float(context['present_probability']); pc=float(pose['confidence'])
        b=boundary['measured']; m=pose['measured']
        bc=float(b['confidence']); a=float(b['axes'][0])
        expected=float(pose['limits']['expected_axis_angle_deg'])
        actual=float(m['axis_angle_deg'])
        tol=float(pose['limits']['angle_tolerance_deg'])
        pos_tol=float(pose['limits']['position_tolerance_mm'])
        raw=[float(x) for x in m['raw_offset_mm']]
        c=[float(x) for x in m['center_px']]
        other=[float(x) for x in b['position'][:2]]
        values=[p,pc,bc,a,expected,actual,tol,pos_tol,*raw,*c,*other]
        if not all(math.isfinite(x) for x in values): return []
        if any(len(x)!=2 for x in (raw,c,other)): return []
        if not (.95<=p<=1 and 0<=pc<=1 and 0<=bc<=1 and tol>=0 and pos_tol>=0): return []
        # Candidate-level trade-off only: a stronger auxiliary detector can
        # support a slightly weaker boundary detector, never two weak votes.
        # Not calibrated probabilities and not independent sensor measurements.
        if not ((bc>=.95 and pc>=.20) or (bc>=.90 and pc>=.40)): return []
        if m.get('axis_angle_checked') is not True: return []
        # Boundary min-area angle is signed relative to vertical, not PCA axis.
        def axial(x): return (x+90)%180-90
        if abs(axial(expected-90))>1e-4: return []
        signed=axial(actual-expected)
        if math.dist(c,other)>3: return []
        if abs(axial(signed-a))>2 or min(abs(signed),abs(axial(a)))<tol+1: return []
        codes=['DIR?']
        # Raw CAD offset only: never let shared component bias create this vote.
        if math.hypot(*raw)>=pos_tol+.50: codes.append('POSE?')
        return codes
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,OverflowError):
        return []
