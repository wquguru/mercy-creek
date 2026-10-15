"""Mercy Creek 窗外大街远景：土路 + 对街假立面 + 木栈道 + 拴马桩 / 水槽 / 木桶 + 远山。

blender --background --python tools/blender/build_street.py -- [--render] [--samples N] [--export path.glb]
默认导出到 Game/Assets/_MercyCreek/Art/Street/StreetBackdrop.glb。
招牌贴图先跑 tools/gen_street_signs.py（Pillow）生成到 art/source/_derived/street/。

坐标与 build_saloon.py 相同：X 向右，Y 向里（酒馆前墙 Y=0，室内 +Y，街道在 -Y），Z 向上，米。
Unity 里与 Saloon.glb 一样把根节点绕 Y 转 180°，于是 Unity (x, y, z) = Blender (x, z, y)。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
import mc_common as mc
from mc_common import T, R, S

argv = mc.args()
RENDER = "--render" in argv
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 48
EXPORT = argv[argv.index("--export") + 1] if "--export" in argv else str(mc.ART / "Street" / "StreetBackdrop.glb")
SIGNS = mc.SRC / "_derived" / "street"

FRONT_Y = -14.0          # 对街立面正面（朝 +Y，朝向酒馆）
WALK_Y = -12.2           # 对街木栈道外沿
WALK_H = 0.35
ROAD_Y0 = -2.4           # 酒馆门前栈道外沿（Saloon.glb 自带 BoardwalkFront 到 -2.4）

sc = mc.reset()
C_EXP = bpy.data.collections.new("Street"); sc.collection.children.link(C_EXP)
C_REV = bpy.data.collections.new("Review"); sc.collection.children.link(C_REV)
ROOT_OBJ = mc.empty("StreetBackdrop", collection=C_EXP)

# ---------------------------------------------------------------- 材质
M = {
    "road":    mc.pbr("Road", "Ground080", tile=1.3, tint=(0.8, 0.72, 0.64), normal=0.5),
    "ground":  mc.pbr("Ground", "Ground054", tile=8.0, tint=(0.9, 0.8, 0.68), normal=0.3),
    "hills":   mc.pbr("Hills", "Ground033", tile=40.0, tint=(0.85, 0.7, 0.58), rough=0.95, normal=0.0),
    "mesa":    mc.pbr("Mesa", "Ground033", tile=60.0, tint=(0.80, 0.66, 0.62), rough=0.95, normal=0.0),
    "cream":   mc.pbr("SidingCream", "WoodSiding009", tile=2.4),
    "red":     mc.pbr("SidingRed", "WoodSiding002", tile=2.4, tint=(0.9, 0.85, 0.8)),
    "brown":   mc.pbr("SidingBrown", "WoodSiding004", tile=2.4),
    "grey":    mc.pbr("SidingGrey", "WoodSiding010", tile=2.4, tint=(1.1, 1.0, 0.9)),
    "white":   mc.pbr("Whitewash", "PaintedWood009C", tile=2.0),
    "blue":    mc.pbr("PaintBlue", "PaintedWood008B", tile=2.0),
    "trim":    mc.pbr("TrimCream", "PaintedWood009C", tile=1.5, tint=(1.0, 0.95, 0.85)),
    "green":   mc.pbr("TrimGreen", "PaintedWood009C", tile=1.5, tint=(0.38, 0.5, 0.42)),
    "dark":    mc.pbr("TrimDark", "Planks012", tile=1.5, tint=(0.55, 0.5, 0.45)),
    "planks":  mc.pbr("Boardwalk", "Planks012", tile=2.0),
    "roof":    mc.pbr("Roof", "WoodSiding010", tile=1.5, tint=(0.55, 0.5, 0.45)),
    "barrel":  mc.pbr("BarrelWood", "Wood066", tile=0.8),
    "iron":    mc.flat("Iron", (0.08, 0.07, 0.065), rough=0.55, metal=0.8),
    "window":  mc.flat("WindowGlass", (0.012, 0.014, 0.016), rough=0.06),
    "curtain": mc.pbr("Curtain", "Fabric040", tile=0.8, tint=(0.9, 0.8, 0.7)),
    "water":   mc.flat("TroughWater", (0.03, 0.035, 0.03), rough=0.03),
}
SIGN_MAT = {n: mc.image_mat(f"Sign_{n}", SIGNS / f"sign_{n}.jpg", rough=0.75)
            for n in ("general_store", "assay_office", "hotel", "feed_livery", "barber", "bank_window")}


def obj(part, name):
    return part.finish(name, parent=ROOT_OBJ, collection=C_EXP)


def swap_uv(part, faces):
    """把 UV 的 u/v 对调：让栈道木板沿 Y（垂直于街）铺。"""
    for f in faces:
        for lp in f.loops:
            u, v = lp[part.uv].uv; lp[part.uv].uv = (v, u)


def bx(part, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    return part.box((abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), mat,
                    xf=T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), bevel=bevel)


def hashf(*a):
    """确定性伪随机 0..1。"""
    s = math.sin(sum(v * k for v, k in zip(a, (12.9898, 78.233, 37.719, 4.581))) ) * 43758.5453
    return s - math.floor(s)


def grid(part, x0, x1, y0, y1, nx, ny, hfun, mat):
    """高度场网格（法线朝 +Z），UV = 世界 XY / tile。"""
    bm, uvl = part.bm, part.uv
    tile = mat.get("tile", 1.0); mi = part._mi(mat)
    vs = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny,
                         hfun(x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny)))
           for i in range(nx + 1)] for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            q = [vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]]
            if y1 < y0: q.reverse()
            f = bm.faces.new(q); f.material_index = mi; f.smooth = True
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x / tile, lp.vert.co.y / tile)


# ---------------------------------------------------------------- 路面与地面
def road_h(x, y):
    h = 0.0
    for c in (-5.6, -7.3, -8.9, -10.6):      # 两条车道各两道车辙
        h -= 0.06 * math.exp(-((y - c) / 0.2) ** 2)
    for c in (-6.45, -9.75):                 # 马蹄踩出的中间浅槽
        h -= 0.02 * math.exp(-((y - c) / 0.5) ** 2)
    h += 0.025 * math.sin(x * 0.7 + y * 1.3) * math.sin(x * 0.23 - y * 0.6)
    h += 0.012 * (hashf(round(x * 2), round(y * 5)) - 0.5)
    return h


p = mc.Part([M["road"]])
grid(p, -40, 40, WALK_Y, ROAD_Y0, 80, 49, road_h, M["road"])
obj(p, "Road")


def ground_h(x, y):
    d = min(1.0, max(0.0, -y - 30) / 60)  # 远处缓缓起伏
    return -0.08 + d * 1.5 * (math.sin(x * 0.05) * math.cos(y * 0.07) + 0.5 * math.sin(x * 0.11 + 1.3))


p = mc.Part([M["ground"]])
grid(p, -200, 200, -240, 30, 40, 30, ground_h, M["ground"])
obj(p, "Ground")


# 远山：两层剪影，近层黄褐，远层带空气透视的淡紫
def ridge(part, y_front, depth, xs, hmax, seed, mat, n=96, rows=5):
    def h(x, t):
        u = x * 0.012 + seed
        r = (0.55 + 0.25 * math.sin(u * 2.1) + 0.15 * math.sin(u * 5.3 + 1.7) + 0.08 * math.sin(u * 11.0 + seed))
        mesa = min(1.0, max(0.0, (math.sin(u * 1.3 + seed * 2) - 0.2) * 3))   # 平顶台地
        r = r * (1 - mesa) + 0.9 * mesa
        return hmax * r * math.sin(math.pi * t) ** 0.6
    bm, uvl = part.bm, part.uv
    tile = mat.get("tile", 1.0); mi = part._mi(mat)
    vs = [[bm.verts.new((xs[0] + (xs[1] - xs[0]) * i / n, y_front - depth * j / rows, h(xs[0] + (xs[1] - xs[0]) * i / n, j / rows) - 0.5))
           for i in range(n + 1)] for j in range(rows + 1)]
    for j in range(rows):
        for i in range(n):
            f = bm.faces.new([vs[j][i], vs[j + 1][i], vs[j + 1][i + 1], vs[j][i + 1]])
            f.material_index = mi; f.smooth = True
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x / tile, (lp.vert.co.z + lp.vert.co.y * 0.3) / tile)


p = mc.Part([M["hills"]]); ridge(p, -110, 60, (-300, 300), 13, 0.7, M["hills"]); obj(p, "Hills_Near")
p = mc.Part([M["mesa"]]); ridge(p, -230, 80, (-480, 480), 38, 3.1, M["mesa"], n=80); obj(p, "Hills_Far")


# ---------------------------------------------------------------- 对街建筑
def window(p, x, z0, w, h, frame=M["trim"], curtains=True, mull=(1, 2), y=FRONT_Y):
    """平贴在立面上的窗：深色反光玻璃 + 窗帘 + 窗框 + 窗棂。"""
    ft = 0.08
    bx(p, x - w / 2, x + w / 2, y, y + 0.02, z0, z0 + h, M["window"])
    if curtains:
        cw = w * 0.22
        for sgn in (-1, 1):
            cx = x + sgn * (w / 2 - cw / 2 - 0.02)
            bx(p, cx - cw / 2, cx + cw / 2, y + 0.02, y + 0.03, z0 + h * 0.08, z0 + h - 0.02, M["curtain"])
        bx(p, x - w / 2, x + w / 2, y + 0.02, y + 0.03, z0 + h * 0.86, z0 + h - 0.02, M["curtain"])
    bx(p, x - w / 2 - ft, x + w / 2 + ft, y, y + 0.07, z0 + h, z0 + h + ft * 1.6, frame)          # 窗楣
    bx(p, x - w / 2 - ft * 1.3, x + w / 2 + ft * 1.3, y, y + 0.1, z0 - ft, z0, frame)             # 窗台
    bx(p, x - w / 2 - ft, x - w / 2, y, y + 0.06, z0, z0 + h, frame)
    bx(p, x + w / 2, x + w / 2 + ft, y, y + 0.06, z0, z0 + h, frame)
    nx, nz = mull
    for i in range(1, nx):
        xx = x - w / 2 + w * i / nx
        bx(p, xx - 0.022, xx + 0.022, y, y + 0.05, z0, z0 + h, frame)
    for k in range(1, nz):
        zz = z0 + h * k / nz
        bx(p, x - w / 2, x + w / 2, y, y + 0.05, zz - 0.022, zz + 0.022, frame)


def door(p, x, w, h, frame=M["trim"], glass=True, z0=WALK_H, double=False, y=FRONT_Y):
    bx(p, x - w / 2, x + w / 2, y, y + 0.03, z0, z0 + h, M["dark"])
    if glass:
        leaves = (x - w / 4, x + w / 4) if double else (x,)
        lw = w / 2 if double else w
        for lx in leaves:
            bx(p, lx - lw * 0.32, lx + lw * 0.32, y + 0.03, y + 0.04, z0 + h * 0.5, z0 + h * 0.9, M["window"])
            bx(p, lx - lw * 0.32, lx + lw * 0.32, y + 0.03, y + 0.05, z0 + h * 0.12, z0 + h * 0.4, M["dark"])
    ft = 0.09
    bx(p, x - w / 2 - ft, x + w / 2 + ft, y, y + 0.08, z0 + h, z0 + h + ft * 2, frame)
    bx(p, x - w / 2 - ft, x - w / 2, y, y + 0.07, z0, z0 + h, frame)
    bx(p, x + w / 2, x + w / 2 + ft, y, y + 0.07, z0, z0 + h, frame)


def sign(p, x, z, w, h, name, frame=M["dark"], y=FRONT_Y):
    bx(p, x - w / 2 - 0.08, x + w / 2 + 0.08, y, y + 0.08, z - h / 2 - 0.08, z + h / 2 + 0.08, frame)
    yy = y + 0.085
    # 面朝 +Y：从酒馆看过去左手是 +X
    p.quad([(x + w / 2, yy, z - h / 2), (x - w / 2, yy, z - h / 2), (x - w / 2, yy, z + h / 2), (x + w / 2, yy, z + h / 2)],
           SIGN_MAT[name])


def boardwalk(p, x0, x1, step_x=None):
    f = bx(p, x0, x1, FRONT_Y, WALK_Y, WALK_H - 0.06, WALK_H, M["planks"])
    swap_uv(p, f)
    bx(p, x0, x1, WALK_Y + 0.0, WALK_Y + 0.05, 0.0, WALK_H - 0.06, M["dark"])   # 前沿挡板
    if step_x is not None:
        f = bx(p, step_x - 0.8, step_x + 0.8, WALK_Y, WALK_Y + 0.35, 0.0, WALK_H * 0.5, M["planks"]); swap_uv(p, f)


def awning(p, x0, x1, z=3.2, posts=None, slope=0.35, balcony=False):
    depth = FRONT_Y - (WALK_Y + 0.15)
    if balcony:
        bx(p, x0, x1, FRONT_Y, WALK_Y + 0.15, z, z + 0.14, M["planks"])
        bx(p, x0, x1, WALK_Y + 0.1, WALK_Y + 0.2, z - 0.25, z + 0.14, M["trim"])        # 横梁
        # 栏杆
        bx(p, x0, x1, WALK_Y + 0.13, WALK_Y + 0.21, z + 1.0, z + 1.07, M["trim"])
        n = int((x1 - x0) / 0.3)
        for i in range(n + 1):
            xx = x0 + (x1 - x0) * i / n
            bx(p, xx - 0.025, xx + 0.025, WALK_Y + 0.14, WALK_Y + 0.19, z + 0.14, z + 1.0, M["trim"])
        for sx in (x0, x1):
            bx(p, sx - 0.04, sx + 0.04, FRONT_Y, WALK_Y + 0.2, z + 1.0, z + 1.07, M["trim"])
    else:
        a = math.atan2(slope, abs(depth))
        L = abs(depth) / math.cos(a) + 0.3
        cy = (FRONT_Y + WALK_Y + 0.15) / 2
        p.box((x1 - x0 + 0.2, L, 0.06), M["roof"], xf=T((x0 + x1) / 2, cy + 0.1, z + slope / 2) @ R("X", -math.degrees(a)))
        bx(p, x0, x1, WALK_Y + 0.08, WALK_Y + 0.22, z - 0.2, z, M["trim"])
    for px in posts or []:
        bx(p, px - 0.07, px + 0.07, WALK_Y + 0.08, WALK_Y + 0.22, WALK_H, z, M["trim"])
        bx(p, px - 0.1, px + 0.1, WALK_Y + 0.05, WALK_Y + 0.25, WALK_H, WALK_H + 0.12, M["trim"])


def body(p, x0, x1, h, siding, depth=9.0, ridge=1.6, hf=99.0):
    """立面后的主体（坡屋顶藏在假立面后面：屋脊不高过假立面）。"""
    ridge = max(0.6, min(ridge, hf - h - 0.15))
    bx(p, x0 + 0.05, x1 - 0.05, FRONT_Y - 0.2 - depth, FRONT_Y - 0.2, 0, h, siding)
    w = x1 - x0; a = math.atan2(ridge, w / 2); L = (w / 2) / math.cos(a) + 0.25
    for sgn in (-1, 1):
        p.box((L, depth + 0.4, 0.08), M["roof"],
              xf=T((x0 + x1) / 2 + sgn * w / 4, FRONT_Y - 0.2 - depth / 2, h + ridge / 2) @ R("Y", sgn * math.degrees(a)))
    # 前后山墙三角（前面的藏在假立面后，从高处看也不漏空）
    for yb in (FRONT_Y - 0.2 - depth, FRONT_Y - 0.35):
        p.poly_extrude([(x0 + 0.05, h), (x1 - 0.05, h), ((x0 + x1) / 2, h + ridge)], 0.15, siding,
                       xf=T(0, yb + 0.15, 0) @ R("X", 90))


def facade(p, x0, x1, hf, siding, top="flat"):
    bx(p, x0, x1, FRONT_Y - 0.2, FRONT_Y, 0, hf, siding)
    # 墙角竖条 + 基脚
    for sx in (x0, x1 - 0.14):
        bx(p, sx, sx + 0.14, FRONT_Y, FRONT_Y + 0.05, 0, hf, M["trim"])
    # 檐口 + 托架
    bx(p, x0 - 0.12, x1 + 0.12, FRONT_Y - 0.2, FRONT_Y + 0.32, hf, hf + 0.12, M["trim"])
    bx(p, x0 - 0.05, x1 + 0.05, FRONT_Y, FRONT_Y + 0.2, hf - 0.25, hf, M["trim"])
    n = max(3, int((x1 - x0) / 0.9))
    for i in range(n + 1):
        xx = x0 + 0.15 + (x1 - x0 - 0.3) * i / n
        bx(p, xx - 0.05, xx + 0.05, FRONT_Y + 0.2, FRONT_Y + 0.3, hf - 0.32, hf, M["trim"])
    if top == "step":       # 阶梯形山花
        cx = (x0 + x1) / 2; w = (x1 - x0) * 0.4
        bx(p, cx - w / 2, cx + w / 2, FRONT_Y - 0.2, FRONT_Y, hf + 0.12, hf + 0.9, siding)
        bx(p, cx - w / 2 - 0.1, cx + w / 2 + 0.1, FRONT_Y - 0.2, FRONT_Y + 0.25, hf + 0.9, hf + 1.0, M["trim"])
    elif top == "pediment":  # 三角山花
        cx = (x0 + x1) / 2
        p.poly_extrude([(cx - 1.6, 0), (cx + 1.6, 0), (cx, 0.8)], 0.2, M["trim"], xf=T(0, FRONT_Y + 0.12, hf + 0.12) @ R("X", 90))


buildings = []

# 1) 饲料行 / 马房：红色谷仓板，大推拉门
p = mc.Part([M["red"]])
x0, x1, hf = -19.4, -11.2, 6.4
facade(p, x0, x1, hf, M["red"], top="step"); body(p, x0, x1, 4.6, M["red"], depth=12, hf=hf)
boardwalk(p, x0, x1)
bx(p, -16.9, -13.7, FRONT_Y, FRONT_Y + 0.05, WALK_H, 3.6, M["brown"])                     # 谷仓门
for xx in (-16.9, -15.3, -13.7):
    bx(p, xx - 0.07, xx + 0.07, FRONT_Y + 0.05, FRONT_Y + 0.1, WALK_H, 3.6, M["trim"])
for zz in (WALK_H + 0.05, 3.55):
    bx(p, -16.95, -13.65, FRONT_Y + 0.05, FRONT_Y + 0.1, zz - 0.07, zz + 0.07, M["trim"])
for a, b in ((-16.9, -15.3), (-15.3, -13.7)):  # X 撑
    L = math.hypot(b - a, 3.1); ang = math.degrees(math.atan2(3.1, b - a))
    for s in (1, -1):
        p.box((L, 0.04, 0.1), M["trim"], xf=T((a + b) / 2, FRONT_Y + 0.08, (WALK_H + 3.6) / 2) @ R("Y", -s * ang))
bx(p, -16.95, -13.65, FRONT_Y + 0.05, FRONT_Y + 0.12, 3.75, 3.85, M["iron"])                # 门轨
window(p, -18.3, 1.3, 1.0, 1.2, mull=(2, 2)); window(p, -12.3, 1.3, 1.0, 1.2, mull=(2, 2))
bx(p, -15.8, -14.8, FRONT_Y, FRONT_Y + 0.04, 4.15, 4.95, M["dark"])                          # 草料口
sign(p, -15.3, 5.35, 6.4, 1.3, "feed_livery")
buildings.append(obj(p, "Bldg_FeedLivery"))

# 2) 杂货店：奶油色护墙板，两层，大橱窗
p = mc.Part([M["cream"]])
x0, x1, hf = -10.2, -2.2, 7.6
facade(p, x0, x1, hf, M["cream"], top="pediment"); body(p, x0, x1, 6.2, M["cream"], depth=10, hf=hf)
boardwalk(p, x0, x1, step_x=-6.2)
bx(p, x0 + 0.2, x1 - 0.2, FRONT_Y, FRONT_Y + 0.06, WALK_H, WALK_H + 0.55, M["green"])       # 橱窗下护板
window(p, -8.4, WALK_H + 0.6, 2.4, 2.0, frame=M["green"], mull=(3, 2))
window(p, -4.0, WALK_H + 0.6, 2.4, 2.0, frame=M["green"], mull=(3, 2))
door(p, -6.2, 1.3, 2.5, frame=M["green"], double=True)
for xx in (-8.6, -6.2, -3.8):
    window(p, xx, 4.1, 0.9, 1.5, frame=M["green"], mull=(2, 2))
sign(p, -6.2, 6.25, 6.6, 1.55, "general_store", frame=M["green"])
awning(p, x0, x1, z=3.25, posts=[x0 + 0.2, -6.2 - 1.3, -6.2 + 1.3, x1 - 0.2])
buildings.append(obj(p, "Bldg_GeneralStore"))

# 3) 化验所（兼收金银）：白粉墙，一层，金字玻璃门
p = mc.Part([M["white"]])
x0, x1, hf = -1.2, 5.0, 5.6
facade(p, x0, x1, hf, M["white"], top="flat"); body(p, x0, x1, 4.4, M["white"], depth=8, hf=hf)
boardwalk(p, x0, x1, step_x=1.9)
window(p, 0.1, 1.15, 1.2, 1.8, frame=M["dark"], mull=(2, 3))
window(p, 3.7, 1.15, 1.2, 1.8, frame=M["dark"], mull=(2, 3))
door(p, 1.9, 1.1, 2.4, frame=M["dark"])
sign(p, 1.9, 2.95, 0.9, 0.22, "bank_window", frame=M["dark"], y=FRONT_Y + 0.05)            # 门上小金字牌
for xx in (0.1, 3.7):                                                                       # 化验所的铁窗栏
    for k in range(1, 6):
        bx(p, xx - 0.6 + 0.2 * k - 0.012, xx - 0.6 + 0.2 * k + 0.012, FRONT_Y + 0.09, FRONT_Y + 0.11, 1.15, 2.95, M["iron"])
sign(p, 1.9, 4.45, 5.4, 1.3, "assay_office")
awning(p, x0, x1, z=3.05, posts=[x0 + 0.2, x1 - 0.2], slope=0.3)
buildings.append(obj(p, "Bldg_AssayOffice"))

# 4) 旅馆：褪色蓝漆，两层带阳台
p = mc.Part([M["blue"]])
x0, x1, hf = 6.0, 16.4, 8.4
facade(p, x0, x1, hf, M["blue"], top="step"); body(p, x0, x1, 7.4, M["blue"], depth=12, hf=hf)
boardwalk(p, x0, x1, step_x=11.2)
for xx in (7.4, 9.2, 13.2, 15.0):
    window(p, xx, 1.0, 1.1, 1.9, mull=(2, 2))
door(p, 11.2, 1.5, 2.6, double=True)
for xx in (7.3, 9.1, 13.3, 15.1):
    window(p, xx, 4.15, 0.95, 1.7, mull=(2, 2))
door(p, 11.2, 1.0, 2.3, z0=3.62, glass=True)
awning(p, x0, x1, z=3.5, posts=[x0 + 0.2, 8.8, 11.2 - 1.2, 11.2 + 1.2, 13.6, x1 - 0.2], balcony=True)
sign(p, 11.2, 7.1, 6.0, 1.5, "hotel", frame=M["trim"])
buildings.append(obj(p, "Bldg_Hotel"))

# 5) 理发店：灰色旧木板小铺
p = mc.Part([M["grey"]])
x0, x1, hf = 17.2, 22.0, 4.6
facade(p, x0, x1, hf, M["grey"]); body(p, x0, x1, 3.6, M["grey"], depth=7, hf=hf)
boardwalk(p, x0, x1)
window(p, 18.4, 1.1, 1.2, 1.5, mull=(2, 2)); door(p, 20.6, 1.0, 2.3)
sign(p, 19.6, 3.75, 3.6, 0.9, "barber")
buildings.append(obj(p, "Bldg_Barber"))
# 理发柱
p = mc.Part([M["trim"]])
p.lathe([(0, 0, 0), (0, 0.07, 0.07), (1.2, 0.07, 0.07), (1.2, 0, 0)], mc.flat("BarberPole", (0.75, 0.1, 0.08), rough=0.4), seg=10,
        xf=T(19.9, FRONT_Y + 0.3, WALK_H + 1.3))
p.sphere(0.09, M["trim"], xf=T(19.9, FRONT_Y + 0.3, WALK_H + 2.55), seg=10, rings=6)
obj(p, "BarberPole")

# 6) 两侧的旧棚屋（斜看窗外时的填充）
for name, x0, x1, h, mat in (("Shack_W", -27.0, -21.0, 4.2, M["brown"]), ("Shack_E", 23.4, 29.0, 4.0, M["grey"])):
    p = mc.Part([mat])
    facade(p, x0, x1, h, mat); body(p, x0, x1, 3.4, mat, depth=7, hf=h)
    window(p, (x0 + x1) / 2 - 1.2, 1.2, 1.0, 1.2, mull=(2, 2), curtains=False)
    door(p, (x0 + x1) / 2 + 1.2, 1.0, 2.2, z0=0.0, glass=False)
    obj(p, name)

# ---------------------------------------------------------------- 街道小物
props = mc.Part([M["dark"]])


def hitching_post(x0, x1, y):
    for xx in (x0, x1):
        bx(props, xx - 0.07, xx + 0.07, y - 0.07, y + 0.07, -0.1, 1.05, M["dark"], bevel=0.01)
    bx(props, x0 - 0.12, x1 + 0.12, y - 0.05, y + 0.05, 0.95, 1.05, M["dark"], bevel=0.01)


for x0, x1, y in ((-17.5, -15.0, WALK_Y + 0.6), (-13.0, -10.6, WALK_Y + 0.6), (7.0, 9.6, WALK_Y + 0.6),
                  (13.0, 15.6, WALK_Y + 0.6), (-6.0, -3.6, ROAD_Y0 - 0.5), (4.2, 6.6, ROAD_Y0 - 0.5)):
    hitching_post(x0, x1, y)

# 水槽（饲料行门口）
tx, ty = -12.0, WALK_Y + 1.6
bx(props, tx - 1.1, tx + 1.1, ty - 0.35, ty + 0.35, 0.05, 0.12, M["planks"])
for sy in (-1, 1):
    bx(props, tx - 1.1, tx + 1.1, ty + sy * 0.33 - 0.03, ty + sy * 0.33 + 0.03, 0.05, 0.6, M["planks"])
for sx in (-1, 1):
    bx(props, tx + sx * 1.08 - 0.03, tx + sx * 1.08 + 0.03, ty - 0.36, ty + 0.36, 0.05, 0.6, M["planks"])
for sx in (-0.9, 0.9):
    bx(props, tx + sx - 0.06, tx + sx + 0.06, ty - 0.42, ty + 0.42, 0.0, 0.1, M["dark"])
bx(props, tx - 1.05, tx + 1.05, ty - 0.3, ty + 0.3, 0.45, 0.47, M["water"])
for sx in (-0.7, 0.7):
    bx(props, tx + sx - 0.03, tx + sx + 0.03, ty - 0.37, ty + 0.37, 0.42, 0.64, M["iron"])


def barrel(x, y, z=0.0, h=0.9, r=0.3):
    prof = [(0, 0, 0)] + [(h * t, r * (0.86 + 0.14 * math.sin(math.pi * t)), r * (0.86 + 0.14 * math.sin(math.pi * t)))
                         for t in [i / 8 for i in range(9)]] + [(h, 0, 0)]
    props.lathe(prof, M["barrel"], seg=14, xf=T(x, y, z))
    for t in (0.12, 0.35, 0.65, 0.88):
        rr = r * (0.86 + 0.14 * math.sin(math.pi * t)) + 0.006
        props.lathe([(h * t - 0.025, rr, rr), (h * t + 0.025, rr, rr)], M["iron"], seg=14, xf=T(x, y, z), cap=False)


for x, y in ((-9.8, FRONT_Y + 0.45), (-9.2, FRONT_Y + 0.5), (-2.8, FRONT_Y + 0.45), (16.0, FRONT_Y + 0.45),
             (-19.0, FRONT_Y + 0.5)):
    barrel(x, y, WALK_H)
barrel(-8.8, ROAD_Y0 - 0.6, 0.0); barrel(-8.25, ROAD_Y0 - 0.75, 0.0)

# 木箱（杂货店门口）
for x, y, z, s in ((-3.3, FRONT_Y + 0.5, WALK_H, 0.55), (-3.3, FRONT_Y + 0.5, WALK_H + 0.55, 0.45), (-2.75, FRONT_Y + 0.55, WALK_H, 0.5)):
    bx(props, x - s / 2, x + s / 2, y - s / 2, y + s / 2, z, z + s, M["planks"], bevel=0.015)


def wheel(cx, cy, cz, r, spokes=12):
    xf = T(cx, cy, cz) @ R("X", 90)
    props.lathe([(-0.035, r, r), (0.035, r, r)], M["iron"], seg=20, xf=xf, cap=False)                # 铁箍
    props.lathe([(-0.04, r - 0.012, r - 0.012), (0.04, r - 0.012, r - 0.012)], M["dark"], seg=20, xf=xf @ R("Z", 9), cap=False)
    props.lathe([(-0.09, 0, 0), (-0.09, 0.09, 0.09), (0.09, 0.07, 0.07), (0.09, 0, 0)], M["dark"], seg=10, xf=xf)  # 轮毂
    for k in range(spokes):
        a = 360 * k / spokes
        props.box((0.035, r - 0.08, 0.03), M["dark"], xf=T(cx, cy, cz) @ R("Y", a) @ T(0, 0, (r - 0.04) / 2) @ R("X", 90))


# 停在对街的平板马车（沿街朝 -X）
wx, wy = 8.6, -9.4
bx(props, wx - 1.5, wx + 1.5, wy - 0.6, wy + 0.6, 0.78, 0.84, M["planks"])
for sy in (-1, 1):
    bx(props, wx - 1.5, wx + 1.5, wy + sy * 0.6 - 0.03, wy + sy * 0.6 + 0.03, 0.84, 1.14, M["planks"])
for sx in (-1, 1):
    bx(props, wx + sx * 1.5 - 0.03, wx + sx * 1.5 + 0.03, wy - 0.6, wy + 0.6, 0.84, 1.14, M["planks"])
bx(props, wx - 1.3, wx + 1.3, wy - 0.05, wy + 0.05, 0.55, 0.78, M["dark"])                           # 纵梁
bx(props, wx - 0.95, wx - 0.85, wy - 0.75, wy + 0.75, 0.38, 0.5, M["dark"])                           # 前轴
bx(props, wx + 1.05, wx + 1.15, wy - 0.75, wy + 0.75, 0.5, 0.62, M["dark"])                           # 后轴
for sy in (-1, 1):
    wheel(wx - 0.9, wy + sy * 0.74, 0.44, 0.44)
    wheel(wx + 1.1, wy + sy * 0.74, 0.56, 0.56)
L = 2.4; ang = math.degrees(math.atan2(0.4, L))
props.box((L, 0.07, 0.07), M["dark"], xf=T(wx - 0.9 - L / 2, wy, 0.25) @ R("Y", -ang))                # 车辕拖地
bx(props, wx - 1.45, wx - 1.05, wy - 0.55, wy + 0.55, 1.14, 1.2, M["planks"])                         # 车夫座
bx(props, wx - 1.4, wx - 1.1, wy - 0.5, wy + 0.5, 0.84, 1.14, M["dark"])
for i, (dx, dy) in enumerate(((0.4, -0.25), (0.9, 0.2))):                                             # 车上的麻袋 / 箱子
    bx(props, wx + dx - 0.25, wx + dx + 0.25, wy + dy - 0.2, wy + dy + 0.2, 0.84, 1.24, M["planks"], bevel=0.015)
obj(props, "StreetProps")

# ---------------------------------------------------------------- 统计 + 导出
exp_objs = [o for o in mc.descendants(ROOT_OBJ)]
tris = mc.tri_count(exp_objs)
print(f"TRIS total {tris}")
for o in exp_objs:
    if o.type == "MESH":
        print(f"  {o.name:20s} {mc.tri_count([o])}")
if EXPORT:
    mc.export_glb(EXPORT, [ROOT_OBJ])

# ---------------------------------------------------------------- 评审渲染
if RENDER:
    mc.setup_render(SAMPLES, exposure=0.0)
    mc.world_hdri("goegap_road", strength=0.9, rot=140)
    sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 5.0; sun_d.angle = math.radians(0.6)
    sun_d.color = (1.0, 0.85, 0.66)
    sun = bpy.data.objects.new("Sun", sun_d); C_REV.objects.link(sun)
    # 与 build_saloon.py 相同的太阳方向（从街道一侧低角度照进酒馆）
    sun.rotation_euler = (math.radians(60), 0, math.radians(20))

    mc.camera("Cam_Street", (-1.0, 0.5, 2.6), (-0.5, -14.0, 3.4), lens=16, coll=C_REV)
    mc.render(mc.REVIEWS / "StreetBackdrop.png")
    mc.camera("Cam_Aerial", (-12.0, 6.0, 12.0), (2.0, -20.0, 0.0), lens=22, coll=C_REV)
    mc.render(mc.REVIEWS / "StreetBackdrop_aerial.png")

    # 仿酒馆前墙（只用于渲染，不导出）：看窗外是什么
    mock = mc.Part([mc.flat("MockWall", (0.25, 0.17, 0.11), rough=0.8)])
    wm = mock.mats[0]
    def mb(x0, x1, y0, y1, z0, z1): bx(mock, x0, x1, y0, y1, z0, z1, wm)
    mb(-7, 7, 0, 10, -0.2, 0); mb(-7, 7, 0, 10, 6.4, 6.6)
    xs = [-7, -5.4, -2.6, -0.9, 0.9, 2.6, 5.4, 7]
    holes = {(-5.4, -2.6): (0.9, 2.8), (2.6, 5.4): (0.9, 2.8), (-0.9, 0.9): (0.0, 2.7)}
    for a, b in zip(xs, xs[1:]):
        hz = holes.get((a, b))
        if hz:
            if hz[0] > 0: mb(a, b, -0.2, 0, 0, hz[0])
            mb(a, b, -0.2, 0, hz[1], 6.4)
        else:
            mb(a, b, -0.2, 0, 0, 6.4)
    for x0w, x1w in ((-5.4, -2.6), (2.6, 5.4)):
        mid = (x0w + x1w) / 2
        mb(mid - 0.03, mid + 0.03, -0.12, -0.08, 0.9, 2.8)
        for zz in (0.9 + 1.9 / 3, 0.9 + 3.8 / 3):
            mb(x0w, x1w, -0.12, -0.08, zz - 0.025, zz + 0.025)
    mb(-8, 8, -2.4, -0.2, 0, 0.25)          # 酒馆门前栈道
    mb(-8, 8, -2.6, 0, 3.7, 3.8)            # 雨棚
    mock.finish("MockSaloon", collection=C_REV)
    mc.camera("Cam_Window", (3.4, 3.2, 1.6), (3.0, -14.0, 2.6), lens=24, coll=C_REV)
    sc.view_settings.exposure = 0.3
    mc.render(mc.REVIEWS / "StreetBackdrop_window.png")
