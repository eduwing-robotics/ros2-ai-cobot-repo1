"""Nominal rectangular geometry only; not calibrated image or collision judgment."""
import math


def nominal_gaps(center_x_mm=0., center_y_mm=0., angle_deg=0.,
                 part=(11.,14.), socket=(12.5,15.)):
    values=[center_x_mm,center_y_mm,angle_deg,*part,*socket]
    if not all(math.isfinite(v) for v in values) or min(*part,*socket)<=0:
        raise ValueError('Finite coordinates and positive dimensions required')
    theta=math.radians(angle_deg)
    c,s=abs(math.cos(theta)),abs(math.sin(theta))
    half_x=(part[0]*c+part[1]*s)/2
    half_y=(part[0]*s+part[1]*c)/2
    return dict(left=socket[0]/2+center_x_mm-half_x,
                right=socket[0]/2-center_x_mm-half_x,
                top=socket[1]/2+center_y_mm-half_y,
                bottom=socket[1]/2-center_y_mm-half_y)


def access_evidence(**kwargs):
    gaps=nominal_gaps(**kwargs)
    return dict(status='UNKNOWN',authority='ADVISORY_ONLY',nominal_gaps_mm=gaps,
                nominal_right_requirement_met=gaps['right']>=1.,
                nominal_inside_socket=all(v>=0 for v in gaps.values()),
                limitation='Nominal geometry, not measured clearance or physical PASS/FAIL; wall identity, pose and uncertainty uncalibrated.')
