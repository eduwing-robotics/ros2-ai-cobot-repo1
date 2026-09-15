"""Current-frame visual detections, including rejected axes; never robot targets."""
import cv2
import numpy as np
from smd_terminal_axis import terminal_axis_from_source_obb


def describe_detections(ordered, inverse_homography, minimum_axis_ratio):
    detections=[]
    for index,item in enumerate(ordered,1):
        if item is None:
            continue
        source_box=cv2.perspectiveTransform(np.asarray(item['box'],np.float32).reshape(-1,1,2),inverse_homography)[:,0]
        row={'instance_index':index,'polygon_source_pixel':np.round(source_box,2).tolist(),
             'confidence':round(float(item['confidence']),4),'axis_valid':False,
             'visualization_only':True}
        try:
            terminal=terminal_axis_from_source_obb(item['box'],inverse_homography,minimum_axis_ratio=minimum_axis_ratio)
            ends=np.asarray(terminal['endpoints_canonical_pixel'],np.float32)
            axis=cv2.perspectiveTransform(ends.reshape(-1,1,2),inverse_homography)[:,0]
            row.update(axis_valid=True,terminal_axis_source_pixel=np.round(axis,2).tolist(),
                       terminal_axis_canonical_deg=round(float(terminal['angle_canonical_deg']),2),
                       directed_axis_canonical_deg=round(float(terminal['angle_canonical_deg']),2),
                       axis_ratio=round(float(terminal['axis_ratio']),3),axis_ratio_frame='source_image')
        except ValueError as error:
            row['reason']=str(error)
        detections.append(row)
    return detections
