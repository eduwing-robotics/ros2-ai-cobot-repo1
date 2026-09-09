"""Extract dimension-matched horizontal CAD faces, without runtime authority.

Face polygons are candidate cavity floors, NOT certified printed inner walls.
OBJ coordinates are retained; no implicit mirroring onto current slot overrides.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def extract(mesh, clearance):
    vertices, faces = [], []
    for line in mesh.read_text().splitlines():
        a = line.split()
        if not a:
            continue
        if a[0] == 'v':
            vertices.append(tuple(float(v)*10 for v in a[1:4]))
        elif a[0] == 'f':
            indices = [int(v.split('/')[0]) for v in a[1:]]
            faces.append([vertices[i-1 if i > 0 else i] for i in indices])
    candidates = []
    for index, points in enumerate(faces):
        if max(p[1] for p in points)-min(p[1] for p in points) > 0.0001:
            continue
        low = [min(p[a] for p in points) for a in (0,2)]
        high = [max(p[a] for p in points) for a in (0,2)]
        size = [b-a for a,b in zip(low,high)]
        for name, spec in clearance['component_types'].items():
            expected = sorted(spec['socket_size_local_mm'])
            if max(abs(a-b) for a,b in zip(sorted(size),expected)) > 0.02:
                continue
            candidates.append(dict(face_index=index, component_type=name,
                center_obj_xz_mm=[(a+b)/2 for a,b in zip(low,high)],
                size_obj_xz_mm=size, floor_obj_y_mm=points[0][1],
                polygon_obj_xz_mm=[[p[0],p[2]] for p in points]))
    return candidates


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--mesh', type=Path, default=Path('/home/hc/My project/Assets/반도체 기판 모델링(Unity)/ASt/motherBoard.obj'))
    args = parser.parse_args()
    spec = json.loads((ROOT/'vision_assembly/config/unity_socket_clearance.json').read_text())
    candidates = extract(args.mesh, spec)
    print(json.dumps(dict(source=str(args.mesh), source_sha256=hashlib.sha256(args.mesh.read_bytes()).hexdigest(),
        obj_scale_to_mm=10, status='CAD_FACE_CANDIDATES_ONLY',
        counts={k:sum(c['component_type']==k for c in candidates) for k in spec['component_types']},
        candidates=candidates,
        limitation='Dimension matching is not cavity topology certification. OBJ orientation, physical slot overrides, wall height and print differences require validation; no runtime mapping or verdict changes.'), indent=2))


if __name__ == '__main__':
    main()
