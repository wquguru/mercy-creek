"""木头人偶马（拉驿站马车的挽马，约 1.6 m 肩高）+ 深色皮挽具。层级即骨架，不蒙皮；和人偶同一套视觉语言。

blender --background --python tools/blender/build_horse.py -- [--no-render] [--samples N] [--only Horse|Horse_B]
输出：Game/Assets/_MercyCreek/Art/Characters/Horse.gltf（浅色木）、Horse_B.gltf（深一点的木色，其余完全相同）
评审图：Reviews/blender/Horse.png（侧面）、Horse_walk.png（按 docs/horse_rig.md 的轴向与幅度摆出的行走中间帧）
坐标：马头朝 Blender -Y（= glTFast 导入后 Unity +Z），Z 向上，根节点 Horse 在身体中心正下方的地面。
L = 马自己的左边 = Blender +X = Unity -X。每段原点在关节上，静止旋转全为单位旋转（四腿方正站立）。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy, bmesh
from mathutils import Vector, Matrix
import mc_common as mc
from mc_common import T, R, Part

A = mc.args()
RENDER = "--no-render" not in A
SAMPLES = int(A[A.index("--samples") + 1]) if "--samples" in A else 48
ONLY = A[A.index("--only") + 1].split(",") if "--only" in A else None
VARIANTS = {"Horse": (0.86, 0.8, 0.68), "Horse_B": (0.6, 0.48, 0.38)}   # 木纹乘色：B 深一档
MAX_TRIS = 20000
X = Vector((1, 0, 0)); Z = Vector((0, 0, 1))

# ------------------------------------------------------------------ 关节（Blender 世界坐标，米）
BODY = Vector((0, 0, 1.30))                # 脊柱中点（髻甲与十字部之间）
NECK = Vector((0, -0.6, 1.38))             # 颈根（胸前上部，埋在躯干里）
HEAD = Vector((0, -1.08, 1.84))            # 寰枕关节（项部）
TAIL = Vector((0, 0.84, 1.46))             # 尾根
HEAD_DIR = Vector((0, -math.cos(math.radians(42)), -math.sin(math.radians(42))))
FORE_X, HIND_X = 0.17, 0.19
# 前腿：肩关节 → 腕（"膝"）→ 球节 → 蹄冠；后腿：髋关节 → 跗关节 → 球节 → 蹄冠
FORE = dict(upper=Vector((0, -0.62, 1.12)), elbow=Vector((0, -0.53, 0.92)), lower=Vector((0, -0.55, 0.52)),
            pastern=Vector((0, -0.555, 0.19)), hoof=Vector((0, -0.615, 0.088)))
HIND = dict(upper=Vector((0, 0.56, 1.22)), stifle=Vector((0, 0.4, 0.93)), lower=Vector((0, 0.66, 0.56)),
            pastern=Vector((0, 0.645, 0.19)), hoof=Vector((0, 0.59, 0.088)))
TRACE_END = Vector((0.335, 0.62, 1.04))    # 挽绳残段末端（左侧；右侧 x 取负）。build_coach.py 从这里接到车上的挽绳


def sx(v, x):
    return Vector((x, v.y, v.z))


# ------------------------------------------------------------------ 几何工具
def loft(p, pts, mat, seg=16, hint=X, closed=False, smooth=True, tile=None):
    """沿折线放样。pts = [(中心, ru, rv[, 法向偏移 ov])]；环的局部 u = hint 去掉切向分量，v = 切向 × u。
    ru / rv = 0 的端点收成极点。环点 = c + v*ov + u*ru*sin(a) - v*rv*cos(a)（和 Part.lathe 一致，法线朝外）。"""
    bm, uvl = p.bm, p.uv
    tile = tile or mat.get("tile", 1.0)
    n = len(pts)
    rings, vs = [], [0.0]
    for i, q in enumerate(pts):
        c = Vector(q[0]); ru, rv = q[1], q[2]; ov = q[3] if len(q) > 3 else 0.0
        if closed:
            t = (Vector(pts[(i + 1) % n][0]) - Vector(pts[i - 1][0]))
        else:
            t = Vector(pts[min(i + 1, n - 1)][0]) - Vector(pts[max(i - 1, 0)][0])
        t.normalize()
        u = Vector(hint) - t * t.dot(hint)
        if u.length < 1e-6:
            u = Z - t * t.dot(Z)
        u.normalize(); v = t.cross(u)
        if i:
            vs.append(vs[-1] + (c - Vector(pts[i - 1][0])).length)
        if ru < 1e-6 and rv < 1e-6:
            rings.append([bm.verts.new(c + v * ov)])
        else:
            rings.append([bm.verts.new(c + v * ov + u * ru * math.sin(2 * math.pi * j / seg) - v * rv * math.cos(2 * math.pi * j / seg))
                          for j in range(seg)])
    circ = 2 * math.pi * max(max(q[1], q[2]) for q in pts)
    faces = []
    pairs = list(zip(range(n - 1), range(1, n))) + ([(n - 1, 0)] if closed else [])
    for i0, i1 in pairs:
        Aa, Bb = rings[i0], rings[i1]
        v0, v1 = vs[i0] / tile, (vs[i1] if i1 else vs[-1] + (Vector(pts[0][0]) - Vector(pts[-1][0])).length) / tile
        for j in range(seg):
            jn = (j + 1) % seg
            u0, u1 = j / seg * circ / tile, (j + 1) / seg * circ / tile
            if len(Aa) == 1:
                vv = [Aa[0], Bb[jn], Bb[j]]; uvs = [((u0 + u1) / 2, v0), (u1, v1), (u0, v1)]
            elif len(Bb) == 1:
                vv = [Aa[j], Aa[jn], Bb[0]]; uvs = [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)]
            else:
                vv = [Aa[j], Aa[jn], Bb[jn], Bb[j]]; uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            try:
                f = bm.faces.new(vv)
            except ValueError:
                continue
            for lp, uvv in zip(f.loops, uvs):
                lp[uvl].uv = (uvv[1], uvv[0])
            faces.append(f)
    p._take(faces, mat, smooth)
    return faces


def catmull(pts, n=4):
    """对 (中心, ru, rv[, ov]) 表做 Catmull-Rom 细分，让木头轮廓平滑。"""
    out = []
    P = [(Vector(q[0]), q[1], q[2], q[3] if len(q) > 3 else 0.0) for q in pts]
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(n):
            t = k / n
            def cr(a, b, c, d):
                return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t * t * t)
            row = [cr(p0[0], p1[0], p2[0], p3[0])]
            for m in range(1, len(p1)):
                row.append(max(0.0, cr(p0[m], p1[m], p2[m], p3[m])) if m < 3 else cr(p0[m], p1[m], p2[m], p3[m]))
            if (p1[1] < 1e-6 and k == 0):
                row[1] = row[2] = 0.0
            out.append(tuple(row))
    out.append(tuple(P[-1]))
    return out


# ------------------------------------------------------------------ 躯干外形（沿 -Y：t = -y；每站 半宽 rx、半高 ry、中心高 cz）
TRUNK = [(-0.885, 0.0, 0.0, 1.31), (-0.87, 0.1, 0.13, 1.31), (-0.825, 0.18, 0.23, 1.305), (-0.735, 0.235, 0.285, 1.29),
         (-0.58, 0.262, 0.31, 1.265), (-0.4, 0.272, 0.322, 1.235), (-0.2, 0.288, 0.33, 1.2), (0.05, 0.296, 0.34, 1.185),
         (0.27, 0.285, 0.355, 1.21), (0.44, 0.26, 0.36, 1.24), (0.58, 0.232, 0.335, 1.245), (0.69, 0.2, 0.29, 1.235),
         (0.765, 0.135, 0.205, 1.22), (0.79, 0.0, 0.0, 1.215)]


def trunk_at(t):
    """躯干在 t（= -y）处的 (rx, ry, cz)，线性插值。"""
    if t <= TRUNK[0][0]: return TRUNK[0][1:]
    for a, b in zip(TRUNK, TRUNK[1:]):
        if a[0] <= t <= b[0]:
            k = (t - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * k for i in (1, 2, 3))
    return TRUNK[-1][1:]


def trunk_halfwidth(y, z):
    rx, ry, cz = trunk_at(-y)
    q = 1 - ((z - cz) / ry) ** 2 if ry > 1e-6 else -1
    return rx * math.sqrt(q) if q > 0 else 0.0


# ------------------------------------------------------------------ 马
class Horse:
    def __init__(self, name, tint, coll=None):
        self.name = name
        self.coll = coll or bpy.context.scene.collection
        sfx = "" if name == "Horse" else "_" + name.split("_")[-1]
        self.WOOD = mc.pbr("HorseWood" + sfx, "Wood050", tile=0.34, size=2048, tint=tint, rough_mul=0.6, normal=0.6)
        jt = tuple(c * 0.52 for c in tint)
        self.JOINT = mc.pbr("HorseJoint" + sfx, "Wood092", tile=0.25, tint=(0.45, 0.33, 0.25) if name == "Horse" else (0.36, 0.26, 0.2),
                            rough_mul=0.5, normal=0.3)
        self.HOOF = mc.pbr("HorseHoof", "Wood092", tile=0.2, tint=(0.22, 0.17, 0.13), rough_mul=0.6, normal=0.3)
        self.LEATHER = mc.pbr("HarnessLeather", "Leather030", tile=0.15, tint=(0.42, 0.34, 0.28), rough_mul=0.85)
        self.COLLAR = mc.pbr("CollarLeather", "Leather037", tile=0.2, tint=(0.36, 0.28, 0.22), rough_mul=0.8)
        self.IRON = mc.pbr("HarnessIron", "Metal027", tile=0.2, tint=(0.5, 0.48, 0.45), metal=0.8, normal=0.4)
        self.BRASS = mc.flat("HarnessBrass", (0.6, 0.45, 0.22), rough=0.38, metal=1.0)
        self.segs = {}
        self.root = mc.empty("Horse", collection=self.coll)
        self._body()
        self._tack()
        for o in self.objects():   # 五边以上的面三角化，glTF 导出才能算切线
            if o.type == "MESH":
                bm = bmesh.new(); bm.from_mesh(o.data)
                ng = [f for f in bm.faces if len(f.verts) > 4]
                if ng: bmesh.ops.triangulate(bm, faces=ng)
                bm.to_mesh(o.data); bm.free()

    def seg(self, name, parent, pivot, build, mats):
        pivot = Vector(pivot)
        p = Part(mats)
        build(p)
        ob = p.finish(name, collection=self.coll, smooth_angle=50)
        ob.data.transform(T(*(-pivot)))
        par = self.segs[parent]["ob"] if parent else self.root
        ppiv = self.segs[parent]["pivot"] if parent else Vector((0, 0, 0))
        ob.parent = par; ob.location = pivot - ppiv
        self.segs[name] = dict(ob=ob, pivot=pivot)
        return ob

    def tack(self, segname, name, build, mats):
        sg = self.segs[segname]
        p = Part(mats)
        build(p)
        ob = p.finish(name, collection=self.coll, smooth_angle=45)
        ob.data.transform(T(*(-sg["pivot"])))
        ob.parent = sg["ob"]; ob.location = (0, 0, 0)
        return ob

    # ---------- 身体 ----------
    def _body(self):
        W, J = self.WOOD, self.JOINT

        def body(p):
            prof = []
            for (t, rx, ry, cz) in catmull([((0, 0, t), rx, ry, cz) for t, rx, ry, cz in TRUNK], 3):
                prof.append((t[2], rx, ry, 0.0, cz))
            p.lathe(prof, W, seg=28, xf=R("X", 90), swap_uv=True)
        self.seg("Body", None, BODY, body, [W])

        # 颈：颈根埋进胸前，向前上到项部；鬃脊一侧（v 正向）拱起
        nd = (HEAD - NECK)
        def neck(p):
            st = []
            for s, rx, rv, ov in [(-0.16, 0.0, 0.0, 0.0), (-0.12, 0.13, 0.2, 0.0), (0.0, 0.155, 0.27, 0.0), (0.18, 0.14, 0.24, 0.02),
                                  (0.4, 0.12, 0.19, 0.035), (0.62, 0.1, 0.15, 0.03), (0.82, 0.088, 0.125, 0.015), (0.98, 0.08, 0.11, 0.0),
                                  (1.06, 0.0, 0.0, 0.0)]:
                st.append((NECK + nd * s, rx, rv, ov))
            loft(p, catmull(st, 3), W, seg=22)
            p.sphere(0.085, J, xf=T(*(HEAD + nd.normalized() * -0.04)), seg=14, rings=8)   # 项部球关节
        self.seg("Neck", "Body", NECK, neck, [W, J])
        n_ball = Part([J])

        # 头：项部 → 口鼻；颌下（-v 一侧）更宽厚
        d = HEAD_DIR
        def head(p):
            st = []
            for t, rx, rv, ov in [(-0.07, 0.0, 0.0, 0.0), (-0.05, 0.06, 0.07, 0.0), (0.02, 0.085, 0.12, -0.02), (0.1, 0.095, 0.15, -0.045),
                                  (0.2, 0.085, 0.12, -0.028), (0.3, 0.068, 0.088, -0.006), (0.42, 0.058, 0.07, 0.0), (0.5, 0.062, 0.078, -0.004),
                                  (0.56, 0.058, 0.07, -0.006), (0.6, 0.042, 0.048, -0.006), (0.618, 0.0, 0.0, -0.006)]:
                st.append((HEAD + d * t, rx, rv, ov))
            loft(p, catmull(st, 3), W, seg=22)
            v = d.cross(X)
            for e in (1, -1):   # 耳朵：前额一侧、项部前面，向上微张
                base = HEAD + d * 0.03 + v * 0.085 + X * (0.052 * e)
                ed = (v * 0.7 + Z * 0.55 + X * (0.25 * e) - d * 0.15).normalized()
                ear = [(base - ed * 0.02, 0.0, 0.0), (base, 0.024, 0.016), (base + ed * 0.05, 0.03, 0.02), (base + ed * 0.1, 0.019, 0.013),
                       (base + ed * 0.13, 0.0, 0.0)]
                loft(p, ear, W, seg=10, hint=d)
        self.seg("Head", "Neck", HEAD, head, [W])
        self.head_d = d

        # 尾：尾根短而细，向后再下垂，木雕的"尾毛"渐宽再收尖
        def tail(p):
            p.sphere(0.05, J, xf=T(*TAIL), seg=12, rings=7)
            st = [(TAIL + Vector((0, -0.02, 0.01)), 0.0, 0.0), (TAIL + Vector((0, 0.0, 0.0)), 0.04, 0.042), (TAIL + Vector((0, 0.09, -0.06)), 0.045, 0.048),
                  (TAIL + Vector((0, 0.15, -0.2)), 0.06, 0.07), (TAIL + Vector((0, 0.17, -0.42)), 0.07, 0.075), (TAIL + Vector((0, 0.16, -0.66)), 0.055, 0.058),
                  (TAIL + Vector((0, 0.14, -0.84)), 0.025, 0.028), (TAIL + Vector((0, 0.13, -0.9)), 0.0, 0.0)]
            loft(p, catmull(st, 3), W, seg=14)
        self.seg("Tail", "Body", TAIL, tail, [W, J])

        for side, x in (("L", 1), ("R", -1)):
            self._leg(f"F{side}", FORE, FORE_X * x, fore=True)
            self._leg(f"H{side}", HIND, HIND_X * x, fore=False)

    def _leg(self, pre, J_, x, fore):
        W, Jm, H = self.WOOD, self.JOINT, self.HOOF
        up, lo, pa, ho = (sx(J_[k], x) for k in ("upper", "lower", "pastern", "hoof"))
        mid = sx(J_["elbow" if fore else "stifle"], x)

        def upper(p):
            p.sphere(0.085 if fore else 0.1, Jm, xf=T(*up), seg=16, rings=9)
            if fore:   # 肩 → 肘（上臂，向后下）→ 前臂（竖直，向下收细）
                st = [(up + Vector((0, -0.02, 0.06)), 0.0, 0.0), (up, 0.08, 0.1), (mid, 0.088, 0.115, 0.01), (mid.lerp(lo, 0.35), 0.072, 0.088),
                      (mid.lerp(lo, 0.75), 0.054, 0.064), (lo + Vector((0, 0, 0.02)), 0.046, 0.054), (lo, 0.0, 0.0)]
            else:      # 髋 → 膝（股骨，向前下）→ 胫（向后下到跗关节）
                st = [(up + Vector((0, 0.02, 0.09)), 0.0, 0.0), (up, 0.095, 0.15, -0.03), (up.lerp(mid, 0.5), 0.1, 0.18, -0.07), (mid, 0.088, 0.14, -0.06),
                      (mid.lerp(lo, 0.4), 0.07, 0.1, -0.025), (mid.lerp(lo, 0.8), 0.05, 0.066), (lo + Vector((0, -0.01, 0.02)), 0.044, 0.052), (lo, 0.0, 0.0)]
            loft(p, catmull(st, 3), W, seg=16)
        self.seg(f"{pre}_Upper", "Body", up, upper, [Jm, W])

        def lower(p):
            p.sphere(0.052 if fore else 0.05, Jm, xf=T(*lo), seg=14, rings=8)
            if not fore:  # 跗骨结节（飞节后面的突起）
                loft(p, [(lo + Vector((0, -0.01, 0.03)), 0.0, 0.0), (lo + Vector((0, 0.03, 0.03)), 0.028, 0.03),
                         (lo + Vector((0, 0.065, 0.045)), 0.022, 0.024), (lo + Vector((0, 0.08, 0.05)), 0.0, 0.0)], W, seg=10)
            st = [(lo, 0.0, 0.0), (lo + (pa - lo) * 0.08, 0.044, 0.052), (lo.lerp(pa, 0.5), 0.035, 0.048), (pa + (lo - pa).normalized() * 0.03, 0.039, 0.05), (pa, 0.0, 0.0)]
            loft(p, catmull(st, 3), W, seg=14)
        self.seg(f"{pre}_Lower", f"{pre}_Upper", lo, lower, [Jm, W])

        def pastern(p):
            p.sphere(0.046, Jm, xf=T(*pa), seg=14, rings=8)
            st = [(pa, 0.0, 0.0), (pa + (ho - pa) * 0.15, 0.032, 0.036), (pa.lerp(ho, 0.6), 0.03, 0.033), (ho, 0.033, 0.035), (ho + (ho - pa) * 0.1, 0.0, 0.0)]
            loft(p, st, W, seg=12)
        self.seg(f"{pre}_Pastern", f"{pre}_Lower", pa, pastern, [Jm, W])

        def hoof(p):  # 竖直车削：底面平贴地面，前壁 ~50° 前倾
            h = ho.z
            prof = [(0.0, 0.0, 0.0, 0, -0.022), (0.0, 0.058, 0.066, 0, -0.022), (0.006, 0.06, 0.068, 0, -0.022), (h * 0.55, 0.052, 0.057, 0, -0.01),
                    (h - 0.006, 0.044, 0.046, 0, 0.0), (h, 0.036, 0.038, 0, 0.0), (h + 0.004, 0.0, 0.0, 0, 0.0)]
            p.lathe(prof, H, seg=18, xf=T(ho.x, ho.y, 0))
        self.seg(f"{pre}_Hoof", f"{pre}_Pastern", ho, hoof, [H])

    # ---------- 挽具 ----------
    def neck_frame(self, s):
        nd = HEAD - NECK
        t = nd.normalized(); v = t.cross(X)
        return NECK + nd * s, t, v

    def _tack(self):
        L, C, I, B = self.LEATHER, self.COLLAR, self.IRON, self.BRASS
        # 颈圈 + 轭木（hames）：套在颈根、压在肩上；挂在 Body 上（颈转动时颈圈不跟着转，和真的一样）
        c0, t, v = self.neck_frame(0.2)
        rx, rv, ov = 0.14 + 0.0, 0.24 + 0.0, 0.02
        def collar(p):
            ring = []
            for j in range(28):
                a = 2 * math.pi * j / 28
                # 下宽上窄的泪滴形：底部（a=0，喉侧）更圆、更厚
                k = 1.0 + 0.12 * math.cos(a)
                ring.append((c0 + v * ov + X * (rx + 0.055) * k * math.sin(a) - v * (rv + 0.05) * math.cos(a), 0.05 + 0.012 * math.cos(a), 0.055))
            loft(p, ring, C, seg=12, hint=t, closed=True)
            for e in (1, -1):  # 轭木：沿颈圈前缘外侧，从底到顶再伸出一截，顶端铜球
                pts = []
                for j in range(9):
                    a = e * (0.5 + (math.pi - 0.62) * j / 8)
                    k = 1.0 + 0.12 * math.cos(a)
                    pts.append((c0 + v * ov - t * 0.035 + X * (rx + 0.1) * k * math.sin(a) - v * (rv + 0.095) * math.cos(a), 0.016, 0.022))
                tip = Vector(pts[-1][0]) + v * 0.1 + X * (0.03 * e)
                pts.append((tip, 0.014, 0.018))
                loft(p, [(Vector(pts[0][0]) + v * 0.02, 0.0, 0.0)] + pts + [(tip + v * 0.012, 0.0, 0.0)], I, seg=8, hint=t)
                p.sphere(0.022, B, xf=T(*(tip + v * 0.02)), seg=10, rings=6)
                # 挽钩（hame tug）：侧面中段
                a = e * 0.62
                tug = c0 + v * ov - t * 0.02 + X * (rx + 0.12) * 1.12 * math.sin(a) - v * (rv + 0.09) * math.cos(a)
                p.box((0.03, 0.1, 0.05), L, xf=T(*tug), bevel=0.008)
            a = 0.62
            self.tug = c0 + v * ov - t * 0.02 + X * (rx + 0.12) * math.sin(a) - v * (rv + 0.09) * math.cos(a)
        self.tack("Body", "Tack_Collar", collar, [C, I, B, L])

        # 挽绳残段：从挽钩沿身体两侧向后，到臀后。车上的挽绳从 TRACE_END 接到车前的单马横木
        def traces(p):
            for e in (1, -1):
                st = Vector((self.tug.x * 1.12 * e, self.tug.y + 0.05, self.tug.z))
                end = Vector((TRACE_END.x * e, TRACE_END.y, TRACE_END.z))
                pts = []
                for k in range(13):
                    f = k / 12
                    pnt = st.lerp(end, f) - Vector((0, 0, 0.03 * math.sin(math.pi * f)))
                    hw = max(trunk_halfwidth(pnt.y, pnt.z), 0.0)
                    near_leg = max(0.0, 1 - abs(pnt.y - FORE["upper"].y) / 0.2) * 0.27 + max(0.0, 1 - abs(pnt.y - 0.45) / 0.3) * 0.31
                    xx = max(abs(pnt.x), hw + 0.03, near_leg)
                    pts.append((Vector((xx * e, pnt.y, pnt.z)), 0.024, 0.007))
                loft(p, pts, L, seg=8, hint=Z)
        self.tack("Body", "Tack_Traces", traces, [L])

        # 背垫（小鞍）+ 肚带 + 背带（到尾根）
        def saddle(p):
            y0 = -0.24
            rx_, ry_, cz = trunk_at(-y0)
            p.lathe([(-y0 - 0.035, rx_ + 0.012, ry_ + 0.012, 0, cz), (-y0 + 0.035, rx_ + 0.012, ry_ + 0.012, 0, cz)], L, seg=28, xf=R("X", 90), cap=False)
            p.lathe([(-y0 - 0.034, rx_ + 0.0, ry_ + 0.0, 0, cz), (-y0 - 0.035, rx_ + 0.012, ry_ + 0.012, 0, cz)], L, seg=28, xf=R("X", 90), cap=False)
            p.lathe([(-y0 + 0.035, rx_ + 0.012, ry_ + 0.012, 0, cz), (-y0 + 0.034, rx_ + 0.0, ry_ + 0.0, 0, cz)], L, seg=28, xf=R("X", 90), cap=False)
            top = cz + ry_
            p.lathe([(-y0 - 0.09, rx_ * 0.62, ry_ + 0.014, 0, cz), (-y0 - 0.08, rx_ * 0.66, ry_ + 0.04, 0, cz), (-y0 + 0.08, rx_ * 0.66, ry_ + 0.04, 0, cz),
                     (-y0 + 0.09, rx_ * 0.62, ry_ + 0.014, 0, cz)], C, seg=28, xf=R("X", 90), arc=(math.pi - 0.75, math.pi + 0.75), cap=False)
            for e in (1, -1):   # 缰绳圈（terret）
                p.lathe([(0, 0.0, 0.0), (0.005, 0.012, 0.012), (0.06, 0.012, 0.012), (0.065, 0, 0)], B, seg=8, xf=T(0.1 * e, y0, top + 0.03))
                loft(p, [(Vector((0.1 * e, y0, top + 0.1)) + Vector((0, math.sin(a), math.cos(a))) * 0.03, 0.006, 0.006) for a in
                         [2 * math.pi * j / 12 for j in range(12)]], B, seg=6, hint=X, closed=True)
            # 背带（crupper strap）沿脊线到尾根
            pts = []
            for k in range(12):
                y = y0 + (TAIL.y - 0.05 - y0) * k / 11
                rx2, ry2, cz2 = trunk_at(-y)
                pts.append((Vector((0, y, max(cz2 + ry2, 0) + 0.006)), 0.022, 0.005))
            loft(p, pts, L, seg=8, hint=X)
            # 臀带：跨过十字部，两端落到后鞦上
            yh = 0.5
            rx3, ry3, cz3 = trunk_at(-yh)
            p.lathe([(-yh - 0.025, rx3 + 0.035, ry3 + 0.016, 0, cz3), (-yh + 0.025, rx3 + 0.035, ry3 + 0.016, 0, cz3)], L, seg=28, xf=R("X", 90),
                    arc=(1.25, 2 * math.pi - 1.25), cap=False)
        self.tack("Body", "Tack_Saddle", saddle, [L, C, B])

        # 后鞦（breeching）：水平绕过臀部
        def breeching(p):
            zb = 1.13
            pts = []
            y_end = max(y for y in [0.5 + k * 0.005 for k in range(80)] if trunk_halfwidth(y, zb) > 0.06)
            ys = [0.2 + (y_end - 0.2) * k / 14 for k in range(15)]
            def hw(y):
                bulge = 0.04 * max(0.0, 1 - abs(y - 0.55) / 0.3)   # 盖过大腿外侧
                return trunk_halfwidth(y, zb) + bulge + 0.018
            outline = [(hw(y), y) for y in ys]
            # 臀后的封口：在尾端用半个椭圆把左右连起来
            xe, ye = outline[-1]
            back = [(xe * math.cos(a), ye + 0.035 * math.sin(a)) for a in [math.pi / 2 * k / 6 for k in range(1, 7)]]
            left = outline + back
            path = left + [(-x, y) for x, y in reversed(left[:-1])]
            for x, y in path:
                pts.append((Vector((x, y, zb)), 0.03, 0.006))
            loft(p, pts, L, seg=8, hint=Z)
        self.tack("Body", "Tack_Breeching", breeching, [L])

        # 笼头：项带 + 额带 + 颊带 + 鼻革 + 眼罩 + 衔铁
        d = self.head_d; v = d.cross(X)
        hst = [(-0.05, 0.06, 0.07, 0.0), (0.02, 0.085, 0.12, -0.02), (0.1, 0.095, 0.15, -0.045), (0.2, 0.085, 0.12, -0.028), (0.3, 0.068, 0.088, -0.006),
               (0.42, 0.058, 0.07, 0.0), (0.5, 0.062, 0.078, -0.004), (0.56, 0.058, 0.07, -0.006)]
        def hd(t):
            for a_, b_ in zip(hst, hst[1:]):
                if a_[0] <= t <= b_[0]:
                    k = (t - a_[0]) / (b_[0] - a_[0])
                    return tuple(a_[i] + (b_[i] - a_[i]) * k for i in (1, 2, 3))
            return hst[-1][1:]
        def P(t, a, e):
            rx, rv, ov = hd(t)
            return HEAD + d * t + v * ov + X * (rx + e) * math.sin(a) - v * (rv + e) * math.cos(a)
        def bridle(p):
            for t0, w in ((0.035, 0.026), (0.4, 0.024)):   # 项带 / 喉革一圈、鼻革一圈
                loft(p, [(P(t0, 2 * math.pi * j / 24, 0.008), w * 0.5, 0.004) for j in range(24)], L, seg=6, hint=d, closed=True)
            loft(p, [(P(0.075, math.pi + 1.1 * (2 * j / 10 - 1), 0.008), 0.011, 0.004) for j in range(11)], L, seg=6, hint=d)  # 额带
            for e in (1, -1):
                a = e * math.pi / 2
                loft(p, [(P(t, a, 0.009), 0.012, 0.004) for t in [0.035 + (0.5 - 0.035) * k / 8 for k in range(9)]], L, seg=6, hint=v)  # 颊带
                # 眼罩：外凸的方皮片，挂在颊带上、略在眼位之上
                ab = e * (math.pi / 2 + 0.38)
                cpt = P(0.15, ab, 0.03)
                nrm = (X * math.sin(ab) - v * math.cos(ab)).normalized()
                w_ = nrm.cross(d).normalized()
                M = Matrix((nrm, d, w_)).transposed().to_4x4()
                p.box((0.012, 0.11, 0.1), C, xf=T(*cpt) @ M, bevel=0.005)
                # 衔铁环
                bc = P(0.52, e * math.pi / 2 * 0.72, 0.01)
                loft(p, [(bc + (d * math.cos(q) + v * math.sin(q)) * 0.03, 0.006, 0.006) for q in [2 * math.pi * j / 12 for j in range(12)]],
                     B, seg=6, hint=X, closed=True)
            # 衔铁杆（穿过嘴角）
            b0 = P(0.52, math.pi / 2 * 0.72, 0.01); b1 = P(0.52, -math.pi / 2 * 0.72, 0.01)
            loft(p, [(b0 + X * 0.005, 0, 0), (b0, 0.007, 0.007), (b1, 0.007, 0.007), (b1 - X * 0.005, 0, 0)], I, seg=8, hint=Z)
            self.bit = (b0, b1)
        self.tack("Head", "Tack_Bridle", bridle, [L, C, B, I])

    def objects(self):
        return mc.descendants(self.root)

    def rest(self):
        for sg in self.segs.values():
            sg["ob"].rotation_euler = (0, 0, 0)
        self.root.location.z = 0


# ------------------------------------------------------------------ 行走（4 拍：左后-左前-右后-右前），与 docs/horse_rig.md 同表
# 角度都是"绕局部 X 的度数"，Blender 与 Unity 同号（Unity (x,y,z) = Blender (-x,z,-y)）。负 = 向前摆。
DUTY = 0.62
PHASE = {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}
WALK = dict(F_pro=21.0, F_ret=19.0, F_knee=55.0, F_fet_swing=38.0,
            H_pro=19.0, H_ret=18.0, H_hock=52.0, H_fet_swing=45.0,
            fet_min=-40.0, fet_max=14.0, neck=4.0, head=3.0, tail=6.0)
HOOF_H = FORE["hoof"].z


def ease(w):
    return 0.5 - 0.5 * math.cos(math.pi * w)


def raw_angles(leg, ph):
    """不含球节 IK 的原始曲线：(Upper, Lower, Pastern, 是否支撑, 支撑/摆动进度)。"""
    W = WALK; fore = leg[0] == "F"
    pro, ret = (W["F_pro"], W["F_ret"]) if fore else (W["H_pro"], W["H_ret"])
    ph = (ph - PHASE[leg]) % 1.0
    if ph < DUTY:      # 支撑期：上段从前摆匀速转到后摆
        u = ph / DUTY
        return -pro + (pro + ret) * u, (0.0 if fore else -3.0 * math.sin(math.pi * u)), 0.0, True, u
    w = (ph - DUTY) / (1 - DUTY)   # 摆动期：缓入缓出摆回前面；腕 / 跗、球节屈曲把蹄抬起
    up = ret - (pro + ret) * ease(w)
    bump = math.sin(math.pi * min(1.0, w / 0.88))
    lo = W["F_knee"] * bump if fore else -W["H_hock"] * bump
    pa = (W["F_fet_swing"] if fore else W["H_fet_swing"]) * bump
    return up, lo, pa, False, w


def _rx(vec, deg):
    a = math.radians(deg); c, s_ = math.cos(a), math.sin(a)
    return Vector((vec.x, vec.y * c - vec.z * s_, vec.y * s_ + vec.z * c))


def fetlock_and_reach(leg, up, lo):
    J = FORE if leg[0] == "F" else HIND
    q = J["upper"] + _rx(J["lower"] - J["upper"], up) + _rx(J["pastern"] - J["lower"], up + lo)
    return q, J["hoof"] - J["pastern"]


def coronet_z(leg, up, lo, pa):
    q, w = fetlock_and_reach(leg, up, lo)
    return (q + _rx(w, up + lo + pa)).z


def hoof_min_z(leg, up, lo, pa, tilt):
    """蹄底最低点（根在地面时）：蹄冠位置 + 蹄底前后两点按蹄子的累计倾角 tilt 旋转。"""
    q, w = fetlock_and_reach(leg, up, lo)
    cor = q + _rx(w, up + lo + pa)
    return min((cor + _rx(Vector((0, dy, -HOOF_H)), tilt)).z for dy in (-0.09, 0.046))


def solve_pastern(leg, up, lo, root_z):
    """支撑腿：解球节角，让蹄冠高度 = 蹄高 - root_z（蹄子保持水平时蹄底正好贴地）。"""
    q, w = fetlock_and_reach(leg, up, lo)
    k = HOOF_H - root_z - q.z
    R_ = math.hypot(w.y, w.z); dl = math.atan2(w.y, w.z)
    # w 绕 X 转 α 后 z = w.y sinα + w.z cosα = R cos(α - dl)
    c = max(-1.0, min(1.0, k / R_))
    best = None
    for sgn in (1, -1):
        alpha = math.degrees(dl + sgn * math.acos(c))
        pa = alpha - up - lo
        pa = (pa + 180) % 360 - 180
        if best is None or abs(pa) < abs(best):
            best = pa
    return best


def _bounds(ph):
    """支撑腿都够得着地面的根高度区间 [lo, hi]：hi = 球节最直时，lo = 球节下沉到极限时。"""
    W = WALK; hi, lo = 9.0, -9.0
    for leg in ("FL", "FR", "HL", "HR"):
        up, lo_, pa, st, _ = raw_angles(leg, ph)
        if st:
            hi = min(hi, HOOF_H - coronet_z(leg, up, lo_, W["fet_max"]))
            lo = max(lo, HOOF_H - coronet_z(leg, up, lo_, W["fet_min"]))
    return lo, hi


_ROOT = None


def root_height(ph):
    """平滑的根高度曲线：取 hi 的环形滑动平均再夹回 [lo, hi]，避免新腿着地时身体突然一沉。"""
    global _ROOT
    n = 128
    if _ROOT is None:
        bs = [_bounds(k / n) for k in range(n)]
        his = [b[1] for b in bs]
        sm = [sum(his[(k + j) % n] for j in range(-12, 13)) / 25 - 0.004 for k in range(n)]
        sm = [sum(sm[(k + j) % n] for j in range(-6, 7)) / 13 for k in range(n)]
        _ROOT = [min(max(v, bs[k][0]), bs[k][1]) for k, v in enumerate(sm)]
    x = (ph % 1.0) * n; i = int(x) % n; f = x - int(x)
    return _ROOT[i] * (1 - f) + _ROOT[(i + 1) % n] * f


def stance_pastern(leg, ph, root_z):
    up, lo, pa, st, u = raw_angles(leg, ph)
    return max(WALK["fet_min"], min(WALK["fet_max"], solve_pastern(leg, up, lo, root_z)))


def walk_angles(ph):
    """一个相位的完整姿势：{leg: (Upper, Lower, Pastern, Hoof)}，根节点高度 root_z（米，≤0 = 下沉），支撑蹄最大误差。"""
    root_z = root_height(ph)
    out, err = {}, 0.0
    for leg in ("FL", "FR", "HL", "HR"):
        up, lo, pa, st, prog = raw_angles(leg, ph)
        if st:
            pa = stance_pastern(leg, ph, root_z)
            err = max(err, abs(coronet_z(leg, up, lo, pa) + root_z - HOOF_H))
            ho = -(up + lo + pa)                  # 蹄底保持水平
        else:
            lp = (ph - PHASE[leg]) % 1.0
            bump = math.sin(math.pi * min(1.0, prog / 0.88))
            # 离地瞬间从支撑末的球节角过渡；着地前过渡到下一次支撑起点的球节角
            pe = stance_pastern(leg, PHASE[leg] + DUTY - 1e-4, root_height(PHASE[leg] + DUTY - 1e-4))
            ps = stance_pastern(leg, PHASE[leg] + 1e-4, root_height(PHASE[leg] + 1e-4))
            base = pe * (1 - ease(prog)) + ps * ease(prog)
            pa = base + pa
            # 蹄关节（coffin joint）只在 -20..+25° 内活动：离地 / 着地时蹄底水平，摆动中段随球节一起向后折
            def hoof_of(up_, lo_, pa_):
                return max(-20.0, min(25.0, -(up_ + lo_ + pa_) * (1 - bump) + 15.0 * bump))
            ho = hoof_of(up, lo, pa)
            # 离地间隙：蹄底任一点低于 1.5 cm 就继续屈腕 / 跗关节（前 +，后 -）
            sgn = 1.0 if leg[0] == "F" else -1.0
            for _ in range(40):
                if hoof_min_z(leg, up, lo, pa, up + lo + pa + ho) + root_z >= 0.015 or prog > 0.97:
                    break
                lo += sgn * 2.0; pa += 1.0
                ho = hoof_of(up, lo, pa)
        out[leg] = (up, lo, pa, ho)
    return out, root_z, err


def pose_walk(h, ph):
    ang, root_z, err = walk_angles(ph)
    for leg, vals in ang.items():
        for part, a in zip(("Upper", "Lower", "Pastern", "Hoof"), vals):
            h.segs[f"{leg}_{part}"]["ob"].rotation_euler = (math.radians(a), 0, 0)
    nod = math.sin(4 * math.pi * (ph - PHASE["FL"]))   # 头颈每个步幅点两次头
    h.segs["Neck"]["ob"].rotation_euler = (math.radians(WALK["neck"] * nod), 0, 0)
    h.segs["Head"]["ob"].rotation_euler = (math.radians(-WALK["head"] * nod), 0, 0)
    h.segs["Tail"]["ob"].rotation_euler = (0, math.radians(WALK["tail"] * math.sin(2 * math.pi * ph)), 0)
    h.root.location.z = root_z
    bpy.context.view_layer.update()
    return root_z, err


def sole_min_z(h, leg):
    ob = h.segs[f"{leg}_Hoof"]["ob"]
    mw = ob.matrix_world
    return min((mw @ v.co).z for v in ob.data.vertices)


def hoof_point(h, leg):
    ob = h.segs[f"{leg}_Hoof"]["ob"]
    mw = ob.matrix_world
    zs = [(mw @ v.co) for v in ob.data.vertices]
    lo = min(p.z for p in zs)
    pts = [p for p in zs if p.z < lo + 0.004]
    return sum(pts, Vector()) / len(pts)


def walk_report(h, n=32):
    """在 Blender 里真的摆姿势量：支撑期蹄底相对身体的前后位移、步幅 = 它 / 支撑占比、根的上下起伏、
    支撑蹄离地 / 入地误差、摆动蹄最低点。"""
    rep = {"bob": [], "stance_err": 0.0, "swing_min": 9.0}
    for k in range(n):
        ph = k / n
        root_z, err = pose_walk(h, ph)
        rep["bob"].append(root_z)
        for leg in ("FL", "FR", "HL", "HR"):
            z = sole_min_z(h, leg)
            if (ph - PHASE[leg]) % 1.0 < DUTY:
                rep["stance_err"] = max(rep["stance_err"], abs(z))
            else:
                rep["swing_min"] = min(rep["swing_min"], z)
    for leg in ("FL", "HL"):
        p0 = PHASE[leg] + 1e-4; p1 = PHASE[leg] + DUTY - 1e-4
        pose_walk(h, p0); a = hoof_point(h, leg) - h.root.location
        pose_walk(h, p1); b = hoof_point(h, leg) - h.root.location
        rep[leg] = (b.y - a.y, (b.y - a.y) / DUTY)
    h.rest()
    return rep


def walk_table(n=16):
    """docs/horse_rig.md 里的关键帧表：前腿 / 后腿各自相对自身相位的四个角 + 全局根高度。"""
    rows = []
    for k in range(n):
        ph = k / n
        ang, root_z, err = walk_angles(ph)
        rows.append((ph, ang, root_z))
    return rows


def rig_report(h):
    lines = []
    for n, sg in h.segs.items():
        p = sg["pivot"]
        lines.append((n, (-p.x, p.z, -p.y)))
    return lines


def ground(coll, size=12):
    gm = mc.pbr("Ground", "Ground054", tile=2.0)
    p = Part([gm]); p.box((size, size, 0.02), gm, xf=T(0, 0, -0.01))
    return p.finish("Ground", collection=coll)


def stage(coll):
    mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.35)
    mc.studio(coll=coll, key=900, scale=2.2, warm=False)


if __name__ == "__main__":
    results = {}
    for name, tint in VARIANTS.items():
        if ONLY and name not in ONLY:
            continue
        sc = mc.reset()
        assetc = bpy.data.collections.new("Asset"); sc.collection.children.link(assetc)
        stage_c = bpy.data.collections.new("Stage"); sc.collection.children.link(stage_c)
        h = Horse(name, tint, coll=assetc)
        objs = h.objects()
        tris = mc.tri_count(objs)
        tack = mc.tri_count([o for o in objs if o.name.startswith("Tack_")])
        print(f"TRIS {name} total={tris} tack={tack}")
        assert tris <= MAX_TRIS, tris
        mc.export_glb(mc.ART / "Characters" / f"{name}.gltf", [h.root])
        for n, pos in rig_report(h):
            print(f"RIG {n} unity=({pos[0]:+.3f},{pos[1]:.3f},{pos[2]:+.3f})")
        print(f"RIG TRACE_END_L unity=({-TRACE_END.x:+.3f},{TRACE_END.z:.3f},{-TRACE_END.y:+.3f})")
        print(f"RIG BIT_L unity=({-h.bit[0].x:+.3f},{h.bit[0].z:.3f},{-h.bit[0].y:+.3f})")
        if name != "Horse":
            continue
        rep = walk_report(h)
        for leg in ("FL", "HL"):
            print(f"STRIDE {leg} stance_sweep={rep[leg][0]:.3f} stride={rep[leg][1]:.3f}")
        print(f"WALK bob=({min(rep['bob']):+.3f},{max(rep['bob']):+.3f}) stance_err={rep['stance_err']:.3f} swing_min={rep['swing_min']:+.3f}")
        for ph, ang, rz in walk_table():
            print(f"TABLE {ph:.4f} root={rz:+.3f} " + " ".join(f"{leg}=" + ",".join(f"{a:+.1f}" for a in ang[leg]) for leg in ("FL", "HL")))
        if RENDER:
            stage(stage_c)
            mc.camera("Cam", (-5.6, -0.2, 1.1), (0, -0.25, 1.0), lens=50, coll=stage_c)
            mc.render(mc.REVIEWS / "Horse.png")
            mc.camera("Cam34", (-3.4, -3.6, 1.7), (0, -0.3, 1.0), lens=45, coll=stage_c)
            mc.render(mc.REVIEWS / "Horse_34.png")
            # 轴向实测：先逐个关节单独转，量末端点在 Unity 坐标里的位移；再左侧视角渲一张（只转左腿 + 颈 / 头 / 尾）
            def tip(n_):
                ob = h.segs[n_]["ob"]; mw = ob.matrix_world
                vs = [mw @ v.co for v in ob.data.vertices]
                if n_.endswith(("Upper", "Lower", "Pastern")):   # 腿：取这条腿蹄底中心
                    return hoof_point(h, n_[:2])
                if n_ == "Neck" or n_ == "Head":
                    ob = h.segs["Head"]["ob"]; mw = ob.matrix_world
                    vs = [mw @ v.co for v in ob.data.vertices]
                    return min(vs, key=lambda q: q.y)            # 口鼻最前点
                return min(vs, key=lambda q: q.z)                # 尾尖
            for n_, e_ in [("FL_Upper", (-20, 0, 0)), ("FL_Lower", (30, 0, 0)), ("FL_Pastern", (30, 0, 0)), ("HL_Upper", (-20, 0, 0)),
                           ("HL_Lower", (-30, 0, 0)), ("HL_Pastern", (30, 0, 0)), ("Neck", (15, 0, 0)), ("Head", (15, 0, 0)),
                           ("Head", (0, 0, 20)), ("Tail", (20, 0, 0)), ("Tail", (0, 20, 0))]:
                h.rest(); bpy.context.view_layer.update(); p0 = tip(n_)
                h.segs[n_]["ob"].rotation_euler = tuple(math.radians(a_) for a_ in e_); bpy.context.view_layer.update(); p1 = tip(n_)
                d_ = p1 - p0
                ax_ = "XYZ"[[i for i in range(3) if e_[i]][0]]; ang_ = [a_ for a_ in e_ if a_][0]
                uax = {"X": "X", "Y": "Z", "Z": "Y"}[ax_]; uang = -ang_ if ax_ == "Z" else ang_
                print(f"AXIS {n_} blender {ax_}{ang_:+d} = unity {uax}{uang:+d} -> end moves unity "
                      f"(dx={-d_.x:+.3f}, dy={d_.z:+.3f}, dz={-d_.y:+.3f})")
            h.rest()
            AX = {"FL_Upper": (-25, 0, 0), "HL_Lower": (-40, 0, 0), "Neck": (15, 0, 0), "Head": (0, 0, 20), "Tail": (0, 25, 0)}
            for n_, e_ in AX.items():
                h.segs[n_]["ob"].rotation_euler = tuple(math.radians(a) for a in e_)
            h.segs["HL_Pastern"]["ob"].rotation_euler = (math.radians(40), 0, 0)
            mc.camera("CamAx", (4.6, -1.6, 1.6), (0, -0.3, 0.95), lens=40, coll=stage_c)
            mc.render(mc.REVIEWS / "Horse_axes.png")
            h.rest()
            pose_walk(h, 0.1)
            mc.camera("CamW", (-5.6, -0.2, 1.1), (0, -0.25, 1.0), lens=50, coll=stage_c)
            mc.render(mc.REVIEWS / "Horse_walk.png")
            h.rest()
