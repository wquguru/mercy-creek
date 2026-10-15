"""Mercy Creek 街道两头：东头教堂（堵住街尾）、东北的墓地、西头的巨幅布景画布（"世界只写到这里"）。

blender --background --python tools/blender/build_edges.py -- [--paint] [--render] [--samples N] [--export path.gltf]
  --paint   先在 Blender 里渲染"往西延伸的路"作为画布底稿（canvas_raw），再调用 tools/gen_edge_textures.py --canvas
            加工成手绘布景贴图；画布贴图不存在时自动执行
  --render  评审渲染到 Reviews/blender/Edges_*.png（导入 StreetBackdrop / Saloon 等已导出的 glTF 作陪衬，只渲染不导出）
默认导出 Game/Assets/_MercyCreek/Art/Town/TownEdges.gltf（根节点 TownEdges）。
其余贴图先跑 tools/gen_edge_textures.py（Pillow）生成到 art/source/_derived/edges/。

坐标与 build_street.py 相同：Blender X 向东、Y 向北、Z 向上，米；Unity (x, y, z) = Blender (x, z, y)。
命名：NoCol_ 前缀 = Unity 不加碰撞体。Church_Bell、TBD_*、Canvas_Flap 按约定名字导出（也不该加碰撞体，见 ASSETS.md）。
"""
import sys, math, pathlib, json, subprocess, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy, bmesh
from mathutils import Vector, Matrix
import mc_common as mc
from mc_common import T, R, S

argv = mc.args()
RENDER = "--render" in argv
PAINT = "--paint" in argv
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 48
EXPORT = argv[argv.index("--export") + 1] if "--export" in argv else str(mc.ART / "Town" / "TownEdges.gltf")
EDGE = mc.SRC / "_derived" / "edges"
STREET_GLTF = mc.ART / "Street" / "StreetBackdrop.gltf"

# 画布（与 gen_edge_textures.py 一致）
CX = -34.0
CY0, CY1, CZ0, CZ1 = -34.0, 20.0, -0.1, 14.0
CY_SPLIT = -7.0                     # 南北两张贴图的分界（也是一道布幅接缝）
HOLE = (-8.6, -6.0, -0.1, 3.4)      # 路口那块可撕开的布：y0, y1, z0, z1
EYE = Vector((-20.0, -7.3, 1.6))    # 画的透视点：站在街上往西看

# Unity 的太阳（SetupSaloon.cs：Euler(26, 18, 0)）换到 Blender：光线前进方向
SUN_DIR = Vector((math.sin(math.radians(18)) * math.cos(math.radians(26)),
                  math.cos(math.radians(18)) * math.cos(math.radians(26)),
                  -math.sin(math.radians(26))))


def hashf(*a):
    s = math.sin(sum(v * k for v, k in zip(a, (12.9898, 78.233, 37.719, 4.581)))) * 43758.5453
    return s - math.floor(s)


def add_sun(coll, energy=5.0):
    sd = bpy.data.lights.new("Sun", "SUN"); sd.energy = energy; sd.angle = math.radians(0.6)
    sd.color = (1.0, 0.86, 0.68)
    so = bpy.data.objects.new("Sun", sd); coll.objects.link(so)
    so.rotation_euler = SUN_DIR.to_track_quat("-Z", "Y").to_euler()
    return so


def import_gltf(path, coll_name):
    """导入已导出的 glTF（坐标与导出时一致），返回新对象。"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    print("imported", path, len(new), "objects")
    return new


# ================================================================ 1) 画布底稿：在 Blender 里渲染"后来的路"
def painted_sky(w):
    """相机直接看到的天空换成布景画师式的渐变 + 横向云；照明仍用 HDRI。"""
    nt = w.node_tree; n = nt.nodes; l = nt.links
    bg_hdri = n["Background"]
    out = n["World Output"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ"); l.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = n.new("ShaderNodeValToRGB"); l.new(sep.outputs["Z"], ramp.inputs[0])
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = (0.86, 0.80, 0.68, 1)
    els[1].position = 0.55; els[1].color = (0.28, 0.42, 0.68, 1)
    e = els.new(0.08); e.color = (0.72, 0.74, 0.74, 1)
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.2, 1.2, 7.0)
    l.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 4.0
    l.new(mp.outputs[0], nz.inputs["Vector"])
    cr = n.new("ShaderNodeValToRGB"); l.new(nz.outputs["Fac"], cr.inputs[0])
    cr.color_ramp.elements[0].position = 0.55; cr.color_ramp.elements[1].position = 0.75
    mask = n.new("ShaderNodeMath"); mask.operation = "MULTIPLY"
    l.new(cr.outputs[0], mask.inputs[0])
    hz = n.new("ShaderNodeMapRange"); l.new(sep.outputs["Z"], hz.inputs[0])
    hz.inputs[1].default_value = 0.02; hz.inputs[2].default_value = 0.25
    l.new(hz.outputs[0], mask.inputs[1])
    mixc = n.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    l.new(mask.outputs[0], mixc.inputs["Factor"])
    l.new(ramp.outputs[0], mixc.inputs[6]); mixc.inputs[7].default_value = (0.95, 0.92, 0.86, 1)
    bg_sky = n.new("ShaderNodeBackground"); bg_sky.inputs["Strength"].default_value = 1.6
    l.new(mixc.outputs[2], bg_sky.inputs[0])
    lp = n.new("ShaderNodeLightPath")
    mix = n.new("ShaderNodeMixShader")
    l.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    l.new(bg_hdri.outputs[0], mix.inputs[1]); l.new(bg_sky.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])


def render_painting():
    sc = mc.reset()
    coll = sc.collection
    if STREET_GLTF.exists():
        for o in import_gltf(STREET_GLTF, "street"):
            if o.type == "MESH" and not o.name.startswith(("Road", "Hills")):
                bpy.data.objects.remove(o)
    # 与街道同一套贴图；粗糙度拉满（逆光时的掠射高光会把地面刷白），地面略压暗，好让路读出来
    ground = mc.pbr("PGround", "Ground054", tile=8.0, tint=(0.8, 0.7, 0.58), normal=0.3, rough=0.97)
    road = mc.pbr("PRoad", "Ground080", tile=1.3, tint=(0.8, 0.72, 0.64), normal=0.5, rough=0.95)
    mesa = mc.pbr("PMesa", "Ground033", tile=60.0, tint=(0.74, 0.66, 0.72), rough=0.95, normal=0.0)    # 远处偏紫灰（空气透视）
    hills = mc.pbr("PHills", "Ground033", tile=40.0, tint=(0.8, 0.66, 0.56), rough=0.95, normal=0.0)
    wood = mc.pbr("PPole", "Wood066", tile=1.0, tint=(0.5, 0.45, 0.4))
    sage = mc.flat("PSage", (0.09, 0.1, 0.07), rough=0.95)
    rockm = mc.pbr("PRock", "Rock030", tile=3.0, tint=(0.75, 0.6, 0.5))
    wire = mc.flat("PWire", (0.05, 0.05, 0.05), rough=0.6)

    def gh(x, y):        # 远处缓缓起伏，近处与街道地面齐平（-0.08）
        d = min(1.0, max(0.0, (-x - 45) / 80))
        return -0.1 + d * (1.2 * math.sin(y * 0.031 + 1.0) * math.sin(x * 0.017) + 0.6 * math.sin(x * 0.043 + y * 0.02))

    def grid(part, xs, ys, h, mat):
        bm, uvl = part.bm, part.uv
        tile = mat.get("tile", 1.0); mi = part._mi(mat)
        vs = [[bm.verts.new((x, y, h(x, y))) for x in xs] for y in ys]
        for j in range(len(ys) - 1):
            for i in range(len(xs) - 1):
                f = bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]])
                f.material_index = mi; f.smooth = True
                for lp in f.loops:
                    lp[uvl].uv = (lp.vert.co.x / tile, lp.vert.co.y / tile)

    # 地面：x 往西远到地平线，非均匀网格（近密远疏）
    xs = [-30 - 4000 * (i / 60) ** 2.2 for i in range(61)][::-1]
    ys = [-7.3 + 3000 * math.copysign(abs(t) ** 2.2, t) for t in [k / 30 - 1 for k in range(61)]]
    p = mc.Part([ground]); grid(p, xs, ys, lambda x, y: gh(x, y) + 0.02, ground); p.finish("PGround")
    # 路：街面往西接着走，过了 x=-70 慢慢收窄成一条车道
    p = mc.Part([road]); bm, uvl = p.bm, p.uv; mi = p._mi(road)
    rows = []
    xs = [-38 - 2500 * (i / 70) ** 2.4 for i in range(71)]
    for x in xs:
        t = min(1.0, max(0.0, (-x - 60) / 140))
        half = 4.9 * (1 - t) + 2.6 * t
        cy = -7.3 + 6.0 * math.sin(min(1.0, max(0.0, (-x - 200) / 900)) * 1.4)   # 远处轻轻拐弯
        row = []
        for k in range(17):
            y = cy - half + 2 * half * k / 16
            edge = 1 - abs(k - 8) / 8
            rut = 0.07 * (math.exp(-((k - 4) / 0.6) ** 2) + math.exp(-((k - 12) / 0.6) ** 2))
            row.append(bm.verts.new((x, y, gh(x, y) + 0.03 * edge - 0.005 - rut)))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for k in range(16):
            f = bm.faces.new([a[k], a[k + 1], b[k + 1], b[k]])
            f.material_index = mi; f.smooth = True
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x / 1.3, lp.vert.co.y / 1.3)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0: f.normal_flip()
    p.finish("PRoad")
    # 远山：西边地平线上的台地（平顶），南北两侧的矮丘
    p = mc.Part([mesa]); bm, uvl = p.bm, p.uv; mi = p._mi(mesa)
    def mesa_h(y, t):
        u = y * 0.0021
        r = 0.45 + 0.2 * math.sin(u * 3.1 + 0.4) + 0.12 * math.sin(u * 7.7 + 2.0)
        m = min(1.0, max(0.0, (math.sin(u * 2.3 + 1.1) - 0.1) * 4))
        r = r * (1 - m) + 1.0 * m
        return 140 * r * math.sin(math.pi * t) ** 0.35
    nY, nT = 160, 6
    vs = [[bm.verts.new((-1500 - 500 * j / nT, -2500 + 5000 * i / nY, mesa_h(-2500 + 5000 * i / nY, j / nT) - 2)) for i in range(nY + 1)] for j in range(nT + 1)]
    for j in range(nT):
        for i in range(nY):
            f = bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]])
            f.material_index = mi; f.smooth = True
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.y / 60, lp.vert.co.z / 60)
    bm.normal_update()
    p.finish("PMesa")
    p = mc.Part([hills]); bm, uvl = p.bm, p.uv; mi = p._mi(hills)
    def hill_h(y, t):
        u = y * 0.01
        return (14 + 8 * math.sin(u * 1.7) + 5 * math.sin(u * 4.1 + 1)) * math.sin(math.pi * t) ** 0.6 * (0.5 + 0.5 * min(1, abs(y + 7.3) / 120))
    vs = [[bm.verts.new((-380 - 160 * j / 5, -1200 + 2400 * i / 120, hill_h(-1200 + 2400 * i / 120, j / 5) - 1)) for i in range(121)] for j in range(6)]
    for j in range(5):
        for i in range(120):
            f = bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]])
            f.material_index = mi; f.smooth = True
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.y / 40, lp.vert.co.z / 40)
    p.finish("PHills")
    # 电线杆：沿路北侧往西排（电报局的线），透视最好读
    p = mc.Part([wood])
    poles = []
    for k in range(40):
        x = -42 - 38 * k
        t = min(1.0, max(0.0, (-x - 200) / 900))
        y = -7.3 + 6.0 * math.sin(t * 1.4) + 6.4
        z = gh(x, y)
        p.box((0.22, 0.22, 7.2), wood, xf=T(x, y, z + 3.5))
        p.box((0.12, 2.0, 0.14), wood, xf=T(x, y, z + 6.6))
        poles.append((x, y, z + 6.66))
    p.finish("PPoles")
    p = mc.Part([wire])
    for (xa, ya, za), (xb, yb, zb) in zip(poles, poles[1:]):
        for dy in (-0.8, 0.8):
            a = Vector((xa, ya + dy, za)); b = Vector((xb, yb + dy, zb))
            for s in range(4):          # 下垂
                t0, t1 = s / 4, (s + 1) / 4
                pa = a.lerp(b, t0) - Vector((0, 0, 0.6 * math.sin(math.pi * t0)))
                pb = a.lerp(b, t1) - Vector((0, 0, 0.6 * math.sin(math.pi * t1)))
                L = (pb - pa).length
                p.lathe([(0, 0.02, 0.02), (L, 0.02, 0.02)], wire, seg=4, xf=T(*pa) @ mc.orient(pb - pa), cap=False)
    p.finish("PWires")
    # 灌木 + 石头
    rnd = random.Random(7)
    p = mc.Part([sage])
    for _ in range(900):
        x = -36 - 600 * rnd.random() ** 1.8
        y = -7.3 + rnd.uniform(-1, 1) * (40 + (-x) * 1.6)
        t = min(1.0, max(0.0, (-x - 200) / 900))
        if abs(y - (-7.3 + 6.0 * math.sin(t * 1.4))) < 5.5 + 2: continue
        s = rnd.uniform(0.25, 0.7) * (1 + (-x) / 300)
        for k in range(3):
            p.sphere(s * rnd.uniform(0.5, 0.8), sage, xf=T(x + rnd.uniform(-s, s) * 0.6, y + rnd.uniform(-s, s) * 0.6, gh(x, y) + s * 0.2), seg=9, rings=5, sz=0.65)
    for _ in range(25):
        x = -40 - 300 * rnd.random() ** 1.5
        y = -7.3 + rnd.choice((-1, 1)) * rnd.uniform(9, 80)
        s = rnd.uniform(0.4, 1.8)
        p.sphere(s, rockm, xf=T(x, y, gh(x, y)) @ R("Z", rnd.uniform(0, 360)), seg=10, rings=6, sx=1.3, sz=0.45)
    p.finish("PScrub")

    mc.setup_render(64, res=(4096, 1070))
    w = mc.world_hdri("goegap_road", strength=0.7, rot=320)     # 只作环境光；HDRI 自带的太阳转到身后
    painted_sky(w)
    add_sun(coll)
    cam = mc.camera("PaintCam", tuple(EYE), tuple(EYE + Vector((-10, 0, 0))), lens=1)
    cd = cam.data
    width = CY1 - CY0
    dist = EYE.x - CX
    cd.sensor_fit = "HORIZONTAL"; cd.sensor_width = 36
    cd.lens = 18 * dist / (width / 2)
    cd.shift_x = ((CY0 + CY1) / 2 - EYE.y) / width
    cd.shift_y = ((CZ0 + CZ1) / 2 - EYE.z) / width
    cd.clip_start = dist          # 画布平面以东的东西（街上的房子）不进画
    cd.clip_end = 6000
    sc.render.resolution_y = int(round(4096 * (CZ1 - CZ0) / width))
    EDGE.mkdir(parents=True, exist_ok=True)
    if "--paint-debug" in argv:      # 俯视检查底稿场景
        sc.render.resolution_x, sc.render.resolution_y = 960, 540; sc.cycles.samples = 16
        mc.camera("Dbg", (-60, -7.3, 120), (-160, -7.3, 0), lens=20)
        mc.render(pathlib.Path(argv[argv.index("--paint-debug") + 1])); sys.exit(0)
    mc.render(EDGE / "edge_canvas_raw.png")
    py = mc.ROOT / ".venv" / "bin" / "python"
    subprocess.run([str(py if py.exists() else "python3"), str(mc.ROOT / "tools" / "gen_edge_textures.py"), "--canvas"], check=True)


if PAINT or not (EDGE / "edge_canvas_paint_s.jpg").exists():
    render_painting()

# ================================================================ 2) 正式场景
sc = mc.reset()
C_EXP = bpy.data.collections.new("Edges"); sc.collection.children.link(C_EXP)
C_REV = bpy.data.collections.new("Review"); sc.collection.children.link(C_REV)
ROOT_OBJ = mc.empty("TownEdges", collection=C_EXP)
CHURCH = mc.empty("Church", parent=ROOT_OBJ, collection=C_EXP)
YARD = mc.empty("Graveyard", parent=ROOT_OBJ, collection=C_EXP)
CANVAS = mc.empty("WorldCanvas", parent=ROOT_OBJ, collection=C_EXP)

GRAVES = json.loads((EDGE / "edge_graves.json").read_text())

M = {
    "white":  mc.pbr("ChurchClapboard", "WoodSiding009", tile=2.4, tint=(0.97, 0.99, 1.14)),
    "trim":   mc.pbr("ChurchTrim", "PaintedWood009C", tile=1.5, tint=(0.97, 0.96, 0.93)),
    "roof":   mc.pbr("ChurchShingles", "WoodSiding011", tile=1.6, tint=(0.62, 0.6, 0.58)),
    "stone":  mc.pbr("Fieldstone", "Rock030", tile=1.6, tint=(1.0, 0.92, 0.84)),
    "planks": mc.pbr("Boardwalk", "Planks012", tile=2.0),
    "dark":   mc.pbr("TrimDark", "Planks012", tile=1.5, tint=(0.55, 0.5, 0.45)),
    "door":   mc.pbr("ChurchDoor", "Wood066", tile=1.2, tint=(0.62, 0.46, 0.33)),
    "glass":  mc.flat("LancetGlass", (0.014, 0.016, 0.02), rough=0.08),
    "iron":   mc.flat("Iron", (0.08, 0.07, 0.065), rough=0.55, metal=0.8),
    "bronze": mc.flat("BellBronze", (0.42, 0.31, 0.17), rough=0.38, metal=1.0),
    "belfry": mc.flat("BelfryDark", (0.12, 0.1, 0.08), rough=0.9),
    "picket": mc.pbr("Picket", "PaintedWood009C", tile=1.2, tint=(0.86, 0.84, 0.79)),
    "yard":   mc.pbr("GraveyardGround", "Ground054", tile=4.0, tint=(0.82, 0.74, 0.58), normal=0.3),
    "path":   mc.pbr("GraveyardPath", "Ground080", tile=1.3, tint=(0.8, 0.72, 0.64), normal=0.5),
    "fresh":  mc.pbr("FreshDirt", "Ground080", tile=1.0, tint=(0.6, 0.48, 0.38), normal=0.8),
    "bark":   mc.pbr("DeadBark", "Bark007", tile=1.0, tint=(0.6, 0.56, 0.52)),
    "xwood":  mc.pbr("CrossWood", "Wood066", tile=0.8, tint=(0.62, 0.6, 0.57)),
    "timber": mc.pbr("Timber", "Wood066", tile=1.5, tint=(0.75, 0.66, 0.55)),
    "burlap": mc.flat("Burlap", (0.40, 0.32, 0.21), rough=0.95),
    "rope":   mc.flat("Rope", (0.42, 0.36, 0.27), rough=0.9),
    "sside":  mc.image_mat("GraveStoneSide", EDGE / "edge_stone_side.jpg", rough=0.85, tile=0.6),
    "atlas":  mc.image_mat("GraveInscriptions", EDGE / "edge_graves_atlas.jpg", rough=0.85, normal_path=EDGE / "edge_graves_atlas_n.png"),
    "martha": mc.image_mat("GraveMartha", EDGE / "edge_grave_martha.jpg", rough=0.8, normal_path=EDGE / "edge_grave_martha_n.png"),
    "blank":  mc.image_mat("GraveBlank", EDGE / "edge_grave_blank.jpg", rough=0.7, normal_path=EDGE / "edge_grave_blank_n.png"),
    "note":   mc.image_mat("NoteTBD_Edges", EDGE / "edge_note_tbd.jpg", rough=0.9),
}


def grass_mat():
    m = bpy.data.materials.new("DryGrass")
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    t = mc.image_tex(n, EDGE / "edge_grass_dry.png")
    l.new(t.outputs[0], b.inputs["Base Color"])
    rd = n.new("ShaderNodeMath"); rd.operation = "ROUND"     # glTF 导出器据此写 alphaMode = MASK
    l.new(t.outputs[1], rd.inputs[0]); l.new(rd.outputs[0], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = 0.9
    m["tile"] = 1.0
    return m


def canvas_mat(name, color_path, tile_m=0.35):
    """布景画：颜色贴图按 UV 0..1；织纹法线用 Mapping 节点平铺（导出成 KHR_texture_transform）。"""
    m = bpy.data.materials.new(name)
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    t = mc.image_tex(n, color_path); l.new(t.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    if "Paint" in name:
        # 画布正面朝东，午后太阳在西南：正面总在背光里。加一点自发光（= 底色 × 0.35），远看才和被照亮的街道接得上
        l.new(t.outputs[0], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = 0.35
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping")
    w = CY_SPLIT - CY0 if "Paint" in name else 1.0
    mp.inputs["Scale"].default_value = (w / tile_m, (CZ1 - CZ0) / tile_m, 1) if "Paint" in name else (1, 1, 1)
    nt = mc.image_tex(n, EDGE / "edge_canvas_weave_n.png", True)
    l.new(tc.outputs["UV"], mp.inputs["Vector"]); l.new(mp.outputs[0], nt.inputs["Vector"])
    nm = n.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.6
    l.new(nt.outputs[0], nm.inputs["Color"]); l.new(nm.outputs[0], b.inputs["Normal"])
    m["tile"] = 1.0
    return m


M["grass"] = grass_mat()
M["paint_s"] = canvas_mat("CanvasPaint_S", EDGE / "edge_canvas_paint_s.jpg")
M["paint_n"] = canvas_mat("CanvasPaint_N", EDGE / "edge_canvas_paint_n.jpg")
M["cback"] = canvas_mat("CanvasBack", EDGE / "edge_canvas_back.jpg")
M["cback"]["tile"] = 0.5


# ---------------------------------------------------------------- 几何工具
def bx(part, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    return part.box((abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), mat,
                    xf=T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), bevel=bevel)


def basis(o, r, u):
    """局部坐标系：原点 o，局部 X = r（右），Y = u（上），Z = r×u（朝外）。"""
    r = Vector(r).normalized(); u = Vector(u).normalized(); n = r.cross(u)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = r[i], u[i], n[i], o[i]
    return m


def _proj_uv(p, f, tile):
    nrm = f.normal; ax = max(range(3), key=lambda i: abs(nrm[i]))
    for lp in f.loops:
        q = lp.vert.co
        u, v = [(q.y, q.z), (q.x, q.z), (q.x, q.y)][ax]
        lp[p.uv].uv = (u / tile, v / tile)


def face(p, pts, mat, hint, uvs=None, smooth=False):
    """一个平面多边形（世界坐标），按 hint 方向定朝向；uvs 给定时逐点写，否则按米投影。"""
    vs = [p.bm.verts.new(Vector(c)) for c in pts]
    f = p.bm.faces.new(vs)
    f.normal_update()
    if f.normal.dot(Vector(hint)) < 0:
        f.normal_flip()
    if uvs is not None:
        m = {v: uv for v, uv in zip(vs, uvs)}
        for lp in f.loops:
            lp[p.uv].uv = m[lp.vert]
    else:
        _proj_uv(p, f, mat.get("tile", 1.0))
    f.material_index = p._mi(mat); f.smooth = smooth
    return f


def slab(p, pts2d, z0, z1, xf, mat, front_mat=None, front_uv=None):
    """局部 XY 多边形在局部 Z∈[z0,z1] 挤出（xf 把局部变到世界）。front_uv(u, v) 给正面（+Z）写 UV。"""
    n = (xf.to_3x3() @ Vector((0, 0, 1))).normalized()
    W = lambda x, y, z: xf @ Vector((x, y, z))
    cen = Vector((sum(q[0] for q in pts2d) / len(pts2d), sum(q[1] for q in pts2d) / len(pts2d)))
    face(p, [W(x, y, z1) for x, y in pts2d], front_mat or mat, n,
         uvs=[front_uv(x, y) for x, y in pts2d] if front_uv else None)
    face(p, [W(x, y, z0) for x, y in pts2d], mat, -n)
    k = len(pts2d)
    for i in range(k):
        a, b = pts2d[i], pts2d[(i + 1) % k]
        mid = Vector(((a[0] + b[0]) / 2 - cen.x, (a[1] + b[1]) / 2 - cen.y, 0))
        out = xf.to_3x3() @ mid
        face(p, [W(a[0], a[1], z0), W(b[0], b[1], z0), W(b[0], b[1], z1), W(a[0], a[1], z1)], mat, out)


def ring(p, outer, inner, z0, z1, xf, mat):
    """窗框：外轮廓与内轮廓（点数相同）之间的环，挤出 z0..z1。"""
    n = (xf.to_3x3() @ Vector((0, 0, 1))).normalized()
    W = lambda q, z: xf @ Vector((q[0], q[1], z))
    k = len(outer)
    cen = Vector((sum(q[0] for q in outer) / k, sum(q[1] for q in outer) / k, 0))
    for i in range(k):
        j = (i + 1) % k
        oa, ob, ia, ib = outer[i], outer[j], inner[i], inner[j]
        face(p, [W(oa, z1), W(ob, z1), W(ib, z1), W(ia, z1)], mat, n)
        mo = Vector(((oa[0] + ob[0]) / 2, (oa[1] + ob[1]) / 2, 0)) - cen
        face(p, [W(oa, z0), W(ob, z0), W(ob, z1), W(oa, z1)], mat, xf.to_3x3() @ mo)
        mi = Vector(((ia[0] + ib[0]) / 2, (ia[1] + ib[1]) / 2, 0)) - cen
        face(p, [W(ia, z0), W(ib, z0), W(ib, z1), W(ia, z1)], mat, xf.to_3x3() @ -mi)


def lancet(w, hs, y0=0.0, n_arc=6):
    """尖拱窗轮廓（逆时针）：宽 w，直边高 hs，拱半径 = w（等边尖拱）。"""
    pts = [(-w / 2, y0), (w / 2, y0), (w / 2, y0 + hs)]
    for k in range(1, n_arc + 1):
        a = math.radians(60 * k / n_arc)
        pts.append((-w / 2 + w * math.cos(a), y0 + hs + w * math.sin(a)))
    for k in range(1, n_arc):
        a = math.radians(120 + 60 * k / n_arc)
        pts.append((w / 2 + w * math.cos(a), y0 + hs + w * math.sin(a)))
    return pts


def lancet_window(p, xf, w, hs, frame=0.1, depth=0.08, mull=True):
    """贴在墙面上的尖拱窗：深色玻璃 + 白框 + 中梃 + 窗台。xf 原点 = 窗底中点，局部 Z 朝外。"""
    outer = lancet(w + 2 * frame, hs + frame, -frame)
    inner = lancet(w, hs, 0.0)
    ring(p, outer, inner, 0.0, depth, xf, M["trim"])
    face(p, [xf @ Vector((x, y, 0.02)) for x, y in inner], M["glass"], xf.to_3x3() @ Vector((0, 0, 1)))
    apex = hs + w * math.sin(math.radians(60))
    if mull:
        p.box((0.045, apex - 0.02, 0.05), M["trim"], xf=xf @ T(0, apex / 2, 0.045))
        for yy in (hs * 0.33, hs * 0.66, hs):
            p.box((w, 0.04, 0.045), M["trim"], xf=xf @ T(0, yy, 0.042))
    p.box((w + 2 * frame + 0.12, 0.06, depth + 0.06), M["trim"], xf=xf @ T(0, -frame - 0.03, (depth + 0.06) / 2))


def obj(part, name, parent):
    return part.finish(name, parent=parent, collection=C_EXP)


# ================================================================ 教堂
X0, X1, Y0, Y1 = 30.0, 41.0, -11.0, -3.6
YC = (Y0 + Y1) / 2               # -7.3
FZ = 0.8                         # 地基顶
EAVE = 5.4
HALF = (Y1 - Y0) / 2
RISE = 2.8
RIDGE = EAVE + RISE
TX0, TX1, TY0, TY1 = 29.9, 32.5, YC - 1.3, YC + 1.3     # 钟楼平面
TXC = (TX0 + TX1) / 2
BELL_Z = 10.0

p = mc.Part([M["white"]])
# 地基 + 墙体（实心盒子：没有室内）
bx(p, X0 - 0.08, X1 + 0.08, Y0 - 0.08, Y1 + 0.08, -0.3, FZ, M["stone"])
bx(p, X0 - 0.12, X1 + 0.12, Y0 - 0.12, Y1 + 0.12, FZ - 0.06, FZ + 0.02, M["stone"])    # 压顶石
bx(p, X0, X1, Y0, Y1, FZ, EAVE, M["white"])
# 前后山墙
for xw, sgn in ((X0, -1), (X1, 1)):
    xf = basis((xw, YC, EAVE), (0, -sgn, 0), (0, 0, 1))
    slab(p, [(-HALF, 0), (HALF, 0), (0, RISE)], -0.3, 0.0, xf, M["white"])
# 屋顶：两片 + 屋脊盖板
a = math.atan2(RISE, HALF)
L = HALF / math.cos(a) + 0.5
for sgn in (-1, 1):
    d = Vector((0, sgn * math.cos(a), -math.sin(a)))
    nrm = Vector((0, sgn * math.sin(a), math.cos(a)))
    c = Vector((0, YC, RIDGE)) + d * (L / 2 - 0.05) + nrm * 0.07
    p.box((X1 - X0 + 0.7, L, 0.12), M["roof"], xf=T(X0 + (X1 - X0) / 2 + 0.0, c.y, c.z) @ R("X", -sgn * math.degrees(a)))
p.box((X1 - X0 + 0.7, 0.3, 0.12), M["trim"], xf=T((X0 + X1) / 2, YC, RIDGE + 0.17))
# 墙角竖条、檐口、山墙封檐板
for xx in (X0, X1):
    for yy in (Y0, Y1):
        bx(p, xx - 0.1, xx + 0.1, yy - 0.1, yy + 0.1, FZ, EAVE, M["trim"])
for ya, yb in ((Y0 - 0.12, Y0), (Y1, Y1 + 0.12)):                     # 檐口板
    bx(p, X0 - 0.35, X1 + 0.35, ya, yb, EAVE - 0.3, EAVE + 0.02, M["trim"])
for xw, sgn in ((X0, -1), (X1, 1)):
    for s2 in (-1, 1):                                                   # 山墙封檐板（沿坡）
        Lr = HALF / math.cos(a) + 0.45
        p.box((0.1, Lr, 0.24), M["trim"], xf=T(xw + sgn * 0.06, YC + s2 * HALF / 2, EAVE + RISE / 2 + 0.05) @ R("X", -s2 * math.degrees(a)))
    bx(p, min(xw, xw + sgn * 0.08), max(xw, xw + sgn * 0.08), Y0, Y1, EAVE - 0.05, EAVE + 0.12, M["trim"])
# 正面：双开门、门上尖拱气窗、两侧尖拱窗
front = lambda y, z: basis((X0, y, z), (0, -1, 0), (0, 0, 1))
DW, DH = 1.8, 2.6
bx(p, X0 - 0.06, X0, YC - DW / 2, YC + DW / 2, FZ, FZ + DH, M["door"])
for s in (-1, 1):
    yl = YC + s * DW / 4
    for zc, hh in ((FZ + 0.75, 0.9), (FZ + 1.85, 1.0)):
        bx(p, X0 - 0.09, X0 - 0.06, yl - DW / 4 + 0.13, yl + DW / 4 - 0.13, zc - hh / 2, zc + hh / 2, M["door"], bevel=0.015)
    bx(p, X0 - 0.11, X0 - 0.07, YC + s * 0.12 - 0.02, YC + s * 0.12 + 0.02, FZ + 1.15, FZ + 1.45, M["iron"])       # 门把
    for zz in (FZ + 0.4, FZ + DH - 0.4):
        bx(p, X0 - 0.08, X0 - 0.06, YC + s * (DW / 2 - 0.45), YC + s * (DW / 2 - 0.02), zz - 0.04, zz + 0.04, M["iron"])  # 合页
bx(p, X0 - 0.075, X0 - 0.06, YC - 0.01, YC + 0.01, FZ, FZ + DH, M["dark"])              # 两扇门缝
for s in (-1, 1):
    bx(p, X0 - 0.12, X0, YC + s * (DW / 2 + 0.07) - 0.07, YC + s * (DW / 2 + 0.07) + 0.07, FZ, FZ + DH + 0.1, M["trim"])
bx(p, X0 - 0.14, X0, YC - DW / 2 - 0.2, YC + DW / 2 + 0.2, FZ + DH, FZ + DH + 0.16, M["trim"])
lancet_window(p, front(YC, FZ + DH + 0.32), 1.5, 0.15, frame=0.1, mull=False)
for yy in (YC - 2.5, YC + 2.5):
    lancet_window(p, front(yy, 2.0), 0.9, 1.3)
# 侧墙 + 后墙尖拱窗
for xx in (33.0, 35.6, 38.2, 40.4 - 0.2):
    lancet_window(p, basis((xx, Y1, 2.0), (-1, 0, 0), (0, 0, 1)), 0.95, 1.5)
    lancet_window(p, basis((xx, Y0, 2.0), (1, 0, 0), (0, 0, 1)), 0.95, 1.5)
lancet_window(p, basis((X1, YC, 2.6), (0, 1, 0), (0, 0, 1)), 0.9, 1.2)
# 门廊平台 + 台阶 + 扶手
PX0 = X0 - 1.1
bx(p, PX0, X0, YC - 1.7, YC + 1.7, -0.1, FZ - 0.12, M["stone"])
f = bx(p, PX0 - 0.05, X0, YC - 1.75, YC + 1.75, FZ - 0.12, FZ, M["planks"])
for k in range(3):
    top = FZ - 0.2 * (k + 1)
    bx(p, PX0 - 0.38 * (k + 1), PX0 - 0.38 * k, YC - 1.2, YC + 1.2, -0.12, top, M["planks"])
    bx(p, PX0 - 0.38 * (k + 1), PX0 - 0.38 * k + 0.02, YC - 1.2, YC + 1.2, top - 0.2, top - 0.02, M["dark"])
for s in (-1, 1):
    yy = YC + s * 1.3
    for xx in (PX0 - 1.14, PX0 + 0.05, X0 - 0.15):
        z0 = -0.1 if xx < PX0 else FZ
        bx(p, xx - 0.05, xx + 0.05, yy - 0.05, yy + 0.05, z0, (FZ + 0.9) if xx >= PX0 else 0.95, M["trim"])
    Lr = math.hypot(1.19, FZ - 0.05)
    p.box((Lr, 0.07, 0.06), M["trim"], xf=T(PX0 - 0.55, yy, (FZ + 0.9 + 0.95) / 2) @ R("Y", -math.degrees(math.atan2(FZ - 0.05, 1.19))))
    bx(p, PX0 + 0.05, X0 - 0.1, yy - 0.04, yy + 0.04, FZ + 0.85, FZ + 0.92, M["trim"])
# 钟楼：方塔身 → 钟室（四根角柱、尖拱开口）→ 檐口 → 八角尖顶 → 铁十字
TB0, TB1 = EAVE - 0.05, 8.9
bx(p, TX0, TX1, TY0, TY1, TB0, TB1, M["white"])
for xx in (TX0, TX1):
    for yy in (TY0, TY1):
        bx(p, xx - 0.08, xx + 0.08, yy - 0.08, yy + 0.08, TB0, TB1, M["trim"])
bx(p, TX0 - 0.15, TX1 + 0.15, TY0 - 0.15, TY1 + 0.15, TB1, TB1 + 0.2, M["trim"])          # 钟室地板 / 腰线
lancet_window(p, basis((TX0, YC, 6.4), (0, -1, 0), (0, 0, 1)), 0.55, 0.6, frame=0.08, mull=False)                       # 塔身正面小窗
BF0, BF1 = TB1 + 0.2, 11.3
bx(p, TX0 + 0.2, TX1 - 0.2, TY0 + 0.2, TY1 - 0.2, BF0 - 0.05, BF0, M["belfry"])          # 钟室内（暗）
for xx in (TX0, TX1 - 0.32):
    for yy in (TY0, TY1 - 0.32):
        bx(p, xx, xx + 0.32, yy, yy + 0.32, BF0, BF1, M["white"])
for (ax0, ax1, ay0, ay1, side) in ((TX0, TX0 + 0.08, TY0, TY1, "x"), (TX1 - 0.08, TX1, TY0, TY1, "x"),
                                   (TX0, TX1, TY0, TY0 + 0.08, "y"), (TX0, TX1, TY1 - 0.08, TY1, "y")):
    bx(p, ax0, ax1, ay0, ay1, BF0, BF0 + 0.55, M["white"])          # 栏板
    bx(p, ax0, ax1, ay0, ay1, BF1 - 0.4, BF1, M["white"])           # 楣
# 开口上沿的尖拱板（每面两块斜板）
for nrm, cen, r in (((-1, 0, 0), (TX0 + 0.04, YC), (0, -1, 0)), ((1, 0, 0), (TX1 - 0.04, YC), (0, 1, 0)),
                    ((0, -1, 0), (TXC, TY0 + 0.04), (1, 0, 0)), ((0, 1, 0), (TXC, TY1 - 0.04), (-1, 0, 0))):
    xf = basis((cen[0], cen[1], BF1 - 0.4), r, (0, 0, 1))
    half_w = 0.98
    slab(p, [(-half_w, 0), (-half_w, -0.75), (0, 0)], -0.04, 0.04, xf, M["white"])
    slab(p, [(half_w, 0), (0, 0), (half_w, -0.75)], -0.04, 0.04, xf, M["white"])
bx(p, TX0 + 0.15, TX1 - 0.15, TY0 + 0.15, TY1 - 0.15, BF1 - 0.05, BF1, M["belfry"])
bx(p, TX0 - 0.2, TX1 + 0.2, TY0 - 0.2, TY1 + 0.2, BF1, BF1 + 0.22, M["trim"])
bx(p, TX0 - 0.08, TX1 + 0.08, TY0 - 0.08, TY1 + 0.08, BF1 + 0.22, BF1 + 0.42, M["white"])
SP0 = BF1 + 0.42
p.lathe([(0, 1.35, 1.35), (4.0, 0.0, 0.0)], M["roof"], seg=8, xf=T(TXC, YC, SP0), uv_rot=math.pi / 8, smooth=False)
p.sphere(0.09, M["iron"], xf=T(TXC, YC, SP0 + 4.02), seg=8, rings=5)
bx(p, TXC - 0.025, TXC + 0.025, YC - 0.025, YC + 0.025, SP0 + 4.0, 16.05, M["iron"])
bx(p, TXC - 0.025, TXC + 0.025, YC - 0.16, YC + 0.16, 15.86, 15.92, M["iron"])
# 挂钟的木梁
bx(p, TXC - 0.09, TXC + 0.09, TY0 + 0.1, TY1 - 0.1, BELL_Z + 0.42, BELL_Z + 0.58, M["dark"])
church = obj(p, "Church_Building", CHURCH)

# 钟：单独网格，原点在钟心
p = mc.Part([M["bronze"]])
prof = [(0.30, 0, 0), (0.22, 0.17, 0.17), (0.0, 0.29, 0.29), (-0.25, 0.345, 0.345), (-0.36, 0.38, 0.38), (-0.375, 0.40, 0.40),
        (-0.36, 0.415, 0.415), (-0.30, 0.37, 0.37), (-0.12, 0.30, 0.30), (0.10, 0.25, 0.25), (0.26, 0.23, 0.23),
        (0.33, 0.17, 0.17), (0.36, 0.0, 0.0)]
p.lathe(prof, M["bronze"], seg=24)
p.box((0.08, 0.3, 0.12), M["iron"], xf=T(0, 0, 0.42))                      # 钟钮
p.lathe([(0, 0.012, 0.012), (0.45, 0.012, 0.012)], M["iron"], seg=6, xf=T(0, 0, -0.18), cap=False)   # 钟舌
p.sphere(0.05, M["iron"], xf=T(0, 0, -0.2), seg=8, rings=5)
bell = p.finish("Church_Bell", parent=CHURCH, collection=C_EXP, location=(TXC, YC, BELL_Z))
mc.empty("Church_BellPos", parent=CHURCH, location=(TXC, YC, BELL_Z), collection=C_EXP)

# 门上"待写"纸条
p = mc.Part([M["note"]])
nw, nh = 0.40, 0.30
ang = math.radians(-3)
pts = []
for (u, v) in ((-nw / 2, -nh / 2), (nw / 2, -nh / 2), (nw / 2, nh / 2), (-nw / 2, nh / 2)):
    uu, vv = u * math.cos(ang) - v * math.sin(ang), u * math.sin(ang) + v * math.cos(ang)
    pts.append((0.0, -uu, vv))          # 朝 -X：观者右手是 -Y
p.quad(pts, M["note"])
p.box((0.012, 0.016, 0.016), M["iron"], xf=T(-0.004, 0.0, nh / 2 - 0.035))
mc_note = p.finish("TBD_Church", parent=CHURCH, collection=C_EXP, location=(X0 - 0.095, YC, FZ + 1.75))

# 教堂周围的干草
grass_church = mc.Part([M["grass"]])


def tuft(part, x, y, z, h, rnd):
    w = h * rnd.uniform(0.8, 1.3)
    a0 = rnd.uniform(0, 180)
    for k in range(3):
        a = math.radians(a0 + 60 * k)
        dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
        lean = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0)) * h
        c = [(x - dx, y - dy, z - 0.03), (x + dx, y + dy, z - 0.03),
             (x + dx + lean.x, y + dy + lean.y, z + h), (x - dx + lean.x, y - dy + lean.y, z + h)]
        part.quad(c, M["grass"])
        part.quad(c[::-1], M["grass"], uvs=((0, 1), (1, 1), (1, 0), (0, 0)))      # 背面


rnd = random.Random(31)
for _ in range(70):
    side = rnd.random()
    if side < 0.35:
        x, y = rnd.uniform(X0 + 0.5, X1 + 0.3), Y1 + rnd.uniform(0.15, 0.9)
    elif side < 0.7:
        x, y = rnd.uniform(X0 + 0.5, X1 + 0.3), Y0 - rnd.uniform(0.15, 1.0)
    else:
        x, y = X1 + rnd.uniform(0.15, 1.2), rnd.uniform(Y0, Y1)
    tuft(grass_church, x, y, -0.08, rnd.uniform(0.25, 0.55), rnd)
for _ in range(14):    # 门廊两边
    s = rnd.choice((-1, 1))
    tuft(grass_church, rnd.uniform(X0 - 1.0, X0 - 0.1), YC + s * rnd.uniform(1.85, 3.6), -0.05, rnd.uniform(0.2, 0.4), rnd)
obj(grass_church, "NoCol_Grass_Church", CHURCH)

# ================================================================ 墓地
GX0, GX1, GY0, GY1 = 24.5, 40.0, -1.5, 12.0
GATE_X0, GATE_X1 = 27.0, 28.4


def yard_h(x, y):
    h = -0.05 + 0.025 * math.sin(x * 1.3 + y * 0.7) * math.sin(x * 0.4 - y * 1.1)
    return h


# 地面
p = mc.Part([M["yard"]])
bm, uvl = p.bm, p.uv; mi = p._mi(M["yard"])
nx, ny = 31, 27
vs = [[bm.verts.new((GX0 + (GX1 - GX0) * i / nx, GY0 + (GY1 - GY0) * j / ny, yard_h(GX0 + (GX1 - GX0) * i / nx, GY0 + (GY1 - GY0) * j / ny)))
       for i in range(nx + 1)] for j in range(ny + 1)]
for j in range(ny):
    for i in range(nx):
        f = bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]]); f.material_index = mi; f.smooth = True
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 4.0, lp.vert.co.y / 4.0)
obj(p, "Graveyard_Ground", YARD)

# 小路：从街边进门，往北再往东经过玛莎的墓
PATH = [(27.7, -2.7), (27.7, -1.5), (27.8, 0.4), (28.4, 1.6), (29.6, 2.3), (31.2, 2.55), (33.0, 2.6), (35.0, 2.45), (37.0, 2.2), (38.6, 2.4)]


def catmull(pts, n=6):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = map(Vector, (P[i - 1], P[i], P[i + 1], P[i + 2]))
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(Vector(pts[-1]))
    return out


cpts = catmull(PATH)
p = mc.Part([M["path"]])
bm, uvl = p.bm, p.uv; mi = p._mi(M["path"])
rows = []
for i, c in enumerate(cpts):
    d = (cpts[min(i + 1, len(cpts) - 1)] - cpts[max(i - 1, 0)]).normalized()
    nrm = Vector((-d.y, d.x))
    half = 0.55 + 0.12 * math.sin(i * 1.7) + (0.25 if c.y < -1.4 else 0)
    row = []
    for k in range(5):
        t = -1 + k / 2
        q = c + nrm * half * t * (1 + 0.1 * hashf(i, k))
        z = (yard_h(q.x, q.y) if q.y > GY0 else -0.06) + 0.012 + 0.006 * (1 - abs(t))
        row.append(bm.verts.new((q.x, q.y, z)))
    rows.append(row)
for a, b in zip(rows, rows[1:]):
    for k in range(4):
        f = bm.faces.new([a[k], a[k + 1], b[k + 1], b[k]]); f.material_index = mi; f.smooth = True
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 1.3, lp.vert.co.y / 1.3)
bm.normal_update()
for f in bm.faces:
    if f.normal.z < 0: f.normal_flip()
obj(p, "Graveyard_Path", YARD)


# 白栅栏（旧、掉漆、有的歪有的缺）
def picket(part, xf, h, w=0.075, t=0.022):
    pts = [(-w / 2, 0), (w / 2, 0), (w / 2, h - 0.06), (0, h), (-w / 2, h - 0.06)]
    slab(part, pts, 0, t, xf, M["picket"])


def fence_run(part, a, b, rnd, outward, gap=None):
    """从 a 到 b 的一段栅栏：柱子、两道横档、尖头板条（钉在 outward 那一侧）。"""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    L = (b - a).length; d = (b - a).normalized()
    n = Vector((*outward, 0)).normalized()
    npost = max(1, round(L / 2.4))
    for k in range(npost + 1):
        q = a + d * (L * k / npost)
        part.box((0.1, 0.1, 1.35), M["picket"], xf=T(q.x, q.y, 1.35 / 2 - 0.2) @ R("Z", math.degrees(math.atan2(d.y, d.x))))
        part.box((0.13, 0.13, 0.04), M["picket"], xf=T(q.x, q.y, 1.17))
    ang = math.degrees(math.atan2(d.y, d.x))
    for zz in (0.28, 0.82):
        c = (a + b) / 2 + n * 0.06
        part.box((L, 0.035, 0.08), M["picket"], xf=T(c.x, c.y, zz) @ R("Z", ang))
    cnt = int(L / 0.16)
    for k in range(cnt):
        s = (k + 0.5) * L / cnt
        if rnd.random() < 0.04: continue                       # 掉了的板条
        q = a + d * s + n * 0.08
        h = 1.05 + rnd.uniform(-0.03, 0.03)
        if rnd.random() < 0.05: h *= rnd.uniform(0.5, 0.75)    # 断了半截
        tilt = rnd.gauss(0, 1.5) + (rnd.random() < 0.06) * rnd.choice((-1, 1)) * rnd.uniform(4, 9)
        xf = basis((q.x, q.y, -0.08), d, (0, 0, 1))
        r = d.cross(Vector((0, 0, 1)))
        if r.dot(n) < 0:
            xf = basis((q.x, q.y, -0.08), -d, (0, 0, 1))
        xf = xf @ R("Z", tilt)
        picket(part, xf, h)


rnd = random.Random(5)
p = mc.Part([M["picket"]])
fence_run(p, (GX0, GY0), (GATE_X0 - 0.15, GY0), rnd, (0, -1))
fence_run(p, (GATE_X1 + 0.15, GY0), (GX1, GY0), rnd, (0, -1))
fence_run(p, (GX1, GY0), (GX1, GY1), rnd, (1, 0))
fence_run(p, (GX1, GY1), (GX0, GY1), rnd, (0, 1))
fence_run(p, (GX0, GY1), (GX0, GY0), rnd, (-1, 0))
for xx in (GATE_X0 - 0.15, GATE_X1 + 0.15):                   # 门柱（高一点，带尖帽）
    p.box((0.16, 0.16, 1.6), M["picket"], xf=T(xx, GY0, 0.6))
    p.lathe([(0, 0.11, 0.11), (0.22, 0.0, 0.0)], M["picket"], seg=4, xf=T(xx, GY0, 1.4), uv_rot=math.pi / 4, smooth=False)
obj(p, "Graveyard_Fence", YARD)

# 门扇：原点在合页轴上（西门柱旁），关着时沿 +X 伸到东门柱
p = mc.Part([M["picket"]])
GW = GATE_X1 - GATE_X0
for zz in (0.25, 0.85):
    bx(p, 0.03, GW - 0.03, 0.02, 0.06, zz - 0.045, zz + 0.045, M["picket"])
for xx in (0.06, GW - 0.06):
    bx(p, xx - 0.04, xx + 0.04, 0.02, 0.06, 0.15, 1.0, M["picket"])
Ld = math.hypot(GW - 0.16, 0.6)
p.box((Ld, 0.035, 0.07), M["picket"], xf=T(GW / 2, 0.04, 0.55) @ R("Y", -math.degrees(math.atan2(0.6, GW - 0.16))))
for k in range(8):
    xx = 0.12 + (GW - 0.24) * (k + 0.5) / 8
    hh = 1.0 + 0.12 * math.sin(math.pi * (k + 0.5) / 8)              # 门扇上沿微拱
    picket(p, basis((xx, 0.0, 0.05), (1, 0, 0), (0, 0, 1)), hh)      # 朝 -Y（街）
for zz in (0.25, 0.85):                                              # 合页铁片
    bx(p, -0.02, 0.28, -0.035, 0.07, zz - 0.03, zz + 0.03, M["iron"])
bx(p, GW - 0.12, GW + 0.02, -0.04, 0.07, 0.72, 0.78, M["iron"])     # 门闩
gate = p.finish("Graveyard_Gate", parent=YARD, collection=C_EXP, location=(GATE_X0, GY0, 0.0))

# 门上的"待写"纸条（门扇的子物体，跟门一起转）
p = mc.Part([M["note"]])
nw, nh = 0.30, 0.225
ang = math.radians(4)
pts = []
for (u, v) in ((-nw / 2, -nh / 2), (nw / 2, -nh / 2), (nw / 2, nh / 2), (-nw / 2, nh / 2)):
    uu, vv = u * math.cos(ang) - v * math.sin(ang), u * math.sin(ang) + v * math.cos(ang)
    pts.append((uu, 0.0, vv))           # 朝 -Y（街）：观者右手是 +X
p.quad(pts, M["note"])
p.box((0.014, 0.01, 0.014), M["iron"], xf=T(0, -0.004, nh / 2 - 0.03))
note_g = p.finish("TBD_Graveyard", parent=gate, collection=C_EXP, location=(GW / 2, -0.03, 0.62))

# 墓碑
GRAVE_POS = {      # id: (x, y, 偏航°, 前后倾°)
    "Grave_01": (25.6, 5.0, 3, -4), "Grave_02": (26.5, 5.1, -2, 3), "Grave_03": (27.5, 4.6, 6, -2),
    "Grave_Martha": (32.0, 5.0, 0, 0), "Grave_Blank": (33.35, 5.0, 0, 0),
    "Grave_04": (35.6, 5.2, -3, 2), "Grave_05": (37.3, 5.0, 5, -5), "Grave_06": (38.8, 4.9, -6, 4),
    "Grave_07": (26.2, 8.3, 2, -3), "Grave_08": (28.2, 8.4, -4, 2), "Grave_09": (30.6, 8.1, 7, -6),
    "Grave_10": (33.2, 8.5, -2, 3), "Grave_11": (35.6, 8.2, 4, 6), "Grave_12": (27.4, 11.0, -9, 8),
}


def outline(kind, w, h):
    if kind == "round":
        r = w / 2
        return [(-r, 0), (r, 0)] + [(r * math.cos(math.radians(a)), h - r + r * math.sin(math.radians(a))) for a in range(0, 181, 15)]
    if kind == "gothic":      # 与贴图遮罩一致：尖顶从顶下 0.6w 处起
        return [(-w / 2, 0), (w / 2, 0), (w / 2, h - 0.6 * w), (0, h), (-w / 2, h - 0.6 * w)]
    if kind == "cross":
        sw, bh, bz = 0.13, 0.15, h - 0.26 * h      # 竖杆宽、横杆高、横杆中心
        return [(-sw / 2, 0), (sw / 2, 0), (sw / 2, bz - bh / 2), (w / 2, bz - bh / 2), (w / 2, bz + bh / 2), (sw / 2, bz + bh / 2),
                (sw / 2, h), (-sw / 2, h), (-sw / 2, bz + bh / 2), (-w / 2, bz + bh / 2), (-w / 2, bz - bh / 2), (-sw / 2, bz - bh / 2)]
    return [(-w / 2, 0), (w / 2, 0), (w / 2, h), (-w / 2, h)]


def headstone(gid, mat):
    g = GRAVES[gid]; kind, w, h, t = g["kind"], g["w"], g["h"], g["t"]
    x, y, yaw, tilt = GRAVE_POS[gid]
    u0, v0, u1, v1 = g["uv"]
    pts = outline(kind, w, h)
    sink = 0.12
    pts = [(px, py - sink) for px, py in pts]
    p = mc.Part([M["sside"] if kind != "cross" else M["xwood"]])
    side = M["sside"] if kind != "cross" else M["xwood"]
    xf = basis((0, 0, 0), (1, 0, 0), (0, 0, 1))      # 正面朝 -Y（南，对着小路）：观者面朝 +Y，右手 +X
    fu = lambda px, py: (u0 + (px / w + 0.5) * (u1 - u0), v0 + ((py + sink) / h) * (v1 - v0))
    slab(p, pts, -t, 0.0, xf, side, front_mat=mat, front_uv=fu)
    if kind in ("round", "gothic") and w > 0.45:          # 基座
        bx(p, -w / 2 - 0.07, w / 2 + 0.07, -0.07, t + 0.07, -0.1, 0.06, side)
    ob = p.finish(gid, parent=YARD, collection=C_EXP, location=(x, y, yard_h(x, y)))
    ob.rotation_euler = (math.radians(tilt), 0, math.radians(yaw))
    return ob


for gid in GRAVE_POS:
    mat = M["martha"] if gid == "Grave_Martha" else M["blank"] if gid == "Grave_Blank" else M["atlas"]
    headstone(gid, mat)

# 新坟土堆（空白墓碑前）+ 插在土里的铁锹
bxm, bym = GRAVE_POS["Grave_Blank"][:2]
p = mc.Part([M["fresh"]])
bm, uvl = p.bm, p.uv; mi = p._mi(M["fresh"])
NU, NV = 10, 16
mx0, mx1, my0, my1 = bxm - 0.5, bxm + 0.5, bym - 2.05, bym - 0.15
vs = []
for j in range(NV + 1):
    row = []
    for i in range(NU + 1):
        u, v = i / NU, j / NV
        hx = math.sin(math.pi * u) ** 0.8; hy = math.sin(math.pi * v) ** 0.5
        z = -0.06 + 0.32 * hx * hy + 0.03 * (hashf(i, j) - 0.5) * hx * hy
        row.append(bm.verts.new((mx0 - 0.08 + (mx1 - mx0 + 0.16) * u, my0 + (my1 - my0) * v, z)))
    vs.append(row)
for j in range(NV):
    for i in range(NU):
        f = bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]]); f.material_index = mi; f.smooth = True
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x, lp.vert.co.y)
rnd = random.Random(12)
for _ in range(14):                      # 土块
    q = (bxm + rnd.uniform(-0.8, 0.8), bym - rnd.uniform(0.2, 2.3))
    p.sphere(rnd.uniform(0.04, 0.09), M["fresh"], xf=T(q[0], q[1], -0.04), seg=6, rings=4, sz=0.6)
mound = obj(p, "Grave_Blank_Mound", YARD)
p = mc.Part([M["xwood"]])
sx, sy = bxm + 0.75, bym - 1.2
p.lathe([(0, 0.018, 0.018), (1.05, 0.018, 0.018)], M["xwood"], seg=8, xf=T(sx, sy, 0.15) @ R("Y", 12))
p.box((0.2, 0.025, 0.28), M["iron"], xf=T(sx - 0.03, sy, 0.02) @ R("Y", 12))
p.box((0.14, 0.03, 0.03), M["xwood"], xf=T(sx + 0.215, sy, 1.17) @ R("Y", 12))
obj(p, "Graveyard_Shovel", YARD)

# 枯树
p = mc.Part([M["bark"]])
rnd = random.Random(3)


def branch(pos, d, length, r, depth):
    d = d.normalized()
    r1 = r * 0.62
    p.lathe([(0, r, r), (length, r1, r1)], M["bark"], seg=max(4, 3 + depth), xf=T(*pos) @ mc.orient(d), cap=False)
    end = pos + d * length
    if depth == 0 or r1 < 0.015:
        return
    nb = 2 if depth < 3 else rnd.choice((2, 3))
    for k in range(nb):
        ax = d.orthogonal().normalized()
        q = Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 3, d) @ ax
        nd = (d * rnd.uniform(0.6, 1.0) + q * rnd.uniform(0.45, 0.9) + Vector((0, 0, 0.15))).normalized()
        branch(end - d * 0.02, nd, length * rnd.uniform(0.6, 0.8), r1 * (0.85 if k == 0 else 0.7), depth - 1)


TREE = Vector((37.8, 10.3, -0.15))
p.lathe([(0, 0.38, 0.38), (0.35, 0.24, 0.24)], M["bark"], seg=8, xf=T(*TREE), cap=False)       # 根部外扩
branch(TREE + Vector((0, 0, 0.3)), Vector((0.12, -0.05, 1)), 2.3, 0.24, 5)
obj(p, "Graveyard_DeadTree", YARD)

# 干草：墓地里撒一片（避开小路和墓碑）
p = mc.Part([M["grass"]])
rnd = random.Random(17)
stones = [(v[0], v[1]) for v in GRAVE_POS.values()]
n = 0
while n < 210:
    x, y = rnd.uniform(GX0 + 0.15, GX1 - 0.15), rnd.uniform(GY0 + 0.15, GY1 - 0.15)
    if min((Vector((x, y)) - c.to_2d()).length for c in cpts) < 0.75: continue
    if min(math.hypot(x - sx_, y - sy_) for sx_, sy_ in stones) < 0.45: continue
    if bxm - 0.7 < x < bxm + 0.7 and bym - 2.2 < y < bym: continue
    if 31.2 < x < 32.8 and 3.6 < y < 5.3: continue          # 玛莎墓碑前留空，刻字不被草挡
    tuft(p, x, y, yard_h(x, y), rnd.uniform(0.22, 0.6), rnd); n += 1
for k in range(60):                      # 栅栏根和街边
    x = rnd.uniform(GX0, GX1); y = GY0 + rnd.uniform(-0.8, 0.3)
    if GATE_X0 - 0.4 < x < GATE_X1 + 0.4: continue
    tuft(p, x, y, -0.06, rnd.uniform(0.3, 0.65), rnd)
obj(p, "NoCol_Grass_Graveyard", YARD)


# ================================================================ 西头画布
def billow(y, z):
    """布面轻微鼓起：上下两头被钉住，中间往后（-X）兜风。"""
    tz = (z - CZ0) / (CZ1 - CZ0)
    return -0.09 * math.sin(math.pi * min(1, max(0, tz))) * (0.6 + 0.4 * math.sin(y * 0.37 + 1.1)) \
        - 0.025 * math.sin(math.pi * min(1, max(0, tz))) * math.sin(y * 2.3)


def axis_pts(a, b, step, must=()):
    pts = sorted(set([a, b] + [v for v in must if a < v < b] + [a + step * k for k in range(1, int((b - a) / step) + 1) if a + step * k < b - 1e-3]))
    return pts


def sheet(part, ys, zs, keep, origin):
    """画布网格：正面（+X）贴画，背面（-X）生布。南北两半用两张贴图，分界 y = CY_SPLIT。"""
    bm, uvl = part.bm, part.uv
    fv, bv = {}, {}
    for i, y in enumerate(ys):
        for j, z in enumerate(zs):
            co = Vector((CX + billow(y, z), y, z)) - Vector(origin)
            fv[i, j] = bm.verts.new(co); bv[i, j] = bm.verts.new(co - Vector((0.015, 0, 0)))   # 背面错开 1.5 cm，免得重面闪烁
    mi_s, mi_n, mi_b = part._mi(M["paint_s"]), part._mi(M["paint_n"]), part._mi(M["cback"])
    for i in range(len(ys) - 1):
        for j in range(len(zs) - 1):
            yc, zc = (ys[i] + ys[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if not keep(yc, zc): continue
            south = yc < CY_SPLIT
            ya = CY0 if south else CY_SPLIT; wy = CY_SPLIT - CY0 if south else CY1 - CY_SPLIT
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]      # (y, z) 逆时针 → 法线 +X
            f = bm.faces.new([fv[k] for k in q]); f.material_index = mi_s if south else mi_n; f.smooth = True
            for lp, k in zip(f.loops, q):
                lp[uvl].uv = ((ys[k[0]] - ya) / wy, (zs[k[1]] - CZ0) / (CZ1 - CZ0))
            f = bm.faces.new([bv[k] for k in q[::-1]]); f.material_index = mi_b; f.smooth = True
            for lp, k in zip(f.loops, q[::-1]):
                lp[uvl].uv = (ys[k[0]] / 0.5, zs[k[1]] / 0.5)


hy0, hy1, hz0, hz1 = HOLE
ys = axis_pts(CY0, CY1, 0.6, must=(hy0, hy1, CY_SPLIT))
zs = axis_pts(CZ0, CZ1, 0.6, must=(hz1,))
p = mc.Part([M["paint_s"]])
sheet(p, ys, zs, lambda y, z: not (hy0 < y < hy1 and z < hz1), (0, 0, 0))
obj(p, "Canvas_Main", CANVAS)
FLAP_ORIGIN = (CX, hy0, 0.0)
p = mc.Part([M["paint_s"]])
sheet(p, [y for y in ys if hy0 - 1e-6 <= y <= hy1 + 1e-6], [z for z in zs if z <= hz1 + 1e-6],
      lambda y, z: True, FLAP_ORIGIN)
flap = p.finish("Canvas_Flap", parent=CANVAS, collection=C_EXP, location=FLAP_ORIGIN)
mc.empty("Canvas_Pos", parent=CANVAS, location=(CX, (hy0 + hy1) / 2, (hz0 + hz1) / 2 + 0.05), collection=C_EXP)

# 框架与脚手架
p = mc.Part([M["timber"]])
for yy in (CY0 - 0.12, CY1 + 0.12):                                   # 两头立柱（压住布边，正面看得见）
    bx(p, CX - 0.3, CX + 0.05, yy - 0.13, yy + 0.13, -0.4, CZ1 + 0.45, M["timber"])
    bx(p, CX + 0.0, CX + 0.12, yy - 0.2, yy + 0.2, -0.1, CZ1 + 0.1, M["timber"])
bx(p, CX - 0.05, CX + 0.1, CY0 - 0.3, CY1 + 0.3, CZ1 - 0.12, CZ1 + 0.14, M["timber"])     # 顶上压条（正面）
bx(p, CX - 0.3, CX - 0.12, CY0 - 0.3, CY1 + 0.3, CZ1 - 0.1, CZ1 + 0.2, M["timber"])      # 背面吊杆
bot_segments = [(CY0, hy0 - 0.25), (hy1 + 0.25, CY1)]
for a_, b_ in bot_segments:                                          # 底边压条（路口那段空着）
    bx(p, CX - 0.02, CX + 0.1, a_, b_, -0.1, 0.07, M["timber"])
# 背后竖档（每道接缝一根）+ 横档 + 斜撑
seams = [CY0 + 2.7 * k for k in range(1, 20)]
for sy_ in seams:
    z0 = hz1 + 0.15 if hy0 - 0.3 < sy_ < hy1 + 0.3 else -0.1
    bx(p, CX - 0.3, CX - 0.16, sy_ - 0.05, sy_ + 0.05, z0, CZ1 - 0.1, M["timber"])
for zz in (4.7, 9.4):
    bx(p, CX - 0.42, CX - 0.3, CY0, CY1, zz - 0.07, zz + 0.07, M["timber"])
braces = [sy_ for k, sy_ in enumerate(seams) if k % 2 == 0 and not (-11.0 < sy_ < -3.6)] + [CY0 + 0.3, CY1 - 0.3]
for sy_ in braces:
    top = Vector((CX - 0.35, sy_, 7.5)); foot = Vector((CX - 4.6, sy_, -0.05))
    d = top - foot
    p.box((0.09, 0.14, d.length), M["timber"], xf=T(*((top + foot) / 2)) @ mc.orient(d))
    bx(p, foot.x - 0.3, foot.x + 0.4, sy_ - 0.12, sy_ + 0.12, -0.08, 0.06, M["timber"])
obj(p, "Canvas_Frame", CANVAS)

# 沙袋：底边前面、斜撑脚、两头立柱
p = mc.Part([M["burlap"]])
rnd = random.Random(21)


def sandbag(x, y, z, yaw):
    s = rnd.uniform(0.9, 1.1)
    p.sphere(0.2 * s, M["burlap"], xf=T(x, y, z + 0.08 * s) @ R("Z", yaw) @ R("Y", rnd.uniform(-6, 6)), seg=10, rings=6, sx=1.6, sy=0.95, sz=0.45)
    p.sphere(0.05, M["burlap"], xf=T(x, y, z + 0.08 * s) @ R("Z", yaw) @ T(0.33 * s, 0, 0.0), seg=6, rings=4, sx=1.2)   # 扎口


for yy in [CY0 + 0.6, CY0 + 0.95, CY1 - 0.6, CY1 - 0.95] + [v for v in (-30.0, -25.5, -21.4, -16.9, -13.2, -11.6, -3.2, -1.5, 2.8, 7.4, 11.9, 16.0)]:
    sandbag(CX + 0.32, yy + rnd.uniform(-0.2, 0.2), -0.07, rnd.uniform(-20, 20))
    if rnd.random() < 0.5:
        sandbag(CX + 0.32, yy + rnd.uniform(-0.15, 0.15), 0.07, rnd.uniform(-30, 30))
for sy_ in braces:
    for k in range(2):
        sandbag(CX - 4.4 + k * 0.1, sy_ + (k - 0.5) * 0.45, -0.07 + 0.0, 90 + rnd.uniform(-15, 15))
    sandbag(CX - 4.35, sy_, 0.09, 90)
# 吊在立柱旁的配重沙袋
for yy in (CY0 - 0.5, CY1 + 0.5):
    p.sphere(0.2, M["burlap"], xf=T(CX + 0.15, yy, 2.4) @ R("X", 90), seg=10, rings=6, sx=0.9, sy=0.5, sz=1.4)
obj(p, "Canvas_Sandbags", CANVAS)

# 绳子（不要碰撞）
p = mc.Part([M["rope"]])


def rope(a, b, sag=0.0, r=0.012, n=6):
    a, b = Vector(a), Vector(b)
    pts = [a.lerp(b, k / n) - Vector((0, 0, sag * math.sin(math.pi * k / n))) for k in range(n + 1)]
    for pa, pb in zip(pts, pts[1:]):
        p.lathe([(0, r, r), ((pb - pa).length, r, r)], M["rope"], seg=4, xf=T(*pa) @ mc.orient(pb - pa), cap=False)


for yy, s in ((CY0 - 0.12, -1), (CY1 + 0.12, 1)):
    top = (CX - 0.1, yy, CZ1 + 0.3)
    for st in ((CX + 3.0, yy + s * 3.0, 0.1), (CX - 4.0, yy + s * 4.0, 0.1), (CX - 7.5, yy, 0.1)):
        rope(top, st, sag=0.25)
        p.box((0.05, 0.05, 0.45), M["timber"], xf=T(st[0], st[1], 0.1))
    rope((CX + 0.05, yy, 6.0), (CX + 0.15, yy - s * 0.0, 2.65), r=0.01, n=2)             # 配重沙袋的吊绳
    for zz in (2.0, 5.5, 9.0, 12.5):                                                         # 布边绑在立柱上
        rope((CX + 0.04, yy - s * 0.18, zz), (CX + 0.06, yy + s * 0.14, zz + 0.12), r=0.014, n=1)
for yy in seams[::3]:
    rope((CX - 0.2, yy, CZ1), (CX - 8.0, yy, 0.05), sag=0.4)
obj(p, "NoCol_Canvas_Ropes", CANVAS)

# ---------------------------------------------------------------- 统计 + 导出
exp_objs = mc.descendants(ROOT_OBJ)
tris = mc.tri_count(exp_objs)
print(f"TRIS total {tris}")
for o in exp_objs:
    if o.type == "MESH":
        print(f"  {o.name:26s} {mc.tri_count([o]):7d}")
if EXPORT:
    mc.export_glb(EXPORT, [ROOT_OBJ])


def unity(v):
    return (round(v[0], 3), round(v[2], 3), round(v[1], 3))


bpy.context.view_layer.update()
for nm in ("Church_BellPos", "Church_Bell", "Graveyard_Gate", "TBD_Graveyard", "TBD_Church", "Grave_Martha", "Grave_Blank", "Canvas_Flap", "Canvas_Pos"):
    o = bpy.data.objects[nm]
    print(f"POS {nm:16s} blender {tuple(round(c, 3) for c in o.matrix_world.translation)}  unity {unity(o.matrix_world.translation)}")

# ---------------------------------------------------------------- 评审渲染
if RENDER:
    for path in [STREET_GLTF, mc.ART / "Saloon" / "Saloon.gltf"] + sorted(p_ for p_ in (mc.ART / "Town").glob("*.gltf") if p_.stem != "TownEdges"):
        if path.exists():
            new = import_gltf(path, path.stem)
            for o in new:
                for c in list(o.users_collection): c.objects.unlink(o)
                C_REV.objects.link(o)
    mc.setup_render(SAMPLES, exposure=0.0)
    mc.world_hdri("goegap_road", strength=0.9, rot=140)
    add_sun(C_REV)
    shots = [
        ("Edges_church", (10.0, -7.3, 1.6), (35.0, -7.3, 7.0), 22),
        ("Edges_graveyard", (31.75, 3.05, 1.6), (32.6, 5.0, 0.55), 30),
        ("Edges_canvas_far", (0.0, -7.3, 1.6), (-34.0, -7.3, 2.6), 24),
        ("Edges_canvas_near", (-32.0, -6.6, 1.6), (-34.0, -7.6, 1.2), 16),
        ("Edges_aerial", (12.0, -30.0, 22.0), (30.0, 0.0, 2.0), 24),
        ("Edges_canvas_side", (-28.0, 14.0, 6.0), (-34.0, 20.0, 6.0), 24),
    ]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    for name, loc, tgt, lens in shots:
        if only and name not in only: continue
        mc.camera("Cam_" + name, loc, tgt, lens=lens, coll=C_REV)
        mc.render(mc.REVIEWS / f"{name}.png")
