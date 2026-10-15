"""Mercy Creek 酒馆白模：建筑（照片材质）+ Poly Haven 道具摆放 + 灯光 + 3 个评审机位。

blender --background --python tools/blender/build_saloon.py -- [--render] [--samples N] [--export path.glb]
输出：art/blender/saloon_blockout.blend，渲染图到 Reviews/
坐标：X 向右，Y 向里（前墙 Y=0，后墙 Y=DEPTH），Z 向上，单位米。
"""
import bpy, bmesh, math, sys, pathlib
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "art" / "source"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "--render" in argv
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 96
EXPORT = argv[argv.index("--export") + 1] if "--export" in argv else None

# ---------- 尺寸 ----------
W, DEPTH, H = 14.0, 10.0, 6.4        # 两层通高的大厅
X0, X1 = -W / 2, W / 2
T = 0.2                              # 墙厚
BALC_Z, BALC_D = 3.2, 2.6            # 二楼回廊高度、进深

# ---------- 清场 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = {}
for name in ("Architecture", "Props", "Lighting", "Cameras", "Exterior"):
    c = bpy.data.collections.new(name); scene.collection.children.link(c); coll[name] = c


# ---------- 材质 ----------
def ac_mat(name, asset, tile=1.0, tint=None, rough_mul=1.0):
    """ambientCG 照片材质。tile = 贴图覆盖的米数。"""
    m = bpy.data.materials.new(name)
    nt = m.node_tree; n = nt.nodes; l = nt.links
    bsdf = n["Principled BSDF"]
    d = (SRC.parent / "generated" / asset[4:]) if asset.startswith("gen:") else SRC / "ambientcg" / asset
    def tex(suffix, non_color=False):
        f = next(d.glob(f"*_{suffix}.jpg"), None)
        if not f: return None
        t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(str(f), check_existing=True)
        if non_color: t.image.colorspace_settings.name = "Non-Color"
        return t
    col = tex("Color")
    if col:
        if tint:
            mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
            mix.inputs[0].default_value = 1.0; mix.inputs[7].default_value = (*tint, 1)
            l.new(col.outputs[0], mix.inputs[6]); l.new(mix.outputs[2], bsdf.inputs["Base Color"])
        else:
            l.new(col.outputs[0], bsdf.inputs["Base Color"])
    r = tex("Roughness", True)
    if r:
        if rough_mul != 1.0:
            mm = n.new("ShaderNodeMath"); mm.operation = "MULTIPLY"; mm.inputs[1].default_value = rough_mul
            l.new(r.outputs[0], mm.inputs[0]); l.new(mm.outputs[0], bsdf.inputs["Roughness"])
        else:
            l.new(r.outputs[0], bsdf.inputs["Roughness"])
    nm = tex("NormalGL", True)
    if nm:
        nn = n.new("ShaderNodeNormalMap"); l.new(nm.outputs[0], nn.inputs["Color"]); l.new(nn.outputs[0], bsdf.inputs["Normal"])
    m["tile"] = tile
    return m


def flat_mat(name, color, rough=0.6, metal=0.0, emit=None, emit_strength=0.0, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = emit_strength
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


M = {
    "floor":   ac_mat("Floor", "WoodFloor041", 2.0, tint=(0.75, 0.62, 0.5), rough_mul=1.3),
    "wall":    ac_mat("WallPlanks", "Planks037A", 3.2, tint=(0.55, 0.36, 0.22)),
    "paper":   ac_mat("Wallpaper", "gen:WallpaperDamask", 1.0),   # tools/textures/make_wallpaper.py
    "ceiling": ac_mat("Ceiling", "Planks021", 2.0, tint=(0.42, 0.3, 0.2)),
    "trim":    ac_mat("Trim", "WoodFloor043", 1.5, tint=(0.45, 0.3, 0.2)),
    "bar":     ac_mat("BarWood", "WoodFloor043", 1.2, tint=(0.38, 0.22, 0.13), rough_mul=1.15),
    "siding":  ac_mat("Siding", "WoodSiding013", 3.0),
    "glass":   flat_mat("DirtyGlass", (0.85, 0.82, 0.7), rough=0.15, transmission=0.9),
    "brass":   flat_mat("Brass", (0.75, 0.55, 0.25), rough=0.3, metal=1.0),
    "sand":    flat_mat("Sand", (0.62, 0.48, 0.33), rough=0.95),
    "piano":   flat_mat("PianoBlockout", (0.12, 0.07, 0.04), rough=0.35),
}


# ---------- 网格工具 ----------
def world_box_uv(obj, tile):
    """按世界坐标做三向投影 UV（导出到 Unity 也有效）。"""
    me = obj.data; bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify(); mw = obj.matrix_world
    for f in bm.faces:
        nrm = (mw.to_3x3() @ f.normal); ax = max(range(3), key=lambda i: abs(nrm[i]))
        for lp in f.loops:
            p = mw @ lp.vert.co
            u, v = [(p.y, p.z), (p.x, p.z), (p.x, p.y)][ax]
            lp[uv].uv = (u / tile, v / tile)
    bm.to_mesh(me); bm.free()


def box(name, x0, x1, y0, y1, z0, z1, mat, col="Architecture"):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); coll[col].objects.link(ob)
    ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    ob.scale = (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
    bpy.context.view_layer.update()
    # 把缩放烘进网格，UV 才按真实尺寸
    me.transform(ob.matrix_basis); ob.matrix_basis.identity()
    ob.data.materials.append(mat)
    world_box_uv(ob, mat.get("tile", 1.0))
    return ob


def wall_x(name, y0, y1, z0, z1, openings, mat):
    """沿 X 方向的墙（前/后墙），openings = [(x0, x1, zb, zt)]。"""
    xs = sorted({X0, X1, *[o[0] for o in openings], *[o[1] for o in openings]})
    for a, b in zip(xs, xs[1:]):
        hole = next((o for o in openings if o[0] <= a and b <= o[1]), None)
        if not hole:
            box(f"{name}_{a:.1f}", a, b, y0, y1, z0, z1, mat)
        else:
            if hole[2] > z0: box(f"{name}_lo_{a:.1f}", a, b, y0, y1, z0, hole[2], mat)
            if hole[3] < z1: box(f"{name}_hi_{a:.1f}", a, b, y0, y1, hole[3], z1, mat)


def wall_y(name, x0, x1, z0, z1, openings, mat):
    ys = sorted({0.0, DEPTH, *[o[0] for o in openings], *[o[1] for o in openings]})
    for a, b in zip(ys, ys[1:]):
        hole = next((o for o in openings if o[0] <= a and b <= o[1]), None)
        if not hole:
            box(f"{name}_{a:.1f}", x0, x1, a, b, z0, z1, mat)
        else:
            if hole[2] > z0: box(f"{name}_lo_{a:.1f}", x0, x1, a, b, z0, hole[2], mat)
            if hole[3] < z1: box(f"{name}_hi_{a:.1f}", x0, x1, a, b, hole[3], z1, mat)


def window_frame(axis, c0, c1, zb, zt, plane):
    """窗框 + 十字窗棂 + 脏玻璃。axis='x' 表示窗在前后墙上。"""
    th, d = 0.08, T + 0.06
    def b(n, u0, u1, z0, z1):
        if axis == "x": box(n, u0, u1, plane - d / 2, plane + d / 2, z0, z1, M["trim"])
        else: box(n, plane - d / 2, plane + d / 2, u0, u1, z0, z1, M["trim"])
    b("WinSill", c0 - 0.1, c1 + 0.1, zb - 0.08, zb)
    b("WinHead", c0 - 0.1, c1 + 0.1, zt, zt + th)
    b("WinL", c0 - th, c0, zb, zt); b("WinR", c1, c1 + th, zb, zt)
    mid = (c0 + c1) / 2
    b("WinMullion", mid - 0.03, mid + 0.03, zb, zt)
    for zz in (zb + (zt - zb) / 3, zb + 2 * (zt - zb) / 3):
        b("WinMuntin", c0, c1, zz - 0.025, zz + 0.025)
    if axis == "x": g = box("WinGlass", c0, c1, plane - 0.005, plane + 0.005, zb, zt, M["glass"])
    else: g = box("WinGlass", plane - 0.005, plane + 0.005, c0, c1, zb, zt, M["glass"])
    g.visible_shadow = False  # 透射玻璃在 Cycles 里会挡住阳光


# ---------- 建筑 ----------
box("Floor", X0, X1, 0, DEPTH, -0.2, 0, M["floor"])
box("Ceiling", X0, X1, 0, DEPTH, H, H + 0.2, M["ceiling"])
for i in range(8):  # 天花梁
    x = X0 + 0.9 + i * (W - 1.8) / 7
    box(f"Beam{i}", x - 0.12, x + 0.12, 0, DEPTH, H - 0.3, H, M["trim"])

DOOR = (-0.9, 0.9, 0.0, 2.7)
FRONT_WIN = [(-5.4, -2.6, 0.9, 2.8), (2.6, 5.4, 0.9, 2.8), (-5.0, -3.0, 4.0, 5.6), (3.0, 5.0, 4.0, 5.6)]
wall_x("FrontWall", -T, 0, 0, H, [DOOR, *FRONT_WIN], M["wall"])
ROOM4_DOOR = (-0.6, 0.6, BALC_Z, BALC_Z + 2.3)     # 二楼：上锁的 4 号房（觉醒结局）
BACK_DOOR = (5.6, 6.6, 0.0, 2.3)                     # 一楼：后门（出逃结局，门外什么都没有）
wall_x("BackWall", DEPTH, DEPTH + T, 0, H, [ROOM4_DOOR, BACK_DOOR], M["wall"])
# 后门门框
for nm, a, b, z0, z1 in [("BackDoorJambL", 5.52, 5.6, 0, 2.38), ("BackDoorJambR", 6.6, 6.68, 0, 2.38), ("BackDoorHead", 5.52, 6.68, 2.3, 2.38)]:
    box(nm, a, b, DEPTH - 0.04, DEPTH + T + 0.02, z0, z1, M["trim"])
# 4 号房：后墙外加一间 4 m × 3 m 的小房间
R4X0, R4X1, R4Y1 = -2.0, 2.0, DEPTH + T + 3.0
box("Room4Floor", R4X0, R4X1, DEPTH + T, R4Y1, BALC_Z - 0.2, BALC_Z, M["floor"])
box("Room4Ceiling", R4X0, R4X1, DEPTH + T, R4Y1, H - 0.4, H - 0.2, M["ceiling"])
box("Room4Under", R4X0 - T, R4X1 + T, DEPTH + T, R4Y1 + T, 0, BALC_Z - 0.2, M["siding"])
box("Room4WallL", R4X0 - T, R4X0, DEPTH + T, R4Y1, BALC_Z - 0.2, H - 0.2, M["wall"])
box("Room4WallR", R4X1, R4X1 + T, DEPTH + T, R4Y1, BALC_Z - 0.2, H - 0.2, M["wall"])
box("Room4Back_lo", R4X0 - T, R4X1 + T, R4Y1, R4Y1 + T, BALC_Z - 0.2, BALC_Z + 0.9, M["wall"])
box("Room4Back_hi", R4X0 - T, R4X1 + T, R4Y1, R4Y1 + T, BALC_Z + 2.1, H - 0.2, M["wall"])
box("Room4Back_l", R4X0 - T, -0.6, R4Y1, R4Y1 + T, BALC_Z + 0.9, BALC_Z + 2.1, M["wall"])
box("Room4Back_r", 0.6, R4X1 + T, R4Y1, R4Y1 + T, BALC_Z + 0.9, BALC_Z + 2.1, M["wall"])
box("Room4Roof", R4X0 - T, R4X1 + T, DEPTH + T, R4Y1 + T, H - 0.2, H, M["trim"])
window_frame("x", -0.6, 0.6, BALC_Z + 0.9, BALC_Z + 2.1, R4Y1 + T / 2)
box("Room4Paper", R4X0 + 0.01, R4X1 - 0.01, R4Y1 - 0.005, R4Y1, BALC_Z + 1.0, H - 0.4, M["paper"])
LEFT_WIN = [(1.2, 2.6, 1.2, 2.6)]
wall_y("LeftWall", X0 - T, X0, 0, H, LEFT_WIN, M["wall"])
wall_y("RightWall", X1, X1 + T, 0, H, [(3.0, 4.6, 0.9, 2.6), (5.6, 7.2, 4.0, 5.4)], M["wall"])
for o in FRONT_WIN: window_frame("x", o[0], o[1], o[2], o[3], -T / 2)
for o in LEFT_WIN: window_frame("y", o[0], o[1], o[2], o[3], X0 - T / 2)
window_frame("y", 3.0, 4.6, 0.9, 2.6, X1 + T / 2)
window_frame("y", 5.6, 7.2, 4.0, 5.4, X1 + T / 2)

# 墙裙 + 上半部墙纸（后墙一层）
wall_x("Wainscot", DEPTH - 0.02, DEPTH, 0, 1.1, [BACK_DOOR], M["trim"])
wall_x("WallpaperBack", DEPTH - 0.025, DEPTH - 0.02, 1.1, BALC_Z - 0.3, [BACK_DOOR], M["paper"])
wall_x("ChairRail", DEPTH - 0.06, DEPTH, 1.08, 1.16, [BACK_DOOR], M["trim"])
# 二楼走廊的后墙也贴墙纸
wall_x("WallpaperBackUpper", DEPTH - 0.025, DEPTH - 0.02, BALC_Z + 1.0, H - 0.05, [ROOM4_DOOR], M["paper"])
wall_x("WainscotUpper", DEPTH - 0.02, DEPTH, BALC_Z, BALC_Z + 1.0, [ROOM4_DOOR], M["trim"])
wall_x("ChairRailUpper", DEPTH - 0.06, DEPTH, BALC_Z + 0.98, BALC_Z + 1.06, [ROOM4_DOOR], M["trim"])

# 二楼回廊（后墙一侧 + 右墙一侧）
box("BalconyBack", X0, X1, DEPTH - BALC_D, DEPTH, BALC_Z - 0.25, BALC_Z, M["floor"])
box("BalconyRight", X1 - 1.6, X1, 2.0, DEPTH - BALC_D, BALC_Z - 0.25, BALC_Z, M["floor"])
box("BalconyFascia", X0, X1 - 1.6, DEPTH - BALC_D - 0.05, DEPTH - BALC_D, BALC_Z - 0.45, BALC_Z, M["trim"])
for i in range(7):  # 立柱
    x = X0 + 1.0 + i * (W - 3.2) / 6
    box(f"Post{i}", x - 0.11, x + 0.11, DEPTH - BALC_D - 0.11, DEPTH - BALC_D + 0.11, 0, BALC_Z - 0.25, M["trim"])
# 栏杆
box("RailTop", X0, X1 - 1.6, DEPTH - BALC_D, DEPTH - BALC_D + 0.08, BALC_Z + 0.95, BALC_Z + 1.02, M["trim"])
box("RailTopR", X1 - 1.62, X1 - 1.54, 2.0, DEPTH - BALC_D, BALC_Z + 0.95, BALC_Z + 1.02, M["trim"])
x = X0 + 0.2
while x < X1 - 1.6:
    box("Baluster", x - 0.025, x + 0.025, DEPTH - BALC_D + 0.015, DEPTH - BALC_D + 0.065, BALC_Z, BALC_Z + 0.95, M["trim"]); x += 0.22
y = 2.1
while y < DEPTH - BALC_D:
    box("BalusterR", X1 - 1.605, X1 - 1.555, y - 0.025, y + 0.025, BALC_Z, BALC_Z + 0.95, M["trim"]); y += 0.22

# 楼梯
steps = 16  # 沿前墙从门边向右爬升，顶端接平台，再转进右侧回廊
for i in range(steps):
    h = BALC_Z * (i + 1) / steps
    xa = X1 - 1.6 - (steps - i) * 0.28
    box(f"Step{i}", xa, xa + 0.3, 0.9, 2.0, h - 0.05, h, M["trim"])
    box(f"Riser{i}", xa, xa + 0.3, 0.9, 2.0, 0, h - 0.05, M["wall"])
box("StairLanding", X1 - 1.6, X1, 0.9, 2.0, BALC_Z - 0.25, BALC_Z, M["floor"])
for i in range(steps):  # 楼梯扶手立柱
    xa = X1 - 1.6 - (steps - i) * 0.28 + 0.15; h = BALC_Z * (i + 1) / steps
    box(f"StairBaluster{i}", xa - 0.025, xa + 0.025, 1.93, 1.98, h, h + 0.9, M["trim"])

# 吧台（左墙一侧）
BAR_X = X0 + 2.4
box("BarTop", BAR_X - 0.45, BAR_X + 0.35, 2.6, 8.2, 1.08, 1.14, M["bar"])
box("BarBody", BAR_X - 0.35, BAR_X + 0.25, 2.7, 8.1, 0.1, 1.08, M["bar"])
box("BarKick", BAR_X + 0.15, BAR_X + 0.25, 2.7, 8.1, 0, 0.12, M["trim"])
rail = box("FootRail", BAR_X + 0.32, BAR_X + 0.36, 2.7, 8.1, 0.2, 0.24, M["brass"])
# 后酒架 + 大镜子位
box("BackBarBase", X0, X0 + 0.6, 3.0, 7.8, 0, 0.95, M["bar"])
box("BackBarTop", X0, X0 + 0.65, 3.0, 7.8, 0.95, 1.0, M["bar"])
for k, z in enumerate((1.45, 1.9)):
    box(f"Shelf{k}", X0, X0 + 0.3, 3.0, 4.6, z, z + 0.04, M["bar"])
    box(f"ShelfB{k}", X0, X0 + 0.3, 6.2, 7.8, z, z + 0.04, M["bar"])
box("BackBarCrown", X0, X0 + 0.35, 3.0, 7.8, 2.6, 2.8, M["trim"])

# 后墙壁灯（Unity 里在同一位置放点光源，见 SetupSaloon）
M["flame"] = flat_mat("LampFlame", (1.0, 0.75, 0.45), rough=0.4, emit=(1.0, 0.62, 0.3), emit_strength=6.0)
for sx in (-3.4, 0.6, 4.6):
    box(f"SconcePlate{sx}", sx - 0.07, sx + 0.07, DEPTH - 0.045, DEPTH - 0.025, 1.95, 2.2, M["brass"], col="Props")
    box(f"SconceArm{sx}", sx - 0.015, sx + 0.015, DEPTH - 0.3, DEPTH - 0.04, 2.02, 2.05, M["brass"], col="Props")
    box(f"SconceCup{sx}", sx - 0.06, sx + 0.06, DEPTH - 0.36, DEPTH - 0.24, 2.05, 2.12, M["brass"], col="Props")
    g = box(f"SconceGlass{sx}", sx - 0.045, sx + 0.045, DEPTH - 0.345, DEPTH - 0.255, 2.12, 2.36, M["glass"], col="Props")
    g.visible_shadow = False
    box(f"SconceFlame{sx}", sx - 0.012, sx + 0.012, DEPTH - 0.312, DEPTH - 0.288, 2.14, 2.2, M["flame"], col="Props")

# 自动钢琴（Tripo 之前的占位）
# 自动钢琴：tools/blender/build_piano.py 单独生成 PlayerPiano.glb，由 SetupSaloon 放在 (3.2, 0, DEPTH - 0.35)

# ---------- 外景：对街立面，窗外不是空的 ----------
# 对街立面、街道：tools/blender/build_street.py → StreetBackdrop.glb（同一坐标系）
box("BoardwalkFront", X0 - 1, X1 + 1, -2.4, -0.2, 0, 0.25, M["floor"], col="Exterior")
box("Awning", X0 - 1, X1 + 1, -2.6, 0, 3.7, 3.8, M["trim"], col="Exterior")
box("OutsideL", -40, X0 - T, 0, 30, -0.25, -0.2, M["sand"], col="Exterior")
box("OutsideR", X1 + T, 40, 0, 30, -0.25, -0.2, M["sand"], col="Exterior")

# ---------- Poly Haven 道具 ----------
def import_ph(asset):
    d = SRC / "polyhaven" / "models" / asset
    f = next(d.glob("*.gltf"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(f))
    objs = [o for o in bpy.data.objects if o not in before]
    for o in objs:
        for c in o.users_collection: c.objects.unlink(o)
        coll["Props"].objects.link(o)
    return objs


_cache = {}
def prop(asset, x, y, rot_deg=0.0, z=0.0, scale=1.0):
    """导入一份（首次）或复制（之后），以包围盒底面中心对齐到 (x, y, z)。"""
    if asset not in _cache:
        objs = import_ph(asset)
        roots = [o for o in objs if o.parent is None]
        _cache[asset] = roots
        src = roots; fresh = True
    else:
        fresh = False
    if not fresh:
        mapping = {}
        allsrc = [o for r in _cache[asset] for o in [r, *r.children_recursive]]
        for o in allsrc:
            c = o.copy(); coll["Props"].objects.link(c); mapping[o] = c
        for o, c in mapping.items():
            if o.parent in mapping: c.parent = mapping[o.parent]
        src = [mapping[r] for r in _cache[asset]]
    root = bpy.data.objects.new(f"{asset}_root", None); coll["Props"].objects.link(root)
    for r in src: r.parent = root
    root.scale = (scale,) * 3
    bpy.context.view_layer.update()
    meshes = [o for r in src for o in [r, *r.children_recursive] if o.type == "MESH"]
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    for r in src: r.location -= centre / scale
    root.location = (x, y, z); root.rotation_euler = (0, 0, math.radians(rot_deg))
    return root, (mx - mn)


# 牌桌区：中央两张圆桌 + 一张方桌，每桌配椅子与油灯
tables = [(-1.2, 4.0, "round_wooden_table_01"), (2.2, 5.2, "round_wooden_table_02"), (0.4, 7.0, "round_wooden_table_01")]
for tx, ty, t in tables:
    _, sz = prop(t, tx, ty, rot_deg=15)
    top = sz.z
    for k in range(4):
        a = math.radians(45 + k * 90 + (tx * 10))
        prop("painted_wooden_chair_02", tx + math.cos(a) * 0.8, ty + math.sin(a) * 0.8, rot_deg=math.degrees(a) + 90)
    prop("wooden_lantern_01" if ty > 6 else "Lantern_01", tx + 0.1, ty - 0.05, z=top)

# 窗边的角落桌：陌生人每轮坐在这里写笔记（Story.CraneSeat）
_, csz = prop("round_wooden_table_02", -3.0, 1.9, rot_deg=10)
prop("painted_wooden_chair_02", -3.0, 1.08, rot_deg=180)   # 模型正面朝 -Y，转过来面向桌子
prop("Lantern_01", -3.35, 2.1, z=csz.z)

# 吧台：高脚凳、酒瓶、镜子
for i in range(6):
    prop("bar_chair_round_01", BAR_X + 0.75, 3.1 + i * 0.95)
prop("wine_bottles_01", X0 + 0.18, 3.8, rot_deg=90, z=1.49)
prop("wine_bottles_01", X0 + 0.18, 7.0, rot_deg=90, z=1.94)
prop("wine_bottles_01", BAR_X - 0.05, 5.4, rot_deg=30, z=1.14)
prop("ornate_mirror_01", X0 + 0.08, 5.4, rot_deg=-90, z=1.15, scale=1.5)

# 后墙：座钟（循环的核心道具）、钢琴旁的摇椅
prop("vintage_grandfather_clock_01", -1.6, DEPTH - 0.35, rot_deg=180)
prop("Rockingchair_01", 4.7, DEPTH - 1.5, rot_deg=200)

# 酒桶、木箱：吧台尽头
prop("wooden_barrels_01", X0 + 1.0, 9.0, rot_deg=10)
prop("wine_barrel_01", X0 + 2.6, 9.2, rot_deg=0)
prop("wooden_crate_01", X0 + 0.7, 1.4, rot_deg=12)
prop("wooden_crate_02", X0 + 0.9, 0.7, rot_deg=-8, z=0)

# 右墙：火炉、飞镖靶
prop("barrel_stove", X1 - 0.7, 5.2)
prop("dartboard", X1 - 0.05, 7.0, rot_deg=90, z=1.5)
prop("wooden_bucket_01", X1 - 1.2, 4.6)

# 二楼回廊
prop("painted_wooden_chair_02", -3.0, DEPTH - 0.6, rot_deg=180, z=BALC_Z)
prop("wooden_ladder", 6.4, DEPTH - 0.3, rot_deg=180, z=BALC_Z)

# ---------- 灯光 ----------
world = bpy.data.worlds.new("World"); scene.world = world
wn = world.node_tree.nodes; wl = world.node_tree.links
env = wn.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(str(SRC / "polyhaven" / "hdris" / "goegap_road_2k.exr"))
mapn = wn.new("ShaderNodeMapping"); tc = wn.new("ShaderNodeTexCoord")
mapn.inputs["Rotation"].default_value[2] = math.radians(140)
wl.new(tc.outputs["Generated"], mapn.inputs["Vector"]); wl.new(mapn.outputs[0], env.inputs[0])
bg = wn["Background"]; bg.inputs["Strength"].default_value = 0.8
wl.new(env.outputs[0], bg.inputs[0])

# 午后斜阳：从前窗低角度射入，形成光柱
sun_data = bpy.data.lights.new("Sun", "SUN"); sun_data.energy = 8.0; sun_data.angle = math.radians(0.6)
sun_data.color = (1.0, 0.82, 0.6)
sun = bpy.data.objects.new("Sun", sun_data); coll["Lighting"].objects.link(sun)
sun.rotation_euler = (math.radians(60), 0, math.radians(20))  # 仰角 30°，从前窗射入、向 +Y

# 室内空气：体积散射，让光柱可见
vol = box("DustVolume", X0 + 0.05, X1 - 0.05, 0.05, DEPTH - 0.05, 0.02, H - 0.05, bpy.data.materials.new("Dust"), col="Lighting")
vm = vol.data.materials[0]
vm.node_tree.nodes.remove(vm.node_tree.nodes["Principled BSDF"])
pv = vm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.012; pv.inputs["Anisotropy"].default_value = 0.6
pv.inputs["Color"].default_value = (1.0, 0.9, 0.78, 1)
vm.node_tree.links.new(pv.outputs[0], vm.node_tree.nodes["Material Output"].inputs["Volume"])
vol.visible_shadow = False

# 室内补光：油灯点光（暖）+ 吧台上方
for i, (x, y, z, e) in enumerate([(-1.1, 3.95, 1.05, 18), (2.3, 5.15, 1.05, 18), (0.7, 7.05, 1.1, 14), (X0 + 1.2, 5.4, 2.6, 60)]):
    ld = bpy.data.lights.new(f"Lamp{i}", "POINT"); ld.energy = e; ld.color = (1.0, 0.7, 0.4); ld.shadow_soft_size = 0.08
    lo = bpy.data.objects.new(f"Lamp{i}", ld); lo.location = (x, y, z); coll["Lighting"].objects.link(lo)
# 天光从窗口进来的面光（模拟窗口 portal）
for i, (x, y, rot) in enumerate([(-4.0, 0.05, 90), (4.0, 0.05, 90)]):
    ad = bpy.data.lights.new(f"WinFill{i}", "AREA"); ad.shape = "RECTANGLE"; ad.size = 2.8; ad.size_y = 1.9; ad.energy = 120; ad.color = (0.85, 0.9, 1.0)
    ao = bpy.data.objects.new(f"WinFill{i}", ad); ao.location = (x, y, 1.85); ao.rotation_euler = (math.radians(rot), 0, 0)
    coll["Lighting"].objects.link(ao)

# ---------- 评审机位 ----------
def cam(name, loc, target, lens=24):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36
    co = bpy.data.objects.new(name, cd); co.location = loc; coll["Cameras"].objects.link(co)
    d = Vector(target) - Vector(loc); co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return co

CAMS = [
    cam("Cam_Entrance", (0.3, 0.6, 1.65), (0.5, 8.0, 1.6), 22),          # 推门进来的第一眼
    cam("Cam_Balcony", (5.6, DEPTH - 1.6, BALC_Z + 1.6), (-2.0, 3.0, 0.6), 20),  # 二楼俯视大厅
    cam("Cam_Bar", (BAR_X + 1.9, 2.2, 1.45), (X0 + 0.3, 6.5, 1.3), 30),   # 吧台近景
]

# ---------- 渲染设置 ----------
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"; prefs.get_devices()
    for d in prefs.devices: d.use = True
    scene.cycles.device = "GPU"
except Exception as e:
    print("GPU unavailable, using CPU:", e)
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.volume_bounces = 1
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.view_settings.view_transform = "AgX"
scene.view_settings.exposure = 0.3
scene.render.film_transparent = False

out_blend = ROOT / "art" / "blender" / "saloon_blockout.blend"
out_blend.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
print("saved", out_blend)

if RENDER:
    rev = ROOT / "Reviews"; rev.mkdir(exist_ok=True)
    for c in CAMS:
        scene.camera = c
        scene.render.filepath = str(rev / f"blockout_{c.name[4:].lower()}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", scene.render.filepath)

if EXPORT:
    # 只导出建筑、道具、外景；灯光 / 相机 / 体积雾在 Unity 里重做
    bpy.ops.object.select_all(action="DESELECT")
    for cname in ("Architecture", "Props", "Exterior"):
        for o in coll[cname].all_objects:
            o.select_set(True)
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import mc_common
    mc_common.export_gltf(EXPORT)
