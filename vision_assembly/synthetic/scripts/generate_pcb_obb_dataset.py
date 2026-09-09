"""Render a synthetic PCB inspection dataset and matching YOLO-OBB labels.

Reads the Unity OBJ assets without modifying the Unity project.  It is designed
for Blender background mode; see ../README.md.
"""

import argparse
import csv
import json
import math
import random
import shutil
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


CLASSES = ["gpu", "hbm", "power_module", "vrm", "inductor", "smd_capacitor"]
CLASS_INDEX = {name: index for index, name in enumerate(CLASSES)}

# Historical fallback. Runtime rendering reads the current Unity scene export
# (`Assets/RobotArm/PcbPickCoordinates.csv`) rather than rebuilding this table.
SLOTS_MM = {
    "gpu_01": ("gpu", 70.000, 55.169, 0.0),
    "hbm_01": ("hbm", 46.000, 30.669, 0.0), "hbm_02": ("hbm", 46.000, 46.869, 0.0),
    "hbm_03": ("hbm", 46.000, 63.369, 0.0), "hbm_04": ("hbm", 46.000, 79.269, 0.0),
    "hbm_05": ("hbm", 93.700, 30.669, 0.0), "hbm_06": ("hbm", 93.700, 46.869, 0.0),
    "hbm_07": ("hbm", 93.700, 63.369, 0.0), "hbm_08": ("hbm", 93.700, 79.269, 0.0),
    "power_module_01": ("power_module", 117.486, 55.480, 0.0),
    "power_module_02": ("power_module", 23.080, 55.480, 0.0),
    "power_module_03": ("power_module", 70.141, 11.138, 90.0),
    "power_module_04": ("power_module", 70.141, 99.038, 90.0),
    "vrm_01": ("vrm", 131.510, 18.709, 0.0), "vrm_02": ("vrm", 131.510, 36.969, 0.0),
    "vrm_03": ("vrm", 131.510, 54.969, 0.0), "vrm_04": ("vrm", 131.510, 73.229, 0.0),
    "vrm_05": ("vrm", 131.510, 91.769, 0.0),
    "inductor_01": ("inductor", 9.897, 88.141, 0.0), "inductor_02": ("inductor", 9.897, 99.601, 0.0),
    "smd_capacitor_01": ("smd_capacitor", 8.800, 73.136, 0.0),
    "smd_capacitor_02": ("smd_capacitor", 8.800, 55.733, 0.0),
    "smd_capacitor_03": ("smd_capacitor", 8.800, 38.933, 0.0),
    "smd_capacitor_04": ("smd_capacitor", 8.800, 21.633, 0.0),
    "smd_capacitor_05": ("smd_capacitor", 28.066, 94.474, 90.0),
}
ASSET_BY_CLASS = {
    "gpu": "nvidia.obj", "hbm": "Sk_hynix.obj", "power_module": "YellowBar.obj",
    "vrm": "BlackBox1.obj", "inductor": "cap_Big.obj", "smd_capacitor": "cap_small.obj",
}
TEXTURE_BY_CLASS = {
    "board": "motherboard.png", "gpu": "Nvidia.png", "hbm": "sk_hynix.png",
    "power_module": "YellowBar.png", "vrm": "BlackBox.png", "inductor": "Cap_big.png",
    "smd_capacitor": "cap_small.png",
}
COLOURS = {
    "board": (0.015, 0.018, 0.022, 1.0), "gpu": (0.035, 0.045, 0.050, 1.0),
    "hbm": (0.050, 0.038, 0.030, 1.0), "power_module": (0.92, 0.56, 0.025, 1.0),
    "vrm": (0.72, 0.64, 0.47, 1.0), "inductor": (0.72, 0.74, 0.74, 1.0),
    "smd_capacitor": (0.83, 0.72, 0.49, 1.0),
}


def parse_args():
    tail = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument(
        "--layout-csv",
        type=Path,
        help="Current Unity PcbPickCoordinates.csv; inferred from --assets-dir when omitted.",
    )
    parser.add_argument(
        "--fixture-file",
        type=Path,
        help="Unity PCB fixture FBX; inferred from Assets/RobotArm/Fixture when omitted.",
    )
    parser.add_argument(
        "--unity-validation-json",
        type=Path,
        help="Unity-native scene bounds export used as the transform authority.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=960)
    return parser.parse_args(tail)


def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def material(name, colour, texture_path=None):
    value = bpy.data.materials.new(name)
    value.use_nodes = True
    nodes = value.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = colour
    shader.inputs["Roughness"].default_value = 0.42
    shader.inputs["Metallic"].default_value = 0.08
    value.diffuse_color = colour
    emission = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
    if emission is not None:
        emission.default_value = colour
    strength = shader.inputs.get("Emission Strength")
    if strength is not None:
        strength.default_value = 0.55
    if texture_path is not None and texture_path.is_file():
        image_node = nodes.new("ShaderNodeTexImage")
        image_node.image = bpy.data.images.load(str(texture_path), check_existing=True)
        value.node_tree.links.new(image_node.outputs["Color"], shader.inputs["Base Color"])
    value.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return value


def set_material(obj, value):
    obj.data.materials.clear()
    obj.data.materials.append(value)
    # Imported OBJ meshes retain material-slot indices.  Reset every face to
    # the only new slot so missing Unity UDIM textures do not fall back to
    # Blender's white default material.
    for polygon in obj.data.polygons:
        polygon.material_index = 0


def import_master(path, class_name):
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis="Y", up_axis="Z")
    imported = list(bpy.context.selected_objects)
    if len(imported) != 1:
        raise RuntimeError(f"Expected one object in {path.name}, got {len(imported)}")
    obj = imported[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (0.01, 0.01, 0.01)  # The Unity assembled prefab uses 0.01.
    obj.name = f"master_{class_name}"
    obj.hide_render = True
    obj.hide_viewport = True
    return obj


def hierarchy_meshes(root):
    return [obj for obj in [root, *root.children_recursive] if obj.type == "MESH"]


def hierarchy_bounds(root):
    points = [obj.matrix_world @ Vector(corner) for obj in hierarchy_meshes(root) for corner in obj.bound_box]
    return Vector(tuple(min(p[axis] for p in points) for axis in range(3))), Vector(
        tuple(max(p[axis] for p in points) for axis in range(3))
    )


def broad_horizontal_support_y(root):
    """Match Unity's broad-support-plane calculation and ignore raised pins."""
    buckets = {}
    bucket_size = 0.00005
    for obj in hierarchy_meshes(root):
        mesh = obj.data
        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            a, b, c = (obj.matrix_world @ mesh.vertices[index].co for index in tri.vertices)
            cross = (b - a).cross(c - a)
            doubled_area = cross.length
            if doubled_area < 1e-12:
                continue
            normal = cross / doubled_area
            if abs(normal.y) < 0.98:
                continue
            area = doubled_area * 0.5
            surface_y = (a.y + b.y + c.y) / 3.0
            key = round(surface_y / bucket_size)
            total_area, weighted_y = buckets.get(key, (0.0, 0.0))
            buckets[key] = (total_area + area, weighted_y + area * surface_y)
    if not buckets:
        raise RuntimeError("Could not identify fixture support surface")
    largest = max(area for area, _ in buckets.values())
    candidates = [(weighted / area, area) for area, weighted in buckets.values() if area >= largest * 0.45]
    return max(candidates)[0]


def import_fixture(path, board, unity_fixture_reference):
    """Import and align the real Unity fixture under the PCB.

    The fixture is permanent scene structure, not a detection class. Its long
    direction and handle point toward board +Z (north), matching Unity.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"Fixture FBX contains no mesh: {path}")
    root = bpy.data.objects.new("pcb_fixture", None)
    bpy.context.collection.objects.link(root)
    imported_set = set(imported)
    for obj in imported:
        if obj.parent not in imported_set:
            obj.parent = root

    # Reproduce PcbAssemblySetup.cs exactly: source FBX is modelled in XY with
    # Z thickness; Unity rotates it -90 degrees around X so pins face +Y.
    low, high = hierarchy_bounds(root)
    source_size = high - low
    thin_axis = min(range(3), key=lambda axis: source_size[axis])
    if thin_axis == 2:
        root.rotation_euler.x = math.radians(-90.0)
    elif thin_axis == 0:
        root.rotation_euler.z = math.radians(90.0)
    # Blender's FBX importer resolves the fixture plane 180 degrees opposite
    # to Unity. Correct only this importer difference so the handle appears on
    # the same board edge as the saved Unity scene.
    root.rotation_euler.y += math.radians(180.0)
    bpy.context.view_layer.update()

    # Match the measured fixture envelope used by the Unity assembly setup.
    low, high = hierarchy_bounds(root)
    width, depth = high.x - low.x, high.z - low.z
    if width > depth:
        root.rotation_euler.y += math.radians(90.0)
        bpy.context.view_layer.update()
        low, high = hierarchy_bounds(root)
        width, depth = high.x - low.x, high.z - low.z
    width_scale, depth_scale = 0.08529513 / width, 0.12482180 / depth
    scale = (width_scale + depth_scale) * 0.5
    if abs(width_scale - depth_scale) > 0.02 * scale:
        raise RuntimeError(f"Fixture FBX aspect mismatch: {width_scale:.5f}, {depth_scale:.5f}")
    root.scale *= scale
    bpy.context.view_layer.update()

    # Align the four-pin pattern with the PCB centre. The small ratios encode
    # the pin-pattern offset measured from the complete fixture model bounds.
    low, high = hierarchy_bounds(root)
    centre = (low + high) * 0.5
    pin_x = centre.x - 0.00375 * (high.x - low.x)
    pin_z = centre.z - 0.06061 * (high.z - low.z)
    # Match the final manually verified Unity fit. The tiny correction is the
    # saved pin/hole-centering adjustment, not a vision/TCP correction.
    root.location.x += 0.00031985 - pin_x
    root.location.z += 0.00008084 - pin_z
    bpy.context.view_layer.update()

    # Match Unity's broad seating plane calculation; raised pin tops must pass
    # through the holes and must not be mistaken for the support surface.
    board_low, _ = hierarchy_bounds(board)
    root.location.y += board_low.y - broad_horizontal_support_y(root)
    bpy.context.view_layer.update()
    # Final authority is the renderer Bounds exported by Unity itself. FBX
    # importer conventions may differ, so snap the complete imported hierarchy
    # to the exact saved Unity centre after reproducing orientation and scale.
    low, high = hierarchy_bounds(root)
    current_center = (low + high) * 0.5
    target_center = Vector(unity_fixture_reference["center_m"])
    root.location += target_center - current_center
    bpy.context.view_layer.update()
    return root


def local_height(obj):
    return (max(c[1] for c in obj.bound_box) - min(c[1] for c in obj.bound_box)) * 0.01


def duplicate(master, value, name, x_m, z_m, yaw_deg, top_y_m):
    obj = master.copy()
    obj.data = master.data.copy()
    bpy.context.collection.objects.link(obj)
    obj.hide_render = False
    obj.hide_viewport = False
    obj.name = name
    set_material(obj, value)
    # `top_y_m` is the exact top-centre value exported from the currently
    # placed Unity scene. It avoids guessing a common board surface height.
    obj.location = (x_m, top_y_m - local_height(obj) / 2.0, z_m)
    obj.rotation_euler = (0.0, math.radians(yaw_deg), 0.0)
    return obj


def look_at(obj, target=(0.0, 0.0, 0.0)):
    # The camera looks almost along world -Y.  Y cannot be used as its image-up
    # axis in that pose, so board +Z is the stable image-up reference.
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Z").to_euler()


def add_area_light(name, location, energy, size, colour):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy, data.shape, data.size, data.color = energy, "DISK", size, colour
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj)
    return obj


def hull(points):
    points = sorted(set((float(x), float(y)) for x, y in points))
    if len(points) < 3:
        return []
    def turn(origin, a, b):
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])
    lower = []
    for point in points:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(points):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def minimum_area_rectangle(points):
    contour = hull(points)
    if len(contour) < 3:
        return None
    best = None
    for first, second in zip(contour, contour[1:] + contour[:1]):
        theta = math.atan2(second[1] - first[1], second[0] - first[0])
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        rotated = [(x * cos_t + y * sin_t, -x * sin_t + y * cos_t) for x, y in contour]
        x0, x1 = min(x for x, _ in rotated), max(x for x, _ in rotated)
        y0, y1 = min(y for _, y in rotated), max(y for _, y in rotated)
        area = (x1 - x0) * (y1 - y0)
        if best is None or area < best[0]:
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            restored = [(x * cos_t - y * sin_t, x * sin_t + y * cos_t) for x, y in corners]
            best = area, restored
    return best[1]


def obb(scene, camera, obj):
    projected = []
    for vertex in obj.data.vertices:
        image = world_to_camera_view(scene, camera, obj.matrix_world @ vertex.co)
        if image.z > 0.0:
            projected.append((image.x, image.y))
    rect = minimum_area_rectangle(projected)
    if rect is None or any(x < -0.03 or x > 1.03 or y < -0.03 or y > 1.03 for x, y in rect):
        return None
    return [(min(1.0, max(0.0, x)), min(1.0, max(0.0, y))) for x, y in rect]


def prepare_scene(width, height):
    scene = bpy.context.scene
    # Blender 5.2 exposes the real-time engine with this compatibility enum.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.035, 0.035, 0.035)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.7
    camera = bpy.data.objects.new("inspection_camera", bpy.data.cameras.new("inspection_camera"))
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    # Imported Unity assets use Y as their up axis, therefore the inspection
    # table must lie in X/Z (not Blender's default X/Y) plane.
    bpy.ops.mesh.primitive_plane_add(size=2.5, location=(0.0, -0.008, 0.0), rotation=(math.radians(90.0), 0.0, 0.0))
    floor = bpy.context.object
    set_material(floor, material("floor", (0.30, 0.31, 0.33, 1.0)))
    return scene, camera, floor


def randomise_camera(camera, rng):
    camera.location = (rng.uniform(-0.025, 0.025), rng.uniform(0.43, 0.50), rng.uniform(-0.020, 0.020))
    look_at(camera, (rng.uniform(-0.008, 0.008), 0.0, rng.uniform(-0.006, 0.006)))
    camera.data.lens = rng.uniform(47.0, 58.0)


def class_from_unity_source(source_name):
    value = source_name.casefold()
    if "gpu" in value:
        return "gpu"
    if "hbm" in value:
        return "hbm"
    if "power module" in value:
        return "power_module"
    if "vrm" in value:
        return "vrm"
    if "inductor" in value:
        return "inductor"
    if "smd capacitor" in value:
        return "smd_capacitor"
    raise RuntimeError(f"Unsupported Unity source_name: {source_name}")


def load_unity_layout(path):
    if not path.is_file():
        raise RuntimeError(f"Unity layout CSV does not exist: {path}")
    placements = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            kind = class_from_unity_source(row["source_name"])
            placements.append(
                {
                    "slot": row["part_id"].casefold(),
                    "source_name": row["source_name"],
                    "kind": kind,
                    "x_m": float(row["unity_world_x_m"]),
                    "top_y_m": float(row["unity_world_y_m"]),
                    "z_m": float(row["unity_world_z_m"]),
                    "yaw_deg": float(row["rotation_y_deg"]),
                }
            )
    expected = {"gpu": 1, "hbm": 8, "power_module": 4, "vrm": 5, "inductor": 2, "smd_capacitor": 5}
    actual = {kind: sum(item["kind"] == kind for item in placements) for kind in CLASSES}
    if actual != expected:
        raise RuntimeError(f"Unexpected Unity component count: {actual}; expected {expected}")
    return placements


def load_unity_fixture_reference(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    fixture = next((item for item in payload.get("items", []) if item.get("name") == "PCB Fixture"), None)
    if fixture is None:
        raise RuntimeError(f"PCB Fixture is missing from Unity validation JSON: {path}")
    if len(fixture.get("center_m", [])) != 3 or len(fixture.get("size_m", [])) != 3:
        raise RuntimeError(f"Invalid PCB Fixture bounds in Unity validation JSON: {path}")
    return fixture


def main():
    args = parse_args()
    if not args.assets_dir.is_dir():
        raise RuntimeError(f"Missing OBJ asset directory: {args.assets_dir}")
    if args.count < 1:
        raise RuntimeError("--count must be >= 1")
    layout_csv = args.layout_csv or args.assets_dir.parents[1] / "RobotArm" / "PcbPickCoordinates.csv"
    fixture_file = args.fixture_file or args.assets_dir.parents[1] / "RobotArm" / "Fixture" / "Cube.001.fbx"
    validation_json = args.unity_validation_json or Path(__file__).resolve().parents[1] / "config" / "unity_current_exact.json"
    placements = load_unity_layout(layout_csv.expanduser().resolve())
    fixture_file = fixture_file.expanduser().resolve()
    if not fixture_file.is_file():
        raise RuntimeError(f"Unity fixture FBX does not exist: {fixture_file}")
    validation_json = validation_json.expanduser().resolve()
    if not validation_json.is_file():
        raise RuntimeError(f"Unity validation JSON does not exist: {validation_json}")
    unity_fixture_reference = load_unity_fixture_reference(validation_json)
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        shutil.rmtree(output)
    images, labels, metadata = output / "images", output / "labels", output / "metadata"
    for directory in (images, labels, metadata):
        directory.mkdir(parents=True, exist_ok=True)
    (output / "dataset.yaml").write_text(
        "path: .\ntrain: images\nval: images\nnames:\n" + "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASSES)) + "\n",
        encoding="utf-8",
    )

    reset()
    scene, camera, floor = prepare_scene(args.width, args.height)
    board_master = import_master(args.assets_dir / "motherBoard.obj", "board")
    masters = {key: import_master(args.assets_dir / asset, key) for key, asset in ASSET_BY_CLASS.items()}
    materials = {
        key: material(f"mat_{key}", colour, args.assets_dir / TEXTURE_BY_CLASS[key])
        for key, colour in COLOURS.items()
    }
    board = board_master.copy()
    board.data = board_master.data.copy()
    bpy.context.collection.objects.link(board)
    board.hide_render = board.hide_viewport = False
    set_material(board, materials["board"])
    fixture = import_fixture(fixture_file, board, unity_fixture_reference)
    fixture_low, fixture_high = hierarchy_bounds(fixture)
    floor.location.y = min(-0.008, fixture_low.y - 0.002)
    key = add_area_light("key", (-0.15, 0.38, 0.10), 60, 0.17, (1.0, 0.95, 0.88))
    fill = add_area_light("fill", (0.16, 0.28, -0.16), 20, 0.12, (0.82, 0.90, 1.0))

    for index in range(args.count):
        rng = random.Random(args.seed + index)
        for obj in [obj for obj in bpy.data.objects if obj.name.startswith("part_")]:
            bpy.data.objects.remove(obj, do_unlink=True)
        scenario = {"missing": [], "position_error": [], "orientation_error": []}
        present = {item["slot"] for item in placements}
        # Keep every fifth sample as a clean normal assembly reference.
        faulty = index % 5 != 0
        if faulty and rng.random() < 0.30:
            scenario["missing"] = rng.sample(sorted(present), rng.randint(1, 3))
            present.difference_update(scenario["missing"])
        parts = []
        for placement in placements:
            slot = placement["slot"]
            if slot not in present:
                continue
            kind = placement["kind"]
            x_m, z_m, top_y_m, yaw = placement["x_m"], placement["z_m"], placement["top_y_m"], placement["yaw_deg"]
            dx = dz = yaw_offset = 0.0
            if faulty and rng.random() < 0.20:
                direction, radius = rng.uniform(0.0, math.tau), rng.uniform(1.0, 5.0)
                dx, dz = math.cos(direction) * radius, math.sin(direction) * radius
                scenario["position_error"].append(slot)
            if faulty and rng.random() < 0.20:
                yaw_offset = rng.choice((-1.0, 1.0)) * rng.uniform(15.0, 60.0)
                scenario["orientation_error"].append(slot)
            part = duplicate(masters[kind], materials[kind], f"part_{slot}", x_m + dx / 1000.0, z_m + dz / 1000.0, yaw + yaw_offset, top_y_m)
            parts.append((slot, kind, part, x_m + dx / 1000.0, z_m + dz / 1000.0, yaw + yaw_offset))
        randomise_camera(camera, rng)
        key.data.energy, fill.data.energy = rng.uniform(35, 75), rng.uniform(8, 30)
        bpy.context.view_layer.update()
        stem = f"{index:06d}"
        scene.render.filepath = str(images / f"{stem}.png")
        bpy.ops.render.render(write_still=True)
        rows, part_rows = [], []
        for slot, kind, part, x_m, z_m, yaw in parts:
            rectangle = obb(scene, camera, part)
            if rectangle is None:
                continue
            part_low, part_high = hierarchy_bounds(part)
            part_center, part_size = (part_low + part_high) * 0.5, part_high - part_low
            rows.append(f"{CLASS_INDEX[kind]} " + " ".join(f"{coordinate:.7f}" for point in rectangle for coordinate in point))
            part_rows.append({
                "slot": slot,
                "class": kind,
                "board_xy_mm": [round(x_m * 1000.0, 3), round(z_m * 1000.0, 3)],
                "world_center_mm": [round(v * 1000.0, 3) for v in part_center],
                "world_size_mm": [round(v * 1000.0, 3) for v in part_size],
                "yaw_deg": round(yaw, 3),
            })
        (labels / f"{stem}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
        (metadata / f"{stem}.json").write_text(json.dumps({
            "image": f"images/{stem}.png", "unity_layout_csv": str(layout_csv), "scenario": scenario, "parts": part_rows,
            "fixture": {
                "included": True,
                "source": str(fixture_file),
                "unity_validation_json": str(validation_json),
                "role": "pcb_transport_and_storage_handle",
                "handle_direction_board": "-Z_saved_unity_scene",
                "fixture_fine_tune_xz_mm": [0.31985, 0.08084],
                "world_center_mm": [round(v * 1000.0, 3) for v in (fixture_low + fixture_high) * 0.5],
                "world_size_mm": [round(v * 1000.0, 3) for v in fixture_high - fixture_low],
                "detection_class": None,
            },
            "camera_location_m": [round(value, 5) for value in camera.location], "camera_lens_mm": round(camera.data.lens, 3),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Rendered {stem}: {len(rows)} labels; missing={len(scenario['missing'])}")
    print(f"Synthetic PCB OBB dataset written: {output}")


if __name__ == "__main__":
    main()
