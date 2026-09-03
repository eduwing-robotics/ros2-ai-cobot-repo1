#!/usr/bin/env python3
"""Register and detect the configured SMD section without full-tray visibility."""
import argparse,json,math,time
from pathlib import Path
import cv2
import numpy as np


def normalize_axis(angle):return (float(angle)+90.0)%180.0-90.0

def resolve_reference(config_path,configured):
 path=Path(configured)
 if path.is_absolute():return path
 repo=config_path.resolve().parents[2]
 return repo/path

def register_clean_section(image,config,config_path):
 reference_path=resolve_reference(config_path,config['clean_reference_raw'])
 reference=cv2.imread(str(reference_path))
 if reference is None:raise RuntimeError(f'cannot read clean reference {reference_path}')
 sift=cv2.SIFT_create(nfeatures=2500,contrastThreshold=.02,edgeThreshold=12)
 ref_gray=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY);cur_gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
 ref_key,ref_desc=sift.detectAndCompute(ref_gray,None);cur_key,cur_desc=sift.detectAndCompute(cur_gray,None)
 if ref_desc is None or cur_desc is None:raise RuntimeError('SMD section feature descriptors unavailable')
 pairs=cv2.BFMatcher(cv2.NORM_L2).knnMatch(ref_desc,cur_desc,k=2)
 good=[pair[0] for pair in pairs if len(pair)==2 and pair[0].distance<.72*pair[1].distance]
 if len(good)<25:raise RuntimeError(f'SMD section registration needs 25 matches; got {len(good)}')
 source=np.float32([ref_key[m.queryIdx].pt for m in good]).reshape(-1,1,2)
 target=np.float32([cur_key[m.trainIdx].pt for m in good]).reshape(-1,1,2)
 transform,inlier=cv2.findHomography(source,target,cv2.RANSAC,3.0)
 inliers=int(inlier.sum()) if inlier is not None else 0
 if transform is None or inliers<18:raise RuntimeError(f'SMD section registration needs 18 inliers; got {inliers}')
 polygon=np.asarray(config['section_polygon_pixel'],np.float32).reshape(-1,1,2)
 current=cv2.perspectiveTransform(polygon,transform)[:,0,:]
 area=abs(float(cv2.contourArea(current)))/abs(float(cv2.contourArea(polygon[:,0,:])))
 if not .80<=area<=1.20:raise RuntimeError(f'SMD section registration scale area {area:.3f} outside [0.80,1.20]')
 return current,{'mode':'clean_section_feature_homography','reference_image':str(reference_path),'matches':len(good),'inliers':inliers,'scale_area':round(area,5),'current_polygon_pixel':np.round(current,3).tolist()}

def contour_axis_deg(contour):
 rect=cv2.minAreaRect(contour)
 width,height=map(float,rect[1]);angle=float(rect[2])
 if height>width:angle+=90.0
 return normalize_axis(angle)

def detect(image,config,config_path):
 source,registration=register_clean_section(image,config,config_path)
 detection_config=config['learned_detection']
 required_count=int(detection_config['required_count'])
 row_size=int(detection_config.get('row_size',required_count))
 width,height=map(int,config['canonical_size']);destination=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
 homography=cv2.getPerspectiveTransform(source.astype(np.float32),destination);inverse=np.linalg.inv(homography)
 rectified=cv2.warpPerspective(image,homography,(width,height));hsv=cv2.cvtColor(rectified,cv2.COLOR_BGR2HSV)
 mask=((hsv[:,:,1]>=35)&(hsv[:,:,2]<=190)).astype(np.uint8)*255
 mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8));mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
 contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);candidates=[]
 for contour in contours:
  area=float(cv2.contourArea(contour))
  if not 300.0<=area<=900.0:continue
  x,y,w,h=cv2.boundingRect(contour)
  if x<8 or y<8 or x+w>width-8 or y+h>height-8:continue
  rect=cv2.minAreaRect(contour);center=np.asarray(rect[0],float);sizes=sorted(map(float,rect[1]))
  if sizes[0]<14 or sizes[1]>50:continue
  angle=contour_axis_deg(contour);src=cv2.perspectiveTransform(center.astype(np.float32).reshape(1,1,2),inverse)[0,0]
  candidates.append({'center_canonical_pixel':center,'center_source_pixel':src,'area_px':area,'axis_canonical_deg':angle,'bbox':[x,y,w,h]})
 if len(candidates)!=required_count:raise RuntimeError(f'exactly {required_count} SMDs required inside registered section; got {len(candidates)}')
 by_y=sorted(candidates,key=lambda item:item['center_canonical_pixel'][1]);ordered=[]
 for start in range(0,required_count,row_size):ordered.extend(sorted(by_y[start:start+row_size],key=lambda item:item['center_canonical_pixel'][0]))
 annotated=rectified.copy();result=[]
 for index,item in enumerate(ordered,1):
  center=np.rint(item['center_canonical_pixel']).astype(int);angle=math.radians(item['axis_canonical_deg']);direction=np.array([math.cos(angle),math.sin(angle)])
  p1=np.rint(center-direction*28).astype(int);p2=np.rint(center+direction*28).astype(int)
  cv2.circle(annotated,tuple(center),5,(0,0,255),-1);cv2.line(annotated,tuple(p1),tuple(p2),(255,0,255),2,cv2.LINE_AA);cv2.putText(annotated,str(index),tuple(center+np.array([8,-8])),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2,cv2.LINE_AA)
  result.append({'instance_index':index,'center_canonical_pixel':np.round(item['center_canonical_pixel'],3).tolist(),'center_source_pixel':np.round(item['center_source_pixel'],3).tolist(),'area_px':round(item['area_px'],1),'long_axis_canonical_deg':round(item['axis_canonical_deg'],4),'bbox':item['bbox']})
 return registration,rectified,mask,annotated,result

def main():
 root=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'data/smd_section_clean_reference_raw.jpg');parser.add_argument('--config',type=Path,default=root/'config/smd_section_view.json');parser.add_argument('--output-json',type=Path,default=root/'data/smd_section_detections.json');parser.add_argument('--output-image',type=Path,default=root/'data/smd_section_detections.jpg');parser.add_argument('--output-mask',type=Path,default=root/'data/smd_section_mask.png');args=parser.parse_args()
 image=cv2.imread(str(args.input));
 if image is None:raise RuntimeError(f'cannot read {args.input}')
 config=json.loads(args.config.read_text(encoding='utf-8'));registration,rectified,mask,annotated,detections=detect(image,config,args.config)
 payload={'schema_version':2,'mode':'clean_registered_smd_section','timestamp_unix':time.time(),'source_image':str(args.input),'config_file':str(args.config),'tray_registration_required':False,'tape_required':False,'registration':registration,'detection_count':len(detections),'detections':detections}
 args.output_json.write_text(json.dumps(payload,indent=2),encoding='utf-8');cv2.imwrite(str(args.output_image),annotated,[cv2.IMWRITE_JPEG_QUALITY,95]);cv2.imwrite(str(args.output_mask),mask);print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
