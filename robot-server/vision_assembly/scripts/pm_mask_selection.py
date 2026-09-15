"""Rank PM duplicate masks without preferring a low-confidence near-perfect ratio."""
import cv2
import numpy as np


def priority(score, polygon, expected_aspect, expected_area, quality):
    polygon=np.asarray(polygon,np.float32)
    (_, _),(width,height),_=cv2.minAreaRect(polygon)
    aspect=max(width,height)/max(1.,min(width,height))
    area=abs(float(cv2.contourArea(polygon)))
    aspect_match=float(np.exp(-abs(np.log(max(aspect,1e-6)/expected_aspect))))
    area_match=float(np.exp(-abs(np.log(max(area,1.)/expected_area))))
    rectangularity=area/max(1.,width*height)
    shape=float((area_match*aspect_match*min(1.,max(0.,rectangularity)))**(1/3))
    passed=(score>=quality['minimum_detection_confidence']
            and shape>=quality['minimum_mask_shape_score']
            and rectangularity>=quality['minimum_rectangularity'])
    return (passed,aspect_match,float(score))
