"""Inspect the Unity PCB OBJ assets without modifying the Unity project.

Run with:
  blender -b --factory-startup --python probe_pcb_models.py -- --assets-dir <ASt>
"""

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    tail = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", type=Path, required=True)
    return parser.parse_args(tail)


def object_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector(map(min, zip(*corners))), Vector(map(max, zip(*corners)))


def main():
    args = parse_args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for path in sorted(args.assets_dir.glob("*.obj")):
        bpy.ops.wm.obj_import(filepath=str(path), forward_axis="Y", up_axis="Z")
        imported = list(bpy.context.selected_objects)
        print(f"ASSET {path.name}: {len(imported)} object(s)")
        for obj in imported:
            lower, upper = object_bounds(obj)
            size = upper - lower
            centre = (lower + upper) * 0.5
            print(
                f"  {obj.name}: center={tuple(round(v, 4) for v in centre)}, "
                f"size={tuple(round(v, 4) for v in size)}"
            )
        bpy.ops.object.select_all(action="DESELECT")


if __name__ == "__main__":
    main()
