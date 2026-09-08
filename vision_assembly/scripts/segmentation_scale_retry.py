"""Replace only weak, geometrically matched PM/VRM/HBM detections in one frame."""
import math
import numpy as np


def passes_quality(item, quality):
    return all(math.isfinite(float(item.get(field, math.nan))) and
               float(item[field]) >= float(quality[limit]) for field, limit in (
        ('segmentation_confidence', 'minimum_detection_confidence'),
        ('mask_shape_score', 'minimum_mask_shape_score'),
        ('rectangularity', 'minimum_rectangularity')))


def merge_scale_retry(primary, alternate, quality, *, primary_size, alternate_size):
    result = []
    for index, original in enumerate(primary):
        if passes_quality(original, quality):
            result.append(original)
            continue
        center = np.asarray(original['center_pixel'], float)
        matches = []
        for candidate in alternate:
            if not passes_quality(candidate, quality):
                continue
            other = np.asarray(candidate['center_pixel'], float)
            distances = [float(np.linalg.norm(other-np.asarray(p['center_pixel'],float))) for p in primary]
            close = [i for i, distance in enumerate(distances) if distance <= 3.0]
            if close != [index]:
                continue  # No new identities, merged masks, or ambiguous matches.
            angle = abs((float(candidate['angle_deg'])-float(original['angle_deg'])+90)%180-90)
            size = np.sort(np.asarray(candidate['bbox_size_px'],float)) / np.sort(np.asarray(original['bbox_size_px'],float))
            if (not np.isfinite(center).all() or not np.isfinite(size).all()
                    or not math.isfinite(angle) or not math.isfinite(float(candidate['depth_m']))
                    or not math.isfinite(float(original['depth_m'])) or angle > 3 or not np.all((size >= .8) & (size <= 1.2))
                    or abs(float(candidate['depth_m'])-float(original['depth_m'])) > .002):
                continue
            matches.append(candidate)
        if len(matches) != 1:
            result.append(original)
            continue
        chosen = dict(matches[0])
        chosen['scale_retry'] = {'primary_size': primary_size, 'selected_size': alternate_size,
            'primary_confidence': original['segmentation_confidence'],
            'center_delta_px': float(np.linalg.norm(np.asarray(chosen['center_pixel'])-center))}
        result.append(chosen)
    return result
