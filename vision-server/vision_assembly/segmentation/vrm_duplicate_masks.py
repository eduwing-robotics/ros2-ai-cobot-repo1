"""Conservative VRM mask deduplication; never grants inspection authority."""
import cv2
import numpy as np


def deduplicate(candidates, width, height):
    """Group only pairwise near-identical raster masks and <=1px extrema.

    Fixed diagnostic tolerances are not assembly tolerances. Complete-link
    grouping avoids collapsing a chain of progressively different boundaries.
    Input must contain only same-class VRM candidates in the same crop frame.
    """
    masks=[]
    for candidate in candidates:
        polygon=np.asarray(candidate['polygon'],dtype=np.float32)
        if polygon.ndim!=2 or polygon.shape[1]!=2 or len(polygon)<3 or not np.isfinite(polygon).all():
            raise ValueError('Invalid polygon')
        mask=np.zeros((height,width),np.uint8)
        cv2.fillPoly(mask,[np.int32(polygon)],1)
        if not mask.any():
            raise ValueError('Empty polygon')
        masks.append(mask.astype(bool))
    def same(a,b):
        iou=np.logical_and(masks[a],masks[b]).sum()/np.logical_or(masks[a],masks[b]).sum()
        delta=np.max(np.abs(np.asarray(candidates[a]['extent_in_fixed_crop'])-
                               candidates[b]['extent_in_fixed_crop']))
        return iou>=.995 and delta<=1
    groups=[]
    for i in sorted(range(len(candidates)),key=lambda i:candidates[i]['confidence'],reverse=True):
        for group in groups:
            if all(same(i,j) for j in group):
                group.append(i)
                break
        else:
            groups.append([i])
    return [candidates[g[0]] for g in groups],groups
