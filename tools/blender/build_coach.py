"""康科德式驿站马车（Concord coach）：蛋形车厢吊在两条皮吊带（thoroughbrace）上，褪色红漆车厢、黄色走行部、
铁箍木轮（后轮 1.5 m、前轮 1.15 m）、车顶行李栏、后行李舱、车夫座 + 脚踏板，加双马的辕杆、平衡横木、单马横木、颈轭。

blender --background --python tools/blender/build_coach.py -- [--no-render] [--samples N]
先跑：build_horse.py 和 build_mannequin.py（评审图要导入 Horse.gltf / Mannequin_Driver.gltf 摆在挂点上）
输出：Game/Assets/_MercyCreek/Art/Vehicles/Stagecoach.gltf；评审图 Reviews/blender/Stagecoach.png（+ _side / _door）
坐标：车头朝 Blender -Y（= glTFast 导入后 Unity +Z，不用额外旋转；Unity (x,y,z) = Blender (-x,z,-y)），Z 向上，
根节点 Stagecoach 在两轴中点正下方的地面。L = 车的左边 = Blender +X = Unity -X。
层级：Stagecoach → Chassis → Wheel_FL/FR/RL/RR（原点在轮毂中心，绕局部 X 转）、Body（原点在吊带最低点 = 摇摆轴心）
      → Door_L/Door_R（原点在合页轴上）、DriverSeat；Stagecoach → PassengerExit_L、Hitch_L、Hitch_R（地面点）。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy, bmesh
from mathutils import Vector, Matrix, Euler
import mc_common as mc
from mc_common import T, R, S, Part
import build_horse as bh

A = mc.args()
RENDER = "--no-render" not in A
SAMPLES = int(A[A.index("--samples") + 1]) if "--samples" in A else 64
OUT = mc.ART / "Vehicles" / "Stagecoach.gltf"
MAX_TRIS = 40000
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0)); Z = Vector((0, 0, 1))
YZX = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # 局部 X→世界 Y、Y→Z、Z→X（在 YZ 画侧面再沿 X 挤出）

# ------------------------------------------------------------------ 尺寸（米，Blender 世界坐标）
FA_Y, RA_Y = -1.2, 1.2          # 前 / 后轴
TRACK = 0.80                    # 轮中心面 x
RF, RR = 0.575, 0.75            # 前 / 后轮半径（含铁箍）
BRACE_X, BRACE_Z, JACK_Y, JACK_Z = 0.48, 0.95, 1.06, 1.22   # 吊带：x 位置、最低点中心高、两端吊架顶
PIVOT = Vector((0, 0, BRACE_Z))                              # Body 原点
SEAT_TOP, SEAT_Y, DRIVER_X = 2.22, -1.07, -0.22             # 车夫坐垫顶高、车夫髋关节 y、车夫在右边（刹车杆一侧）
HIP_DROP = 0.85                 # 坐姿人偶：根节点到坐面的高度（髋 0.92 - 大腿半径 0.07）
HITCH_X, HITCH_Y = 0.62, -3.0   # 两匹马根节点（地面、身体中心）
DOOR_Y0, DOOR_Y1, DOOR_Z0, DOOR_Z1 = -0.29, 0.29, 1.12, 2.05
WIN_Z0, WIN_Z1 = 1.62, 2.02
NEXP = 5.0                      # 车厢俯视截面的超椭圆指数（侧板近乎平直，四角圆）
# 车厢水平切片：z → 半长 a、半宽 b（侧视是"蛋形"：底部弧线上翘，腰线最宽，往上略收）
BODY = [(0.975, 0.14, 0.5), (0.985, 0.32, 0.56), (1.02, 0.53, 0.6), (1.08, 0.69, 0.63), (1.16, 0.805, 0.65), (1.26, 0.89, 0.665),
        (1.36, 0.95, 0.675), (1.45, 0.985, 0.68), (1.55, 0.978, 0.677), (1.75, 0.955, 0.667), (2.0, 0.925, 0.655), (2.2, 0.902, 0.645),
        (2.26, 0.895, 0.64)]


def ab(z):
    if z <= BODY[0][0]: return BODY[0][1:]
    for p, q in zip(BODY, BODY[1:]):
        if p[0] <= z <= q[0]:
            k = (z - p[0]) / (q[0] - p[0]); kk = k * k * (3 - 2 * k) * 0.35 + k * 0.65
            return p[1] + (q[1] - p[1]) * kk, p[2] + (q[2] - p[2]) * kk
    return BODY[-1][1:]


def sell(a, b, th, n=NEXP):
    c, s = math.cos(th), math.sin(th)
    return Vector((b * math.copysign(abs(c) ** (2 / n), c), a * math.copysign(abs(s) ** (2 / n), s), 0))


def surf_x(y, z, off=0.0):
    """车厢外表面在 (y, z) 处的 |x|（左侧为正）。"""
    a, b = ab(z); a += off; b += off
    q = 1 - (abs(y) / a) ** NEXP
    return b * q ** (1 / NEXP) if q > 0 else 0.0


def brace_z(y):
    k = (JACK_Z - BRACE_Z) / JACK_Y ** 2
    return BRACE_Z + k * y * y


# ------------------------------------------------------------------ 材质
def materials():
    M = {}
    M["paint"] = mc.pbr("CoachRed", "PaintedWood009C", tile=1.2, tint=(0.62, 0.17, 0.11), rough_mul=0.9)
    M["trim"] = mc.pbr("CoachOchre", "PaintedWood009C", tile=0.8, tint=(0.82, 0.58, 0.24), rough_mul=0.9)
    M["gear"] = mc.pbr("CoachYellow", "PaintedWood009C", tile=1.0, tint=(0.86, 0.66, 0.3), rough_mul=0.95)
    M["interior"] = mc.pbr("CoachInterior", "Leather037", tile=0.4, tint=(0.32, 0.16, 0.12), rough_mul=0.9)
    M["leather"] = mc.pbr("CoachLeather", "Leather030", tile=0.4, tint=(0.38, 0.28, 0.22), rough_mul=0.85)
    M["boot"] = mc.pbr("BootLeather", "Leather037", tile=0.6, tint=(0.3, 0.24, 0.2), rough_mul=0.9)
    M["iron"] = mc.pbr("CoachIron", "Metal027", tile=0.4, tint=(0.42, 0.4, 0.38), metal=0.85, normal=0.5)
    M["wood"] = mc.pbr("TrunkWood", "Wood066", tile=0.6, tint=(0.8, 0.7, 0.6))
    M["canvas"] = mc.pbr("Tarp", "Fabric066", tile=0.5, tint=(0.62, 0.56, 0.46), normal=0.9)
    M["brass"] = mc.flat("CoachBrass", (0.6, 0.45, 0.22), rough=0.4, metal=1.0)
    M["gold"] = mc.flat("GoldLeaf", (0.72, 0.52, 0.2), rough=0.5, metal=0.6)
    M["glass"] = mc.flat("LampGlass", (0.75, 0.7, 0.55), rough=0.15, metal=0.0)
    M["dark"] = mc.flat("WindowDark", (0.02, 0.015, 0.012), rough=0.8)
    return M


# ------------------------------------------------------------------ 小工具
def loft(p, pts, mat, seg=8, hint=X, closed=False):
    return bh.loft(p, pts, mat, seg=seg, hint=hint, closed=closed)


def rod(p, a, b, r, mat, seg=8, hint=Z, rb=None):
    a, b = Vector(a), Vector(b); d = (b - a).normalized() * 0.001
    loft(p, [(a - d, 0, 0), (a, r, r), (b, rb or r, rb or r), (b + d, 0, 0)], mat, seg=seg, hint=hint)


def beam(p, a, b, w, h, mat, up=Z, bevel=0.008):
    """两点之间的方木（截面 w × h，h 沿 up）。"""
    a, b = Vector(a), Vector(b); d = b - a; L = d.length; f = d.normalized()
    u = (Vector(up) - f * f.dot(up)).normalized(); s = f.cross(u)
    M = Matrix((s, f, u)).transposed().to_4x4()
    p.box((w, L, h), mat, xf=T(*((a + b) / 2)) @ M, bevel=bevel)


def ring_pts(z, off, n=56, y0=-1.0, y1=1.0, side=None):
    a, b = ab(z); a += off; b += off
    pts = [sell(a, b, 2 * math.pi * j / n) for j in range(n)]
    return [Vector((q.x, q.y, z)) for q in pts]


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = objs[0]; ob.name = name; ob.data.name = name
    return ob


def apply_mod(ob, m):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)


def boolean(ob, cutter, op):
    m = ob.modifiers.new("bool", "BOOLEAN"); m.operation = op; m.object = cutter
    try: m.solver = "EXACT"
    except Exception: pass
    apply_mod(ob, m)


def cutter_box(name, x0, x1, y0, y1, z0, z1):
    p = Part([bpy.data.materials.get("CoachRed")])
    p.box((x1 - x0, y1 - y0, z1 - z0), p.mats[0], xf=T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    ob = p.finish(name); ob.hide_render = True
    return ob


def set_origin(ob, pivot, parent=None, parent_pivot=Vector()):
    ob.data.transform(T(*(-Vector(pivot))))
    ob.parent = parent; ob.location = Vector(pivot) - Vector(parent_pivot)


# ------------------------------------------------------------------ 车轮（局部：原点 = 轮毂中心，轴 = X）
def wheel(name, M, r, nspokes, out):
    p = Part([M["gear"]])
    G, I = M["gear"], M["iron"]
    hub_r = 0.085 if r > 0.7 else 0.075
    fel_d, fel_w, tyre_t = 0.07, 0.062, 0.013
    rin = r - tyre_t - fel_d
    dish = 0.035 * out
    ax = R("Y", 90)   # 局部 Z → 世界 X
    # 轮毂：腰鼓形木毂 + 两端铁箍 + 外端轴帽
    hp = [(-0.15, 0.0, 0.0), (-0.15, hub_r * 0.62, hub_r * 0.62), (-0.13, hub_r * 0.78, hub_r * 0.78), (-0.07, hub_r * 0.98, hub_r * 0.98),
          (0.0, hub_r, hub_r), (0.06, hub_r * 0.97, hub_r * 0.97), (0.11, hub_r * 0.8, hub_r * 0.8), (0.14, hub_r * 0.66, hub_r * 0.66), (0.14, 0, 0)]
    hp = [(z * out, rr, ry) for z, rr, ry in hp]
    if out < 0: hp = list(reversed(hp))
    p.lathe(hp, G, seg=20, xf=ax)
    for z0, rr in ((-0.13, 0.8), (0.11, 0.82)):
        z0 *= out
        p.lathe([(z0 - 0.012, hub_r * rr + 0.004, hub_r * rr + 0.004), (z0 + 0.012, hub_r * rr + 0.004, hub_r * rr + 0.004)], I, seg=20, xf=ax, cap=False)
    cap = [(0.14, 0.05, 0.05), (0.175, 0.045, 0.045), (0.185, 0.03, 0.03), (0.19, 0, 0)]
    cap = [(z * out, a_, b_) for z, a_, b_ in cap]
    if out < 0: cap = list(reversed(cap))
    p.lathe(cap, I, seg=12, xf=ax)
    # 辐条：椭圆截面（沿轴向更厚），向外"碟"出 dish
    for k in range(nspokes):
        th = 2 * math.pi * (k + 0.5) / nspokes
        dr = Vector((0, math.cos(th), math.sin(th)))
        a = dr * (hub_r * 0.9) + X * 0.0
        b = dr * (rin + 0.02) + X * dish
        mid = a.lerp(b, 0.25)
        loft(p, [(a - (b - a).normalized() * 0.01, 0, 0), (a, 0.026, 0.019), (mid, 0.024, 0.018), (b, 0.018, 0.013), (b + (b - a).normalized() * 0.005, 0, 0)],
             G, seg=8, hint=X)
    # 轮辋（felloe）：矩形截面圆环；铁箍更宽、更薄
    def rect_ring(r0, r1, w, xo, mat, seg=56):
        prof = [(xo - w / 2, r0, r0), (xo - w / 2, r1, r1), (xo + w / 2, r1, r1), (xo + w / 2, r0, r0), (xo - w / 2, r0, r0)]
        p.lathe(prof, mat, seg=seg, xf=ax, cap=False)
    rect_ring(rin, r - tyre_t, fel_w, dish, G)
    rect_ring(r - tyre_t - 0.001, r, fel_w + 0.008, dish, I)
    ob = p.finish(name, smooth_angle=35)
    return ob


# ------------------------------------------------------------------ 走行部（Chassis，局部原点 = 根）
def chassis(M):
    p = Part([M["gear"]])
    G, I, L = M["gear"], M["iron"], M["leather"]
    for ya, r in ((FA_Y, RF), (RA_Y, RR)):
        rod(p, (-TRACK - 0.02, ya, r), (TRACK + 0.02, ya, r), 0.035, I, seg=10, hint=Z)          # 铁轴
        beam(p, (-TRACK + 0.13, ya, r + 0.07), (TRACK - 0.13, ya, r + 0.07), 0.11, 0.1, G)        # 轴床
    fz = RF + 0.07
    # 前：枕木 + 第五轮（转向圈）
    beam(p, (-0.62, FA_Y, fz + 0.1), (0.62, FA_Y, fz + 0.1), 0.12, 0.09, G)
    loft(p, [(Vector((0.36 * math.cos(a), FA_Y + 0.36 * math.sin(a), fz + 0.053)), 0.012, 0.012) for a in
             [2 * math.pi * j / 24 for j in range(24)]], I, seg=6, hint=Z, closed=True)
    # 纵梁（reach）：前轴到后轴，从吊带下面穿过
    rz = RR + 0.07
    beam(p, (0, FA_Y - 0.05, fz + 0.02), (0, -0.4, 0.78), 0.1, 0.08, G)
    beam(p, (0, -0.4, 0.78), (0, 0.4, 0.78), 0.1, 0.08, G)
    beam(p, (0, 0.4, 0.78), (0, RA_Y + 0.05, rz + 0.02), 0.1, 0.08, G)
    for e in (1, -1):   # 斜撑（从轴床到纵梁）
        beam(p, (0.5 * e, RA_Y, rz + 0.02), (0.04 * e, 0.45, 0.78), 0.06, 0.06, G)
        beam(p, (0.5 * e, FA_Y, fz + 0.06), (0.04 * e, -0.5, 0.78), 0.06, 0.06, G)
    # 吊架（jack）：轴床两端的立柱，顶端铁吊环挂皮吊带
    for ya, zb in ((-JACK_Y, fz + 0.12), (JACK_Y, rz + 0.04)):
        yb = FA_Y if ya < 0 else RA_Y
        for e in (1, -1):
            top = Vector((BRACE_X * e, ya, JACK_Z))
            beam(p, (BRACE_X * e, yb, zb), top + Vector((0, 0, -0.03)), 0.08, 0.08, G, up=Y)
            beam(p, (BRACE_X * e, yb + (0.2 if ya < 0 else -0.2), zb), top + Vector((0, 0.04 * (1 if ya < 0 else -1), -0.12)), 0.05, 0.05, I, up=Y)
            loft(p, [(top + Vector((0, 0.06 * math.cos(a), 0.06 * math.sin(a))), 0.012, 0.012) for a in
                     [2 * math.pi * j / 12 for j in range(12)]], I, seg=6, hint=X, closed=True)
    # 皮吊带：每侧一条厚皮叠层带，两端绕在吊环上，中间托住车厢底
    for e in (1, -1):
        pts = [(Vector((BRACE_X * e, y, brace_z(y))), 0.04, 0.025) for y in [-JACK_Y + 2 * JACK_Y * k / 24 for k in range(25)]]
        loft(p, pts, L, seg=8, hint=X)
        for ya in (-JACK_Y, JACK_Y):
            loft(p, [(Vector((BRACE_X * e, ya, JACK_Z)) + Vector((0, 0.05 * math.cos(a), 0.05 * math.sin(a))), 0.04, 0.012)
                     for a in [2 * math.pi * j / 12 for j in range(12)]], L, seg=6, hint=X, closed=True)
    # 刹车横梁 + 闸瓦（贴在后轮前缘）
    bz = 0.55; by = RA_Y - math.sqrt(RR ** 2 - (bz - RR) ** 2) - 0.045
    beam(p, (-TRACK + 0.05, by, bz), (TRACK - 0.05, by, bz), 0.07, 0.07, G)
    for e in (1, -1):
        beam(p, (TRACK * e, by + 0.01, bz - 0.12), (TRACK * e, by - 0.01, bz + 0.12), 0.08, 0.05, L, up=Y)
        beam(p, (0.62 * e, by, bz + 0.03), (0.5 * e, RA_Y - 0.3, rz + 0.05), 0.04, 0.04, I)
    # 辕杆：从前轴的辕叉（hounds）伸到两马之间，尖端铁箍
    tip = Vector((0, -3.97, 1.08)); butt = Vector((0, FA_Y + 0.15, fz))
    loft(p, [(butt + Vector((0, 0.02, 0)), 0, 0), (butt, 0.05, 0.05), (butt.lerp(tip, 0.4), 0.052, 0.052), (tip, 0.034, 0.034), (tip + Vector((0, -0.01, 0)), 0, 0)],
         G, seg=12, hint=Z)
    rod(p, tip + Vector((0, 0.12, -0.01)), tip + Vector((0, -0.005, 0)), 0.04, I, seg=10)
    for e in (1, -1):
        beam(p, (0.62 * e, FA_Y, fz + 0.03), butt.lerp(tip, 0.18) + Vector((0.03 * e, 0, 0)), 0.05, 0.05, G)
    # 平衡横木（evener）+ 两根单马横木（whiffletree），挽钩在两端
    ev_y, ev_z = -1.62, 0.78
    pz = butt.z + (tip.z - butt.z) * ((butt.y - ev_y) / (butt.y - tip.y))
    beam(p, (0, ev_y, pz), (0, ev_y, ev_z - 0.03), 0.07, 0.07, I, up=Y)
    beam(p, (-0.66, ev_y, ev_z), (0.66, ev_y, ev_z), 0.08, 0.07, G)
    wt = {}
    for e in (1, -1):
        cx = HITCH_X * e
        beam(p, (cx, ev_y, ev_z), (cx, ev_y - 0.06, ev_z), 0.04, 0.04, I)
        beam(p, (cx - 0.37, ev_y - 0.07, ev_z), (cx + 0.37, ev_y - 0.07, ev_z), 0.06, 0.06, G)
        for ex in (-1, 1):
            hx = cx + 0.37 * ex
            rod(p, (hx, ev_y - 0.07, ev_z), (hx, ev_y - 0.12, ev_z), 0.012, I, seg=6)
            wt[(e, ex)] = Vector((hx, ev_y - 0.12, ev_z))
    # 挽绳：从单马横木两端接到马身上挽绳残段的末端（build_horse.TRACE_END）
    for e in (1, -1):
        hx0 = HITCH_X * e
        for side in (1, -1):   # side：马自己的左(+)/右(-)
            end = Vector((hx0 + bh.TRACE_END.x * side, HITCH_Y + bh.TRACE_END.y, bh.TRACE_END.z))
            w_ = wt[(e, 1 if end.x > hx0 else -1)]
            pts = [(w_.lerp(end, k / 8) - Vector((0, 0, 0.05 * math.sin(math.pi * k / 8))), 0.024, 0.007) for k in range(9)]
            loft(p, pts, L, seg=6, hint=Z)
    # 颈轭：挂在两马颈圈底下，辕杆尖穿过中间
    yk = tip.y + 0.09
    collar_bot = bh.NECK + (bh.HEAD - bh.NECK) * 0.2
    t_ = (bh.HEAD - bh.NECK).normalized(); v_ = t_.cross(X)
    collar_bot = collar_bot + v_ * 0.02 - v_ * 0.3
    beam(p, (-0.72, yk, tip.z + 0.02), (0.72, yk, tip.z + 0.02), 0.07, 0.07, G)
    for e in (1, -1):
        cb = Vector((HITCH_X * e, HITCH_Y + collar_bot.y, collar_bot.z))
        loft(p, [(Vector((HITCH_X * e, yk, tip.z + 0.05)), 0.02, 0.006), (cb, 0.02, 0.006)], L, seg=6, hint=Y)
    return p.finish("Chassis", smooth_angle=35)


# ------------------------------------------------------------------ 车厢
def body_shell(M):
    """外壳：水平超椭圆切片堆成的封闭体 → 向内加厚（内表面用内饰材质）→ 切门洞和窗洞。返回 (body, doors{side: ob})。"""
    p = Part([M["paint"], M["interior"]])
    P_, I_ = M["paint"], M["interior"]
    zs = []
    for p0, p1 in zip(BODY, BODY[1:]):
        n = max(1, int(round((p1[0] - p0[0]) / 0.05)))
        zs += [p0[0] + (p1[0] - p0[0]) * k / n for k in range(n)]
    zs.append(BODY[-1][0])
    N = 64
    bm, uvl = p.bm, p.uv
    rings = [[bm.verts.new(v) for v in ring_pts(z, 0.0, N)] for z in zs]
    tile = P_["tile"]; per = 2 * (BODY[7][1] + BODY[7][2]) * 1.6
    faces = []
    for i in range(len(rings) - 1):
        for j in range(N):
            jn = (j + 1) % N
            f = bm.faces.new([rings[i][j], rings[i][jn], rings[i + 1][jn], rings[i + 1][j]])
            for lp, (u, v) in zip(f.loops, [(j, zs[i]), (j + 1, zs[i]), (j + 1, zs[i + 1]), (j, zs[i + 1])]):
                lp[uvl].uv = (u / N * per / tile, v / tile)
            faces.append(f)
    for ring, top in ((rings[0], False), (rings[-1], True)):
        f = bm.faces.new(ring if top else list(reversed(ring)))
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / tile, lp.vert.co.y / tile)
        faces.append(f)
    p._take(faces, P_, True)
    shell = p.finish("BodyShell", smooth_angle=50)
    m = shell.modifiers.new("solid", "SOLIDIFY"); m.thickness = 0.03; m.offset = -1.0; m.material_offset = 1; m.use_even_offset = True
    apply_mod(shell, m)
    # 门板 = 外壳 ∩ 门洞（四周缩 4 mm 留门缝）
    doors = {}
    for side, e in (("L", 1), ("R", -1)):
        x0, x1 = (0.3, 1.2) if e > 0 else (-1.2, -0.3)
        dob = shell.copy(); dob.data = shell.data.copy(); bpy.context.scene.collection.objects.link(dob)
        c = cutter_box(f"cutD{side}", x0, x1, DOOR_Y0 + 0.004, DOOR_Y1 - 0.004, DOOR_Z0 + 0.004, DOOR_Z1 - 0.004)
        boolean(dob, c, "INTERSECT"); bpy.data.objects.remove(c)
        c = cutter_box(f"cutDW{side}", x0, x1, DOOR_Y0 + 0.07, DOOR_Y1 - 0.07, WIN_Z0, WIN_Z1 - 0.03)
        boolean(dob, c, "DIFFERENCE"); bpy.data.objects.remove(c)
        dob.name = f"Door_{side}"; dob.data.name = f"Door_{side}"
        doors[side] = dob
    # 门洞、两侧窗洞、前脸小窗
    cuts = []
    for e in (1, -1):
        x0, x1 = (0.3, 1.2) if e > 0 else (-1.2, -0.3)
        cuts.append(cutter_box("cd", x0, x1, DOOR_Y0, DOOR_Y1, DOOR_Z0, DOOR_Z1))
        cuts.append(cutter_box("cw1", x0, x1, -0.86, -0.42, WIN_Z0, WIN_Z1))
        cuts.append(cutter_box("cw2", x0, x1, 0.42, 0.86, WIN_Z0, WIN_Z1))
    for c in cuts:
        boolean(shell, c, "DIFFERENCE"); bpy.data.objects.remove(c)
    return shell, doors


def body_details(M):
    """挂在 Body 上的其余部分：腰线 / 窗框装饰条、车顶 + 行李栏 + 行李、后行李舱、车夫座 / 前舱 / 脚踏板、刹车杆、车灯、
    车厢内座椅、门下踏板、车身字。全部世界坐标。"""
    p = Part([M["trim"]])
    Tr, L, I, B, Wd, Cv, Bs = M["trim"], M["leather"], M["iron"], M["boot"], M["wood"], M["canvas"], M["brass"]
    # 腰线 + 顶线装饰条：绕车厢一圈，在门洞处断开（门板上另有一段，见 door_details）
    def molding(z, off, r1, r2, mat, gap=True):
        n = 72
        pts = [Vector((q.x, q.y, z)) for q in [sell(ab(z)[0] + off, ab(z)[1] + off, 2 * math.pi * j / n) for j in range(n)]]
        if not gap:
            loft(p, [(q, r1, r2) for q in pts], mat, seg=5, hint=Z, closed=True); return
        segs, cur = [], []
        for q in pts + pts[:1]:
            if abs(q.x) > 0.3 and DOOR_Y0 - 0.002 < q.y < DOOR_Y1 + 0.002:
                if cur: segs.append(cur); cur = []
            else:
                cur.append(q)
        if cur: segs.append(cur)
        if len(segs) > 2 and (segs[0][0] - segs[-1][-1]).length < 0.2:
            segs[0] = segs[-1] + segs[0]; segs.pop()
        for sg in segs:
            if len(sg) < 2: continue
            d0 = (sg[1] - sg[0]).normalized() * 0.003; d1 = (sg[-1] - sg[-2]).normalized() * 0.003
            loft(p, [(sg[0] - d0, 0, 0)] + [(q, r1, r2) for q in sg] + [(sg[-1] + d1, 0, 0)], mat, seg=5, hint=Z)
    molding(1.45, 0.008, 0.016, 0.012, Tr)
    molding(1.58, 0.004, 0.009, 0.008, Tr)
    molding(2.075, 0.002, 0.01, 0.008, Tr, gap=False)
    molding(2.235, 0.002, 0.012, 0.01, Tr, gap=False)
    molding(1.0, 0.006, 0.012, 0.012, Tr, gap=False)
    # 窗框（只做车身上的两个侧窗，门窗框在门板上）
    for e in (1, -1):
        for y0, y1 in ((-0.86, -0.42), (0.42, 0.86)):
            frame_rect(p, e, y0 - 0.012, y1 + 0.012, WIN_Z0 - 0.012, WIN_Z1 + 0.012, Tr)
    # 车顶：略拱的顶板 + 檐口
    rz = BODY[-1][0]
    roof = [(rz - 0.01, 0.905, 0.652), (rz + 0.015, 0.915, 0.66), (rz + 0.035, 0.91, 0.655), (rz + 0.045, 0.85, 0.6), (rz + 0.055, 0.0, 0.0)]
    bm, uvl = p.bm, p.uv
    N = 64
    rings = []
    for z, a_, b_ in roof:
        if a_ < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((q.x, q.y, z)) for q in [sell(a_, b_, 2 * math.pi * j / N) for j in range(N)]])
    fs = []
    for i in range(len(rings) - 1):
        A_, B_ = rings[i], rings[i + 1]
        for j in range(N):
            jn = (j + 1) % N
            vv = [A_[j], A_[jn], B_[0]] if len(B_) == 1 else [A_[j], A_[jn], B_[jn], B_[j]]
            f = bm.faces.new(vv)
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x / 0.8, lp.vert.co.y / 0.8)
            fs.append(f)
    f = bm.faces.new(list(reversed(rings[0])))
    fs.append(f)
    p._take(fs, B, True)
    top = rz + 0.05
    # 行李栏：铁栏杆（四周一圈 + 立柱），前面就是车夫座的靠背
    a_r, b_r = 0.84, 0.6
    rail = [Vector((q.x, q.y, top + 0.17)) for q in [sell(a_r, b_r, 2 * math.pi * j / 48) for j in range(48)]]
    loft(p, [(q, 0.012, 0.012) for q in rail], I, seg=6, hint=Z, closed=True)
    for j in range(0, 48, 3):
        q = rail[j]
        rod(p, (q.x, q.y, top - 0.01), q, 0.009, I, seg=6)
    # 行李：两只木箱、一只皮箱、一个帆布包裹，用皮带捆着
    def trunk(c, size, rot, mat, band):
        M_ = T(*c) @ R("Z", rot)
        p.box(size, mat, xf=M_, bevel=0.012, bseg=2)
        for k in (-0.3, 0.3):
            p.box((size[0] + 0.012, 0.04, size[2] + 0.012), band, xf=M_ @ T(0, size[1] * k, 0), bevel=0.004)
    trunk((0.2, 0.35, top + 0.16), (0.42, 0.62, 0.3), 4, Wd, L)
    trunk((-0.22, 0.4, top + 0.14), (0.44, 0.5, 0.26), -3, L, I)
    trunk((0.05, -0.15, top + 0.11), (0.7, 0.36, 0.2), 2, Wd, L)
    # 帆布包裹（圆角软包）+ 毡毯卷
    for c_, sz_, rot_ in (((-0.2, 0.74, top + 0.1), (0.5, 0.32, 0.2), 14), ((0.22, 0.76, top + 0.09), (0.36, 0.3, 0.18), -8)):
        M_ = T(*c_) @ R("Z", rot_)
        p.box(sz_, Cv, xf=M_, bevel=0.07, bseg=3)
        p.box((sz_[0] * 0.3, sz_[1] + 0.012, sz_[2] + 0.012), L, xf=M_, bevel=0.004)
    loft(p, [(Vector((-0.3, -0.5, top + 0.08)), 0, 0), (Vector((-0.28, -0.5, top + 0.08)), 0.075, 0.075), (Vector((0.3, -0.5, top + 0.08)), 0.075, 0.075),
             (Vector((0.32, -0.5, top + 0.08)), 0, 0)], L, seg=12, hint=Z)
    # 卷起来的皮窗帘（窗洞上沿）
    for e in (1, -1):
        for y0, y1 in ((-0.84, -0.44), (0.44, 0.84)):
            z_ = WIN_Z1 - 0.035
            x0 = e * (surf_x((y0 + y1) / 2, z_) - 0.03)
            rod(p, (x0, y0, z_), (x0, y1, z_), 0.026, L, seg=10, hint=Z)
    # 后行李舱：铁托架上的平台 + 斜下来的皮罩
    bx = 0.6
    def wedge(pts2d, x0, x1, mat):
        p.poly_extrude(pts2d, x1 - x0, mat, xf=T(x0, 0, 0) @ YZX)
    wedge([(0.86, 1.22), (1.42, 1.22), (1.42, 1.3), (1.38, 1.36), (0.96, 1.92), (0.86, 1.92)], -bx, bx, B)
    p.box((1.26, 0.6, 0.04), Tr, xf=T(0, 1.14, 1.2), bevel=0.01)
    for e in (1, -1):
        rod(p, (0.55 * e, 1.43, 1.19), (0.55 * e, 0.9, 1.6), 0.014, I, seg=6)
        rod(p, (0.55 * e, 1.43, 1.19), (0.55 * e, 0.92, 1.08), 0.014, I, seg=6)
    for x_ in (-0.35, 0.35):
        loft(p, [(Vector((x_, 0.96, 1.93)), 0.03, 0.005), (Vector((x_, 1.39, 1.37)), 0.03, 0.005), (Vector((x_, 1.43, 1.3)), 0.03, 0.005),
                 (Vector((x_, 1.43, 1.2)), 0.03, 0.005)], L, seg=6, hint=X)
    # 前舱（车夫座下）+ 坐垫 + 靠背 + 脚踏板
    wedge([(-0.86, 1.62), (-1.4, 1.62), (-1.25, 2.13), (-0.86, 2.13)], -0.62, 0.62, B)
    wedge([(-0.84, 2.12), (-1.25, 2.12), (-1.25, 2.175), (-1.2, 2.19), (-0.88, SEAT_TOP), (-0.84, SEAT_TOP)], -0.6, 0.6, L)
    wedge([(-0.86, SEAT_TOP - 0.02), (-0.79, SEAT_TOP - 0.02), (-0.77, SEAT_TOP + 0.33), (-0.84, SEAT_TOP + 0.33)], -0.6, 0.6, L)
    for e in (1, -1):   # 座椅扶手栏
        rod(p, (0.6 * e, -0.82, SEAT_TOP + 0.3), (0.6 * e, -1.18, SEAT_TOP + 0.12), 0.012, I, seg=6)
        rod(p, (0.6 * e, -1.18, SEAT_TOP + 0.12), (0.6 * e, -1.2, SEAT_TOP - 0.03), 0.012, I, seg=6)
    fb = foot_plane()
    y_a, y_b = -1.36, -1.92
    za, zb = fb(y_a), fb(y_b)
    beam(p, (0, y_a, za - 0.015), (0, y_b, zb - 0.015), 1.24, 0.03, Wd, up=Z)
    p.box((1.24, 0.03, 0.2), B, xf=T(0, y_b - 0.01, zb + 0.08), bevel=0.008)   # 挡泥板（dash）
    for e in (1, -1):
        rod(p, (0.58 * e, y_b, zb - 0.02), (0.58 * e, -1.15, 1.45), 0.014, I, seg=6)
        rod(p, (0.58 * e, -1.4, za - 0.02), (0.58 * e, -1.05, 1.45), 0.014, I, seg=6)
    # 刹车杆（车夫右手边）
    rod(p, (-0.68, -1.5, 1.6), (-0.68, -1.42, 2.55), 0.016, I, seg=8, rb=0.012)
    p.sphere(0.024, I, xf=T(-0.68, -1.42, 2.56), seg=8, rings=5)
    # 车灯：前舱两角
    for e in (1, -1):
        c = Vector((0.7 * e, -1.02, 2.02))
        rod(p, (0.63 * e, -0.98, 1.98), c, 0.012, I, seg=6)
        p.box((0.11, 0.11, 0.16), I, xf=T(*c), bevel=0.01)
        p.box((0.085, 0.02, 0.12), M["glass"], xf=T(c.x, c.y - 0.05, c.z), bevel=0.004)
        p.lathe([(0.08, 0.06, 0.06), (0.12, 0.03, 0.03), (0.16, 0.015, 0.015), (0.17, 0, 0)], I, seg=10, xf=T(c.x, c.y, c.z))
        p.lathe([(0.08, 0.075, 0.075), (0.09, 0.075, 0.075), (0.095, 0.0, 0.0)], Bs, seg=10, xf=T(c.x, c.y, c.z))
    # 车厢内：前后两排长椅 + 中间一排 + 地板
    In = M["interior"]
    p.box((1.22, 1.6, 0.03), Wd, xf=T(0, 0, 1.03))
    for yc, back in ((-0.68, -1), (0.68, 1), (0.0, 0)):
        p.box((1.18, 0.4, 0.1), In, xf=T(0, yc, 1.42), bevel=0.03, bseg=2)
        p.box((1.18, 0.36, 0.38), Wd, xf=T(0, yc, 1.22))
        if back:
            p.box((1.18, 0.1, 0.5), In, xf=T(0, yc + 0.22 * back, 1.72), bevel=0.03, bseg=2)
    # 门下踏板（铁托架）
    for e in (1, -1):
        p.box((0.16, 0.34, 0.025), I, xf=T(0.76 * e, 0.0, 0.82), bevel=0.004)
        for y_ in (-0.13, 0.13):
            rod(p, (0.76 * e, y_, 0.82), (0.6 * e, y_, 1.08), 0.012, I, seg=6)
    lettering(p, M["gold"])
    return p.finish("BodyDetails", smooth_angle=35)


def frame_rect(p, e, y0, y1, z0, z1, mat, r=0.012):
    def P_(y, z):
        return Vector((e * (surf_x(y, z) + 0.004), y, z))
    edges = [[P_(y0 + (y1 - y0) * k / 8, z0) for k in range(9)], [P_(y0 + (y1 - y0) * k / 8, z1) for k in range(9)],
             [P_(y0, z0 + (z1 - z0) * k / 4) for k in range(5)], [P_(y1, z0 + (z1 - z0) * k / 4) for k in range(5)]]
    for pts in edges:
        d0 = (pts[1] - pts[0]).normalized() * 0.012; d1 = (pts[-1] - pts[-2]).normalized() * 0.012
        bh.loft(p, [(pts[0] - d0, 0, 0)] + [(q, r, 0.008) for q in pts] + [(pts[-1] + d1, 0, 0)], mat, seg=6, hint=X * e)


def foot_plane():
    """坐姿车夫（UpperLeg X -80°、LowerLeg X +60°）的鞋底平面：脚跟 / 脚尖两点（见 docs/mannequin_rig.md 段长），返回 y → 板面 z。"""
    hip = Vector((0, SEAT_Y, SEAT_TOP - HIP_DROP + 0.92))
    knee = hip + bh._rx(Vector((0, -0.004, -0.415)), -80)
    ankle = knee + bh._rx(Vector((0, 0.012, -0.42)), -20)
    heel = ankle + bh._rx(Vector((0, 0.066, -0.093)), -20)
    toe = ankle + bh._rx(Vector((0, -0.19, -0.088)), -20)
    k = (toe.z - heel.z) / (toe.y - heel.y)
    return lambda y: heel.z + (y - heel.y) * k


def lettering(p, mat):
    """车身上沿的金字（Rye，SIL OFL；在 art/source/fonts/，已在 ASSETS.md 登记），贴着车身曲面。"""
    font_path = mc.SRC / "fonts" / "Rye-Regular.ttf"
    if not font_path.exists():
        print("WARN no Rye font, skip lettering"); return
    cu = bpy.data.curves.new("txt", "FONT"); cu.body = "MERCY CREEK"
    cu.font = bpy.data.fonts.load(str(font_path), check_existing=True); cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.size = 0.1; cu.resolution_u = 1; cu.fill_mode = "FRONT"
    tob = bpy.data.objects.new("txt", cu); bpy.context.scene.collection.objects.link(tob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = tob.evaluated_get(dg).to_mesh()
    vs = [v.co.copy() for v in me.vertices]
    w = max(v.x for v in vs) - min(v.x for v in vs); h = max(v.y for v in vs) - min(v.y for v in vs)
    sc = min(1.2 / w, 0.085 / h)
    polys = [list(pl.vertices) for pl in me.polygons]
    tob.evaluated_get(dg).to_mesh_clear(); bpy.data.objects.remove(tob); bpy.data.curves.remove(cu)
    zc = (2.075 + 2.235) / 2
    for e in (1, -1):
        nv = []
        for v in vs:
            y = v.x * sc * e; z = zc + v.y * sc
            nv.append(p.bm.verts.new((e * (surf_x(y, z) + 0.003), y, z)))
        fs = []
        for pl in polys:
            try:
                f = p.bm.faces.new([nv[i] for i in pl])
            except ValueError:
                continue
            for lp in f.loops:
                lp[p.uv].uv = (lp.vert.co.y, lp.vert.co.z)
            fs.append(f)
        if e < 0:
            for f in fs: f.normal_flip()
        p._take(fs, mat, False)


def door_details(M, side, e):
    """门板上的装饰条、窗框、铜把手（世界坐标）。"""
    p = Part([M["trim"]])
    Tr = M["trim"]
    frame_rect(p, e, DOOR_Y0 + 0.07 - 0.012, DOOR_Y1 - 0.07 + 0.012, WIN_Z0 - 0.012, WIN_Z1 - 0.03 + 0.012, Tr)
    frame_rect(p, e, DOOR_Y0 + 0.05, DOOR_Y1 - 0.05, DOOR_Z0 + 0.06, 1.52, Tr, r=0.008)
    for z, r1 in ((1.45, 0.016), (1.58, 0.009)):
        pts = [Vector((e * (surf_x(y, z, 0.008 if z < 1.5 else 0.004)), y, z)) for y in [DOOR_Y0 + 0.006 + (DOOR_Y1 - DOOR_Y0 - 0.012) * k / 8 for k in range(9)]]
        bh.loft(p, [(pts[0] - Y * 0.003, 0, 0)] + [(q, r1, 0.012 if z < 1.5 else 0.008) for q in pts] + [(pts[-1] + Y * 0.003, 0, 0)], Tr, seg=6, hint=Z)
    hy, hz = DOOR_Y0 + 0.07, 1.5
    hx = e * (surf_x(hy, hz) + 0.03)
    p.sphere(0.018, M["brass"], xf=T(hx, hy, hz), seg=10, rings=6)
    rod(p, (e * surf_x(hy, hz), hy, hz), (hx, hy, hz), 0.007, M["brass"], seg=6)
    for hz2 in (1.3, 1.85):   # 合页
        hy2 = DOOR_Y1 - 0.01
        rod(p, (e * (surf_x(hy2, hz2) + 0.006), hy2, hz2 - 0.05), (e * (surf_x(hy2, hz2) + 0.006), hy2, hz2 + 0.05), 0.011, M["iron"], seg=8)
    return p.finish(f"DoorDetails_{side}", smooth_angle=35)


# ------------------------------------------------------------------ 组装
def build():
    M = materials()
    root = mc.empty("Stagecoach")
    ch = chassis(M); ch.parent = root
    wheels = {}
    for nm, (x, y, r, n, out) in {"Wheel_FL": (TRACK, FA_Y, RF, 12, 1), "Wheel_FR": (-TRACK, FA_Y, RF, 12, -1),
                                  "Wheel_RL": (TRACK, RA_Y, RR, 14, 1), "Wheel_RR": (-TRACK, RA_Y, RR, 14, -1)}.items():
        w = wheel(nm, M, r, n, out); w.parent = ch; w.location = (x, y, r)
        wheels[nm] = w
    shell, doors = body_shell(M)
    det = body_details(M)
    body = join([shell, det], "Body")
    try: body.data.set_sharp_from_angle(angle=math.radians(40))
    except Exception: pass
    set_origin(body, PIVOT, ch)
    hinge = {}
    for side, e in (("L", 1), ("R", -1)):
        d = join([doors[side], door_details(M, side, e)], f"Door_{side}")
        hz = (DOOR_Z0 + DOOR_Z1) / 2
        hp = Vector((e * (surf_x(DOOR_Y1, hz) + 0.006), DOOR_Y1 - 0.01, hz))
        set_origin(d, hp, body, PIVOT)
        hinge[side] = hp
    seat = Vector((DRIVER_X, SEAT_Y, SEAT_TOP - HIP_DROP))
    mc.empty("DriverSeat", parent=body, location=seat - PIVOT)
    mc.empty("PassengerExit_L", parent=root, location=(1.1, 0.0, 0.0))
    mc.empty("Hitch_L", parent=root, location=(HITCH_X, HITCH_Y, 0.0))
    mc.empty("Hitch_R", parent=root, location=(-HITCH_X, HITCH_Y, 0.0))
    for o in mc.descendants(root):
        o.rotation_euler = (0, 0, 0)
        if o.type == "MESH":   # 五边以上的面三角化，glTF 导出才能算切线（法线贴图需要）
            bm = bmesh.new(); bm.from_mesh(o.data)
            ng = [f for f in bm.faces if len(f.verts) > 4]
            if ng: bmesh.ops.triangulate(bm, faces=ng)
            bm.to_mesh(o.data); bm.free()
    return root, dict(chassis=ch, body=body, wheels=wheels, hinge=hinge, seat=seat)


def u(v):
    v = Vector(v); return (-v.x, v.z, -v.y)


# ------------------------------------------------------------------ 评审场景：导入马和车夫，摆到挂点上
def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    root = next(o for o in new if o.parent is None)
    return root, {o.name.split(".")[0]: o for o in new}


def setrot(ob, deg):
    ob.rotation_mode = "XYZ"; ob.rotation_euler = tuple(math.radians(a) for a in deg)


DRIVER_POSE = {"L_UpperLeg": (-80, 0, -4), "R_UpperLeg": (-80, 0, 4), "L_LowerLeg": (60, 0, 0), "R_LowerLeg": (60, 0, 0),
               "Spine": (6, 0, 0), "Chest": (4, 0, 0), "Neck": (4, 0, 0), "Head": (-2, -6, 0),
               "L_UpperArm": (-38, 0, -8), "R_UpperArm": (-34, 0, 8), "L_LowerArm": (-52, 0, 0), "R_LowerArm": (-56, 0, 0),
               "L_Hand": (-10, 0, 0), "R_Hand": (-10, 0, 0), "L_Fingers": (0, 60, 0), "L_FingersTip": (0, 50, 0),
               "R_Fingers": (0, -60, 0), "R_FingersTip": (0, -50, 0)}


def review(root, info):
    stage_c = bpy.context.scene.collection
    mc.setup_render(SAMPLES, res=(1280, 720))
    mc.world_hdri("goegap_road", strength=0.8, rot=20)
    sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.6; sun.angle = math.radians(1.5); sun.color = (1.0, 0.88, 0.74)
    so = bpy.data.objects.new("Sun", sun); stage_c.objects.link(so); so.rotation_euler = (math.radians(55), 0, math.radians(28))
    gm = mc.pbr("Road", "Ground080", tile=3.0)
    p = Part([gm]); p.box((40, 40, 0.02), gm, xf=T(0, -2, -0.01)); p.finish("Ground")
    bpy.context.view_layer.update()
    horses = {}
    for side in ("L", "R"):
        hr, objs = import_gltf(mc.ART / "Characters" / ("Horse.gltf" if side == "L" else "Horse_B.gltf"))
        hk = bpy.data.objects[f"Hitch_{side}"]
        hr.matrix_world = hk.matrix_world.copy()
        horses[side] = (hr, objs)
    dr, dobjs = import_gltf(mc.ART / "Characters" / "Mannequin_Driver.gltf")
    dr.matrix_world = bpy.data.objects["DriverSeat"].matrix_world.copy()
    for n, e in DRIVER_POSE.items():
        setrot(dobjs[n], e)
    bpy.context.view_layer.update()
    # 缰绳（只在评审图里）：两匹马的衔铁 → 鞍上缰绳圈 → 车夫双手
    rein = mc.pbr("Reins", "Leather030", tile=0.2, tint=(0.4, 0.32, 0.26))
    hands = [dobjs["L_Fingers"].matrix_world.translation, dobjs["R_Fingers"].matrix_world.translation]
    for side, (hr, objs) in horses.items():
        mw = hr.matrix_world
        bridle = objs["Tack_Bridle"]
        bits = [mw @ Vector((0.064 * s_, -1.439, 1.462)) for s_ in (1, -1)]
        for k, bt in enumerate(bits):
            ter = mw @ Vector((0.1 * (1 if k == 0 else -1), -0.24, 1.66))
            hand = hands[0] if side == "L" else hands[1]
            pts = [bt, bt.lerp(ter, 0.5) + Vector((0, 0, 0.05)), ter, ter.lerp(hand, 0.5) - Vector((0, 0, 0.12)), hand]
            cu = bpy.data.curves.new("rein", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.006
            sp = cu.splines.new("NURBS"); sp.points.add(len(pts) - 1)
            for q, pt in zip(sp.points, pts):
                q.co = (*pt, 1)
            sp.use_endpoint_u = True; sp.order_u = 3
            ob = bpy.data.objects.new("Rein", cu); ob.data.materials.append(rein); stage_c.objects.link(ob)
    bpy.context.view_layer.update()
    tgt = Vector((0, -1.2, 1.2))
    mc.camera("Cam", (6.4, -7.6, 2.6), tgt, lens=32)
    mc.render(mc.REVIEWS / "Stagecoach.png")
    mc.camera("CamSide", (8.4, -0.9, 1.3), (0, -0.9, 1.15), lens=28)
    mc.render(mc.REVIEWS / "Stagecoach_side.png")
    # 开门 + 车厢摇摆：验证合页轴和 Body 轴心
    bpy.data.objects["Door_L"].rotation_euler = (0, 0, math.radians(75))
    info["body"].rotation_euler = (math.radians(-3), math.radians(4), 0)
    mc.camera("CamDoor", (3.4, -2.4, 1.7), (0.5, 0.15, 1.4), lens=30)
    mc.render(mc.REVIEWS / "Stagecoach_door.png")
    bpy.data.objects["Door_L"].rotation_euler = (0, 0, 0); info["body"].rotation_euler = (0, 0, 0)
    mc.camera("CamDriver", (-2.6, -1.9, 2.3), (-0.2, -1.35, 2.0), lens=35)
    mc.render(mc.REVIEWS / "Stagecoach_driver.png")


if __name__ == "__main__":
    sc = mc.reset()
    root, info = build()
    objs = mc.descendants(root)
    tris = mc.tri_count(objs)
    per = {o.name: mc.tri_count([o]) for o in objs if o.type == "MESH"}
    print(f"TRIS Stagecoach total={tris} " + " ".join(f"{k}={v}" for k, v in per.items()))
    assert tris <= MAX_TRIS, tris
    mc.export_glb(OUT, [root])
    bpy.context.view_layer.update()
    for nm in ("Chassis", "Body", "Door_L", "Door_R", "DriverSeat", "PassengerExit_L", "Hitch_L", "Hitch_R",
               "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"):
        ob = bpy.data.objects[nm]
        print(f"NODE {nm} parent={ob.parent.name if ob.parent else '-'} unity_world=({u(ob.matrix_world.translation)[0]:+.3f},"
              f"{u(ob.matrix_world.translation)[1]:.3f},{u(ob.matrix_world.translation)[2]:+.3f})")
    if RENDER:
        review(root, info)
