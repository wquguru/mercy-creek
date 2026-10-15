"""Mercy Creek 小道具：打字机、书桌 + 椅子、笔记本、挂历、信、威士忌杯。

blender --background --python tools/blender/build_props.py -- [--only Typewriter,Desk] [--no-render] [--samples 48]
先跑：<装了 Pillow 的 python> tools/gen_prop_textures.py   （生成文字贴图到 art/source/_derived/props/）
输出：Game/Assets/_MercyCreek/Art/Props/<Name>.glb，评审图 Reviews/blender/<Name>.png
朝向：正面朝 Blender -Y（glTFast 导入后为 Unity +Z），Z 向上，原点在落地 / 底面中心，单位米。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy, bmesh
from mathutils import Vector, Matrix
import mc_common as mc
from mc_common import T, R, S

A = mc.args()
ONLY = A[A.index("--only") + 1].split(",") if "--only" in A else None
RENDER = "--no-render" not in A
SAMPLES = int(A[A.index("--samples") + 1]) if "--samples" in A else 48
OUT = mc.ART / "Props"
PTEX = mc.SRC / "_derived" / "props"
MAX_TRIS = 3000
RESULTS = {}

# 让局部 X→世界 Y、局部 Y→世界 Z、局部 Z→世界 X（在 YZ 平面画侧轮廓再沿 X 挤出）
YZX = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


# ------------------------------------------------------------------ 本文件专用的小工具
def disc(p, xf, r, n, mat, uvc=(0.5, 0.5), uvr=(0.5, 0.5)):
    """局部 XY 平面上的 n 边形面（朝 +Z），UV 映射到图集里的一个圆。"""
    vs = []
    for j in range(n):
        a = 2 * math.pi * j / n
        vs.append(p.bm.verts.new(xf @ Vector((r * math.cos(a), r * math.sin(a), 0))))
    f = p.bm.faces.new(vs)
    for j, lp in enumerate(f.loops):
        a = 2 * math.pi * j / n
        lp[p.uv].uv = (uvc[0] + uvr[0] * math.cos(a), uvc[1] + uvr[1] * math.sin(a))
    p._take([f], mat, False)
    return f


def sheet(p, path, x0, x1, mat, nx=1, zfn=None, u_range=(0.0, 1.0)):
    """沿 path=[(y, z)] 扫出一张纸（X 从 x0 到 x1），UV：u 横向、v 沿路径 0→1。zfn(x, y, z) 可加起伏。"""
    L = [0.0]
    for a, b in zip(path, path[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    rows = []
    for (y, z), s in zip(path, L):
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            zz = z + (zfn(x, y, z) if zfn else 0.0)
            row.append((p.bm.verts.new((x, y, zz)), (u_range[0] + (u_range[1] - u_range[0]) * i / nx, s / L[-1])))
        rows.append(row)
    faces = []
    for A_, B_ in zip(rows, rows[1:]):
        for i in range(nx):
            q = [A_[i], A_[i + 1], B_[i + 1], B_[i]]
            f = p.bm.faces.new([v for v, _ in q])
            for lp, (_, uv) in zip(f.loops, q):
                lp[p.uv].uv = uv
            faces.append(f)
    p._take(faces, mat, True)
    return faces


def fix_normals(p):
    bmesh.ops.recalc_face_normals(p.bm, faces=p.bm.faces[:])


def turned(profile_rz, z0=0.0):
    """车床件轮廓：[(z, r)] → lathe profile。"""
    return [(z0 + z, r, r) for z, r in profile_rz]


def start(name):
    mc.reset()
    print(f"==== {name}")


def finish_asset(name, roots, cam_loc, cam_target, lens=50, scale=0.3, key=500, floor=(0.2, 0.16, 0.13), extra=None):
    tris = mc.tri_count([o for r in roots for o in mc.descendants(r)])
    names = [o.name for r in roots for o in mc.descendants(r)]
    RESULTS[name] = (tris, names)
    print(f"{name}: {tris} tris, objects {names}")
    assert tris <= MAX_TRIS, f"{name} over budget: {tris}"
    mc.export_glb(OUT / f"{name}.glb", roots)
    if not RENDER:
        return
    sc = mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.35)
    mc.studio(scale=scale, key=key, floor_color=floor)
    if extra:
        extra()
    mc.camera("Cam", cam_loc, cam_target, lens=lens)
    mc.render(mc.REVIEWS / f"{name}.png")


# ------------------------------------------------------------------ 打字机（1870–80 年代上击式，Sholes & Glidden 风格）
KEYROWS = ["23456789-,", "QWE.TYIUOP", "ZSDFGHJKLM", "AX&CVBN?;R"]


def build_typewriter():
    start("Typewriter")
    enamel = mc.pbr("TW_BlackEnamel", "Metal027", tile=0.25, metal=0.2, normal=0.4, tint=(0.45, 0.45, 0.45))
    chrome = mc.flat("TW_Nickel", (0.78, 0.76, 0.72), rough=0.25, metal=1.0)
    gold = mc.flat("TW_GoldLeaf", (0.85, 0.62, 0.28), rough=0.35, metal=1.0)
    rubber = mc.flat("TW_Platen", (0.035, 0.032, 0.03), rough=0.75)
    keys = mc.image_mat("TW_KeyTops", PTEX / "typewriter_keys.png", rough=0.35)
    wood = mc.pbr("TW_WoodBase", "Wood027", tile=0.4, tint=(0.8, 0.7, 0.6))
    p = mc.Part([enamel, chrome, gold, rubber, keys, wood])

    # 木底座 + 铸铁底板
    p.box((0.44, 0.34, 0.022), wood, xf=T(0, 0.0, 0.011), bevel=0.006, bseg=2)
    p.box((0.40, 0.30, 0.012), enamel, xf=T(0, 0.0, 0.028), bevel=0.004)
    # 两侧铸铁侧板（侧面轮廓：前低后高）
    side = [(-0.13, 0.0), (0.13, 0.0), (0.13, 0.15), (0.09, 0.185), (0.0, 0.185), (-0.07, 0.11), (-0.13, 0.075)]
    for sx in (-1, 1):
        x = sx * 0.185
        p.poly_extrude(side, 0.012, enamel, xf=T(x - 0.006, 0, 0.034) @ YZX)
        # 侧板金色描线（细金条，略突出侧板外表面）
        for (a, b) in [((-0.12, 0.012), (0.12, 0.012)), ((0.12, 0.012), (0.12, 0.14))]:
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); ln = math.hypot(b[0] - a[0], b[1] - a[1])
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            p.box((0.0015, ln, 0.004), gold, xf=T(x + sx * 0.0065, mid[0], 0.034 + mid[1]) @ R("X", ang))
    # 前面板（键盘下方斜板）+ 金色铭牌
    # 键盘底板：顺着键排的坡度，藏在键杆下面；前沿一条金色铭牌
    slope = math.degrees(math.atan2(0.042, 0.09))
    p.box((0.36, 0.13, 0.006), enamel, xf=T(0, -0.105, 0.052) @ R("X", slope), bevel=0.002)
    p.box((0.36, 0.006, 0.035), enamel, xf=T(0, -0.172, 0.045), bevel=0.002)
    p.box((0.14, 0.002, 0.014), gold, xf=T(0, -0.1755, 0.047))
    # 顶部机身盖板
    p.box((0.36, 0.11, 0.008), enamel, xf=T(0, 0.04, 0.215), bevel=0.003)
    # 字杆篮：圆盘 + 放射的字杆
    p.lathe(turned([(0, 0.0), (0, 0.10), (0.012, 0.10), (0.012, 0.0)]), enamel, seg=20, xf=T(0, 0.04, 0.221))
    for i in range(14):
        a = math.radians(-80 + 160 * i / 13)
        d = Vector((math.sin(a), -math.cos(a), 0))
        c = Vector((0, 0.04, 0.236)) + d * 0.05
        p.box((0.003, 0.09, 0.002), chrome, xf=T(*c) @ R("Z", math.degrees(a)) @ R("X", 12))
    # 滑架：导轨 + 胶辊 + 两端旋钮 + 压纸杆 + 回车杆
    PY, PZ, PR = 0.085, 0.27, 0.024
    for dy in (-0.035, 0.035):
        p.box((0.46, 0.012, 0.01), chrome, xf=T(0, PY + dy, PZ - 0.035), bevel=0.002)
    for sx in (-1, 1):
        p.box((0.012, 0.08, 0.05), enamel, xf=T(sx * 0.215, PY, PZ - 0.02), bevel=0.003)
        p.lathe(turned([(0, 0.0), (0, 0.016), (0.008, 0.02), (0.03, 0.02), (0.036, 0.012), (0.036, 0)]), rubber, seg=14,
                xf=T(sx * 0.221, PY, PZ) @ R("Y", 90 * sx))
    p.lathe(turned([(-0.2, 0.0), (-0.2, PR), (0.2, PR), (0.2, 0.0)]), rubber, seg=20, xf=T(0, PY, PZ) @ R("Y", 90))
    p.lathe(turned([(-0.19, 0.0), (-0.19, 0.003), (0.19, 0.003), (0.19, 0.0)]), chrome, seg=6, xf=T(0, PY - 0.03, PZ + 0.012) @ R("Y", 90))
    p.box((0.006, 0.006, 0.08), chrome, xf=T(-0.235, PY - 0.03, PZ + 0.025) @ R("Y", -35))
    # 键盘：4 排 x 10 圆键，阶梯上升；镀镍键圈 + 象牙字面
    for r, row in enumerate(KEYROWS):
        y = -0.06 - r * 0.03       # 后排（数字）在 +Y，前排在 -Y
        z = 0.105 - r * 0.014
        for k, ch in enumerate(row):
            x = (k - 4.5) * 0.031 + (r % 2) * 0.008 - 0.004
            p.box((0.003, 0.003, 0.05), chrome, xf=T(x, y + 0.004, z - 0.025))
            p.lathe([(0, 0.0115, 0.0115), (0.004, 0.0115, 0.0115)], chrome, seg=10, xf=T(x, y, z), cap=False)
            idx = "".join(KEYROWS).index(ch)
            cx, cy = (idx % 8) * 128 + 64, (idx // 8) * 128 + 64
            disc(p, T(x, y, z + 0.0035), 0.0105, 10, keys, uvc=(cx / 1024, 1 - cy / 640), uvr=(60 / 1024, 60 / 640))
    p.box((0.24, 0.012, 0.007), chrome, xf=T(0, -0.175, 0.05), bevel=0.002)   # 空格杆
    for sx in (-1, 1):
        p.box((0.004, 0.03, 0.004), chrome, xf=T(sx * 0.11, -0.16, 0.047))
    fix_normals(p)
    tw = p.finish("Typewriter")

    # 纸：从胶辊后下方绕过前面、出顶部，向后上方立起；正面（打的字）朝打字的人（-Y）
    paper = mc.image_mat("TW_Paper", PTEX / "typed_page.png", rough=0.85)
    pp = mc.Part([paper]); path = []
    rr = PR + 0.0008
    for i in range(10):     # 尾部：后下方 → 底 → 前 → 顶
        th = math.radians(-30 - 240 * i / 9)
        path.append((PY + rr * math.cos(th), PZ + rr * math.sin(th)))
    path.insert(0, (PY + 0.05, PZ - 0.055))
    # 立起的部分（略向后仰，顶部微卷）
    top = Vector(path[-1]); L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))
    rest = 0.279 - L
    for i in range(1, 7):
        t = i / 6
        path.append((top.x + 0.025 * t + 0.02 * t * t, top.y + rest * t * 0.985))
    path = [(y, z) for y, z in path]
    sheet(pp, path, -0.108, 0.108, paper, nx=4)
    mc_paper = pp.finish("Paper", parent=tw)
    finish_asset("Typewriter", [tw], (-0.62, -0.95, 0.62), (0, 0.02, 0.2), lens=50, scale=0.3, key=420)


# ------------------------------------------------------------------ 书桌 + 椅子
def build_desk():
    start("Desk")
    wood = mc.pbr("Desk_Walnut", "Wood066", tile=0.8, tint=(0.7, 0.6, 0.55))
    leather = mc.pbr("Desk_Leather", "Leather037", tile=0.5, tint=(0.42, 0.62, 0.36), rough=0.9)  # 墨绿书写皮面
    leather.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.15
    brass = mc.flat("Desk_Brass", (0.72, 0.52, 0.24), rough=0.35, metal=1.0)
    dark = mc.pbr("Desk_DarkWood", "Wood027", tile=0.6)
    p = mc.Part([wood, leather, brass, dark])
    W, D, H = 1.20, 0.66, 0.76
    p.box((W, D, 0.035), wood, xf=T(0, 0, H - 0.0175), bevel=0.01, bseg=2)
    p.box((W - 0.16, D - 0.16, 0.003), leather, xf=T(0, 0.01, H + 0.0005))
    # 左侧抽屉柜：踢脚 + 柜体 + 三个抽屉
    px0, px1 = -0.585, -0.17
    p.box((px1 - px0 + 0.03, D - 0.06, 0.06), dark, xf=T((px0 + px1) / 2, 0, 0.03), bevel=0.006)
    p.box((px1 - px0, D - 0.08, H - 0.035 - 0.06), wood, xf=T((px0 + px1) / 2, 0, 0.06 + (H - 0.095) / 2), bevel=0.005)
    zs = [0.07, 0.30, 0.50, 0.70]
    for i in range(3):
        z0, z1 = zs[i] + 0.008, zs[i + 1] - 0.008
        cx, cz = (px0 + px1) / 2, (z0 + z1) / 2
        p.box((px1 - px0 - 0.04, 0.02, z1 - z0), wood, xf=T(cx, -(D - 0.08) / 2 - 0.006, cz), bevel=0.008, bseg=2)
        p.box((px1 - px0 - 0.10, 0.006, z1 - z0 - 0.06), dark, xf=T(cx, -(D - 0.08) / 2 - 0.016, cz), bevel=0.002)
        p.lathe(turned([(0, 0), (0, 0.008), (0.012, 0.006), (0.02, 0.012), (0.026, 0.0)]), brass, seg=10,
                xf=T(cx, -(D - 0.08) / 2 - 0.018, cz) @ R("X", 90))
    # 中间扁抽屉 + 右侧车腿 + 围板 + 背板
    p.box((0.62, 0.02, 0.09), wood, xf=T(0.22, -(D - 0.08) / 2 - 0.004, H - 0.035 - 0.05), bevel=0.006, bseg=2)
    p.lathe(turned([(0, 0), (0, 0.008), (0.012, 0.006), (0.02, 0.012), (0.026, 0.0)]), brass, seg=10,
            xf=T(0.22, -(D - 0.08) / 2 - 0.016, H - 0.085) @ R("X", 90))
    leg = [(0, 0.0), (0, 0.022), (0.03, 0.026), (0.06, 0.02), (0.30, 0.026), (0.42, 0.03), (0.46, 0.022), (0.50, 0.034),
           (0.56, 0.034), (0.58, 0.028), (H - 0.035, 0.028), (H - 0.035, 0.0)]
    for y in (-(D - 0.12) / 2, (D - 0.12) / 2):
        p.lathe(turned(leg), wood, seg=12, xf=T(0.54, y, 0))
    p.box((0.03, D - 0.14, 0.12), wood, xf=T(0.54, 0, H - 0.035 - 0.06))
    p.box((0.68, 0.02, 0.32), wood, xf=T(0.19, (D - 0.08) / 2 - 0.01, H - 0.035 - 0.16))
    fix_normals(p)
    desk = p.finish("Desk")

    # 椅子：车腿木椅，座面朝 +Y（坐着面对书桌）；对象原点在椅子落地中心
    c = mc.Part([wood, dark])
    SZ = 0.46
    c.box((0.42, 0.40, 0.035), wood, xf=T(0, 0, SZ - 0.0175), bevel=0.012, bseg=2)
    fl = [(0, 0.0), (0, 0.019), (0.10, 0.021), (0.16, 0.016), (0.20, 0.023), (0.24, 0.016), (0.36, 0.022), (SZ - 0.035, 0.022), (SZ - 0.035, 0)]
    for sx in (-1, 1):
        c.lathe(turned(fl), wood, seg=10, xf=T(sx * 0.18, 0.16, 0))
        # 后腿一体通到靠背，略向后仰
        bl = [(0, 0.0), (0, 0.02), (0.20, 0.022), (0.24, 0.016), (0.30, 0.022), (0.88, 0.018), (0.91, 0.022), (0.93, 0.0)]
        c.lathe(turned(bl), wood, seg=10, xf=T(sx * 0.18, -0.17, 0) @ R("X", 6))
    # 横撑
    for (a, b) in [((-0.18, 0.16), (-0.18, -0.17)), ((0.18, 0.16), (0.18, -0.17)), ((-0.18, 0.16), (0.18, 0.16))]:
        ma = Vector((a[0], a[1], 0.18)); mb = Vector((b[0], b[1], 0.18)); d = mb - ma
        c.lathe(turned([(0, 0.0), (0, 0.008), (d.length, 0.008), (d.length, 0.0)]), wood, seg=8, xf=T(*ma) @ mc.orient(d))
    # 靠背：弯顶板 + 中横档 + 中间板 + 两根细杆
    for z, h in ((0.86, 0.075), (0.58, 0.03)):
        yb = -0.17 - math.tan(math.radians(6)) * z
        for k in range(4):     # 用 4 段拼出向后弯的顶板
            x0 = -0.17 + 0.34 * k / 4; x1 = -0.17 + 0.34 * (k + 1) / 4
            ym = yb - 0.02 * (1 - ((x0 + x1) / 2 / 0.17) ** 2)
            c.box((0.34 / 4 + 0.004, 0.02, h), wood, xf=T((x0 + x1) / 2, ym, z) @ R("X", 6), bevel=0.004)
    yb0 = -0.17 - math.tan(math.radians(6)) * 0.72 - 0.02
    c.box((0.09, 0.014, 0.25), dark, xf=T(0, yb0 + 0.02, 0.72) @ R("X", 6), bevel=0.004)
    for sx in (-1, 1):
        c.lathe(turned([(0, 0.0), (0, 0.008), (0.25, 0.008), (0.25, 0.0)]), wood, seg=8,
                xf=T(sx * 0.1, yb0 + 0.024, 0.595) @ R("X", 6))
    fix_normals(c)
    chair = c.finish("Chair", location=(0.12, -0.62, 0))
    chair.rotation_euler = (0, 0, math.radians(-8))
    finish_asset("Desk", [desk, chair], (-1.55, -2.35, 1.45), (0.0, -0.2, 0.5), lens=40, scale=0.9, key=500)


# ------------------------------------------------------------------ 打开的皮面笔记本
def build_notebook():
    start("Notebook")
    leather = mc.pbr("NB_Leather", "Leather030", tile=0.25)
    pages = mc.image_mat("NB_Pages", PTEX / "notebook_pages.png", rough=0.8)
    edge = mc.flat("NB_PageEdge", (0.78, 0.72, 0.58), rough=0.9)
    ribbon = mc.flat("NB_Ribbon", (0.22, 0.02, 0.02), rough=0.6)
    p = mc.Part([leather, pages, edge, ribbon])
    PW, PH = 0.105, 0.165
    CW, CH = PW + 0.006, PH + 0.008
    for sx in (-1, 1):
        p.box((CW, CH, 0.003), leather, xf=T(sx * (CW / 2 + 0.002), 0, 0.0015), bevel=0.0012)
        # 页块
        p.box((PW - 0.004, PH, 0.006), edge, xf=T(sx * (PW / 2 + 0.002), 0, 0.006))
    p.lathe(turned([(-CH / 2, 0.0), (-CH / 2, 0.006), (CH / 2, 0.006), (CH / 2, 0.0)]), leather, seg=8, xf=T(0, 0, 0.004) @ R("X", 90))
    # 页面：向书脊隆起再沉进书沟
    def zf(x, y, z):
        t = min(1.0, abs(x) / PW)
        return 0.0095 + 0.007 * math.sin(math.pi * (1 - t) ** 0.55) - 0.004 * max(0.0, 1 - t * 12)
    pa = [(-PH / 2, 0.0), (PH / 2, 0.0)]
    sheet(p, pa, -PW, 0.0, pages, nx=10, zfn=zf, u_range=(0.0, 0.5))
    sheet(p, pa, 0.0, PW, pages, nx=10, zfn=zf, u_range=(0.5, 1.0))
    # 书签丝带：从书沟垂出到下边
    p.quad([(-0.003, -PH / 2, 0.0062), (0.003, -PH / 2, 0.0062), (0.003, 0.03, 0.0062), (-0.003, 0.03, 0.0062)], ribbon)
    p.quad([(-0.003, -PH / 2 - 0.04, 0.0009), (0.003, -PH / 2 - 0.04, 0.0009), (0.003, -PH / 2, 0.0062), (-0.003, -PH / 2, 0.0062)], ribbon)
    nb = p.finish("Notebook")
    # 铅笔（子对象）
    wood = mc.flat("NB_PencilWood", (0.28, 0.07, 0.04), rough=0.45)
    lead = mc.flat("NB_PencilLead", (0.08, 0.08, 0.08), rough=0.4)
    q = mc.Part([wood, lead])
    q.lathe([(0, 0.0, 0.0), (0, 0.0035, 0.0035), (0.13, 0.0035, 0.0035)], wood, seg=6, xf=Matrix.Identity(4), cap=False)
    q.lathe([(0.13, 0.0035, 0.0035), (0.148, 0.0011, 0.0011), (0.152, 0.0, 0.0)], lead, seg=6)
    fix_normals(q)
    pencil = q.finish("Pencil", parent=nb, location=(0.03, -0.02, 0.0205))
    pencil.rotation_euler = (0, math.radians(90), math.radians(28))
    finish_asset("Notebook", [nb], (-0.10, -0.40, 0.32), (0, -0.005, 0.0), lens=60, scale=0.12, key=300)


# ------------------------------------------------------------------ 挂历（挂墙：背面贴墙 y=0，正面朝 -Y，原点在下沿中心）
def build_calendar():
    start("Calendar")
    card = mc.pbr("Cal_Card", "Paper005", tile=0.3, tint=(0.55, 0.45, 0.35))
    page = mc.image_mat("Cal_Page", PTEX / "calendar.png", rough=0.85)
    edge = mc.flat("Cal_Under", (0.76, 0.7, 0.58), rough=0.9)
    tin = mc.flat("Cal_Tin", (0.12, 0.1, 0.09), rough=0.4, metal=0.8)
    string = mc.flat("Cal_String", (0.55, 0.45, 0.32), rough=0.9)
    p = mc.Part([card, page, edge, tin, string])
    W, H = 0.30, 0.40
    p.box((W + 0.02, 0.003, H + 0.06), card, xf=T(0, -0.0015, (H + 0.06) / 2))
    for k in range(3):   # 下面几页的纸边，每页错开一点
        p.box((W, 0.0006, H - 0.004 * k), edge, xf=T(0, -0.0035 - 0.0007 * k, 0.03 + 0.004 * k + (H - 0.004 * k) / 2))
    # 当前这一页：右下角微翘
    def zfn(x, y, z):  # 这里的 "z" 其实是 sheet 扫出的竖直位置，用 x 方向翘角
        return 0.0
    rows = []
    bm, uvl = p.bm, p.uv
    nx, nz = 6, 8
    grid = []
    for j in range(nz + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / nz
            lift = 0.025 * max(0.0, u - 0.55) / 0.45 * max(0.0, 0.35 - v) / 0.35
            co = Vector(((u - 0.5) * W, -0.0062 - lift, 0.03 + v * H))
            row.append((bm.verts.new(co), (u, v)))
        grid.append(row)
    fs = []
    for j in range(nz):
        for i in range(nx):
            q = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
            f = bm.faces.new([a for a, _ in q])
            for lp, (_, uv) in zip(f.loops, q): lp[uvl].uv = uv
            fs.append(f)
    p._take(fs, page, True)
    # 顶部铁皮夹条、挂绳、钉子
    p.box((W + 0.03, 0.012, 0.03), tin, xf=T(0, -0.008, H + 0.045), bevel=0.003)
    nail = (0, -0.012, H + 0.16)
    for sx in (-1, 1):
        a = Vector((sx * 0.1, -0.008, H + 0.06)); d = Vector(nail) - a
        p.lathe(turned([(0, 0.0), (0, 0.0012), (d.length, 0.0012), (d.length, 0)]), string, seg=4, xf=T(*a) @ mc.orient(d))
    p.lathe(turned([(0, 0.0), (0, 0.0022), (0.02, 0.0022), (0.02, 0.005), (0.023, 0.005), (0.023, 0)]), tin, seg=8,
            xf=T(0, 0.004, H + 0.16) @ R("X", 90))
    cal = p.finish("Calendar")
    def wall():
        w = mc.Part([mc.pbr("Cal_Wall", "Planks037A", tile=1.2, tint=(0.7, 0.6, 0.5))])
        w.box((2, 0.02, 2), w.mats[0], xf=T(0, 0.01, 0.4)); w.finish("Wall")
    finish_asset("Calendar", [cal], (-0.3, -1.25, 0.36), (0, 0, 0.28), lens=50, scale=0.3, key=350, extra=wall)


# ------------------------------------------------------------------ 折过三折、半摊开的信 + 信封
def build_letter():
    start("Letter")
    paper = mc.image_mat("Letter_Paper", PTEX / "letter.png", rough=0.85)
    env = mc.pbr("Letter_Envelope", "Paper005", tile=0.25, tint=(1.0, 0.97, 0.85), normal=0.5)
    p = mc.Part([paper])
    W, H = 0.20, 0.256
    h3 = H / 3
    def panel(y0, y1, ang_deg, rising_up):
        pass
    # 中间一折平放；下折（-Y）抬 22°，上折（+Y）抬 14° 并微卷
    path = []
    a1 = math.radians(22)
    path += [(-h3 / 2 - h3 * math.cos(a1), h3 * math.sin(a1) + 0.001), (-h3 / 2 - h3 * 0.5 * math.cos(a1), h3 * 0.5 * math.sin(a1) + 0.001)]
    path += [(-h3 / 2, 0.001), (0.0, 0.0008), (h3 / 2, 0.001)]
    a2 = math.radians(14)
    for t in (0.35, 0.7, 1.0):
        path.append((h3 / 2 + h3 * t * math.cos(a2), 0.001 + h3 * t * math.sin(a2) + 0.004 * t * t))
    sheet(p, path, -W / 2, W / 2, paper, nx=3)
    letter = p.finish("Letter")
    letter.rotation_euler = (0, 0, math.radians(6))
    e = mc.Part([env])
    e.box((0.165, 0.095, 0.0025), env, xf=T(0, 0, 0.00125), bevel=0.0008)
    # 信封口盖（三角）
    bm = e.bm
    vs = [bm.verts.new(c) for c in [(-0.0825, 0.0475, 0.0026), (0.0825, 0.0475, 0.0026), (0.0, -0.005, 0.0028)]]
    f = bm.faces.new(vs)
    for lp in f.loops: lp[e.uv].uv = (lp.vert.co.x / 0.25, lp.vert.co.y / 0.25)
    e._take([f], env, False)
    envelope = e.finish("Envelope", location=(0.06, 0.09, 0))
    envelope.rotation_euler = (0, 0, math.radians(-24))
    letter.location = (0, 0, 0.0)
    finish_asset("Letter", [letter, envelope], (0.0, -0.42, 0.42), (0.01, 0.02, 0.0), lens=50, scale=0.15, key=300)


# ------------------------------------------------------------------ 有缺口的威士忌杯
def build_glass():
    start("WhiskeyGlass")
    glass = mc.flat("Glass", (0.92, 0.95, 0.92), rough=0.04, transmission=1.0, alpha=0.3, ior=1.5)
    p = mc.Part([glass])
    RIM = 0.088
    prof = [(0, 0.0, 0.0), (0, 0.031, 0.031), (0.002, 0.0335, 0.0335), (0.03, 0.0365, 0.0365), (0.085, 0.0400, 0.0400),
            (RIM, 0.0396, 0.0396), (RIM, 0.0380, 0.0380), (0.085, 0.0376, 0.0376), (0.03, 0.0345, 0.0345),
            (0.016, 0.0335, 0.0335), (0.0145, 0.030, 0.030), (0.0145, 0.0, 0.0)]
    p.lathe(prof, glass, seg=48)
    fix_normals(p)
    g = p.finish("WhiskeyGlass", smooth_angle=60)
    # 缺口：在杯口某个角度把上沿的点往下压，做出 V 形崩口（朝前偏右，正面看得见）
    chip_ang = math.radians(35)       # 从 -Y 朝 +X 转
    for v in g.data.vertices:
        co = v.co
        if co.z < 0.074: continue
        a = math.atan2(co.x, -co.y)
        da = abs((a - chip_ang + math.pi) % (2 * math.pi) - math.pi)
        w = math.radians(13)
        if da < w:
            depth = 0.009 * (1 - (da / w) ** 1.5)
            co.z -= depth * (co.z - 0.074) / (RIM - 0.074)
    g.data.update()
    whisky = mc.flat("Whiskey", (0.55, 0.24, 0.05), rough=0.05, transmission=0.85, alpha=0.75, ior=1.36)
    q = mc.Part([whisky])
    q.lathe([(0, 0.0, 0.0), (0, 0.0332, 0.0332), (0.016, 0.0343, 0.0343), (0.032, 0.0352, 0.0352), (0.032, 0.0, 0.0)], whisky, seg=32)
    fix_normals(q)
    w_ = q.finish("Whiskey", parent=g, location=(0, 0, 0.0146))
    def table():
        t = mc.Part([mc.pbr("Table", "WoodFloor043", tile=0.6, tint=(0.6, 0.45, 0.35))])
        t.box((1.2, 1.2, 0.02), t.mats[0], xf=T(0, 0.2, -0.01)); t.finish("Table")
        bpy.data.objects["Backdrop"].location.z = -0.05   # 与桌面共面会让阴影射线全黑
    finish_asset("WhiskeyGlass", [g], (0.04, -0.30, 0.22), (0.0, 0.0, 0.045), lens=60, scale=0.3, key=500,
                 floor=(0.35, 0.3, 0.25), extra=table)


BUILDERS = {"Typewriter": build_typewriter, "Desk": build_desk, "Notebook": build_notebook,
            "Calendar": build_calendar, "Letter": build_letter, "WhiskeyGlass": build_glass}
for name, fn in BUILDERS.items():
    if ONLY and name not in ONLY:
        continue
    fn()
print("SUMMARY")
for k, (t, n) in RESULTS.items():
    print(f"  {k}: {t} tris  {n}")
