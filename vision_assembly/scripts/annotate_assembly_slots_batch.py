#!/usr/bin/env python3
"""Append multiple directly clicked assembly-slot polygons in fixed order."""
import argparse, json, time
from pathlib import Path
import cv2
import numpy as np

ORDER=('TOP-LEFT','TOP-RIGHT','BOTTOM-RIGHT','BOTTOM-LEFT')

def main():
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--slot-codes',nargs='+',required=True);a=p.parse_args()
 image=cv2.imread(str(a.image))
 if image is None:raise SystemExit(f'cannot read {a.image}')
 payload=json.loads(a.output.read_text()) if a.output.exists() else {'schema_version':1,'slots':[]}
 saved={str(x['slot_code']):x for x in payload.get('slots',[])}
 window='DIRECT ASSEMBLY SLOT BATCH';points=[];current=[a.slot_codes[0]]
 def redraw():
  shown=image.copy();cv2.rectangle(shown,(0,0),(shown.shape[1],78),(18,24,30),-1)
  slot=current[0];idx=a.slot_codes.index(slot)+1;instruction='DONE - press ENTER' if len(points)==4 else f'Click corner {len(points)+1}/4'
  cv2.putText(shown,f'{slot}  ({idx}/{len(a.slot_codes)})',(20,31),cv2.FONT_HERSHEY_SIMPLEX,.82,(255,255,255),2)
  cv2.putText(shown,instruction+'  [R reset / Q stop]',(20,65),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,255),2)
  for old in saved.values():
   poly=np.asarray(old['polygon_image_pixel'],np.int32);cv2.polylines(shown,[poly],True,(115,115,115),1,cv2.LINE_AA)
   center=np.rint(poly.mean(0)).astype(int);cv2.putText(shown,old['slot_code'],tuple(center),cv2.FONT_HERSHEY_SIMPLEX,.28,(150,150,150),1)
  for i,pt in enumerate(points):cv2.circle(shown,pt,3,(0,0,255),-1);cv2.putText(shown,str(i+1),(pt[0]+5,pt[1]-5),cv2.FONT_HERSHEY_SIMPLEX,.38,(0,0,255),1)
  if len(points)>1:cv2.polylines(shown,[np.asarray(points,np.int32)],len(points)==4,(0,255,255),1,cv2.LINE_AA)
  cv2.imshow(window,shown)
 def mouse(event,x,y,flags,param):
  if event==cv2.EVENT_LBUTTONDOWN and len(points)<4 and y>=78:points.append((x,y));redraw()
 cv2.namedWindow(window,cv2.WINDOW_NORMAL);cv2.setWindowProperty(window,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN);cv2.setMouseCallback(window,mouse);redraw()
 index=0
 while True:
  key=cv2.waitKey(30)&0xff
  if key in (ord('q'),27):break
  if key==ord('r'):points.clear();redraw()
  if key in (10,13,32) and len(points)==4:
   code=a.slot_codes[index];saved[code]={'slot_code':code,'polygon_image_pixel':[list(x) for x in points],'status':'operator_direct_annotation'}
   payload.update({'timestamp_unix':time.time(),'source_image':str(a.image.resolve()),'image_size':[image.shape[1],image.shape[0]],'coordinate_frame':'PlaceCamera_image_pixel','display_only':True,'slots':list(saved.values())})
   a.output.write_text(json.dumps(payload,indent=2));print('Saved',code,flush=True);index+=1
   if index>=len(a.slot_codes):break
   current[0]=a.slot_codes[index];points.clear();redraw()
 cv2.destroyAllWindows();print(f'Completed {index}/{len(a.slot_codes)} requested slots')

if __name__=='__main__':main()
