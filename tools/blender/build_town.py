"""Mercy Creek 北侧一排：酒馆外壳（外墙护板 + 假立面 + 坡屋顶 + 雨棚柱）+ 电报局（可进，带室内）
+ 殡仪馆 / 治安官办公室 / 澡堂（关着，门上钉"TO BE WRITTEN"纸条）+ 巷口木栅栏 + 栈道小物。

blender --background --python tools/blender/build_town.py -- [--render] [--samples N] [--export path.gltf]
默认导出到 Game/Assets/_MercyCreek/Art/Town/Town.gltf（根节点 "Town"）。
招牌 / 纸条 / 告示 / 钟面贴图先跑 tools/gen_street_signs.py（Pillow）生成到 art/source/_derived/street/。

坐标与 build_saloon.py / build_street.py 相同：X 向东，Y 向北（酒馆前墙外表面 y=-0.2，室内 +Y），Z 向上，米。
Unity 里根节点绕 Y 转 180°，于是 Unity (x, y, z) = Blender (x, z, y)。
命名约定：名字以 "NoCol_" 开头的网格在 Unity 里不加碰撞体（纸、招牌、小杂物）；其余都加 MeshCollider。
需要被脚本按名字找到的节点（Telegraph_Tape、TBD_*）是空节点，网格挂在它下面（NoCol_ 前缀）。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy, bmesh
from mathutils import Vector, Matrix
import mc_common as mc
from mc_common import T, R, S

argv = mc.args()
RENDER = "--render" in argv
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 64
EXPORT = argv[argv.index("--export") + 1] if "--export" in argv else str(mc.ART / "Town" / "Town.gltf")
SIGNS = mc.SRC / "_derived" / "street"

FRONT = -0.2             # 北侧一排门脸外表面（与酒馆前墙外表面齐平）
WALK_Y = -2.4            # 栈道外沿（街面从这里开始）
WALK_H = 0.25            # 栈道面高度（与 Saloon.glb 的 BoardwalkFront 一致）
GROUND = -0.08           # StreetBackdrop 的地面高度

sc = mc.reset()
C_EXP = bpy.data.collections.new("Town"); sc.collection.children.link(C_EXP)
C_REV = bpy.data.collections.new("Review"); sc.collection.children.link(C_REV)
ROOT_OBJ = mc.empty("Town", collection=C_EXP)

# ---------------------------------------------------------------- 材质（与 build_street.py 同名同参数 → 共用同一批派生贴图）
M = {
    "cream":   mc.pbr("SidingCream", "WoodSiding009", tile=2.4),
    "red":     mc.pbr("SidingRed", "WoodSiding002", tile=2.4, tint=(0.9, 0.85, 0.8)),
    "brown":   mc.pbr("SidingBrown", "WoodSiding004", tile=2.4),
    "grey":    mc.pbr("SidingGrey", "WoodSiding010", tile=2.4, tint=(1.1, 1.0, 0.9)),
    "white":   mc.pbr("Whitewash", "PaintedWood009C", tile=2.0),
    "trim":    mc.pbr("TrimCream", "PaintedWood009C", tile=1.5, tint=(1.0, 0.95, 0.85)),
    "green":   mc.pbr("TrimGreen", "PaintedWood009C", tile=1.5, tint=(0.38, 0.5, 0.42)),
    "dark":    mc.pbr("TrimDark", "Planks012", tile=1.5, tint=(0.55, 0.5, 0.45)),
    "planks":  mc.pbr("Boardwalk", "Planks012", tile=2.0),
    "roof":    mc.pbr("Roof", "WoodSiding010", tile=1.5, tint=(0.55, 0.5, 0.45)),
    "barrel":  mc.pbr("BarrelWood", "Wood066", tile=0.8),
    "iron":    mc.flat("Iron", (0.08, 0.07, 0.065), rough=0.55, metal=0.8),
    "curtain": mc.pbr("Curtain", "Fabric040", tile=0.8, tint=(0.9, 0.8, 0.7)),
    "water":   mc.flat("TroughWater", (0.03, 0.035, 0.03), rough=0.03),
    # 本脚本新增
    "saloon":  mc.pbr("SidingSaloon", "WoodSiding013", tile=3.0, tint=(0.95, 0.88, 0.8)),   # 与酒馆 Room4Under 同一种护墙板
    "black":   mc.pbr("TrimBlack", "PaintedWood009C", tile=1.5, tint=(0.16, 0.15, 0.14)),
    "oxblood": mc.pbr("TrimOxblood", "PaintedWood009C", tile=1.5, tint=(0.42, 0.16, 0.12)),
    "drape":   mc.pbr("DrapeBlack", "Fabric040", tile=0.8, tint=(0.18, 0.16, 0.16)),
    "blind":   mc.pbr("BlindGreen", "Fabric040", tile=0.8, tint=(0.35, 0.42, 0.33)),
    "glass":   mc.flat("GlassDirty", (0.07, 0.075, 0.068), rough=0.06, alpha=0.32),
    "frosted": mc.flat("GlassFrosted", (0.6, 0.6, 0.56), rough=0.6, alpha=0.8),
    "pole":    mc.pbr("PoleWood", "Wood066", tile=1.2, tint=(0.5, 0.56, 0.7), rough_mul=1.6, normal=0.6),   # 偏蓝的乘色把橙色压成旧灰木
    "void":    mc.flat("InteriorDark", (0.025, 0.022, 0.02), rough=0.9),
    # 电报局室内
    "floor":   mc.pbr("TelFloor", "WoodFloor041", tile=2.0, tint=(0.75, 0.62, 0.5)),
    "paint":   mc.pbr("TelWallPaint", "PaintedWood009C", tile=2.0, tint=(0.86, 0.84, 0.74)),
    "wains":   mc.pbr("TelWainscot", "Planks037A", tile=2.0, tint=(0.55, 0.36, 0.22)),
    "ceil":    mc.pbr("TelCeiling", "Planks021", tile=2.0, tint=(0.62, 0.5, 0.38)),
    "wood":    mc.pbr("TelCounterWood", "WoodFloor043", tile=1.2, tint=(0.45, 0.3, 0.2)),
    "brass":   mc.flat("Brass", (0.75, 0.55, 0.25), rough=0.3, metal=1.0),
    "blackiron": mc.flat("StoveIron", (0.035, 0.033, 0.032), rough=0.6, metal=0.7),
    "ebonite": mc.flat("Ebonite", (0.02, 0.018, 0.016), rough=0.35),
    "zinc":    mc.flat("Zinc", (0.42, 0.42, 0.4), rough=0.45, metal=0.9),
    "paper":   mc.pbr("TapePaper", "Paper005", tile=0.4, tint=(0.95, 0.9, 0.78), normal=0.3),
    "wicker":  mc.pbr("Wicker", "Fabric040", tile=0.3, tint=(0.62, 0.48, 0.3)),
    "lampglass": mc.flat("LampGlass", (0.9, 0.9, 0.85), rough=0.05, alpha=0.3),
    "shade":   mc.flat("LampShade", (0.88, 0.85, 0.76), rough=0.4),
}


def img(name, file, rough=0.75):
    return mc.image_mat(name, SIGNS / file, rough=rough)


SIGN = {n: img(f"Sign_{n}", f"sign_{n}.jpg") for n in ("saloon", "telegraph", "undertaker", "sheriff", "baths")}
NOTE_MAT = img("Note_TBD", "note_tbd.jpg", rough=0.85)
NOTICE = {n: img(f"Notice_{n}", f"notice_{n}.jpg", rough=0.85) for n in ("rates", "hours", "line")}
CLOCK_MAT = img("ClockFace", "clock_face.jpg", rough=0.35)


# ---------------------------------------------------------------- 工具
def swap_uv(part, faces):
    for f in faces:
        for lp in f.loops:
            u, v = lp[part.uv].uv; lp[part.uv].uv = (v, u)


# 木板类材质的贴图木纹是横向的：立着的细长件（柱子、栅栏板、墙角板）要把 UV 转 90°，木纹才顺着竖向
VERT_GRAIN = {M[k].name for k in ("dark", "planks", "black", "wood", "trim", "green", "oxblood", "pole")}


def bx(part, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    dx, dy, dz = abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)
    faces = part.box((dx, dy, dz), mat, xf=T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), bevel=bevel)
    if mat.name in VERT_GRAIN and dz > 2.5 * max(dx, dy):
        swap_uv(part, faces)
    return faces


def obj(part, name, parent=None, origin=None):
    """origin 给定时把网格平移到以 origin 为原点（Unity 里 transform.position 就是这个点）。"""
    if origin is not None:
        bmesh.ops.translate(part.bm, vec=-Vector(origin), verts=part.bm.verts)
    return part.finish(name, parent=parent or ROOT_OBJ, collection=C_EXP, location=origin or (0, 0, 0))


# 立面坐标系：face = (轴, 平面坐标, 朝外符号)。u 沿墙（轴 'y' 时 u=x，轴 'x' 时 u=y），n = 离墙面向外的距离（负 = 往墙里）
def fpt(face, u, n, z):
    ax, pl, sg = face
    return Vector((u, pl + sg * n, z)) if ax == "y" else Vector((pl + sg * n, u, z))


def fbox(p, face, u0, u1, n0, n1, z0, z1, mat, bevel=0.0):
    ax, pl, sg = face
    a, b = pl + sg * n0, pl + sg * n1
    if ax == "y":
        return bx(p, u0, u1, a, b, z0, z1, mat, bevel)
    return bx(p, a, b, u0, u1, z0, z1, mat, bevel)


def right_sign(face):
    ax, _, sg = face
    return -sg if ax == "y" else sg


def fquad(p, face, uc, n, zc, w, h, mat, rot=0.0):
    """贴在立面上、朝外的整图四边形（招牌 / 纸）。rot = 绕墙面法线的倾斜（度）。"""
    rs = right_sign(face)
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for du, dz in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        ru, rz = du * c - dz * s, du * s + dz * c
        pts.append(tuple(fpt(face, uc + rs * ru, n, zc + rz)))
    return p.quad(pts, mat)


def slab(p, face, u0, u1, n0, n1, z0, z1, holes, mat):
    """开洞的墙板：holes = [(a, b, zb, zt)]，按列切分，每列可有多个洞。"""
    us = sorted({u0, u1, *[min(max(h[i], u0), u1) for h in holes for i in (0, 1)]})
    for a, b in zip(us, us[1:]):
        if b - a < 1e-4:
            continue
        hs = sorted((h for h in holes if h[0] <= a + 1e-6 and b <= h[1] + 1e-6), key=lambda h: h[2])
        z = z0
        for h in hs:
            if h[2] > z + 1e-4: fbox(p, face, a, b, n0, n1, z, min(h[2], z1), mat)
            z = max(z, h[3])
        if z < z1 - 1e-4: fbox(p, face, a, b, n0, n1, z, z1, mat)


def casing(p, face, a, b, zb, zt, mat, n0=0.0, n1=0.03, w=0.12, gap=0.0, sill=True, zfloor=None):
    """洞口外框：两侧立板 + 楣板（带滴水线）+ 窗台。gap = 内沿离洞口边的距离。"""
    jb = (zb - gap) if sill else (zfloor if zfloor is not None else zb)
    fbox(p, face, a - gap - w, a - gap, n0, n1, jb, zt + gap, mat)
    fbox(p, face, b + gap, b + gap + w, n0, n1, jb, zt + gap, mat)
    fbox(p, face, a - gap - w - 0.03, b + gap + w + 0.03, n0, n1 + 0.005, zt + gap, zt + gap + w * 1.15, mat)
    fbox(p, face, a - gap - w - 0.06, b + gap + w + 0.06, n0, n1 + 0.045, zt + gap + w * 1.15, zt + gap + w * 1.15 + 0.035, mat)
    if sill:
        fbox(p, face, a - gap - w - 0.05, b + gap + w + 0.05, n0, n1 + 0.05, zb - gap - 0.055, zb - gap, mat)


def hashf(*a):
    s = math.sin(sum(v * k for v, k in zip(a, (12.9898, 78.233, 37.719, 4.581)))) * 43758.5453
    return s - math.floor(s)


def ribbon(p, pts, width, mat, side=Vector((1, 0, 0))):
    """沿折线的扁带（纸带）。宽度方向尽量贴近 side。"""
    bm, uvl = p.bm, p.uv
    tile = mat.get("tile", 1.0); mi = p._mi(mat)
    pts = [Vector(q) for q in pts]
    L = [0.0]
    for i in range(1, len(pts)): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    rows = []
    for i, q in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        s = (side - side.dot(t) * t).normalized()
        rows.append((bm.verts.new(q - s * width / 2), bm.verts.new(q + s * width / 2)))
    for i in range(len(rows) - 1):
        f = bm.faces.new([rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]])
        f.material_index = mi; f.smooth = True
        for lp, uv in zip(f.loops, ((L[i], 0), (L[i + 1], 0), (L[i + 1], width), (L[i], width))):
            lp[uvl].uv = (uv[0] / tile, uv[1] / tile)


def disc(p, face, uc, n, zc, r, mat, seg=32):
    """朝外的圆盘，平面 UV 0..1（表盘）。"""
    bm, uvl = p.bm, p.uv; mi = p._mi(mat); rs = right_sign(face)
    c = bm.verts.new(fpt(face, uc, n, zc))
    ring = [bm.verts.new(fpt(face, uc + rs * r * math.cos(2 * math.pi * i / seg), n, zc + r * math.sin(2 * math.pi * i / seg)))
            for i in range(seg)]
    for i in range(seg):
        f = bm.faces.new([c, ring[i], ring[(i + 1) % seg]]); f.material_index = mi
        for lp in f.loops:
            q = lp.vert.co
            du = (q.x - c.co.x) if face[0] == "y" else (q.y - c.co.y)
            lp[uvl].uv = (0.5 + rs * du / (2 * r), 0.5 + (q.z - c.co.z) / (2 * r))


def cyl(p, x, y, z0, z1, r, mat, seg=12, xf=None):
    m = (xf or Matrix.Identity(4)) @ T(x, y, z0)
    return p.lathe([(0, 0, 0), (0, r, r), (z1 - z0, r, r), (z1 - z0, 0, 0)], mat, seg=seg, xf=m)


def barrel(p, x, y, z=0.0, h=0.9, r=0.3, open_top=False):
    prof = [(0, 0, 0)] + [(h * t, r * (0.86 + 0.14 * math.sin(math.pi * t)), r * (0.86 + 0.14 * math.sin(math.pi * t)))
                         for t in [i / 8 for i in range(9)]]
    if open_top:
        ri = r * 0.86 - 0.025
        prof += [(h, ri, ri), (h * 0.85, ri, ri), (h * 0.85, 0, 0)]
    else:
        prof += [(h, 0, 0)]
    p.lathe(prof, M["barrel"], seg=16, xf=T(x, y, z))
    for t in (0.12, 0.35, 0.65, 0.88):
        rr = r * (0.86 + 0.14 * math.sin(math.pi * t)) + 0.006
        p.lathe([(h * t - 0.025, rr, rr), (h * t + 0.025, rr, rr)], M["iron"], seg=16, xf=T(x, y, z), cap=False)


# 立面上的常用件 ------------------------------------------------------------
FF = ("y", FRONT, -1)       # 北侧门脸（朝 -Y）


def cornice(p, x0, x1, hf, mat, face=FF):
    """假立面顶的檐口 + 托架 + 腰线（同 build_street.facade，方向朝 -Y）。"""
    fbox(p, face, x0 - 0.12, x1 + 0.12, -0.2, 0.32, hf, hf + 0.12, mat)
    fbox(p, face, x0 - 0.05, x1 + 0.05, 0, 0.2, hf - 0.25, hf, mat)
    n = max(3, int((x1 - x0) / 0.9))
    for i in range(n + 1):
        xx = x0 + 0.15 + (x1 - x0 - 0.3) * i / n
        fbox(p, face, xx - 0.05, xx + 0.05, 0.2, 0.3, hf - 0.32, hf, mat)


def corner_boards(p, x0, x1, z0, z1, mat, face=FF):
    for sx in (x0, x1 - 0.14):
        fbox(p, face, sx, sx + 0.14, 0, 0.05, z0, z1, mat)


def sign_board(p, psign, x, z, w, h, name, frame, face=FF):
    fbox(p, face, x - w / 2 - 0.08, x + w / 2 + 0.08, 0, 0.08, z - h / 2 - 0.08, z + h / 2 + 0.08, frame)
    fquad(psign, face, x, 0.085, z, w, h, SIGN[name])


def awning(p, x0, x1, z, posts, slope=0.32, mat_post=None):
    """朝街的单坡雨棚：靠墙高、外沿低；外沿横梁 + 立柱落在栈道上。"""
    mp = mat_post or M["trim"]
    depth = (FRONT - WALK_Y) + 0.05
    a = math.atan2(slope, depth); L = depth / math.cos(a) + 0.15
    p.box((x1 - x0 + 0.2, L, 0.06), M["roof"], xf=T((x0 + x1) / 2, (FRONT + WALK_Y) / 2 - 0.03, z + slope / 2 + 0.06) @ R("X", math.degrees(a)))
    bx(p, x0, x1, WALK_Y + 0.08, WALK_Y + 0.22, z - 0.2, z + 0.03, mp)                     # 外沿横梁
    bx(p, x0, x1, FRONT - 0.1, FRONT, z + slope - 0.12, z + slope + 0.04, mp)               # 墙上的托梁
    for px in posts:
        bx(p, px - 0.07, px + 0.07, WALK_Y + 0.08, WALK_Y + 0.22, WALK_H, z - 0.2, mp)
        bx(p, px - 0.1, px + 0.1, WALK_Y + 0.05, WALK_Y + 0.25, WALK_H, WALK_H + 0.12, mp)
        for sg in (-1, 1):                                                               # 斜撑
            p.box((0.05, 0.05, 0.5), mp, xf=T(px + sg * 0.16, WALK_Y + 0.15, z - 0.36) @ R("Y", sg * 45))


def gable_roof(p, x0, x1, y0, y1, h, ridge, wall_mat, eave=0.3, back_gable=True):
    """沿 Y 的双坡屋顶（屋脊在 x 中线），檐口落在墙顶 h。"""
    w = x1 - x0; cx = (x0 + x1) / 2
    a = math.atan2(ridge, w / 2)
    for sg in (-1, 1):
        L = (w / 2 + eave) / math.cos(a) + 0.06
        # 板的中心沿坡线外移 eave/2，再沿法线抬 0.04 让板底贴在坡线上
        d = Vector((sg * math.cos(a), 0, -math.sin(a)))
        nrm = Vector((sg * math.sin(a), 0, math.cos(a)))
        top = Vector((cx, 0, h + ridge)) - d * 0.06
        c = top + d * (L / 2) + nrm * 0.045
        p.box((L, y1 - y0, 0.09), M["roof"], xf=T(c.x, (y0 + y1) / 2, c.z) @ R("Y", sg * math.degrees(a)))
    bx(p, cx - 0.12, cx + 0.12, y0, y1, h + ridge + 0.02, h + ridge + 0.12, M["roof"])     # 屋脊盖板
    if back_gable:
        yb = y1 - 0.3
        p.poly_extrude([(x0, h - 0.01), (x1, h - 0.01), (cx, h + ridge)], 0.2, wall_mat, xf=T(0, yb, 0) @ R("X", 90))


def window_open(p, pglass, face, a, b, zb, zt, t=0.2, ext=None, intr=None, closed=False, drape=None):
    """墙上的真窗洞：内衬板 + 中间的窗扇（中梃 + 横棂）+ 玻璃 + 内外窗套。closed=True 时玻璃后面挂帘子、再后面是暗底。"""
    ext = ext or M["trim"]
    lin = 0.015
    for u0, u1 in ((a, a + lin), (b - lin, b)):
        fbox(p, face, u0, u1, -t, 0, zb, zt, ext)
    fbox(p, face, a, b, -t, 0, zt - lin, zt, ext)
    fbox(p, face, a, b, -t, 0.0, zb, zb + lin, ext)
    m = -t / 2
    fr = 0.045
    for u0, u1 in ((a + lin, a + lin + fr), (b - lin - fr, b - lin)):
        fbox(p, face, u0, u1, m - 0.025, m + 0.025, zb + lin, zt - lin, ext)
    fbox(p, face, a + lin, b - lin, m - 0.025, m + 0.025, zt - lin - fr, zt - lin, ext)
    fbox(p, face, a + lin, b - lin, m - 0.025, m + 0.025, zb + lin, zb + lin + fr * 1.4, ext)
    mid = (a + b) / 2
    fbox(p, face, mid - 0.02, mid + 0.02, m - 0.02, m + 0.02, zb + lin, zt - lin, ext)
    zm = (zb + zt) / 2
    fbox(p, face, a + lin, b - lin, m - 0.02, m + 0.02, zm - 0.03, zm + 0.03, ext)
    fbox(pglass, face, a + lin, b - lin, m - 0.003, m + 0.003, zb + lin, zt - lin, M["glass"])
    casing(p, face, a, b, zb, zt, ext, 0, 0.03, w=0.11)
    if intr:
        ax, pl, sg = face
        inner = (ax, pl - sg * t, -sg)
        casing(p, inner, a, b, zb, zt, intr, 0, 0.02, w=0.09)
    if closed:
        dm = drape or M["curtain"]
        fbox(p, face, a + lin, b - lin, -t + 0.005, -t + 0.012, zb + lin, zt - lin, M["void"])
        cw = (b - a) * 0.3
        fbox(p, face, a + lin, a + lin + cw, m - 0.05, m - 0.04, zb + 0.04, zt - 0.03, dm)
        fbox(p, face, b - lin - cw, b - lin, m - 0.05, m - 0.04, zb + 0.04, zt - 0.03, dm)
        fbox(p, face, a + lin, b - lin, m - 0.06, m - 0.05, zt - (zt - zb) * 0.22, zt - 0.03, dm)


# ================================================================ 1. 酒馆外壳（不改 build_saloon.py，紧贴外墙外表面另做）
# 酒馆：前墙 y∈[-0.2,0]，侧墙 x∈±[7,7.2]，后墙 y∈[10,10.2]，墙高 6.4、天花板 6.4..6.6；4 号房 x∈[-2.2,2.2] y∈[10.2,13.4]
SX, SBACK, SH = 7.2, 10.2, 6.6
CL = 0.025                                    # 护板厚度
FF_HI = 8.8                                   # 假立面顶
DOOR = (-0.9, 0.9, 0.0, 2.7)
FRONT_WIN = [(-5.4, -2.6, 0.9, 2.8), (2.6, 5.4, 0.9, 2.8), (-5.0, -3.0, 4.0, 5.6), (3.0, 5.0, 4.0, 5.6)]
LEFT_WIN = [(1.2, 2.6, 1.2, 2.6)]
RIGHT_WIN = [(3.0, 4.6, 0.9, 2.6), (5.6, 7.2, 4.0, 5.4)]
BACK_DOOR = (5.6, 6.6, 0.0, 2.3)
R4 = (-2.2, 2.2, 13.4)
R4_WIN = (-0.6, 0.6, 4.1, 5.3)


def grow(o, d=0.08, bottom=True):
    """酒馆窗框（window_frame）在洞口外圈各占 8 cm：护板的洞开到窗框外沿，窗框自己把缝填上。"""
    return (o[0] - d, o[1] + d, o[2] - (d if bottom else 0.3), o[3] + d)


p = mc.Part([M["saloon"]])
sal = M["saloon"]
F_FRONT = ("y", -0.2, -1); F_LEFT = ("x", -SX, -1); F_RIGHT = ("x", SX, 1); F_BACK = ("y", SBACK, 1)
slab(p, F_FRONT, -SX - CL, SX + CL, 0, CL, 0.0, FF_HI, [DOOR, *[grow(o) for o in FRONT_WIN]], sal)
slab(p, F_LEFT, -0.2, SBACK, 0, CL, GROUND - 0.04, SH, [grow(o) for o in LEFT_WIN], sal)
slab(p, F_RIGHT, -0.2, SBACK, 0, CL, GROUND - 0.04, SH, [grow(o) for o in RIGHT_WIN], sal)
slab(p, F_BACK, -SX - CL, SX + CL, 0, CL, GROUND - 0.04, SH, [(R4[0], R4[1], -1, 6.4), grow(BACK_DOOR, bottom=False)], sal)
# 4 号房外面
slab(p, ("x", R4[0], -1), SBACK, R4[2] + CL, 0, CL, GROUND - 0.04, 6.4, [], sal)
slab(p, ("x", R4[1], 1), SBACK, R4[2] + CL, 0, CL, GROUND - 0.04, 6.4, [], sal)
slab(p, ("y", R4[2], 1), R4[0] - CL, R4[1] + CL, 0, CL, GROUND - 0.04, 6.4, [grow(R4_WIN)], sal)
bx(p, R4[0] - 0.12, R4[1] + 0.12, SBACK, R4[2] + 0.15, 6.4, 6.47, M["roof"])            # 4 号房平顶的盖板
# 窗套 / 门套（压在酒馆自带窗框外沿 2 cm 上，内沿退 6 cm，没有共面）
tr = M["dark"]
for o in FRONT_WIN: casing(p, F_FRONT, *o, tr, CL, CL + 0.035, gap=0.06)
for o in LEFT_WIN: casing(p, F_LEFT, *o, tr, CL, CL + 0.035, gap=0.06)
for o in RIGHT_WIN: casing(p, F_RIGHT, *o, tr, CL, CL + 0.035, gap=0.06)
casing(p, F_BACK, *BACK_DOOR, tr, CL, CL + 0.035, gap=0.06, sill=False, zfloor=GROUND - 0.04)
casing(p, ("y", R4[2], 1), *R4_WIN, tr, CL, CL + 0.035, gap=0.06)
casing(p, F_FRONT, *DOOR, tr, CL, CL + 0.04, w=0.16, sill=False, zfloor=WALK_H)
# 前门洞口内衬（只在墙厚范围内，不进室内）
for u0, u1 in ((DOOR[0], DOOR[0] + 0.02), (DOOR[1] - 0.02, DOOR[1])):
    fbox(p, F_FRONT, u0, u1, -0.2 + 0.002, CL, WALK_H, DOOR[3], tr)
fbox(p, F_FRONT, DOOR[0], DOOR[1], -0.2 + 0.002, CL, DOOR[3] - 0.02, DOOR[3], tr)
# 墙角竖条
for x, y in ((-SX - CL, -0.2 - CL), (SX + CL, -0.2 - CL), (-SX - CL, SBACK + CL), (SX + CL, SBACK + CL)):
    sx, sy = (1 if x < 0 else -1), (1 if y < 0 else -1)
    bx(p, x - sx * 0.03, x + sx * 0.13, y - sy * 0.03, y + sy * 0.13, GROUND - 0.04 if y > 0 else 0.0, SH if y > 0 else FF_HI, tr)
# 墙脚踢板（两侧 + 后面）
for face, u0, u1 in ((F_LEFT, -0.2, SBACK), (F_RIGHT, -0.2, SBACK)):
    fbox(p, face, u0, u1, CL, CL + 0.03, GROUND - 0.04, 0.22, tr)
# 二楼腰线：一圈横向束带板（前 / 侧），让 6.6 m 高的墙不那么空
for face, u0, u1, holes in ((F_FRONT, -SX - CL, SX + CL, []), (F_LEFT, -0.2, SBACK, []), (F_RIGHT, -0.2, SBACK, [])):
    fbox(p, face, u0, u1, CL, CL + 0.04, 3.32, 3.48, tr)
obj(p, "Saloon_Cladding")

# 假立面：前墙护板已经一直做到 8.8，这里补背板（藏在屋顶上方、天花板以上，不进室内）+ 檐口 + 招牌
p = mc.Part([sal]); ps = mc.Part([SIGN["saloon"]])
bx(p, -SX - CL, SX + CL, -0.2, 0.0, 6.4, FF_HI, sal)
cornice(p, -SX - CL, SX + CL, FF_HI, M["dark"], face=F_FRONT)
fbox(p, F_FRONT, -2.6, 2.6, -0.2, 0.06, FF_HI + 0.12, FF_HI + 0.75, sal)                 # 中间升起的山花
fbox(p, F_FRONT, -2.72, 2.72, -0.2, 0.28, FF_HI + 0.75, FF_HI + 0.86, M["dark"])
fbox(p, F_FRONT, -2.6, -2.48, 0.06, 0.1, FF_HI + 0.12, FF_HI + 0.75, M["dark"])
fbox(p, F_FRONT, 2.48, 2.6, 0.06, 0.1, FF_HI + 0.12, FF_HI + 0.75, M["dark"])
sign_board(p, ps, 0.0, 7.55, 10.6, 1.49, "saloon", M["dark"], face=("y", -0.2 - CL, -1))
obj(p, "Saloon_FalseFront"); obj(ps, "NoCol_Saloon_Sign")

# 坡屋顶：屋脊沿 Y，檐口压在 6.6 的护板顶上，屋脊低于假立面顶
p = mc.Part([M["roof"]])
gable_roof(p, -SX - CL, SX + CL, 0.0, SBACK + CL + 0.3, SH, 1.75, sal)
obj(p, "Saloon_Roof")

# 雨棚柱：酒馆自带的雨棚是 y∈[-2.6,0]、z 3.7..3.8 的平板，这里补外沿横梁和立柱
p = mc.Part([M["dark"]])
bx(p, -8.0, 8.0, -2.52, -2.36, 3.52, 3.7, M["dark"])
bx(p, -8.0, 8.0, -2.62, -2.56, 3.62, 3.86, M["dark"])                                    # 雨棚封檐板
for px in (-7.8, -1.75, 1.75, 7.8):
    bx(p, px - 0.075, px + 0.075, -2.52, -2.37, WALK_H, 3.52, M["dark"], bevel=0.01)
    bx(p, px - 0.11, px + 0.11, -2.55, -2.33, WALK_H, WALK_H + 0.14, M["dark"])
    for sg in (-1, 1):
        p.box((0.06, 0.06, 0.55), M["dark"], xf=T(px + sg * 0.18, -2.445, 3.32) @ R("Y", sg * 45))
obj(p, "Saloon_AwningPosts")


# ================================================================ 2. 北侧一排
# 栈道：x∈[-24,-8] 和 [8,23]（酒馆自带 [-8,8]），y∈[-2.4,-0.2]，面高 0.25
p = mc.Part([M["planks"]])
for x0, x1 in ((-24.0, -8.0), (8.0, 23.0)):
    f = bx(p, x0, x1, WALK_Y, FRONT, GROUND - 0.04, WALK_H, M["planks"]); swap_uv(p, f)
    bx(p, x0, x1, WALK_Y - 0.05, WALK_Y, GROUND - 0.04, WALK_H - 0.04, M["dark"])          # 前沿挡板
    for xx in [x0 + 0.3 + i * 1.6 for i in range(int((x1 - x0) / 1.6) + 1)]:
        if xx < x1 - 0.1:
            bx(p, xx - 0.07, xx + 0.07, WALK_Y - 0.06, WALK_Y + 0.06, GROUND - 0.06, WALK_H - 0.02, M["dark"])
obj(p, "Boardwalk_North")


def closed_building(key, x0, x1, depth, h, hf, siding, trimm, door_x, windows, sign_kw, awn=None, drape=None,
                    door_mat=None, ridge=1.2, extra=None):
    """关着的门脸：开窗的前墙（真洞口 + 帘子 + 暗底）+ 实心主体 + 假立面 + 坡屋顶 + 关着的门 + 手写纸条。"""
    p = mc.Part([siding]); pg = mc.Part([M["glass"]]); ps = mc.Part([SIGN[sign_kw["name"]]])
    dw, dh = 1.1, 2.4
    dz = WALK_H
    door = (door_x - dw / 2, door_x + dw / 2, dz, dz + dh)
    slab(p, FF, x0, x1, -0.2, 0, GROUND - 0.04, hf, [door, *windows], siding)
    bx(p, x0, x1, 0.0, depth, GROUND - 0.04, h, siding)
    corner_boards(p, x0, x1, GROUND - 0.04, hf, trimm)
    cornice(p, x0, x1, hf, trimm)
    gable_roof(p, x0, x1, 0.0, depth + 0.3, h, min(ridge, hf - h - 0.2), siding)
    for o in windows:
        window_open(p, pg, FF, *o, ext=trimm, closed=True, drape=drape)
    # 门：内衬 + 退进 6 cm 的四镶板门（上半玻璃，后面拉着帘）+ 门套 + 门把手
    lin = 0.02
    for u0, u1 in ((door[0], door[0] + lin), (door[1] - lin, door[1])):
        fbox(p, FF, u0, u1, -0.2, 0, dz, door[3], trimm)
    fbox(p, FF, door[0], door[1], -0.2, 0, door[3] - lin, door[3], trimm)
    dmat = door_mat or M["dark"]
    a, b = door[0] + lin, door[1] - lin
    gz0, gz1 = dz + 1.45, door[3] - 0.2
    fbox(p, FF, a, b, -0.11, -0.06, dz, gz0, dmat)                                        # 下半门板（含锁档）
    fbox(p, FF, a, a + 0.12, -0.11, -0.06, gz0, door[3] - lin, dmat)                      # 上半：两边梃 + 上冒头
    fbox(p, FF, b - 0.12, b, -0.11, -0.06, gz0, door[3] - lin, dmat)
    fbox(p, FF, a + 0.12, b - 0.12, -0.11, -0.06, gz1, door[3] - lin, dmat)
    for (u0, u1) in ((a + 0.1, (a + b) / 2 - 0.05), ((a + b) / 2 + 0.05, b - 0.1)):
        fbox(p, FF, u0, u1, -0.06, -0.045, dz + 0.15, dz + 1.0, dmat, bevel=0.01)           # 下镶板
    fbox(p, FF, a + 0.12, b - 0.12, -0.11, -0.104, gz0, gz1, M["void"])                   # 门玻璃后面：暗底 + 半拉的帘
    fbox(p, FF, a + 0.12, b - 0.12, -0.1, -0.096, gz0 + (gz1 - gz0) * 0.4, gz1, drape or M["curtain"])
    fbox(pg, FF, a + 0.12, b - 0.12, -0.085, -0.081, gz0, gz1, M["glass"])
    for u0, u1, z0, z1 in ((a + 0.1, a + 0.12, gz0, gz1), (b - 0.12, b - 0.1, gz0, gz1), (a + 0.1, b - 0.1, gz0 - 0.02, gz0),
                           (a + 0.1, b - 0.1, gz1, gz1 + 0.02)):
        fbox(p, FF, u0, u1, -0.06, -0.045, z0, z1, dmat)                                   # 压条
    kx = b - 0.1
    p.sphere(0.03, M["brass"], xf=T(kx, FRONT + 0.06 - 0.035, dz + 1.02), seg=10, rings=6)
    fbox(p, FF, kx - 0.025, kx + 0.025, -0.06, -0.05, dz + 0.9, dz + 1.12, M["brass"])
    casing(p, FF, door[0], door[1], dz, door[3], trimm, 0, 0.035, w=0.13, sill=False, zfloor=dz)
    sign_board(p, ps, sign_kw["x"], sign_kw["z"], sign_kw["w"], sign_kw["h"], sign_kw["name"], trimm)
    if awn: awning(p, x0, x1, *awn, mat_post=trimm)
    if extra: extra(p)
    obj(p, key); obj(pg, f"{key}_Glass"); obj(ps, f"NoCol_Sign_{key}")
    # 门上的纸条：空节点 TBD_<key> 在纸面中心，网格 NoCol_TBD_<key> 挂在下面
    yy = FRONT + 0.06 - 0.002                                                           # 门板外表面前 2 mm
    zc = dz + 1.24                                                                       # 锁档上，齐眼
    cx = (a + b) / 2 - 0.06
    tbd = mc.empty(f"TBD_{key}", parent=ROOT_OBJ, location=(cx, yy, zc), collection=C_EXP)
    pn = mc.Part([NOTE_MAT])
    fquad(pn, ("y", 0.0, -1), 0.0, 0.0, 0.0, 0.26, 0.195, NOTE_MAT, rot=-4)
    pn.lathe([(0, 0, 0), (0, 0.007, 0.007), (0.006, 0.007, 0.007), (0.006, 0, 0)], M["iron"], seg=8,
             xf=T(0.007, 0.0, 0.085) @ R("X", 90))                                    # 钉子头
    pn.lathe([(0, 0, 0), (0, 0.006, 0.006), (0.006, 0.006, 0.006), (0.006, 0, 0)], M["iron"], seg=8,
             xf=T(-0.01, 0.0, -0.085) @ R("X", 90))
    pn.finish(f"NoCol_TBD_{key}", parent=tbd, collection=C_EXP)
    return tbd


# --- 殡仪馆：灰色旧板 + 黑色饰条，黑帘；门边立着一口松木棺材
def coffin_extra(p):
    pts = [(-0.2, 0.0), (0.2, 0.0), (0.3, 1.45), (0.24, 1.9), (-0.24, 1.9), (-0.3, 1.45)]
    p.poly_extrude(pts, 0.32, M["planks"], xf=T(-21.45, FRONT - 0.6, WALK_H + 0.02) @ R("X", 82) @ T(0, 0, -0.32))
    pts2 = [(-0.21, 0.0), (0.21, 0.0), (0.31, 1.45), (0.25, 1.91), (-0.25, 1.91), (-0.31, 1.45)]
    p.poly_extrude(pts2, 0.04, M["dark"], xf=T(-21.45, FRONT - 0.6, WALK_H + 0.02) @ R("X", 82) @ T(0, -0.005, 0.0))


closed_building("Undertaker", -24.0, -16.5, 9.0, 4.4, 6.3, M["grey"], M["black"], -19.9,
                [(-23.2, -21.95, 1.0, 2.7), (-18.5, -17.25, 1.0, 2.7)],
                dict(name="undertaker", x=-20.25, z=5.25, w=5.4, h=1.18), awn=None, drape=M["drape"], door_mat=M["black"],
                extra=coffin_extra)


# --- 治安官：棕色板，铁窗栏，雨棚
def sheriff_extra(p):
    for k in range(1, 7):
        xx = 9.95 + 1.2 * k / 7
        fbox(p, FF, xx - 0.012, xx + 0.012, 0.05, 0.075, 1.0, 2.65, M["iron"])
    for zz in (1.05, 2.6):
        fbox(p, FF, 9.8, 11.3, 0.045, 0.08, zz - 0.02, zz + 0.02, M["iron"])


closed_building("Sheriff", 9.0, 15.0, 8.0, 4.2, 5.7, M["brown"], M["dark"], 12.9,
                [(9.95, 11.15, 1.05, 2.6)],
                dict(name="sheriff", x=12.0, z=4.75, w=4.8, h=1.05), awn=(3.2, [9.2, 11.6, 14.8]),
                drape=M["blind"], door_mat=M["oxblood"], extra=sheriff_extra)


# --- 澡堂：奶油色板 + 绿饰条，磨砂玻璃；屋顶上一根铁烟囱（热水炉）
def baths_extra(p):
    cyl(p, 21.4, 6.0, 4.35, 6.9, 0.13, M["blackiron"], seg=14)
    p.lathe([(0, 0, 0), (0, 0.24, 0.24), (0.06, 0.16, 0.16), (0.12, 0, 0)], M["blackiron"], seg=14, xf=T(21.4, 6.0, 6.9))
    p.lathe([(0, 0.2, 0.2), (0.08, 0.2, 0.2)], M["blackiron"], seg=14, xf=T(21.4, 6.0, 4.58), cap=True)


closed_building("Baths", 16.5, 23.0, 8.0, 3.9, 5.3, M["cream"], M["green"], 18.1,
                [(19.45, 20.7, 1.0, 2.55), (21.35, 22.6, 1.0, 2.55)],
                dict(name="baths", x=19.75, z=4.5, w=4.6, h=1.0), awn=(3.15, [16.7, 19.2, 22.8]),
                drape=M["frosted"], door_mat=M["green"], extra=baths_extra)


# ================================================================ 电报局（可进）
TX0, TX1, TY1 = -15.5, -9.0, 7.0
TW = 0.2
TH_WALL, T_HF = 4.3, 5.7
T_CEIL = 3.6
T_FLOOR = WALK_H
TDOOR = (-12.8, -11.7, T_FLOOR, T_FLOOR + 2.4)                 # 门洞中心 x=-12.25，宽 1.1，高 2.4
TWIN_F = [(-14.85, -13.55, 1.05, 2.6), (-10.95, -9.65, 1.05, 2.6)]
TWIN_B = [(-13.45, -12.25, 1.35, 2.45)]
TWIN_E = [(4.3, 5.4, 1.35, 2.45)]
tsid = M["red"]

p = mc.Part([tsid]); pg = mc.Part([M["glass"]]); ps = mc.Part([SIGN["telegraph"]])
FT = ("y", FRONT, -1); BT = ("y", TY1, 1); WT = ("x", TX0, -1); ET = ("x", TX1, 1)
for face, u0, u1, holes in ((FT, TX0, TX1, [TDOOR, *TWIN_F]), (BT, TX0, TX1, TWIN_B),
                            (WT, FRONT, TY1, []), (ET, FRONT, TY1, TWIN_E)):
    hf = T_HF if face is FT else TH_WALL
    slab(p, face, u0, u1, -0.03, 0, GROUND - 0.04, hf, holes, tsid)                      # 外护板
    slab(p, face, u0 + (0.03 if face[0] == "x" else 0), u1 - (0.03 if face[0] == "x" else 0), -TW, -0.03, GROUND - 0.04, T_CEIL + 0.15,
         holes, M["paint"])                                                              # 室内层（白漆板）
    slab(p, face, u0, u1, -TW, -0.03, T_CEIL + 0.15, hf, [], tsid)                       # 天花板以上（阁楼）
# 地板 / 天花板
f = bx(p, TX0 + TW, TX1 - TW, 0.0, TY1 - TW, GROUND - 0.04, T_FLOOR, M["floor"]); swap_uv(p, f)
bx(p, TX0 + TW, TX1 - TW, 0.0, TY1 - TW, T_CEIL, T_CEIL + 0.15, M["ceil"])
for i in range(4):                                                                       # 天花梁
    yy = 1.0 + i * 1.6
    bx(p, TX0 + TW, TX1 - TW, yy - 0.08, yy + 0.08, T_CEIL - 0.16, T_CEIL, M["wood"])
# 室内：墙裙 + 腰线 + 踢脚 + 顶角线（贴在内表面，向室内凸出 ≤ 3 cm）
INNER = [(("y", 0.0, 1), TX0 + TW, TX1 - TW, [TDOOR, *TWIN_F]), (("y", TY1 - TW, -1), TX0 + TW, TX1 - TW, TWIN_B),
         (("x", TX0 + TW, 1), 0.0, TY1 - TW, []), (("x", TX1 - TW, -1), 0.0, TY1 - TW, TWIN_E)]
for face, u0, u1, holes in INNER:
    slab(p, face, u0, u1, 0, 0.012, T_FLOOR, 1.1, holes, M["wains"])
    slab(p, face, u0, u1, 0, 0.03, 1.08, 1.15, holes, M["wood"])
    slab(p, face, u0, u1, 0, 0.022, T_FLOOR, T_FLOOR + 0.16, holes, M["wood"])
    slab(p, face, u0, u1, 0, 0.05, T_CEIL - 0.1, T_CEIL, [], M["wood"])
# 窗（真洞口 + 玻璃）
for o in TWIN_F: window_open(p, pg, FT, *o, t=TW, ext=M["trim"], intr=M["wood"])
for o in TWIN_B: window_open(p, pg, BT, *o, t=TW, ext=M["trim"], intr=M["wood"])
for o in TWIN_E: window_open(p, pg, ET, *o, t=TW, ext=M["trim"], intr=M["wood"])
# 门洞：内衬 + 门槛 + 内外门套
lin = 0.02
for u0, u1 in ((TDOOR[0], TDOOR[0] + lin), (TDOOR[1] - lin, TDOOR[1])):
    fbox(p, FT, u0, u1, -TW, 0, T_FLOOR, TDOOR[3], M["wood"])
fbox(p, FT, TDOOR[0], TDOOR[1], -TW, 0, TDOOR[3] - lin, TDOOR[3], M["wood"])
fbox(p, FT, TDOOR[0], TDOOR[1], -TW - 0.02, 0.03, T_FLOOR - 0.03, T_FLOOR + 0.012, M["wood"])  # 门槛（只凸 1.2 cm）
casing(p, FT, TDOOR[0], TDOOR[1], T_FLOOR, TDOOR[3], M["trim"], 0, 0.035, w=0.13, sill=False, zfloor=T_FLOOR)
casing(p, ("y", 0.0, 1), TDOOR[0], TDOOR[1], T_FLOOR, TDOOR[3], M["wood"], 0, 0.02, w=0.1, sill=False, zfloor=T_FLOOR)
# 门脸：墙角板、檐口、招牌、雨棚、屋顶
corner_boards(p, TX0, TX1, GROUND - 0.04, T_HF, M["trim"])
cornice(p, TX0, TX1, T_HF, M["trim"])
sign_board(p, ps, -12.25, 4.6, 4.7, 1.03, "telegraph", M["trim"])
awning(p, TX0, TX1, 3.05, [TX0 + 0.2, -12.25 - 1.0, -12.25 + 1.0, TX1 - 0.2])
gable_roof(p, TX0, TX1, 0.0, TY1 + 0.3, TH_WALL, 1.05, tsid)
INSUL = (TX1 + 0.1, TX1 + 0.24)
# 假立面东端的绝缘子横担（电报线从街边的电线杆接过来）
bx(p, TX1 - 0.05, TX1 + 0.3, -0.14, -0.06, 5.0, 5.08, M["dark"])
for xx in INSUL:
    cyl(p, xx, -0.1, 5.08, 5.18, 0.03, M["glass"], seg=8)
obj(p, "Telegraph_Shell"); obj(pg, "Telegraph_Glass"); obj(ps, "NoCol_Sign_Telegraph")

# 门：向内开约 100° 固定（铰链在西侧门框）
p = mc.Part([M["wood"]])
hinge = Vector((TDOOR[0] + 0.03, 0.02, T_FLOOR + 0.005))
dw, dh, dt = 1.06, 2.36, 0.045
X = T(*hinge) @ R("Z", 100)
p.box((dw, dt, dh), M["wood"], xf=X @ T(dw / 2, dt / 2, dh / 2))
for (u0, u1, z0, z1) in ((0.1, 0.48, 0.15, 1.0), (0.58, 0.96, 0.15, 1.0), (0.1, 0.48, 1.15, 2.2), (0.58, 0.96, 1.15, 2.2)):
    for side in (-1, 1):                                                                 # 两面都有凸镶板
        yy = dt / 2 + side * (dt / 2 + 0.006)
        p.box((u1 - u0, 0.012, z1 - z0), M["wood"], xf=X @ T((u0 + u1) / 2, yy, (z0 + z1) / 2), bevel=0.004)
for side in (-1, 1):
    p.sphere(0.03, M["brass"], xf=X @ T(dw - 0.08, dt / 2 + side * 0.06, 1.0), seg=10, rings=6)
    p.box((0.05, 0.01, 0.2), M["brass"], xf=X @ T(dw - 0.08, dt / 2 + side * 0.028, 1.0))
for zz in (0.3, 2.0):                                                                    # 合页
    p.box((0.16, 0.008, 0.1), M["iron"], xf=X @ T(0.08, -0.005, zz))
obj(p, "Telegraph_Door", origin=tuple(hinge))

# ---------------- 室内道具
IX0, IX1, IY1 = TX0 + TW, TX1 - TW, TY1 - TW                   # 室内 x∈[-15.3,-9.2]，y∈[0,6.8]

# 柜台（隔开前厅与报务区），东头留 1.2 m 通道；台上黄铜栅栏，中间留收发窗口
p = mc.Part([M["wood"]])
CY0, CY1, CZ = 2.95, 3.55, T_FLOOR + 1.05
CXE = -10.45
bx(p, IX0, CXE, CY0 + 0.05, CY1, T_FLOOR, CZ - 0.04, M["wood"])
bx(p, IX0, CXE + 0.04, CY0 - 0.04, CY1 + 0.02, CZ - 0.04, CZ, M["wood"], bevel=0.008)
bx(p, IX0, CXE, CY0, CY0 + 0.05, T_FLOOR, T_FLOOR + 0.12, M["wains"])
n = 5
for i in range(n):                                                                       # 前脸镶板
    a = IX0 + 0.12 + i * (CXE - IX0 - 0.12) / n
    b = a + (CXE - IX0 - 0.12) / n - 0.12
    bx(p, a, b, CY0 + 0.035, CY0 + 0.05, T_FLOOR + 0.22, CZ - 0.16, M["wains"], bevel=0.008)
bx(p, IX0, CXE, CY0 + 0.02, CY0 + 0.05, CZ - 0.12, CZ - 0.06, M["wood"])
GX0, GX1, GY = -13.55, -10.95, CY0 + 0.12
bx(p, GX0, GX1, GY - 0.02, GY + 0.02, CZ, CZ + 0.05, M["brass"])
bx(p, GX0, GX1, GY - 0.02, GY + 0.02, CZ + 0.93, CZ + 0.97, M["brass"])
for xx in (GX0, GX1):
    bx(p, xx - 0.025, xx + 0.025, GY - 0.025, GY + 0.025, CZ, CZ + 1.02, M["brass"])
    p.sphere(0.03, M["brass"], xf=T(xx, GY, CZ + 1.05), seg=10, rings=6)
WK0, WK1, WKZ = -12.5, -12.0, CZ + 0.32                                                  # 收发窗口
bx(p, WK0 - 0.02, WK1 + 0.02, GY - 0.02, GY + 0.02, WKZ, WKZ + 0.03, M["brass"])
x = GX0 + 0.06
while x < GX1 - 0.03:
    z0 = WKZ + 0.03 if WK0 - 0.01 < x < WK1 + 0.01 else CZ + 0.05
    p.lathe([(0, 0.008, 0.008), (CZ + 0.93 - z0, 0.008, 0.008)], M["brass"], seg=6, xf=T(x, GY, z0), cap=False)
    x += 0.065
bx(p, WK0, WK1, CY0 - 0.12, GY + 0.04, CZ, CZ + 0.015, M["brass"])                       # 窗口下的小台
obj(p, "Telegraph_Counter")

# 报务桌（靠后墙，窗下）+ 椅子 + 文件格
p = mc.Part([M["wood"]])
DX0, DX1, DY0, DY1, DZ = -13.75, -12.0, 6.05, 6.78, T_FLOOR + 0.78
bx(p, DX0, DX1, DY0, DY1, DZ - 0.035, DZ, M["wood"], bevel=0.006)
for xx in (DX0 + 0.05, DX1 - 0.05):
    for yy in (DY0 + 0.05, DY1 - 0.05):
        bx(p, xx - 0.03, xx + 0.03, yy - 0.03, yy + 0.03, T_FLOOR, DZ - 0.035, M["wood"])
bx(p, DX1 - 0.48, DX1 - 0.02, DY0 + 0.02, DY1 - 0.02, T_FLOOR + 0.05, DZ - 0.035, M["wood"])  # 抽屉柜
for k in range(3):
    z0 = T_FLOOR + 0.1 + k * 0.2
    bx(p, DX1 - 0.45, DX1 - 0.05, DY0 + 0.005, DY0 + 0.02, z0, z0 + 0.17, M["wains"], bevel=0.004)
    bx(p, DX1 - 0.28, DX1 - 0.22, DY0 - 0.01, DY0 + 0.005, z0 + 0.075, z0 + 0.095, M["brass"])
bx(p, DX0, DX0 + 0.04, DY0 + 0.05, DY1 - 0.05, DZ - 0.2, DZ - 0.035, M["wood"])
# 椅子（面向桌子，+Y）
cx, cy = -12.75, 5.45
bx(p, cx - 0.21, cx + 0.21, cy - 0.21, cy + 0.21, T_FLOOR + 0.44, T_FLOOR + 0.48, M["wood"], bevel=0.008)
for sx in (-1, 1):
    for sy in (-1, 1):
        bx(p, cx + sx * 0.18 - 0.02, cx + sx * 0.18 + 0.02, cy + sy * 0.18 - 0.02, cy + sy * 0.18 + 0.02, T_FLOOR, T_FLOOR + 0.44, M["wood"])
    bx(p, cx + sx * 0.18 - 0.02, cx + sx * 0.18 + 0.02, cy - 0.2, cy - 0.16, T_FLOOR + 0.48, T_FLOOR + 0.95, M["wood"])
bx(p, cx - 0.2, cx + 0.2, cy - 0.21, cy - 0.17, T_FLOOR + 0.78, T_FLOOR + 0.93, M["wood"], bevel=0.008)
bx(p, cx - 0.2, cx + 0.2, cy - 0.2, cy - 0.18, T_FLOOR + 0.55, T_FLOOR + 0.6, M["wood"])
# 西墙文件格
FX0, FY0, FY1 = IX0, 4.1, 5.7
bx(p, FX0, FX0 + 0.34, FY0, FY1, T_FLOOR, T_FLOOR + 0.8, M["wood"])
bx(p, FX0, FX0 + 0.3, FY0, FY1, T_FLOOR + 0.8, T_FLOOR + 1.9, M["wains"])
for k in range(6):
    zz = T_FLOOR + 0.8 + k * 0.2
    bx(p, FX0, FX0 + 0.32, FY0, FY1, zz, zz + 0.02, M["wood"])
for k in range(7):
    yy = FY0 + k * (FY1 - FY0) / 6
    bx(p, FX0, FX0 + 0.32, yy - 0.01, yy + 0.01, T_FLOOR + 0.8, T_FLOOR + 1.9, M["wood"])
bx(p, FX0, FX0 + 0.36, FY0 - 0.02, FY1 + 0.02, T_FLOOR + 1.9, T_FLOOR + 1.96, M["wood"])
obj(p, "Telegraph_Desk")

# 电报机：电键 + 发声器 + 纸带记录器（一个网格 "Telegraph_Machine"，原点在底板中心）
MC = Vector((-13.0, 6.42, DZ))
p = mc.Part([M["wood"]])
def mb(x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    bx(p, MC.x + x0, MC.x + x1, MC.y + y0, MC.y + y1, MC.z + z0, MC.z + z1, mat, bevel)
mb(-0.3, 0.32, -0.15, 0.15, 0, 0.025, M["wood"], bevel=0.004)                            # 底板
# 电键（靠操作员一侧，右手）
kx = 0.2
mb(kx - 0.035, kx + 0.035, -0.04, 0.06, 0.025, 0.035, M["brass"])
for sx in (-1, 1):
    mb(kx + sx * 0.03 - 0.008, kx + sx * 0.03 + 0.008, 0.0, 0.03, 0.035, 0.07, M["brass"])
mb(kx - 0.012, kx + 0.012, -0.12, 0.06, 0.06, 0.072, M["brass"])                       # 杠杆
p.lathe([(0, 0, 0), (0, 0.022, 0.022), (0.012, 0.026, 0.026), (0.022, 0.018, 0.018), (0.026, 0, 0)], M["ebonite"], seg=14,
        xf=T(MC.x + kx, MC.y - 0.12, MC.z + 0.072))                                    # 胶木按钮
cyl(p, MC.x + kx, MC.y - 0.12, MC.z + 0.035, MC.z + 0.06, 0.004, M["brass"], seg=6)
cyl(p, MC.x + kx, MC.y + 0.05, MC.z + 0.072, MC.z + 0.09, 0.006, M["brass"], seg=6)    # 调节螺丝
mb(kx - 0.012, kx + 0.012, 0.09, 0.12, 0.025, 0.05, M["brass"])                         # 短路开关
# 发声器（中间）：两只线圈 + 黄铜支架 + 衔铁
sx0 = 0.0
mb(sx0 - 0.07, sx0 + 0.07, -0.02, 0.09, 0.025, 0.035, M["wood"])
for dy in (0.015, 0.06):
    cyl(p, MC.x + sx0, MC.y + dy, MC.z + 0.035, MC.z + 0.095, 0.018, M["ebonite"], seg=14)
    cyl(p, MC.x + sx0, MC.y + dy, MC.z + 0.095, MC.z + 0.1, 0.012, M["brass"], seg=10)
mb(sx0 - 0.05, sx0 - 0.03, -0.01, 0.09, 0.035, 0.14, M["brass"])                         # 立柱
mb(sx0 - 0.05, sx0 + 0.015, -0.01, 0.0, 0.13, 0.14, M["brass"])
mb(sx0 - 0.012, sx0 + 0.012, -0.03, 0.085, 0.105, 0.118, M["brass"])                    # 衔铁
cyl(p, MC.x + sx0, MC.y - 0.03, MC.z + 0.118, MC.z + 0.15, 0.005, M["brass"], seg=6)
for sx in (-0.05, 0.05):                                                                 # 接线柱
    cyl(p, MC.x + sx0 + sx, MC.y - 0.06, MC.z + 0.025, MC.z + 0.05, 0.008, M["brass"], seg=8)
    cyl(p, MC.x + sx0 + sx, MC.y - 0.06, MC.z + 0.05, MC.z + 0.056, 0.012, M["brass"], seg=8)
# 纸带记录器（左边）：机芯盒 + 纸卷 + 出纸滚轮
rx = -0.2
mb(rx - 0.085, rx + 0.085, -0.06, 0.08, 0.025, 0.13, M["blackiron"], bevel=0.004)
mb(rx - 0.08, rx + 0.08, -0.065, -0.06, 0.03, 0.125, M["brass"])
p.lathe([(0, 0, 0), (0, 0.018, 0.018), (0.04, 0.018, 0.018), (0.04, 0, 0)], M["brass"], seg=10,
        xf=T(MC.x + rx + 0.085, MC.y + 0.01, MC.z + 0.08) @ R("Y", 90))               # 发条钥匙轴
p.lathe([(0, 0, 0), (0, 0.07, 0.07), (0.022, 0.07, 0.07), (0.022, 0, 0)], M["paper"], seg=20,
        xf=T(MC.x + rx - 0.011, MC.y + 0.1, MC.z + 0.19) @ R("Y", 90))                 # 纸卷
p.lathe([(0, 0, 0), (0, 0.075, 0.075), (0.004, 0.075, 0.075), (0.004, 0, 0)], M["brass"], seg=20,
        xf=T(MC.x + rx + 0.011, MC.y + 0.1, MC.z + 0.19) @ R("Y", 90))
mb(rx - 0.004, rx + 0.004, 0.06, 0.12, 0.13, 0.2, M["brass"])
for zz in (0.115, 0.14):                                                                 # 出纸滚轮
    p.lathe([(0, 0, 0), (0, 0.01, 0.01), (0.03, 0.01, 0.01), (0.03, 0, 0)], M["brass"], seg=10,
            xf=T(MC.x + rx - 0.015, MC.y - 0.065, MC.z + zz) @ R("Y", 90))
obj(p, "Telegraph_Machine", origin=tuple(MC))

# 纸带：从记录器出纸口拉出来，顺着桌面越过桌沿，垂到地上盘成几圈
TAPE_X = MC.x + rx
pts = []
def seg(a, b, n):
    for i in range(n):
        t = i / n; pts.append(a.lerp(b, t))
P0 = Vector((TAPE_X, MC.y - 0.07, MC.z + 0.127))
P1 = Vector((TAPE_X, MC.y - 0.12, MC.z + 0.004))
seg(P0, P1, 4)
P2 = Vector((TAPE_X - 0.02, DY0 + 0.02, DZ + 0.002))
seg(P1, P2, 10)
for i in range(9):                                                                       # 桌沿的圆角
    a = math.pi / 2 * i / 8
    pts.append(Vector((TAPE_X - 0.02 - 0.003 * i, DY0 + 0.02 - 0.02 * math.sin(a), DZ + 0.002 - 0.02 * (1 - math.cos(a)))))
# 垂下：轻微摆动，中间打一个卷
zt = DZ - 0.02
yb = DY0 - 0.004
for i in range(1, 21):
    t = i / 20
    pts.append(Vector((TAPE_X - 0.05 - 0.03 * t, yb - 0.04 * math.sin(t * math.pi) - 0.12 * t * t, zt - t * (zt - T_FLOOR - 0.35))))
c = pts[-1].copy()
for i in range(1, 25):                                                                   # 半空中的一个卷（绕 X 轴的圆）
    a = 2 * math.pi * i / 24
    r = 0.07
    pts.append(Vector((c.x - 0.022 * i / 24, c.y - r * math.sin(a), c.z - r + r * math.cos(a) - 0.003 * i)))
c = pts[-1].copy()
for i in range(1, 13):
    t = i / 12
    pts.append(Vector((c.x - 0.01 * t, c.y - 0.1 * t, c.z - t * (c.z - T_FLOOR - 0.004))))
# 地上：几个立着的圈 + 平铺的弯
c = pts[-1].copy()
loops = [(0.09, -0.02), (0.12, -0.04), (0.08, -0.03), (0.1, -0.05)]
for k, (r, dx) in enumerate(loops):
    for i in range(1, 25):
        a = 2 * math.pi * i / 24
        pts.append(Vector((c.x + dx * i / 24, c.y - r * math.sin(a) - 0.05 * i / 24, T_FLOOR + 0.004 + r - r * math.cos(a))))
    c = pts[-1].copy()
for i in range(1, 16):
    t = i / 15
    pts.append(Vector((c.x - 0.25 * t + 0.08 * math.sin(t * 5), c.y - 0.05 * math.sin(t * 3) - 0.15 * t, T_FLOOR + 0.004)))
TAPE_C = Vector((TAPE_X - 0.1, DY0 - 0.25, T_FLOOR + 0.3))
tape = mc.empty("Telegraph_Tape", parent=ROOT_OBJ, location=tuple(TAPE_C), collection=C_EXP)
p = mc.Part([M["paper"]])
ribbon(p, [q - TAPE_C for q in pts], 0.0175, M["paper"])
p.finish("NoCol_Telegraph_Tape", parent=tape, collection=C_EXP)

# 挂钟（后墙，东侧，从门口一眼能看到）：指针停在三点
CK = ("y", IY1, -1)                                                                      # 后墙内表面，朝室内
ckx, ckz = -10.45, 2.55
p = mc.Part([M["wood"]])
fbox(p, CK, ckx - 0.17, ckx + 0.17, 0, 0.03, ckz - 0.75, ckz - 0.18, M["wood"])          # 下面的摆箱：背板 + 框 + 玻璃
for (u0, u1, z0, z1) in ((-0.17, -0.12, -0.75, -0.18), (0.12, 0.17, -0.75, -0.18), (-0.17, 0.17, -0.75, -0.68), (-0.17, 0.17, -0.27, -0.18)):
    fbox(p, CK, ckx + u0, ckx + u1, 0.03, 0.085, ckz + z0, ckz + z1, M["wood"])
fbox(p, CK, ckx - 0.12, ckx + 0.12, 0.077, 0.08, ckz - 0.68, ckz - 0.27, M["glass"])
fbox(p, CK, ckx - 0.006, ckx + 0.006, 0.05, 0.06, ckz - 0.62, ckz - 0.24, M["brass"])   # 摆杆
p.lathe([(0, 0, 0), (0, 0.04, 0.04), (0.012, 0.04, 0.04), (0.012, 0, 0)], M["brass"], seg=16,
        xf=T(*fpt(CK, ckx, 0.05, ckz - 0.56)) @ R("X", 90))
p.lathe([(0, 0, 0), (0, 0.23, 0.23), (0.07, 0.23, 0.23), (0.09, 0.2, 0.2), (0.09, 0, 0)], M["wood"], seg=8,
        xf=T(*fpt(CK, ckx, 0, ckz)) @ R("X", 90) @ R("Z", 22.5))                         # 八角钟壳
p.lathe([(0, 0.2, 0.2), (0.012, 0.2, 0.2), (0.012, 0.172, 0.172), (0, 0.172, 0.172)], M["brass"], seg=32,
        xf=T(*fpt(CK, ckx, 0.09, ckz)) @ R("X", 90), cap=False)                          # 铜圈
disc(p, CK, ckx, 0.091, ckz, 0.175, CLOCK_MAT)
fbox(p, CK, ckx, ckx + 0.1, 0.094, 0.098, ckz - 0.008, ckz + 0.008, M["ebonite"])       # 时针 → 3（朝右）
fbox(p, CK, ckx - 0.006, ckx + 0.006, 0.099, 0.103, ckz, ckz + 0.145, M["ebonite"])     # 分针 → 12
p.lathe([(0, 0, 0), (0, 0.012, 0.012), (0.012, 0.012, 0.012), (0.012, 0, 0)], M["brass"], seg=10,
        xf=T(*fpt(CK, ckx, 0.096, ckz)) @ R("X", 90))
obj(p, "NoCol_Telegraph_Clock")

# 铸铁肚子炉（前厅西侧）+ 炉下铁皮 + 烟囱穿天花板
SXc, SYc = -14.45, 2.05
p = mc.Part([M["blackiron"]])
bx(p, SXc - 0.45, SXc + 0.45, SYc - 0.45, SYc + 0.45, T_FLOOR, T_FLOOR + 0.006, M["zinc"])
z0 = T_FLOOR + 0.2
prof = [(0, 0, 0), (0, 0.2, 0.2), (0.06, 0.21, 0.21), (0.08, 0.17, 0.17), (0.2, 0.24, 0.24), (0.38, 0.28, 0.28),
        (0.55, 0.25, 0.25), (0.66, 0.18, 0.18), (0.7, 0.2, 0.2), (0.76, 0.16, 0.16), (0.82, 0.12, 0.12), (0.86, 0.075, 0.075), (0.86, 0, 0)]
p.lathe(prof, M["blackiron"], seg=20, xf=T(SXc, SYc, z0))
for k in range(4):                                                                       # 弯脚
    a = math.radians(45 + 90 * k)
    p.box((0.05, 0.05, 0.24), M["blackiron"], xf=T(SXc + 0.16 * math.cos(a), SYc + 0.16 * math.sin(a), T_FLOOR + 0.11) @ R("Z", math.degrees(a)) @ R("Y", 12))
for zz in (0.2, 0.47):                                                                   # 装饰铜箍
    rr = 0.245 if zz < 0.3 else 0.282
    p.lathe([(0, rr, rr), (0.03, rr, rr)], M["brass"], seg=20, xf=T(SXc, SYc, z0 + zz - 0.015), cap=False)
p.box((0.18, 0.03, 0.14), M["blackiron"], xf=T(SXc + 0.2, SYc - 0.15, z0 + 0.32) @ R("Z", -40), bevel=0.006)  # 炉门
cyl(p, SXc, SYc, z0 + 0.86, T_CEIL + 0.15, 0.075, M["blackiron"], seg=14)
p.lathe([(0, 0.11, 0.11), (0.02, 0.11, 0.11)], M["blackiron"], seg=14, xf=T(SXc, SYc, T_CEIL - 0.02), cap=True)
obj(p, "Telegraph_Stove")

# 长凳（前厅西窗下）
p = mc.Part([M["wood"]])
BX0, BX1, BY = -15.2, -13.75, 0.38
bx(p, BX0, BX1, BY - 0.18, BY + 0.18, T_FLOOR + 0.42, T_FLOOR + 0.46, M["wood"], bevel=0.008)
for xx in (BX0 + 0.08, BX1 - 0.08):
    bx(p, xx - 0.025, xx + 0.025, BY - 0.15, BY + 0.15, T_FLOOR, T_FLOOR + 0.42, M["wood"])
bx(p, BX0 + 0.05, BX1 - 0.05, BY - 0.02, BY + 0.02, T_FLOOR + 0.12, T_FLOOR + 0.18, M["wood"])
bx(p, BX0, BX1, BY - 0.2, BY - 0.165, T_FLOOR + 0.62, T_FLOOR + 0.82, M["wood"], bevel=0.006)
for xx in (BX0 + 0.08, BX1 - 0.08):
    bx(p, xx - 0.025, xx + 0.025, BY - 0.2, BY - 0.16, T_FLOOR + 0.46, T_FLOOR + 0.82, M["wood"])
obj(p, "Telegraph_Bench")

# 墙上的告示（前厅东墙）+ 图钉
p = mc.Part([NOTICE["rates"]])
NE = ("x", IX1, -1)
for (yy, zz, nm, rot) in ((0.75, 1.72, "rates", 1.5), (1.25, 1.62, "hours", -2.0), (1.8, 1.78, "line", 3.0)):
    fquad(p, NE, yy, 0.003, zz, 0.27, 0.37, NOTICE[nm], rot=rot)
    p.sphere(0.008, M["brass"], xf=T(*fpt(NE, yy, 0.006, zz + 0.16)), seg=6, rings=4)
obj(p, "NoCol_Telegraph_Notices")

# 废纸篓（藤编）+ 几团废纸
p = mc.Part([M["wicker"]])
WX, WY = -11.75, 6.45
p.lathe([(0, 0, 0), (0, 0.13, 0.13), (0.34, 0.16, 0.16), (0.34, 0.15, 0.15), (0.03, 0.12, 0.12), (0.03, 0, 0)], M["wicker"], seg=16,
        xf=T(WX, WY, T_FLOOR))
for k, (dx, dy, dz) in enumerate(((0.03, 0.02, 0.33), (-0.05, -0.02, 0.31), (0.0, -0.06, 0.3))):
    p.sphere(0.045, M["paper"], xf=T(WX + dx, WY + dy, T_FLOOR + dz) @ R("Z", k * 70), seg=7, rings=5, sx=1.0, sy=0.85, sz=0.8)
p.sphere(0.04, M["paper"], xf=T(WX + 0.25, WY - 0.1, T_FLOOR + 0.035), seg=7, rings=5, sz=0.8)
obj(p, "NoCol_Telegraph_Wastebasket")

# 吊顶油灯（柜台上方）：吊链 + 烟罩 + 灯罩 + 玻璃灯筒 + 黄铜油壶；Telegraph_LampPos 在火焰位置
LX, LY = -12.25, 3.25
LAMP_Z = 2.78                                                                            # 火焰中心
p = mc.Part([M["brass"]])
p.lathe([(0, 0, 0), (0, 0.09, 0.09), (0.02, 0.09, 0.09), (0.03, 0, 0)], M["brass"], seg=16, xf=T(LX, LY, T_CEIL - 0.03))
z = T_CEIL - 0.03
k = 0
while z > LAMP_Z + 0.36:                                                                 # 吊链（交替转 90° 的扁环）
    p.box((0.028, 0.006, 0.05), M["brass"], xf=T(LX, LY, z - 0.025) @ R("Z", 90 * (k % 2)))
    z -= 0.045; k += 1
p.lathe([(0, 0, 0), (0, 0.035, 0.035), (0.06, 0.1, 0.1), (0.075, 0.1, 0.1), (0.08, 0, 0)], M["brass"], seg=16,
        xf=T(LX, LY, LAMP_Z + 0.32) @ R("X", 180))                                       # 烟罩
for a in (0, 120, 240):                                                                  # 吊架三根
    aa = math.radians(a)
    p.box((0.008, 0.008, 0.36), M["brass"], xf=T(LX + 0.15 * math.cos(aa), LY + 0.15 * math.sin(aa), LAMP_Z + 0.13) @ R("Z", a) @ R("Y", -14))
p.lathe([(0, 0.07, 0.07), (0.03, 0.12, 0.12), (0.08, 0.2, 0.2), (0.11, 0.26, 0.26), (0.12, 0.27, 0.27)], M["shade"], seg=24,
        xf=T(LX, LY, LAMP_Z + 0.08) @ R("X", 180), cap=False)                            # 乳白灯罩（下开口）
p.lathe([(0, 0.27, 0.27), (0.012, 0.27, 0.27)], M["brass"], seg=24, xf=T(LX, LY, LAMP_Z - 0.04), cap=False)
p.lathe([(0, 0.03, 0.03), (0.04, 0.045, 0.045), (0.09, 0.03, 0.03), (0.2, 0.022, 0.022)], M["lampglass"], seg=14,
        xf=T(LX, LY, LAMP_Z - 0.06), cap=False)                                          # 玻璃灯筒
p.lathe([(0, 0, 0), (0, 0.04, 0.04), (0.05, 0.08, 0.08), (0.1, 0.075, 0.075), (0.13, 0.04, 0.04), (0.14, 0.035, 0.035), (0.14, 0, 0)],
        M["brass"], seg=16, xf=T(LX, LY, LAMP_Z - 0.2))                                  # 油壶
p.lathe([(0, 0, 0), (0, 0.02, 0.02), (0.03, 0, 0)], M["brass"], seg=8, xf=T(LX, LY, LAMP_Z - 0.235))
obj(p, "NoCol_Telegraph_Lamp")
mc.empty("Telegraph_LampPos", parent=ROOT_OBJ, location=(LX, LY, LAMP_Z), collection=C_EXP)

# 电报线：从电报机后面沿桌子后沿走到窗西边，再沿后墙爬到天花板、穿出去（细线不加碰撞）
p = mc.Part([M["ebonite"]])
WIRE_X = TWIN_B[0][0] - 0.2                                                              # 窗洞西边 20 cm
for k, dx in enumerate((0.0, 0.025)):
    yy = IY1 - 0.03 - 0.02 * k
    xx = WIRE_X - dx
    bx(p, MC.x - 0.004, MC.x + 0.004, MC.y + 0.15, yy, MC.z + 0.028, MC.z + 0.034, M["ebonite"])
    bx(p, xx - 0.003, MC.x + 0.004, yy - 0.003, yy + 0.003, MC.z + 0.028, MC.z + 0.034, M["ebonite"])
    bx(p, xx - 0.003, xx + 0.003, yy - 0.003, IY1 - 0.005, MC.z + 0.028, MC.z + 0.034, M["ebonite"])
    bx(p, xx - 0.003, xx + 0.003, IY1 - 0.011, IY1 - 0.005, MC.z + 0.028, T_CEIL - 0.1, M["ebonite"])
for zz in (1.5, 2.2, 2.9):
    bx(p, WIRE_X - 0.05, WIRE_X + 0.02, IY1 - 0.016, IY1, zz, zz + 0.015, M["brass"])
obj(p, "NoCol_Telegraph_Wires")


# ================================================================ 巷口木栅栏（挡住玩家进巷子）
p = mc.Part([M["dark"]])
FY0, FY1 = FRONT + 0.02, FRONT + 0.05                                                    # 板面 y∈[-0.18,-0.15]，横档在后
ALLEYS = [(-9.0, -7.26, True), (7.26, 9.0, True), (-16.5, -15.5, False), (15.0, 16.5, False)]
for x0, x1, gate in ALLEYS:
    H = 2.15
    for xx in (x0 + 0.05, x1 - 0.05):
        bx(p, xx - 0.05, xx + 0.05, FY1, FY1 + 0.1, GROUND - 0.1, H + 0.12, M["dark"], bevel=0.01)
    if gate:                                                                             # 门扇：留缝、Z 撑、铁合页
        g0, g1 = x0 + 0.13, x1 - 0.13
        nb = max(3, int((g1 - g0) / 0.15))
        bw = (g1 - g0) / nb
        for i in range(nb):
            a = g0 + i * bw
            top = H - 0.08 + 0.05 * hashf(a, 3.0)
            bx(p, a + 0.004, a + bw - 0.004, FY0, FY1, 0.06, top, M["dark"])
        for zz in (0.35, 1.75):
            bx(p, g0, g1, FY0 - 0.025, FY0, zz - 0.06, zz + 0.06, M["dark"])
            bx(p, g0 - 0.06, g0 + 0.32, FY0 - 0.032, FY0 - 0.025, zz - 0.02, zz + 0.02, M["iron"])
        L = math.hypot(g1 - g0 - 0.12, 1.28); ang = math.degrees(math.atan2(1.28, g1 - g0 - 0.12))
        p.box((L, 0.025, 0.1), M["dark"], xf=T((g0 + g1) / 2, FY0 - 0.0125, 1.05) @ R("Y", -ang))
        bx(p, g1 - 0.2, g1 - 0.05, FY0 - 0.03, FY0 - 0.02, 1.1, 1.14, M["iron"])            # 门闩
    else:
        nb = max(3, int((x1 - x0 - 0.2) / 0.15))
        bw = (x1 - x0 - 0.2) / nb
        for i in range(nb):
            a = x0 + 0.1 + i * bw
            top = H + 0.05 * hashf(a, 7.0)
            bx(p, a + 0.004, a + bw - 0.004, FY0, FY1, GROUND, top, M["dark"])
            p.box((bw - 0.008, 0.03, 0.08), M["dark"], xf=T(a + bw / 2, (FY0 + FY1) / 2, top) @ R("Y", 45 if i % 2 else -45) @ S(0.7, 1, 1))
    for zz in (0.4, 1.8):                                                                # 后面的横档
        bx(p, x0 + 0.1, x1 - 0.1, FY1, FY1 + 0.06, zz - 0.06, zz + 0.06, M["dark"])
obj(p, "AlleyFences")


# ================================================================ 3. 栈道小物
p = mc.Part([M["dark"]])
pn = mc.Part([M["iron"]])                                                                # NoCol 小杂物


def bench(x0, x1, y=-0.62, back=True):
    z = WALK_H
    bx(p, x0, x1, y - 0.2, y + 0.2, z + 0.43, z + 0.47, M["dark"], bevel=0.008)
    for xx in (x0 + 0.1, x1 - 0.1):
        bx(p, xx - 0.03, xx + 0.03, y - 0.17, y + 0.17, z, z + 0.43, M["dark"])
    if back:
        bx(p, x0, x1, y + 0.2, y + 0.24, z + 0.62, z + 0.85, M["dark"], bevel=0.006)
        for xx in (x0 + 0.1, x1 - 0.1):
            bx(p, xx - 0.03, xx + 0.03, y + 0.18, y + 0.24, z + 0.47, z + 0.85, M["dark"])


bench(-15.05, -13.55)                                                                    # 电报局西窗下
bench(19.3, 20.8)                                                                        # 澡堂窗下
bench(-23.5, -22.2, back=False)
for x, y in ((14.35, -0.6), (13.8, -0.75)):                                              # 治安官门口两只桶
    barrel(p, x, y, WALK_H)
barrel(p, 9.45, -0.62, WALK_H, h=0.95, r=0.32, open_top=True)                            # 接雨水的桶 + 落水管
bx(p, 9.37, 9.53, -0.66, -0.58, 0.88 + WALK_H, 0.9 + WALK_H, M["water"])
p.lathe([(0, 0.21, 0.21), (0.003, 0.21, 0.21), (0.003, 0, 0)], M["water"], seg=16, xf=T(9.45, -0.62, WALK_H + 0.85))
for (x0, x1, y0, y1, z0, z1) in ((9.38, 9.5, -0.28, -0.2, WALK_H + 1.05, 4.15), (9.38, 9.5, -0.62, -0.2, WALK_H + 0.98, WALK_H + 1.08)):
    bx(p, x0, x1, y0, y1, z0, z1, M["iron"])
for x, y, z, s in ((-16.95, -0.55, WALK_H, 0.55), (-16.95, -0.55, WALK_H + 0.55, 0.42), (-17.55, -0.6, WALK_H, 0.5),
                   (8.55, -0.55, WALK_H, 0.48)):                                         # 木箱
    bx(p, x - s / 2, x + s / 2, y - s / 2, y + s / 2, z, z + s, M["planks"], bevel=0.015)
    for zz in (z + 0.06, z + s - 0.06):
        bx(p, x - s / 2 - 0.006, x + s / 2 + 0.006, y - s / 2 - 0.006, y + s / 2 + 0.006, zz - 0.03, zz + 0.03, M["dark"])
for x0, x1 in ((10.6, 13.4),):                                                           # 治安官门前的拴马桩（街面上）
    for xx in (x0, x1):
        bx(p, xx - 0.07, xx + 0.07, -3.07, -2.93, -0.1, 1.05, M["dark"], bevel=0.01)
    bx(p, x0 - 0.12, x1 + 0.12, -3.05, -2.95, 0.95, 1.05, M["dark"], bevel=0.01)
# 路灯柱（栈道外沿）：柱子带碰撞，灯头在 NoCol 里
for lx in (-16.0, 15.75):
    bx(p, lx - 0.06, lx + 0.06, WALK_Y + 0.1, WALK_Y + 0.22, WALK_H, WALK_H + 2.75, M["dark"], bevel=0.01)
    bx(p, lx - 0.1, lx + 0.1, WALK_Y + 0.06, WALK_Y + 0.26, WALK_H, WALK_H + 0.15, M["dark"])
    hz = WALK_H + 2.75
    pn.box((0.03, 0.03, 0.3), M["iron"], xf=T(lx, WALK_Y + 0.16, hz + 0.1))
    pn.box((0.22, 0.22, 0.012), M["iron"], xf=T(lx, WALK_Y + 0.16, hz + 0.26))
    pn.lathe([(0, 0.12, 0.12), (0.08, 0.02, 0.02), (0.1, 0, 0)], M["iron"], seg=4, xf=T(lx, WALK_Y + 0.16, hz + 0.6) @ R("Z", 45))
    pn.box((0.16, 0.16, 0.012), M["iron"], xf=T(lx, WALK_Y + 0.16, hz + 0.6))
    pn.box((0.15, 0.15, 0.33), M["lampglass"], xf=T(lx, WALK_Y + 0.16, hz + 0.43))
    for sx in (-1, 1):
        for sy in (-1, 1):
            pn.box((0.012, 0.012, 0.34), M["iron"], xf=T(lx + sx * 0.075, WALK_Y + 0.16 + sy * 0.075, hz + 0.43))
    pn.lathe([(0, 0, 0), (0, 0.035, 0.035), (0.05, 0.035, 0.035), (0.05, 0.03, 0.03), (0.12, 0.012, 0.012), (0.12, 0, 0)],
             M["brass"], seg=10, xf=T(lx, WALK_Y + 0.16, hz + 0.27))
# 电报局门边：扫帚 + 木桶
pn.lathe([(0, 0.012, 0.012), (1.15, 0.012, 0.012)], M["barrel"], seg=6, xf=T(-11.35, -0.47, WALK_H + 0.3) @ R("X", -12), cap=True)
pn.box((0.26, 0.05, 0.32), M["curtain"], xf=T(-11.35, -0.5, WALK_H + 0.16) @ R("X", -12), bevel=0.01)
pn.lathe([(0, 0, 0), (0, 0.13, 0.13), (0.28, 0.15, 0.15), (0.28, 0.14, 0.14), (0.03, 0.12, 0.12), (0.03, 0, 0)], M["barrel"], seg=14,
         xf=T(-10.9, -0.45, WALK_H))
pn.lathe([(0, 0.15, 0.15), (0.025, 0.15, 0.15)], M["iron"], seg=14, xf=T(-10.9, -0.45, WALK_H + 0.2), cap=False)
obj(p, "Town_Props"); obj(pn, "NoCol_Town_Clutter")

# 街边电报杆 + 两根线接到电报局东山墙
p = mc.Part([M["pole"]])
PX, PY = -8.7, -2.75
p.lathe([(0, 0.13, 0.13), (7.2, 0.09, 0.09), (7.25, 0, 0)], M["pole"], seg=10, xf=T(PX, PY, GROUND - 0.3), swap_uv=True)
bx(p, PX - 0.9, PX + 0.9, PY - 0.06, PY + 0.06, 6.55, 6.67, M["dark"])
obj(p, "TelegraphPole")
def wire(part, pts):
    """电报线：竖、横两条扁带交叉成十字截面，从哪个角度看都有宽度；1.4 cm 宽，
    远处不再因为不到一个像素而断成虚线（原来是 8 mm 单条竖带）。"""
    d = (Vector(pts[-1]) - Vector(pts[0])).normalized()
    ribbon(part, pts, 0.014, M["iron"], side=Vector((0, 0, 1)))
    ribbon(part, pts, 0.014, M["iron"], side=d.cross(Vector((0, 0, 1))))


pw = mc.Part([M["iron"]])
for k, xx in enumerate((PX - 0.75, PX - 0.35, PX + 0.35, PX + 0.75)):
    cyl(pw, xx, PY, 6.67, 6.8, 0.03, M["glass"], seg=8)
    bx(pw, xx - 0.006, xx + 0.006, PY - 0.006, PY + 0.006, 6.67, 6.7, M["iron"])
for xx, yy in ((PX - 0.75, INSUL[0]), (PX - 0.35, INSUL[1])):                                     # 下垂的两根线
    a = Vector((xx, PY, 6.8)); b = Vector((yy, -0.1, 5.18))
    ptsw = [a.lerp(b, i / 16) - Vector((0, 0, 0.25 * math.sin(math.pi * i / 16))) for i in range(17)]
    wire(pw, ptsw)
for xx in (PX + 0.35, PX + 0.75):                                                       # 沿街往西去的线（接到殡仪馆门前那根杆）
    a = Vector((xx, PY, 6.8)); b = Vector((xx - 14, PY, 6.8))
    ptsw = [a.lerp(b, i / 20) - Vector((0, 0, 0.6 * math.sin(math.pi * i / 20))) for i in range(21)]
    wire(pw, ptsw)
# 西边的第二根杆子（线的另一头）
p2 = mc.Part([M["pole"]])
p2.lathe([(0, 0.13, 0.13), (7.2, 0.09, 0.09), (7.25, 0, 0)], M["pole"], seg=10, xf=T(PX - 14, PY, GROUND - 0.3), swap_uv=True)
bx(p2, PX - 14 - 0.9, PX - 14 + 0.9, PY - 0.06, PY + 0.06, 6.55, 6.67, M["dark"])
for xx in (PX - 13.65, PX - 13.25):
    cyl(pw, xx, PY, 6.67, 6.8, 0.03, M["glass"], seg=8)
obj(p2, "TelegraphPole_W")
obj(pw, "NoCol_TelegraphWires")


# ================================================================ 统计 + 导出
exp_objs = [o for o in mc.descendants(ROOT_OBJ)]
tris = mc.tri_count(exp_objs)
print(f"TRIS total {tris}")
for o in exp_objs:
    if o.type == "MESH":
        print(f"  {o.name:32s} {mc.tri_count([o])}")
for nm in ("Telegraph_Machine", "Telegraph_LampPos", "Telegraph_Tape", "TBD_Undertaker", "TBD_Sheriff", "TBD_Baths"):
    o = bpy.data.objects[nm]; w = o.matrix_world.translation
    print(f"NODE {nm:20s} blender ({w.x:.3f}, {w.y:.3f}, {w.z:.3f})  unity ({w.x:.3f}, {w.z:.3f}, {w.y:.3f})")
if EXPORT:
    mc.export_glb(EXPORT, [ROOT_OBJ])

# ================================================================ 评审渲染
if RENDER:
    def import_ctx(path):
        if not pathlib.Path(path).exists():
            print("context missing", path); return []
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in o.users_collection: c.objects.unlink(o)
            C_REV.objects.link(o)
        return new
    ctx = import_ctx(mc.ART / "Street" / "StreetBackdrop.gltf") + import_ctx(mc.ART / "Saloon" / "Saloon.gltf")
    for o in ctx:                     # 酒馆里的玻璃 / 体积不挡阳光
        if o.type == "MESH" and ("Glass" in o.name):
            o.visible_shadow = False
    for o in exp_objs:
        if o.type == "MESH" and ("Glass" in o.name or "Lamp" in o.name):
            o.visible_shadow = False

    mc.setup_render(SAMPLES, res=(1280, 720), exposure=0.0)
    mc.world_hdri("goegap_road", strength=0.9, rot=140)
    sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 5.0; sun_d.angle = math.radians(0.6)
    sun_d.color = (1.0, 0.85, 0.66)
    sun = bpy.data.objects.new("Sun", sun_d); C_REV.objects.link(sun)
    sun.rotation_euler = (math.radians(60), 0, math.radians(20))
    which = argv[argv.index("--only") + 1].split(",") if "--only" in argv else ["street", "aerial", "interior"]

    if "street" in which:
        mc.camera("Cam_Street", (-20.0, -1.5, 1.65), (-6.0, -0.6, 2.0), lens=24, coll=C_REV)
        mc.render(mc.REVIEWS / "Town_street.png")
    if "aerial" in which:
        mc.camera("Cam_Aerial", (0.0, -12.5, 21.0), (0.0, 4.0, 2.0), lens=15, coll=C_REV)
        mc.render(mc.REVIEWS / "Town_aerial.png")
    # 只看细节用的机位（--only note,fence,back,saloon），不属于常规评审图
    DETAIL = {
        "note":   ((12.2, -1.6, 1.6), (12.75, -0.14, 1.45), 30, "Town_detail_note.png"),
        "fence":  ((-6.0, -2.0, 1.7), (-8.5, -0.2, 1.2), 22, "Town_detail_fence.png"),
        "back":   ((12.0, 22.0, 6.0), (0.0, 10.0, 4.0), 24, "Town_detail_back.png"),
        "saloon": ((-3.0, -6.0, 1.7), (0.0, -0.2, 2.5), 20, "Town_detail_saloon.png"),
        "west":   ((-27.0, -5.0, 3.5), (-18.0, 0.0, 2.5), 24, "Town_detail_west.png"),
    }
    for k, (loc, tgt, lens, fn) in DETAIL.items():
        if k in which:
            mc.camera(f"Cam_{k}", loc, tgt, lens=lens, coll=C_REV)
            mc.render(mc.REVIEWS / fn)
    if "interior" in which:
        # 评审用灯：油灯位置的点光 + 窗口天光（Unity 里另配灯，这些不导出）
        ld = bpy.data.lights.new("LampFlame", "POINT"); ld.energy = 120; ld.color = (1.0, 0.7, 0.42); ld.shadow_soft_size = 0.03
        lo = bpy.data.objects.new("LampFlame", ld); lo.location = (LX, LY, LAMP_Z); C_REV.objects.link(lo)
        for (wpos, tgt) in (((-14.2, -0.6, 1.85), (-14.2, 3.0, 1.0)), ((-10.3, -0.6, 1.85), (-10.3, 3.0, 1.0)),
                                  ((-12.85, 7.6, 1.9), (-12.85, 4.0, 1.0)), ((-8.4, 4.85, 1.9), (-12.0, 4.85, 1.0))):
            mc.area("WinSky", wpos, tgt, 60, size=1.2, color=(0.85, 0.9, 1.0), coll=C_REV)
        sc.view_settings.exposure = 0.6
        mc.camera("Cam_Interior", (-9.65, 2.75, 1.75), (-13.2, 6.1, 0.95), lens=16, coll=C_REV)
        mc.render(mc.REVIEWS / "Town_telegraph_interior.png")
        if "door" in which:
            mc.camera("Cam_InteriorDoor", (-13.0, 5.6, 1.6), (-12.25, -0.2, 1.3), lens=18, coll=C_REV)
            mc.render(mc.REVIEWS / "Town_detail_interior_door.png")
        if "desk" in which:
            mc.camera("Cam_Desk", (-12.5, 5.3, 1.55), (-13.05, 6.4, 1.0), lens=28, coll=C_REV)
            mc.render(mc.REVIEWS / "Town_detail_desk.png")
