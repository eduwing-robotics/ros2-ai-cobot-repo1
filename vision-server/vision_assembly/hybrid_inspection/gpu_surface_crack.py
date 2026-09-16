"""Advisory transverse dark-ridge evidence below a GPU logo.

No per-component registration, training or PASS authority. This limited
candidate detects a visible transverse groove, not every physical crack.
"""
import cv2
import numpy as np
from opencv_inspectors import CheckEvidence


def inspect_gpu_crack(crop, presence_state, alignment_valid):
    limits = dict(scope="VISIBLE_TRANSVERSE_DARK_RIDGE_BELOW_GPU_LOGO",
                  contrast_min=8., blackhat_min=12, min_length_fraction=.08,
                  aspect_min=3., authority="ADVISORY_ONLY", validated=False)
    def result(reason, measured=None, status="UNKNOWN"):
        return CheckEvidence("gpu_lower_surface_crack", status, "ADVISORY_ONLY", 0.,
                             reason, measured or {}, limits)
    if not alignment_valid or presence_state != "PRESENT":
        return result("GPU_CRACK_PRESENCE_OR_ALIGNMENT_UNCERTAIN")
    if crop is None or min(crop.shape[:2]) < 64:
        return result("GPU_CRACK_IMAGE_INVALID")
    h, w = crop.shape[:2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (40,65,45), (95,255,255))
    green[:int(h*.2)] = 0
    green[int(h*.7):] = 0
    green[:, :int(w*.2)] = 0
    green[:, int(w*.8):] = 0
    ys, _ = np.where(green > 0)
    if len(ys) < 20:
        return result("GPU_CRACK_LOGO_NOT_LOCATED")
    x0, x1 = int(w*.22), int(w*.78)
    y0, y1 = int(ys.max())+int(h*.09), int(h*.82)
    if y1-y0 < 20:
        return result("GPU_CRACK_LOWER_FACE_UNAVAILABLE")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    roi = gray[y0:y1, x0:x1]
    response = cv2.morphologyEx(roi, cv2.MORPH_BLACKHAT,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (3,17)))
    mask = np.uint8(response >= limits['blackhat_min'])*255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1,5),np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x,y,cw,ch = cv2.boundingRect(contour)
        if cw < w*limits['min_length_fraction'] or cw/ch < limits['aspect_min'] or ch > h*.03:
            continue
        if y < 4 or y+ch+4 >= roi.shape[0]:
            continue
        line = roi[y:y+ch, x:x+cw]
        surrounding = np.concatenate((roi[y-4:y,x:x+cw].ravel(), roi[y+ch:y+ch+4,x:x+cw].ravel()))
        contrast = float(np.median(surrounding)-np.median(line))
        if contrast < limits['contrast_min']:
            continue
        candidates.append(dict(bbox_crop_px=[x+x0,y+y0,x+x0+cw,y+y0+ch],
                               raw_contrast=contrast, length_px=cw))
    measured = dict(roi_crop_xyxy=[x0,y0,x1,y1], candidates=candidates,
                    alternative_causes_not_excluded=["PRINT_SEAM", "SHADOW", "SCRATCH"],
                    certifies_physical_crack=False)
    # Fragmented grooves can have low bounding-box aspect and diluted median
    # contrast. Measure the actual near-horizontal line against parallel raw
    # pixels instead; retain the same strong-response and raw-contrast gates.
    lines = cv2.HoughLinesP(np.uint8(response >= limits['blackhat_min'])*255,
                           1, np.pi/180, threshold=12,
                           minLineLength=max(20,int(w*.06)), maxLineGap=max(3,int(w*.02)))
    measured['fragment_line_evidence'] = []
    if lines is not None and not candidates:
        for ax,ay,bx,by in lines.reshape(-1,4):
            dx,dy = int(bx-ax), int(by-ay)
            if abs(dx) < w*.06 or abs(dy) > abs(dx)*.27:
                continue
            xs = np.rint(np.linspace(ax,bx,abs(dx)+1)).astype(int)
            yy = np.rint(np.linspace(ay,by,abs(dx)+1)).astype(int)
            if yy.min()<10 or yy.max()+10>=roi.shape[0]:
                continue
            # Sample the darkest of three adjacent rows on the located ridge;
            # compare with both sides to reject a one-sided shadow edge.
            line = np.minimum.reduce([roi[yy+d,xs] for d in range(-3,4)])
            upper = np.median(np.stack([roi[yy+d,xs] for d in (-10,-9,-8)]),axis=0)
            lower = np.median(np.stack([roi[yy+d,xs] for d in (8,9,10)]),axis=0)
            contrast = float(np.median(np.minimum(upper,lower)-line.astype(float)))
            if contrast < limits['contrast_min']:
                continue
            box = [int(xs.min())+x0,int(yy.min())+y0-2,
                   int(xs.max())+x0+1,int(yy.max())+y0+3]
            candidates.append(dict(bbox_crop_px=box, raw_contrast=contrast,
                                   length_px=abs(dx), method='PARALLEL_RAW_LINE_CONTRAST'))
            measured['fragment_line_evidence'].append(dict(bbox_crop_px=box, raw_contrast=contrast))
    limits['fragment_min_length_fraction'] = .06
    return result("GPU_TRANSVERSE_DARK_CRACK_CANDIDATE" if candidates else
                  "GPU_CRACK_NO_QUALIFIED_DARK_RIDGE", measured,
                  "FAIL" if candidates else "UNKNOWN")
