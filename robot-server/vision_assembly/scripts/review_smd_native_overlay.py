#!/usr/bin/env python3
"""Project saved candidate geometry onto native pixels; no new targets or motion."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
edge=json.loads((a.directory/'terminal_edge_comparison.json').read_text())
obb=json.loads((a.directory/'analysis.json').read_text())
cfg=json.loads((Path(__file__).resolve().parents[1]/'config/smd_section_view.json').read_text())
rows=[r for r in edge['results'] if r['kind']=='jpeg' and 'center' in r]
by_obb={r['index']:r for r in obb['results'] if r['kind']=='jpeg' and 'box' in r}
centers=np.array([r['center'] for r in rows]);median=np.median(centers,0)
reference=edge['summary']['jpeg']['angle_median']
angle_delta=lambda r:(r['angle']-reference+90)%180-90
chosen=[rows[int(np.argmin(np.linalg.norm(centers-median,axis=1)))],
        min(rows,key=angle_delta),max(rows,key=angle_delta)]
w,h=cfg['canonical_size'];dst=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
sheet=np.full((len(chosen)*325,3*300,3),245,np.uint8);metrics=[]
for row,r in enumerate(chosen):
    im=cv2.imread(str(a.directory/f"{r['index']:03d}_jpeg.jpg"))
    scale=np.float32([im.shape[1],im.shape[0]])/cfg['source_image_size']
    H=cv2.getPerspectiveTransform(np.float32(cfg['section_polygon_pixel'])*scale.astype(np.float32),dst)
    inv=np.linalg.inv(H)
    def project(points):return cv2.perspectiveTransform(np.float32(points).reshape(-1,1,2),inv)[:,0]
    source_center=project([r['center']])[0];x0,y0=np.rint(source_center-[30,32]).astype(int)
    crop=im[y0:y0+64,x0:x0+60];base=cv2.resize(crop,(240,256),interpolation=cv2.INTER_NEAREST)
    def panel_points(points):return np.rint((project(points)-[x0,y0])*4).astype(int)
    edge_panel=base.copy();obb_panel=base.copy();cx,cy=r['roi'];center=np.array(r['center'])
    for m,b,_ in r['terminal_lines']:
        points=panel_points([[cx-22,cy+m*(-22)+b],[cx+22,cy+m*22+b]])
        cv2.line(edge_panel,tuple(points[0]),tuple(points[1]),(0,180,0),1)
    for m,b,_ in r['body_sides']:
        points=panel_points([[cx+m*(-14)+b,cy-14],[cx+m*14+b,cy+14]])
        cv2.line(edge_panel,tuple(points[0]),tuple(points[1]),(0,180,0),1)
    v=np.array([np.cos(np.deg2rad(r['angle'])),np.sin(np.deg2rad(r['angle']))])
    points=panel_points([center-v*33,center+v*33]);cv2.line(edge_panel,tuple(points[0]),tuple(points[1]),(255,180,0),1)
    pc=panel_points([center])[0];cv2.drawMarker(edge_panel,tuple(pc),(0,0,255),cv2.MARKER_CROSS,13,1)
    o=by_obb[r['index']];cv2.polylines(obb_panel,[panel_points(o['box'])],True,(0,0,255),1)
    op=panel_points([o['center']])[0];cv2.drawMarker(obb_panel,tuple(op),(0,0,255),cv2.MARKER_CROSS,13,1)
    native_delta=project([r['center']])[0]-project([o['center']])[0]
    metrics.append(dict(frame=r['index'],edge_center_canonical=r['center'],edge_angle_canonical=r['angle'],
                        edge_center_native=source_center.tolist(),edge_minus_obb_native_px=native_delta.tolist()))
    for col,(label,panel) in enumerate([('Native pixels x4',base),('Edges + center + axis',edge_panel),('Existing OBB',obb_panel)]):
        x=col*300;y=row*325
        sheet[y+40:y+296,x+30:x+270]=panel
        cv2.putText(sheet,f"{r['index']:03d} {label}",(x+8,y+23),cv2.FONT_HERSHEY_SIMPLEX,.48,(0,0,0),1)
        if col==1:cv2.putText(sheet,f"canonical axis {r['angle']:.2f} deg",(x+8,y+317),cv2.FONT_HERSHEY_SIMPLEX,.43,(0,0,0),1)
cv2.imwrite(str(a.directory/'native_center_axis_review.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,90])
(a.directory/'native_center_axis_review.json').write_text(json.dumps(dict(diagnostic_only=True,robot_motion_authorized=False,frames=metrics),indent=2))
print(json.dumps(metrics,indent=2))
