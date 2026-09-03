#!/usr/bin/env python3
"""Direct HBM annotation with lossless ROI zoom and shadow enhancement."""
import argparse, json, time
from pathlib import Path
import cv2
import numpy as np

def main():
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--registration',type=Path,required=True);p.add_argument('--reference-slots',type=Path,required=True);p.add_argument('--zoom',type=int,default=4);p.add_argument('--padding-px',type=int,default=28);a=p.parse_args()
 image=cv2.imread(str(a.image));registration=json.loads(a.registration.read_text());reference=json.loads(a.reference_slots.read_text());payload=json.loads(a.output.read_text());saved={x['slot_code']:x for x in payload['slots']};H=np.asarray(registration['homography_reference_to_live'],np.float32)
 codes=[f'HBM-{i:02d}' for i in range(1,9)];window='HBM LOSSLESS ZOOM';points=[];index=0;enhanced=[True]
 def roi_for(code):
  slot=next(x for x in reference['slots'] if x['slot_code']==code);src=np.asarray(slot['polygon_reference_pixel'],np.float32).reshape(-1,1,2);q=cv2.perspectiveTransform(src,H)[:,0];x0,y0=np.floor(q.min(0)-a.padding_px).astype(int);x1,y1=np.ceil(q.max(0)+a.padding_px).astype(int);x0=max(0,x0);y0=max(0,y0);x1=min(image.shape[1],x1);y1=min(image.shape[0],y1);return x0,y0,x1,y1
 roi=[roi_for(codes[0])]
 def view_image():
  x0,y0,x1,y1=roi[0];crop=image[y0:y1,x0:x1]
  if enhanced[0]:
   lab=cv2.cvtColor(crop,cv2.COLOR_BGR2LAB);l,aa,bb=cv2.split(lab);l=cv2.createCLAHE(clipLimit=3.0,tileGridSize=(6,6)).apply(l);crop=cv2.cvtColor(cv2.merge((l,aa,bb)),cv2.COLOR_LAB2BGR);crop=cv2.convertScaleAbs(crop,alpha=1.35,beta=18)
  return cv2.resize(crop,None,fx=a.zoom,fy=a.zoom,interpolation=cv2.INTER_LANCZOS4)
 def redraw():
  shown=view_image();mode='ENHANCED' if enhanced[0] else 'ORIGINAL';cv2.rectangle(shown,(0,0),(shown.shape[1],58),(18,24,30),-1);cv2.putText(shown,f'{codes[index]} {index+1}/8  {mode}  [C toggle/R reset/Q stop]',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1);cv2.putText(shown,'Click 4 corners around boundary; ENTER next',(12,49),cv2.FONT_HERSHEY_SIMPLEX,.46,(0,255,255),1)
  for i,pt in enumerate(points):cv2.circle(shown,pt,3,(0,0,255),-1);cv2.putText(shown,str(i+1),(pt[0]+4,pt[1]-4),cv2.FONT_HERSHEY_SIMPLEX,.32,(0,0,255),1)
  if len(points)>1:cv2.polylines(shown,[np.asarray(points,np.int32)],len(points)==4,(0,255,255),1,cv2.LINE_AA)
  cv2.imshow(window,shown)
 def mouse(event,x,y,flags,param):
  if event==cv2.EVENT_LBUTTONDOWN and len(points)<4 and y>=58:points.append((x,y));redraw()
 cv2.namedWindow(window,cv2.WINDOW_NORMAL);cv2.setMouseCallback(window,mouse);redraw()
 while True:
  key=cv2.waitKey(30)&255
  if key in (ord('q'),27):break
  if key==ord('r'):points.clear();redraw()
  if key==ord('c'):enhanced[0]=not enhanced[0];redraw()
  if key in (10,13,32) and len(points)==4:
   x0,y0,_,_=roi[0];original=[[round(x/a.zoom+x0),round(y/a.zoom+y0)] for x,y in points];code=codes[index];saved[code]={'slot_code':code,'polygon_image_pixel':original,'status':'operator_direct_annotation_lossless_zoom'};payload.update({'timestamp_unix':time.time(),'source_image':str(a.image.resolve()),'image_size':[image.shape[1],image.shape[0]],'coordinate_frame':'PlaceCamera_image_pixel','display_only':True,'slots':list(saved.values())});a.output.write_text(json.dumps(payload,indent=2));print('Saved',code,original,flush=True);index+=1
   if index==len(codes):break
   roi[0]=roi_for(codes[index]);points.clear();enhanced[0]=True;redraw()
 cv2.destroyAllWindows();print(f'Completed {index}/8 HBM slots')

if __name__=='__main__':main()
