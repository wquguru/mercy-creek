"""关节木头人偶（真人大小的素描人偶）+ 每个角色的刚性服装壳。层级即骨架，不蒙皮。

blender --background --python tools/blender/build_mannequin.py -- [--only Gus] [--no-render] [--samples N] [--lineup]
输出：Game/Assets/_MercyCreek/Art/Characters/Mannequin_<Name>.glb；评审图 Reviews/blender/Mannequin_<Name>{,_pose}.png
坐标：角色面朝 Blender -Y（= glTFast 导入后 Unity +Z），Z 向上，原点在两脚之间的地面；L = 角色左手 = Blender +X = Unity -X。
每段是一个对象，原点在关节轴心，静止旋转为单位旋转（手臂自然下垂、外展 8°）。节点名见 docs/mannequin_rig.md。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy
from mathutils import Vector, Matrix
import mc_common as mc
from mc_common import T, R, Part

A = mc.args()
RENDER = "--no-render" not in A
SAMPLES = int(A[A.index("--samples") + 1]) if "--samples" in A else 48
ONLY = A[A.index("--only") + 1] if "--only" in A else None
LINEUP = "--lineup" in A
LINEUP_TOWN = "--lineup-town" in A
VARIANTS = ["Gus", "Professor", "Crane", "Nell", "Driver", "Townsman", "Townswoman"]
TOWN = ["Driver", "Townsman", "Townswoman"]   # 街上的群演（--lineup-town 出合影）
FEMALE = ("Nell", "Townswoman")               # 用女性骨架（整体 0.943、肩窄胯宽）
ABD = math.radians(8.0)  # 手臂静止外展角


def frame(d):
    """段的局部坐标：局部 Z 沿骨段方向。向下的段先绕 X 转 180°（局部 X 仍≈世界 X，局部 +Y = 世界前方 -Y）。"""
    d = Vector(d).normalized()
    if d.z < -0.5:
        base = Matrix.Rotation(math.pi, 4, "X")
        return Vector((0, 0, -1)).rotation_difference(d).to_matrix().to_4x4() @ base
    if abs(d.z) < 0.5:  # 朝前（脚）：局部 Z → 世界 -Y，局部 Y → 世界 +Z
        return Matrix.Rotation(math.radians(90), 4, "X")
    return Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()


def norm5(p):
    return tuple(p) + (0.0,) * (5 - len(p))


def interp(prof, t):
    prof = [norm5(p) for p in prof]
    if t <= prof[0][0]: return prof[0]
    for a, b in zip(prof, prof[1:]):
        if a[0] <= t <= b[0]:
            k = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * k for i in range(5))
    return prof[-1]


def pad(prof, t0, t1, d, hem=True, dy=0.0, minr=0.03, flare=None):
    """沿身体轮廓外扩 d 的布料壳。hem=True 时两端收回到身体半径，避免看到壳的内侧。
    flare(t)->额外外扩量。dy：沿局部 Y 的整体偏移。"""
    p0, p1 = norm5(prof[0])[0], norm5(prof[-1])[0]
    if abs(t0 - p0) < 1e-4: t0 = p0          # 浮点误差会把极点变成一圈开口
    if abs(t1 - p1) < 1e-4: t1 = p1
    ts = sorted({t0, t1, *[p[0] for p in prof if t0 < p[0] < t1]})
    # 插入更多采样，让壳够圆
    fine = []
    for a, b in zip(ts, ts[1:]):
        n = max(1, int((b - a) / 0.05))
        fine += [a + (b - a) * i / n for i in range(n)]
    fine.append(ts[-1])
    nz = [norm5(p)[0] for p in prof if norm5(p)[1] > 2e-3]
    inner = (min(nz), max(nz)) if nz else (p0, p1)
    out = []
    for t in fine:
        _, rx, ry, ox, oy = interp(prof, t)
        e = d + (flare(t) if flare else 0.0)
        if rx < 2e-3 and t in (p0, p1):          # 轮廓自身的极点：在壳端点处保持封闭圆顶，在壳中间则跳过
            if t in (t0, t1):
                out.append((t - e if t == p0 else t + e, 0.0, 0.0, ox, oy + dy))
            continue
        if not (inner[0] <= t <= inner[1]):       # 超出段身（关节处）：至少 minr，盖住关节球
            rx, ry = max(rx, minr), max(ry, minr)
        out.append((t, rx + e, ry + e, ox, oy + dy))
    if hem:
        if out[0][1] > 1e-6:
            _, rx, ry, ox, oy = interp(prof, t0); out.insert(0, (t0 - 0.002, max(rx, minr) * 0.98, max(ry, minr) * 0.98, ox, oy + dy))
        if out[-1][1] > 1e-6:
            _, rx, ry, ox, oy = interp(prof, t1); out.append((t1 + 0.002, max(rx, minr) * 0.98, max(ry, minr) * 0.98, ox, oy + dy))
    return out


def vlathe(p, prof, gaps, mat, seg, xf):
    """开口宽度逐圈变化的车削（V 领 / 敞怀）。gaps[i] = 第 i 圈前方开口的半角（弧度）。"""
    bm, uvl = p.bm, p.uv
    tile = mat.get("tile", 1.0)
    rings = []
    for (t, rx, ry, ox, oy), g in zip([norm5(q) for q in prof], gaps):
        rings.append([bm.verts.new(xf @ Vector((ox + rx * math.sin(a), oy - ry * math.cos(a), t)))
                      for a in [g + (2 * math.pi - 2 * g) * j / seg for j in range(seg + 1)]])
    faces = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(seg):
            f = bm.faces.new([A[j], A[j + 1], B[j + 1], B[j]])
            for lp, (u, v) in zip(f.loops, [(j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1)]):
                lp[uvl].uv = (u / seg * 0.9 / tile, prof[min(int(v), len(prof) - 1)][0] / tile)
            faces.append(f)
    p._take(faces, mat, True)


class Mannequin:
    def __init__(self, name, offset=(0, 0, 0), coll=None):
        self.name = name
        self.coll = coll or bpy.context.scene.collection
        self.nell = name in FEMALE
        s = self.s = 0.943 if self.nell else 1.0
        self.off = Vector(offset)
        # ---------- 材质 ----------
        self.WOOD = mc.pbr("MannequinWood", "Wood050", tile=0.28, size=2048, tint=(0.86, 0.8, 0.68), rough_mul=0.6, normal=0.6)
        self.JOINT = mc.pbr("MannequinJoint", "Wood092", tile=0.25, tint=(0.45, 0.33, 0.25), rough_mul=0.5, normal=0.3)
        self.segs = {}
        self.root = mc.empty("Mannequin", location=self.off, collection=self.coll)
        self._body()

    # 世界坐标（相对于根）→ 段
    def seg(self, name, parent, pivot, direction, length, prof, ball=None, mat=None, seg=14, extra=None):
        pivot = Vector(pivot)
        xf = T(*pivot) @ frame(direction)
        p = Part([mat or self.WOOD])
        if ball:
            p.sphere(ball, self.JOINT, xf=T(*pivot), seg=14, rings=8)
        if prof:
            p.lathe(prof, mat or self.WOOD, seg=seg, xf=xf, swap_uv=True)
        if extra:
            extra(p, xf)
        ob = p.finish(name, collection=self.coll)
        ob.data.transform(T(*(-pivot)))
        par = self.segs[parent]["ob"] if parent else self.root
        ppiv = self.segs[parent]["pivot"] if parent else Vector((0, 0, 0))
        ob.parent = par; ob.location = pivot - ppiv
        self.segs[name] = dict(ob=ob, pivot=pivot, dir=Vector(direction).normalized(), len=length, prof=prof, xf=xf)
        return ob

    def cloth(self, segname, cname, build, mats):
        """build(part, xf) 在该段局部框架里建布料；结果挂在段下，原点 = 关节。"""
        sg = self.segs[segname]
        p = Part(mats)
        build(p, sg["xf"])
        ob = p.finish(cname, collection=self.coll, smooth_angle=60)
        ob.data.transform(T(*(-sg["pivot"])))
        ob.parent = sg["ob"]; ob.location = (0, 0, 0)
        return ob

    def torso(self, segname, cname, mat, z0, z1, d, seg=20, arc=None, hem_top=True, hem_bot=True, flare=None, gap=None):
        """躯干布料：沿统一的躯干外形（世界高度 z）外扩 d，切成 [z0,z1] 一段挂到该段上。相邻段的布料互相重叠，弯腰时不露缝。"""
        s = self.s
        sg = self.segs[segname]; pz = sg["pivot"].z
        env = self.TORSO
        zs = [z0] + [e[0] for e in env if z0 < e[0] < z1] + [z1]
        out = []
        for z in zs:
            _, rx, ry, _, oy = interp([(e[0], e[1], e[2], 0, e[3]) for e in env], z)
            f = flare(z) if flare else 0.0
            out.append((z - pz, rx + d + f, ry + d + f, 0, oy))
        if hem_bot:
            t, rx, ry, ox, oy = out[0]; out.insert(0, (t - 0.001, rx - 0.008, ry - 0.008, ox, oy))
        if hem_top:
            t, rx, ry, ox, oy = out[-1]; out.append((t + 0.001, rx - 0.008, ry - 0.008, ox, oy))
        if gap:
            gaps = [gap(t + pz) for t, *_ in out]
            return self.cloth(segname, cname, lambda p, xf: vlathe(p, out, gaps, mat, seg, xf), [mat])
        return self.cloth(segname, cname, lambda p, xf: p.lathe(out, mat, seg=seg, xf=xf, arc=arc, cap=False), [mat])

    def shell(self, segname, cname, mat, t0, t1, d, seg=16, arc=None, flare=None, dy=0.0, hem=True, prof=None, minr=0.03):
        sg = self.segs[segname]
        pr = pad(prof or sg["prof"], t0, t1, d, hem=hem, flare=flare, dy=dy, minr=minr)
        return self.cloth(segname, cname, lambda p, xf: p.lathe(pr, mat, seg=seg, xf=xf, arc=arc), [mat])

    # ---------- 身体 ----------
    def _body(self):
        s = self.s; nell = self.nell
        sc = lambda prof: [tuple(v * s for v in norm5(p)) for p in prof]
        HIP_Z, WAIST_Z, CHEST_Z, NECK_Z, HEAD_Z = 0.98 * s, 1.085 * s, 1.22 * s, 1.465 * s, 1.555 * s
        SH_X = (0.168 if nell else 0.185) * s; SH_Z = 1.425 * s
        HIP_X = (0.088 if nell else 0.092) * s
        KNEE_Z, ANK_Z = 0.505 * s, 0.085 * s
        UP, FORE, PALM = 0.29 * s, 0.255 * s, 0.096 * s
        hipw = 1.08 if nell else 1.0     # 女性骨盆略宽、胸廓略窄
        chw = 0.9 if nell else 1.0
        self.dims = dict(hip_z=HIP_Z, waist_z=WAIST_Z, chest_z=CHEST_Z, neck_z=NECK_Z, head_z=HEAD_Z, shoulder_x=SH_X,
                         shoulder_z=SH_Z, hip_x=HIP_X, knee_z=KNEE_Z, ankle_z=ANK_Z, upper_arm=UP, forearm=FORE, palm=PALM)
        up = (0, 0, 1)
        # 统一的躯干外形（身体表面，世界 z, rx, ry, oy），布料按它外扩
        hw = 1.1 if nell else 1.0; ww = 0.88 if nell else 1.0; cw = 0.9 if nell else 1.0
        self.TORSO = [(z * s, rx * s, ry * s, oy * s) for z, rx, ry, oy in [
            (0.84, 0.10 * hw, 0.08, 0.0), (0.88, 0.15 * hw, 0.1, 0.006), (0.94, 0.165 * hw, 0.106, 0.008), (1.0, 0.16 * hw, 0.102, 0.006),
            (1.05, 0.145 * ww, 0.094, 0.002), (1.1, 0.132 * ww, 0.088, 0.0), (1.16, 0.138 * cw, 0.092, -0.004), (1.22, 0.15 * cw, 0.098, -0.008),
            (1.29, 0.162 * cw, 0.104, -0.01), (1.36, 0.168 * cw, 0.104, -0.009), (1.4, 0.17 * cw, 0.098, -0.005), (1.43, 0.158 * cw, 0.09, -0.002),
            (1.455, 0.13 * cw, 0.078, 0.0), (1.475, 0.095, 0.064, 0.0), (1.492, 0.062, 0.054, 0.0), (1.5, 0.05, 0.05, 0.0)]]

        hips = sc([(-0.125, 0, 0, 0, 0.004), (-0.12, 0.07 * hipw, 0.06, 0, 0.004), (-0.1, 0.12 * hipw, 0.085, 0, 0.006),
                   (-0.06, 0.158 * hipw, 0.1, 0, 0.008), (-0.01, 0.163 * hipw, 0.104, 0, 0.006), (0.035, 0.148 * hipw, 0.096, 0, 0.003),
                   (0.06, 0.12, 0.084), (0.07, 0.09, 0.07), (0.075, 0, 0)])
        self.seg("Hips", None, (0, 0, HIP_Z), up, 0.105 * s, hips, seg=20)
        spine = sc([(0.03, 0, 0), (0.034, 0.088, 0.068), (0.06, 0.112 * chw, 0.082), (0.095, 0.118 * chw, 0.085),
                    (0.115, 0.1, 0.076), (0.12, 0, 0)])
        self.seg("Spine", "Hips", (0, 0, WAIST_Z), up, CHEST_Z - WAIST_Z, spine, ball=0.066 * s, seg=20)
        chest = sc([(0.025, 0, 0), (0.03, 0.1 * chw, 0.074, 0, -0.004), (0.06, 0.135 * chw, 0.092, 0, -0.008),
                    (0.1, 0.156 * chw, 0.102, 0, -0.01), (0.15, 0.163 * chw, 0.103, 0, -0.008), (0.19, 0.158 * chw, 0.097, 0, -0.004),
                    (0.22, 0.138 * chw, 0.086), (0.238, 0.1 * chw, 0.068), (0.246, 0.05, 0.042), (0.248, 0, 0)])
        self.seg("Chest", "Spine", (0, 0, CHEST_Z), up, NECK_Z - CHEST_Z, chest, ball=0.07 * s, seg=22)
        neck = sc([(0.012, 0, 0), (0.015, 0.03, 0.033), (0.04, 0.032, 0.035), (0.07, 0.029, 0.032), (0.078, 0, 0)])
        self.seg("Neck", "Chest", (0, 0, NECK_Z), up, HEAD_Z - NECK_Z, neck, ball=0.04 * s)
        head = sc([(0.012, 0, 0, 0, -0.03), (0.018, 0.03, 0.035, 0, -0.03), (0.035, 0.052, 0.064, 0, -0.026),
                   (0.065, 0.068, 0.084, 0, -0.018), (0.1, 0.077, 0.094, 0, -0.01), (0.14, 0.078, 0.095, 0, -0.004),
                   (0.17, 0.07, 0.085, 0, 0.0), (0.19, 0.054, 0.066, 0, 0.002), (0.2, 0.032, 0.04, 0, 0.002), (0.205, 0, 0, 0, 0.002)])
        self.seg("Head", "Neck", (0, 0, HEAD_Z), up, 0.205 * s, head, ball=0.032 * s, seg=22)

        for side, sx in (("L", 1), ("R", -1)):
            d = Vector((sx * math.sin(ABD), 0, -math.cos(ABD)))
            sh = Vector((sx * SH_X, 0, SH_Z))
            el = sh + d * UP; wr = el + d * FORE; kn = wr + d * PALM
            uarm = sc([(0.03, 0, 0), (0.034, 0.034, 0.036), (0.06, 0.045, 0.048), (0.12, 0.046, 0.047), (0.2, 0.039, 0.04),
                       (0.255, 0.032, 0.033), (0.262, 0, 0)])
            self.seg(f"{side}_UpperArm", "Chest", sh, d, UP, uarm, ball=0.048 * s)
            larm = sc([(0.027, 0, 0), (0.031, 0.029, 0.031), (0.06, 0.037, 0.04), (0.12, 0.032, 0.035), (0.2, 0.025, 0.028),
                       (0.233, 0.021, 0.023), (0.238, 0, 0)])
            self.seg(f"{side}_LowerArm", f"{side}_UpperArm", el, d, FORE, larm, ball=0.034 * s)
            palm = sc([(0.014, 0, 0), (0.018, 0.013, 0.026), (0.04, 0.0165, 0.039), (0.07, 0.016, 0.043), (0.09, 0.0135, 0.041),
                       (0.097, 0, 0)])
            self.seg(f"{side}_Hand", f"{side}_LowerArm", wr, d, PALM, palm, ball=0.022 * s)
            fr = frame(d)
            # 四指：近节在 Fingers，远节在 FingersTip（局部 +Y = 前 = 食指一侧）
            lens = [(0.03, 0.036), (0.01, 0.04), (-0.01, 0.037), (-0.03, 0.029)]
            def fingers(p, xf, tip=False):
                for yo, tl in lens:
                    L = (tl if tip else 0.042) * s; r = (0.0078 if tip else 0.0088) * s * (0.9 if yo < -0.02 else 1.0)
                    prof = [(-0.003 * s, 0, 0), (-0.001 * s, r * 0.7, r * 0.7), (0.004 * s, r, r), (L - 0.004 * s, r * 0.93, r * 0.93),
                            (L - 0.001 * s, r * 0.6, r * 0.6), (L + 0.001 * s, 0, 0)]
                    p.lathe(prof, self.WOOD, seg=8, xf=xf @ T(0, yo * s, 0), swap_uv=True)
            self.seg(f"{side}_Fingers", f"{side}_Hand", kn, d, 0.042 * s, None, extra=lambda p, xf: fingers(p, xf))
            tipp = kn + d * 0.044 * s
            self.seg(f"{side}_FingersTip", f"{side}_Fingers", tipp, d, 0.04 * s, None, extra=lambda p, xf: fingers(p, xf, True))
            # 拇指：掌根前缘，朝前下方、略向掌心
            tp = wr + (fr @ Vector((-sx * 0.006, 0.03, 0.028))) * s
            td = (fr.to_3x3() @ Vector((-sx * 0.3, 0.55, 0.78))).normalized()
            thumb = sc([(-0.004, 0, 0), (0.0, 0.011, 0.011), (0.02, 0.0105, 0.0105), (0.05, 0.0092, 0.0092), (0.058, 0.006, 0.006), (0.061, 0, 0)])
            self.seg(f"{side}_Thumb", f"{side}_Hand", tp, td, 0.061 * s, thumb, ball=0.012 * s, seg=10)

            hp = Vector((sx * HIP_X, 0, 0.92 * s)); kp = Vector((sx * HIP_X, -0.004 * s, KNEE_Z)); ap = Vector((sx * HIP_X, 0.008 * s, ANK_Z))
            thigh = sc([(0.035, 0, 0), (0.04, 0.058, 0.06), (0.08, 0.073, 0.076, 0, 0.004), (0.16, 0.066, 0.069, 0, 0.004),
                        (0.3, 0.051, 0.053), (0.37, 0.044, 0.045), (0.383, 0, 0)])
            self.seg(f"{side}_UpperLeg", "Hips", hp, kp - hp, (kp - hp).length, thigh, ball=0.056 * s, seg=16)
            shin = sc([(0.034, 0, 0), (0.039, 0.044, 0.044), (0.1, 0.049, 0.054, 0, -0.01), (0.2, 0.042, 0.045, 0, -0.006),
                       (0.33, 0.03, 0.031), (0.38, 0.026, 0.027), (0.388, 0, 0)])
            self.seg(f"{side}_LowerLeg", f"{side}_UpperLeg", kp, ap - kp, (ap - kp).length, shin, ball=0.043 * s)
            fh = ANK_Z / s
            foot = [(-0.066, 0, 0, 0, 0.03 - fh), (-0.062, 0.026, 0.03, 0, 0.03 - fh), (-0.045, 0.034, 0.04, 0, 0.04 - fh),
                    (-0.01, 0.038, 0.042, 0, 0.042 - fh), (0.05, 0.043, 0.033, 0, 0.033 - fh), (0.11, 0.047, 0.025, 0, 0.025 - fh),
                    (0.16, 0.043, 0.02, 0, 0.02 - fh), (0.19, 0.03, 0.015, 0, 0.015 - fh), (0.198, 0, 0, 0, 0.012 - fh)]
            self.seg(f"{side}_Foot", f"{side}_LowerLeg", ap, (0, -1, 0), 0.198 * s + 0.066 * s, sc(foot), ball=0.03 * s)

    # ---------- 服装构件 ----------
    def trousers(self, mat, shoe, shin_end=0.33):
        s = self.s
        self.torso("Hips", "Cloth_Trousers_Seat", mat, 0.84 * s, 1.08 * s, 0.012, hem_bot=False)
        self.cloth("Hips", "Cloth_Trousers_Crotch", lambda p, xf: p.sphere(0.1 * s, mat, xf=xf @ T(0, 0.004 * s, -0.12 * s), seg=16, rings=8, sx=1.05, sy=0.95, sz=0.5), [mat])
        for sd in "LR":
            self.shell(f"{sd}_UpperLeg", f"Cloth_Trousers_{sd}_Thigh", mat, -0.045 * s, 0.44 * s, 0.014, seg=14, minr=0.05 * s)
            self.shell(f"{sd}_LowerLeg", f"Cloth_Trousers_{sd}_Shin", mat, -0.04 * s, shin_end * s, 0.014, seg=14, minr=0.048 * s,
                       flare=lambda t: max(0.0, (t - 0.15 * s)) * 0.08)
            if shoe:
                self.shoe(sd, shoe)

    def shoe(self, sd, mat, boot_top=None):
        s = self.s
        sg = self.segs[f"{sd}_Foot"]
        pr = [(t, rx + 0.008, ry + 0.008, ox, oy + 0.006) for (t, rx, ry, ox, oy) in [norm5(p) for p in sg["prof"]]]
        self.cloth(f"{sd}_Foot", f"Cloth_{sd}_Shoe", lambda p, xf: p.lathe(pr, mat, seg=14, xf=xf), [mat])
        if boot_top:
            self.shell(f"{sd}_LowerLeg", f"Cloth_{sd}_BootShaft", mat, boot_top * s, 0.4 * s, 0.024, seg=14,
                       flare=lambda t: max(0.0, (boot_top * s + 0.05 - t)) * 0.2)

    def cap_prof(self, sd):
        """上臂布料轮廓：肩部是半球顶（盖住肩关节球），往下接上臂。"""
        s = self.s; Rr = 0.047 * s
        cap = [(-Rr * math.cos(math.radians(a)) + 0.004 * s, Rr * math.sin(math.radians(a)), Rr * math.sin(math.radians(a)) * 1.03)
               for a in (0, 20, 38, 55, 70, 82, 90)]
        return cap + [p for p in self.segs[f"{sd}_UpperArm"]["prof"] if p[0] > 0.045 * s]

    def sleeves(self, mat, lower_t1, cuff=None, upper_d=0.01, puff=0.0):
        s = self.s
        def cap(sd):
            sg = self.segs[f"{sd}_UpperArm"]
            return [(-0.046 * s, 0, 0), (-0.043 * s, 0.02 * s, 0.02 * s), (-0.034 * s, 0.033 * s, 0.033 * s), (-0.018 * s, 0.041 * s, 0.042 * s),
                    (0.005 * s, 0.045 * s, 0.047 * s)] + [p for p in sg["prof"] if p[0] > 0.04 * s]
        for sd in "LR":
            self.shell(f"{sd}_UpperArm", f"Cloth_{sd}_Sleeve_Upper", mat, -0.043 * s, 0.31 * s, upper_d, seg=16, prof=self.cap_prof(sd), hem=True, minr=0.04 * s,
                       flare=(lambda t: puff * math.cos(min(1.0, abs(t - 0.06 * s) / (0.12 * s)) * math.pi / 2) ** 2) if puff else None)
            self.shell(f"{sd}_LowerArm", f"Cloth_{sd}_Sleeve_Lower", mat, -0.035 * s, lower_t1 * s, 0.014, seg=14, minr=0.038 * s)
            if cuff:
                cm, rolled = cuff
                t0 = (lower_t1 - 0.03) * s
                self.shell(f"{sd}_LowerArm", f"Cloth_{sd}_Cuff", cm, t0, lower_t1 * s + 0.004, 0.022 if rolled else 0.017, seg=14,
                           flare=(lambda t: 0.006 * math.sin(math.pi * (t - t0) / (0.034 * s))) if rolled else None)

    def shirt(self, mat, collar=True):
        s = self.s
        self.torso("Chest", "Cloth_Shirt", mat, 1.16 * s, 1.5 * s, 0.008, hem_top=False)
        if collar:
            nk = self.segs["Neck"]
            self.cloth("Neck", "Cloth_Collar", lambda p, xf: p.lathe(
                [(0.025 * s, 0.05 * s, 0.054 * s, 0, -0.004), (0.035 * s, 0.047 * s, 0.05 * s, 0, -0.004), (0.068 * s, 0.043 * s, 0.047 * s, 0, -0.004),
                 (0.072 * s, 0.037 * s, 0.04 * s, 0, -0.004)], mat, seg=16, xf=xf), [mat])

    def vest(self, mat, button_mat, gap=0.42, d=0.022):
        s = self.s
        self.torso("Chest", "Cloth_Vest", mat, 1.17 * s, 1.3 * s, d, hem_top=False)
        self.torso("Chest", "Cloth_Vest_Upper", mat, 1.3 * s, 1.462 * s, d, hem_bot=False, seg=22,
                   gap=lambda z: 0.04 + gap * max(0.0, (z - 1.29 * s) / (0.17 * s)) ** 0.8)
        self.torso("Spine", "Cloth_Vest_Lower", mat, 0.99 * s, 1.24 * s, d + 0.003)
        env = [(e[0], e[1], e[2], 0, e[3]) for e in self.TORSO]
        sg = self.segs["Spine"]
        def b(p, xf):
            for k in range(5):
                z = (1.02 + 0.06 * k) * s
                _, rx, ry, ox, oy = interp(env, z)
                p.sphere(0.0065 * s, button_mat, xf=T(0, oy - ry - d - 0.005, z), seg=8, rings=4)
        ob = self.cloth("Spine", "Cloth_Vest_Buttons", b, [button_mat])
        ob.data.transform(T(0, 0, 0))

    def hat_brim(self, p, xf, mat, z, r0, r1, curl, thick=0.008):
        s = self.s
        p.lathe([(z, r0[0], r0[1], 0, -0.004), (z, r1[0], r1[1], 0, -0.004), (z + curl * 0.6, r1[0] + 0.01 * s, r1[1] + 0.01 * s, 0, -0.004),
                 (z + curl + thick, r1[0] + 0.004 * s, r1[1] + 0.004 * s, 0, -0.004), (z + thick, r1[0] - 0.01 * s, r1[1] - 0.01 * s, 0, -0.004),
                 (z + thick, r0[0], r0[1], 0, -0.004)], mat, seg=28, xf=xf, cap=False)

    # ---------- 角色 ----------
    def dress(self):
        s = self.s
        getattr(self, "dress_" + self.name)()

    def dress_Gus(self):
        s = self.s
        shirt = mc.pbr("ShirtLinen", "Fabric032", tile=0.25, tint=(0.95, 0.92, 0.84), normal=0.6)
        vest = mc.pbr("GusVest", "Fabric061", tile=0.2, tint=(0.55, 0.5, 0.45), normal=0.8)
        pants = mc.pbr("GusTrousers", "Fabric063", tile=0.25, tint=(0.75, 0.72, 0.68), normal=0.8)
        apron = mc.pbr("ApronCotton", "Fabric032", tile=0.3, tint=(0.9, 0.86, 0.76), normal=0.6)
        shoe = mc.pbr("ShoeLeather", "Leather026", tile=0.15, rough_mul=0.7)
        garter = mc.flat("GarterRed", (0.42, 0.04, 0.04), rough=0.55)
        brass = mc.flat("Button", (0.55, 0.42, 0.2), rough=0.35, metal=1.0)
        hair = mc.flat("MoustacheHair", (0.045, 0.028, 0.018), rough=0.75)
        self.shirt(shirt)
        self.vest(vest, brass)
        self.sleeves(shirt, 0.085, cuff=(shirt, True))
        for sd in "LR":
            self.shell(f"{sd}_UpperArm", f"Cloth_{sd}_Garter", garter, 0.085 * s, 0.11 * s, 0.026, seg=14, hem=True)
        self.trousers(pants, shoe)
        # 腰围裙：前片，从腰到膝下
        def ap(p, xf):
            p.lathe([(-0.47 * s, 0.205 * s, 0.17 * s, 0, -0.025 * s), (-0.25 * s, 0.195 * s, 0.15 * s, 0, -0.015 * s),
                     (-0.1 * s, 0.196 * s, 0.136 * s, 0, -0.008 * s), (0.0, 0.192 * s, 0.132 * s, 0, -0.006 * s), (0.065 * s, 0.186 * s, 0.128 * s, 0, -0.004 * s)],
                    apron, seg=20, xf=xf, arc=(-1.35, 1.35), cap=False)
            p.lathe([(0.04 * s, 0.191 * s, 0.132 * s), (0.068 * s, 0.188 * s, 0.13 * s)], apron, seg=24, xf=xf, cap=False)
        self.cloth("Hips", "Cloth_Apron", ap, [apron])
        # 八字胡贴片：两段弯曲的锥
        def mo(p, xf):
            hz = 0.062 * s; fy = -0.098 * s
            for sx in (1, -1):
                pts = [Vector((0.004 * sx, fy, hz)), Vector((0.03 * sx, fy + 0.008 * s, hz - 0.006 * s)),
                       Vector((0.052 * sx, fy + 0.026 * s, hz - 0.002 * s)), Vector((0.06 * sx, fy + 0.04 * s, hz + 0.014 * s))]
                rs = [0.009, 0.008, 0.005, 0.0025]
                for i in range(3):
                    a, b = pts[i], pts[i + 1]; dd = b - a
                    p.lathe([(0, rs[i] * s * 0.7, rs[i] * s), (dd.length, rs[i + 1] * s * 0.7, rs[i + 1] * s)], hair, seg=8,
                            xf=xf @ T(*a) @ mc.orient(dd), cap=True)
        self.cloth("Head", "Cloth_Moustache", mo, [hair])

    def dress_Professor(self):
        s = self.s
        shirt = mc.pbr("ShirtLinen", "Fabric032", tile=0.25, tint=(0.95, 0.92, 0.84), normal=0.6)
        vest = mc.pbr("ProfVest", "Fabric026", tile=0.18, tint=(0.62, 0.42, 0.4), normal=0.8)
        pants = mc.pbr("ProfTrousers", "Fabric061", tile=0.2, tint=(0.62, 0.6, 0.58), normal=0.8)
        felt = mc.pbr("BowlerFelt", "Fabric063", tile=0.15, tint=(0.32, 0.3, 0.29), rough_mul=0.9, normal=0.5)
        black = mc.flat("BlackSatin", (0.02, 0.018, 0.016), rough=0.38)
        shoe = mc.pbr("ShoeLeather", "Leather026", tile=0.15, rough_mul=0.7)
        btn = mc.flat("BoneButton", (0.75, 0.68, 0.55), rough=0.4)
        self.shirt(shirt)
        self.vest(vest, btn, gap=0.5)
        self.sleeves(shirt, 0.245, cuff=(shirt, False))
        self.trousers(pants, shoe)
        # 领结
        def bt(p, xf):
            z = 0.25 * s; fy = -0.052 * s
            p.sphere(0.009 * s, black, xf=xf @ T(0, fy, z), seg=10, rings=6)
            for sx in (1, -1):
                p.lathe([(0, 0.006 * s, 0.006 * s), (0.04 * s, 0.006 * s, 0.022 * s), (0.042 * s, 0, 0)], black, seg=8,
                        xf=xf @ T(0, fy, z) @ R("Y", 90 * sx))
        self.cloth("Chest", "Cloth_BowTie", bt, [black])
        # 圆顶礼帽
        def hat(p, xf):
            p.lathe([(0.138 * s, 0.084 * s, 0.098 * s, 0, -0.004), (0.17 * s, 0.087 * s, 0.101 * s, 0, -0.004),
                     (0.215 * s, 0.087 * s, 0.1 * s, 0, -0.004), (0.245 * s, 0.078 * s, 0.09 * s, 0, -0.004), (0.265 * s, 0.058 * s, 0.067 * s, 0, -0.004),
                     (0.277 * s, 0.03 * s, 0.035 * s, 0, -0.004), (0.28 * s, 0, 0, 0, -0.004)], felt, seg=28, xf=xf)
            self.hat_brim(p, xf, felt, 0.138 * s, (0.084 * s, 0.098 * s), (0.125 * s, 0.142 * s), 0.016 * s)
            p.lathe([(0.143 * s, 0.0885 * s, 0.1025 * s, 0, -0.004), (0.165 * s, 0.0885 * s, 0.1025 * s, 0, -0.004)], black, seg=28, xf=xf, cap=False)
        self.cloth("Head", "Cloth_BowlerHat", hat, [felt, black])

    def dress_Crane(self):
        s = self.s
        duster = mc.pbr("DusterCanvas", "Fabric066", tile=0.3, tint=(0.82, 0.7, 0.55), normal=0.8)
        pants = mc.pbr("CraneTrousers", "Fabric063", tile=0.25, tint=(0.7, 0.66, 0.6), normal=0.8)
        felt = mc.pbr("HatFelt", "Fabric028", tile=0.2, tint=(0.42, 0.32, 0.24), rough_mul=0.95, normal=0.5)
        band = mc.pbr("HatBand", "Leather030", tile=0.1)
        boot = mc.pbr("DustyBoot", "Leather037", tile=0.2, tint=(0.5, 0.43, 0.37), rough_mul=1.4, rough_add=0.15,
                      mix=("Ground080", "Color", 0.32, lambda x, y: 0.75 + 0.25 * __import__("numpy").sin(x * 37 + y * 11)),
                      mixkey="_dust3")
        shirt = mc.pbr("ShirtLinen", "Fabric032", tile=0.25, tint=(0.8, 0.76, 0.68), normal=0.6)
        vest = mc.pbr("CraneVest", "Fabric063", tile=0.2, tint=(0.45, 0.42, 0.4), normal=0.8)
        self.shirt(shirt)
        self.vest(vest, mc.flat("DarkButton", (0.05, 0.04, 0.03), rough=0.4), gap=0.38, d=0.018)
        self.trousers(pants, None, shin_end=0.2)
        for sd in "LR":
            self.shoe(sd, boot, boot_top=0.12)
        # 风衣：躯干 / 腹部 / 上臂 / 前臂 / 下摆 分段，跟着各自关节动
        self.torso("Chest", "Cloth_Coat_Torso", duster, 1.16 * s, 1.47 * s, 0.032, seg=24, hem_top=False,
                   gap=lambda z: 0.32 + 0.35 * max(0.0, (z - 1.3 * s) / (0.17 * s)))
        self.torso("Spine", "Cloth_Coat_Waist", duster, 1.0 * s, 1.25 * s, 0.036, seg=24, gap=lambda z: 0.3)
        def cape(p, xf):  # 披肩
            cz = self.segs["Chest"]["pivot"].z
            cp = [(1.25 * s - cz, 0.285 * s, 0.2 * s, 0, 0.004), (1.262 * s - cz, 0.288 * s, 0.203 * s, 0, 0.004), (1.33 * s - cz, 0.262 * s, 0.17 * s, 0, 0.0),
                  (1.4 * s - cz, 0.23 * s, 0.14 * s, 0, -0.004), (1.45 * s - cz, 0.19 * s, 0.115 * s, 0, -0.004), (1.48 * s - cz, 0.12 * s, 0.085 * s),
                  (1.495 * s - cz, 0.072 * s, 0.065 * s)]
            vlathe(p, cp, [0.42, 0.42, 0.45, 0.5, 0.58, 0.7, 0.8], duster, 26, xf)
            # 立领
            p.lathe([(0.24 * s, 0.062 * s, 0.062 * s, 0, 0.004), (0.3 * s, 0.07 * s, 0.072 * s, 0, 0.008), (0.305 * s, 0.072 * s, 0.075 * s, 0, 0.008)],
                    duster, seg=18, xf=xf, arc=(0.55, 2 * math.pi - 0.55), cap=False)
        self.cloth("Chest", "Cloth_Coat_Cape", cape, [duster])
        for sd in "LR":
            self.shell(f"{sd}_UpperArm", f"Cloth_Coat_{sd}_UpperSleeve", duster, -0.043 * s, 0.31 * s, 0.022, seg=16, hem=True,
                       prof=self.cap_prof(sd), minr=0.04 * s)
            self.shell(f"{sd}_LowerArm", f"Cloth_Coat_{sd}_LowerSleeve", duster, -0.035 * s, 0.232 * s, 0.022, seg=14, minr=0.038 * s,
                       flare=lambda t: max(0.0, t - 0.16 * s) * 0.15)
        def tail(p, xf):  # 下摆：前面开口，腿从开口处摆出
            p.lathe([(-0.72 * s, 0.31 * s, 0.27 * s, 0, 0.03 * s), (-0.45 * s, 0.25 * s, 0.205 * s, 0, 0.02 * s), (-0.2 * s, 0.2 * s, 0.145 * s, 0, 0.01 * s),
                     (-0.06 * s, 0.186 * s, 0.13 * s, 0, 0.008 * s), (0.08 * s, 0.17 * s, 0.12 * s, 0, 0.004 * s)],
                    duster, seg=28, xf=xf, arc=(0.62, 2 * math.pi - 0.62), cap=False)
        self.cloth("Hips", "Cloth_Coat_Tail", tail, [duster])
        def hat(p, xf):
            p.lathe([(0.13 * s, 0.088 * s, 0.103 * s, 0, -0.004), (0.2 * s, 0.085 * s, 0.098 * s, 0, -0.004), (0.255 * s, 0.078 * s, 0.09 * s, 0, -0.004),
                     (0.272 * s, 0.062 * s, 0.072 * s, 0, -0.004), (0.274 * s, 0.03 * s, 0.035 * s, 0, -0.004), (0.262 * s, 0, 0, 0, -0.004)], felt, seg=28, xf=xf)
            self.hat_brim(p, xf, felt, 0.13 * s, (0.088 * s, 0.103 * s), (0.215 * s, 0.235 * s), 0.03 * s, thick=0.01)
            p.lathe([(0.138 * s, 0.0895 * s, 0.1045 * s, 0, -0.004), (0.165 * s, 0.0885 * s, 0.1035 * s, 0, -0.004)], band, seg=28, xf=xf, cap=False)
        self.cloth("Head", "Cloth_WideBrimHat", hat, [felt, band])

    def dress_Nell(self):
        s = self.s
        blouse = mc.pbr("BlouseCotton", "Fabric032", tile=0.25, tint=(0.96, 0.93, 0.86), normal=0.6)
        skirt = mc.pbr("SkirtWool", "Fabric022", tile=0.3, tint=(0.75, 0.75, 0.8), normal=0.8)
        bodice = mc.pbr("Bodice", "Fabric063", tile=0.2, tint=(0.55, 0.5, 0.48), normal=0.8)
        apron = mc.pbr("ApronCotton", "Fabric032", tile=0.3, tint=(0.9, 0.86, 0.76), normal=0.6)
        boot = mc.pbr("ShoeLeather", "Leather026", tile=0.15, rough_mul=0.7)
        self.shirt(blouse)
        self.torso("Chest", "Cloth_Bodice", bodice, 1.17 * s, 1.33 * s, 0.016)
        self.torso("Spine", "Cloth_Bodice_Waist", bodice, 0.99 * s, 1.24 * s, 0.019)
        self.sleeves(blouse, 0.1, cuff=(blouse, True), puff=0.006)
        for sd in "LR":
            self.shoe(sd, boot, boot_top=0.3)
        # 长裙：钟形，裙摆够宽让腿能迈步
        hz = self.dims["hip_z"]
        def sk(p, xf):
            p.lathe([(0.05 * s - hz, 0.36 * s, 0.36 * s, 0, 0.02 * s), (0.25 * s - hz, 0.315 * s, 0.31 * s, 0, 0.015 * s),
                     (0.55 * s - hz, 0.25 * s, 0.225 * s, 0, 0.01 * s), (0.82 * s - hz, 0.198 * s, 0.15 * s, 0, 0.008 * s),
                     (0.95 * s - hz, 0.18 * s, 0.125 * s, 0, 0.006 * s), (1.04 * s - hz, 0.152 * s, 0.108 * s, 0, 0.002 * s),
                     (1.05 * s - hz, 0.13 * s, 0.1 * s)], skirt, seg=32, xf=xf, cap=False)
        self.cloth("Hips", "Cloth_Skirt", sk, [skirt])
        def ap(p, xf):
            p.lathe([(0.38 * s - hz, 0.295 * s, 0.274 * s, 0, 0.012 * s), (0.55 * s - hz, 0.262 * s, 0.24 * s, 0, 0.008 * s),
                     (0.82 * s - hz, 0.21 * s, 0.163 * s, 0, 0.006 * s), (0.95 * s - hz, 0.192 * s, 0.138 * s, 0, 0.004 * s),
                     (1.04 * s - hz, 0.164 * s, 0.12 * s, 0, 0.002 * s)], apron, seg=20, xf=xf, arc=(-1.15, 1.15), cap=False)
            p.lathe([(1.025 * s - hz, 0.172 * s, 0.124 * s), (1.045 * s - hz, 0.16 * s, 0.114 * s)], apron, seg=28, xf=xf, cap=False)
        self.cloth("Hips", "Cloth_Apron", ap, [apron])
        hair = mc.flat("HairBrown", (0.09, 0.055, 0.035), rough=0.6)
        def bun(p, xf):  # 发髻：脸是空白的，发髻让她一眼可辨
            p.sphere(0.045 * s, hair, xf=xf @ T(0, 0.085 * s, 0.155 * s), seg=14, rings=8, sy=0.8)
            p.lathe([(0.09 * s, 0.07 * s, 0.075 * s, 0, 0.012 * s), (0.14 * s, 0.081 * s, 0.096 * s, 0, 0.004 * s), (0.18 * s, 0.073 * s, 0.087 * s, 0, 0.002 * s),
                     (0.2 * s, 0.056 * s, 0.068 * s, 0, 0.004 * s), (0.212 * s, 0.03 * s, 0.04 * s, 0, 0.004 * s), (0.215 * s, 0, 0, 0, 0.004 * s)],
                    hair, seg=20, xf=xf, arc=(1.25, 2 * math.pi - 1.25), cap=False)
        self.cloth("Head", "Cloth_HairBun", bun, [hair])

    # ---------- 镇上群演（车夫 / 镇民） ----------
    def patch(self, segname, cname, mat, z0, z1, d, a_c, halfang, nz=6, na=6, thick=0.004):
        """贴着统一躯干外形的一块布（领巾三角、披肩后摆）：世界高度 z0..z1，中心角 a_c（0 = 正前，π = 正后），
        halfang(z) = 该高度的半角宽度。外 / 内两层 + 封边，所以从哪边看都有面。"""
        s = self.s
        sg = self.segs[segname]; pz = sg["pivot"].z
        env = [(e[0], e[1], e[2], 0, e[3]) for e in self.TORSO]
        def build(p, xf):
            bm, uvl = p.bm, p.uv
            tile = mat.get("tile", 1.0)
            layers = []
            for dd in (d, d - thick):
                rows = []
                for i in range(nz + 1):
                    z = z0 + (z1 - z0) * i / nz
                    _, rx, ry, ox, oy = interp(env, z)
                    h = halfang(z)
                    rows.append([bm.verts.new(xf @ Vector(((rx + dd) * math.sin(a_c + h * (2 * j / na - 1)),
                                                           oy - (ry + dd) * math.cos(a_c + h * (2 * j / na - 1)), z - pz)))
                                 for j in range(na + 1)])
                layers.append(rows)
            faces = []
            def q(vs, flip):
                f = bm.faces.new(list(reversed(vs)) if flip else vs)
                for lp in f.loops:
                    co = lp.vert.co; lp[uvl].uv = (co.x / tile + co.y / tile, co.z / tile)
                faces.append(f)
            O, I = layers
            for i in range(nz):
                for j in range(na):
                    q([O[i][j], O[i][j + 1], O[i + 1][j + 1], O[i + 1][j]], a_c > 1.0)
                    q([I[i][j], I[i][j + 1], I[i + 1][j + 1], I[i + 1][j]], a_c <= 1.0)
            for i in range(nz):  # 两侧封边
                for j, fl in ((0, False), (na, True)):
                    q([O[i][j], O[i + 1][j], I[i + 1][j], I[i][j]], fl ^ (a_c > 1.0))
            for i, fl in ((0, True), (nz, False)):
                for j in range(na):
                    q([O[i][j], O[i][j + 1], I[i][j + 1], I[i][j]], fl ^ (a_c > 1.0))
            p._take(faces, mat, True)
        return self.cloth(segname, cname, build, [mat])

    def gloves(self, mat):
        """皮手套：手掌、四指两节、拇指各一层壳，跟着各自的关节动；腕口加一圈短护腕。"""
        s = self.s
        for sd in "LR":
            self.shell(f"{sd}_Hand", f"Cloth_{sd}_Glove", mat, -0.004 * s, 0.098 * s, 0.0035, seg=12, minr=0.024 * s)
            self.shell(f"{sd}_LowerArm", f"Cloth_{sd}_GloveCuff", mat, 0.19 * s, 0.243 * s, 0.012, seg=14,
                       flare=lambda t: max(0.0, t - 0.19 * s) * 0.25)
            self.shell(f"{sd}_Thumb", f"Cloth_{sd}_GloveThumb", mat, -0.004 * s, 0.061 * s, 0.0035, seg=10, minr=0.011 * s)
            lens = [(0.03, 0.036), (0.01, 0.04), (-0.01, 0.037), (-0.03, 0.029)]
            def fg(p, xf, tip):
                for yo, tl in lens:
                    L = (tl if tip else 0.042) * s; r = ((0.0078 if tip else 0.0088) * s * (0.9 if yo < -0.02 else 1.0)) + 0.0032
                    prof = [(-0.004 * s, 0, 0), (-0.002 * s, r * 0.75, r * 0.75), (0.004 * s, r, r), (L - 0.003 * s, r * 0.95, r * 0.95),
                            (L + 0.0005, r * 0.62, r * 0.62), (L + 0.0025, 0, 0)]
                    p.lathe(prof, mat, seg=8, xf=xf @ T(0, yo * s, 0), swap_uv=True)
            self.cloth(f"{sd}_Fingers", f"Cloth_{sd}_GloveFingers", lambda p, xf: fg(p, xf, False), [mat])
            self.cloth(f"{sd}_FingersTip", f"Cloth_{sd}_GloveTips", lambda p, xf: fg(p, xf, True), [mat])

    def neckerchief(self, mat):
        s = self.s
        self.cloth("Neck", "Cloth_Neckerchief", lambda p, xf: p.lathe(
            [(-0.006 * s, 0.052 * s, 0.056 * s, 0, -0.006), (0.0, 0.06 * s, 0.065 * s, 0, -0.008), (0.03 * s, 0.059 * s, 0.064 * s, 0, -0.008),
             (0.05 * s, 0.054 * s, 0.058 * s, 0, -0.006), (0.054 * s, 0.047 * s, 0.05 * s, 0, -0.005)], mat, seg=18, xf=xf, cap=False), [mat])
        # 胸前的三角垂角 + 结
        self.patch("Chest", "Cloth_Neckerchief_Tip", mat, 1.33 * s, 1.47 * s, 0.024, 0.0,
                   lambda z: 0.02 + 0.3 * max(0.0, (z - 1.33 * s)) / (0.14 * s), nz=5, na=4)
        self.cloth("Chest", "Cloth_Neckerchief_Knot", lambda p, xf: p.sphere(
            0.018 * s, mat, xf=xf @ T(0, -0.098 * s, 0.235 * s), seg=10, rings=6, sx=1.25, sy=0.7), [mat])

    def dress_Driver(self):
        """车夫：长风衣（无披肩，翻立领）、宽檐平顶帽、红领巾、皮手套、高筒靴。主要用法是坐在车夫座上。"""
        s = self.s
        duster = mc.pbr("DriverDuster", "Fabric066", tile=0.3, tint=(0.4, 0.33, 0.26), normal=0.8)
        pants = mc.pbr("DriverTrousers", "Fabric063", tile=0.25, tint=(0.5, 0.47, 0.43), normal=0.8)
        felt = mc.pbr("DriverHatFelt", "Fabric028", tile=0.2, tint=(0.3, 0.26, 0.22), rough_mul=0.95, normal=0.5)
        band = mc.pbr("HatBand", "Leather030", tile=0.1)
        boot = mc.pbr("DriverBoot", "Leather037", tile=0.2, tint=(0.42, 0.36, 0.3), rough_mul=1.3, rough_add=0.1)
        shirt = mc.pbr("DriverShirt", "Fabric032", tile=0.25, tint=(0.7, 0.66, 0.6), normal=0.6)
        vest = mc.pbr("DriverVest", "Fabric061", tile=0.2, tint=(0.36, 0.34, 0.32), normal=0.8)
        glove = mc.pbr("GloveLeather", "Leather037", tile=0.12, tint=(0.78, 0.62, 0.46), rough_mul=0.9)
        kerchief = mc.pbr("KerchiefRed", "Fabric032", tile=0.15, tint=(0.55, 0.12, 0.08), normal=0.5)
        self.shirt(shirt)
        self.vest(vest, mc.flat("DarkButton", (0.05, 0.04, 0.03), rough=0.4), gap=0.36, d=0.018)
        self.trousers(pants, None, shin_end=0.2)
        for sd in "LR":
            self.shoe(sd, boot, boot_top=0.1)
        self.neckerchief(kerchief)
        self.torso("Chest", "Cloth_Coat_Torso", duster, 1.16 * s, 1.47 * s, 0.032, seg=24, hem_top=False,
                   gap=lambda z: 0.3 + 0.38 * max(0.0, (z - 1.3 * s) / (0.17 * s)))
        self.torso("Spine", "Cloth_Coat_Waist", duster, 1.0 * s, 1.25 * s, 0.036, seg=24, gap=lambda z: 0.28)
        def collar(p, xf):  # 车夫披肩（短，到上臂中部）+ 翻领
            cz = self.segs["Chest"]["pivot"].z
            cp = [(1.29 * s - cz, 0.272 * s, 0.19 * s, 0, 0.004), (1.302 * s - cz, 0.275 * s, 0.193 * s, 0, 0.004), (1.36 * s - cz, 0.255 * s, 0.165 * s, 0, 0.0),
                  (1.41 * s - cz, 0.228 * s, 0.14 * s, 0, -0.004), (1.45 * s - cz, 0.19 * s, 0.116 * s, 0, -0.004), (1.48 * s - cz, 0.122 * s, 0.086 * s),
                  (1.495 * s - cz, 0.074 * s, 0.066 * s)]
            vlathe(p, cp, [0.36, 0.36, 0.4, 0.46, 0.55, 0.68, 0.8], duster, 26, xf)
            p.lathe([(0.225 * s, 0.072 * s, 0.07 * s, 0, 0.006), (0.29 * s, 0.074 * s, 0.076 * s, 0, 0.012),
                     (0.296 * s, 0.084 * s, 0.088 * s, 0, 0.012), (0.255 * s, 0.11 * s, 0.112 * s, 0, 0.012), (0.24 * s, 0.112 * s, 0.11 * s, 0, 0.01)],
                    duster, seg=20, xf=xf, arc=(0.62, 2 * math.pi - 0.62), cap=False)
        self.cloth("Chest", "Cloth_Coat_Collar", collar, [duster])
        for sd in "LR":
            self.shell(f"{sd}_UpperArm", f"Cloth_Coat_{sd}_UpperSleeve", duster, -0.043 * s, 0.31 * s, 0.024, seg=16, hem=True,
                       prof=self.cap_prof(sd), minr=0.04 * s)
            self.shell(f"{sd}_LowerArm", f"Cloth_Coat_{sd}_LowerSleeve", duster, -0.035 * s, 0.22 * s, 0.024, seg=14, minr=0.038 * s,
                       flare=lambda t: max(0.0, t - 0.15 * s) * 0.15)
        def tail(p, xf):  # 下摆：前面开口；坐下时大腿从开口伸出，后片落在座位里
            p.lathe([(-0.7 * s, 0.3 * s, 0.26 * s, 0, 0.03 * s), (-0.45 * s, 0.25 * s, 0.205 * s, 0, 0.02 * s), (-0.2 * s, 0.2 * s, 0.145 * s, 0, 0.01 * s),
                     (-0.06 * s, 0.186 * s, 0.13 * s, 0, 0.008 * s), (0.08 * s, 0.17 * s, 0.12 * s, 0, 0.004 * s)],
                    duster, seg=28, xf=xf, arc=(0.66, 2 * math.pi - 0.66), cap=False)
        self.cloth("Hips", "Cloth_Coat_Tail", tail, [duster])
        self.gloves(glove)
        def hat(p, xf):  # 平顶宽檐（plainsman）
            p.lathe([(0.13 * s, 0.089 * s, 0.104 * s, 0, -0.004), (0.2 * s, 0.087 * s, 0.1 * s, 0, -0.004), (0.24 * s, 0.083 * s, 0.096 * s, 0, -0.004),
                     (0.248 * s, 0.07 * s, 0.082 * s, 0, -0.004), (0.25 * s, 0, 0, 0, -0.004)], felt, seg=28, xf=xf)
            self.hat_brim(p, xf, felt, 0.13 * s, (0.089 * s, 0.104 * s), (0.225 * s, 0.245 * s), 0.012 * s, thick=0.01)
            p.lathe([(0.138 * s, 0.0905 * s, 0.1055 * s, 0, -0.004), (0.17 * s, 0.0895 * s, 0.1045 * s, 0, -0.004)], band, seg=28, xf=xf, cap=False)
        self.cloth("Head", "Cloth_WideBrimHat", hat, [felt, band])

    def dress_Townsman(self):
        """镇民（男）：卷袖工装衬衫、背带、帆布裤、短靴、软毡宽边帽。"""
        s = self.s
        shirt = mc.pbr("WorkShirt", "Fabric032", tile=0.25, tint=(0.56, 0.62, 0.7), normal=0.6)
        pants = mc.pbr("WorkTrousers", "Fabric066", tile=0.3, tint=(0.52, 0.42, 0.32), normal=0.8)
        strap = mc.pbr("Suspenders", "Leather030", tile=0.1, tint=(0.7, 0.6, 0.5))
        felt = mc.pbr("SlouchFelt", "Fabric028", tile=0.2, tint=(0.48, 0.42, 0.34), rough_mul=0.95, normal=0.5)
        band = mc.pbr("HatBand", "Leather030", tile=0.1)
        boot = mc.pbr("ShoeLeather", "Leather026", tile=0.15, rough_mul=0.7)
        brass = mc.flat("Button", (0.55, 0.42, 0.2), rough=0.35, metal=1.0)
        self.shirt(shirt)
        self.torso("Spine", "Cloth_Shirt_Waist", shirt, 1.0 * s, 1.24 * s, 0.01)
        self.sleeves(shirt, 0.12, cuff=(shirt, True))
        self.trousers(pants, None, shin_end=0.36)
        for sd in "LR":
            self.shoe(sd, boot, boot_top=0.3)
        self.torso("Hips", "Cloth_Waistband", pants, 1.03 * s, 1.1 * s, 0.022)
        # 背带：前后各两条，贴着躯干外形；前面在胸口、后面在背上
        for sd, sx in (("L", 1), ("R", -1)):
            for side, ac in (("Front", 0.0), ("Back", math.pi)):
                a = ac + sx * (0.62 if side == "Front" else -0.5)
                self.patch("Chest", f"Cloth_Suspender_{sd}_{side}", strap, 1.2 * s, 1.45 * s, 0.016, a, lambda z: 0.075, nz=6, na=1)
                self.patch("Spine", f"Cloth_Suspender_{sd}_{side}_Low", strap, 1.06 * s, 1.21 * s, 0.017, a, lambda z: 0.08, nz=3, na=1)
        def btn(p, xf):
            env = [(e[0], e[1], e[2], 0, e[3]) for e in self.TORSO]
            for sx in (1, -1):
                z = 1.075 * s; _, rx, ry, ox, oy = interp(env, z); a = sx * 0.62
                p.sphere(0.008 * s, brass, xf=T((rx + 0.03) * math.sin(a), oy - (ry + 0.03) * math.cos(a), 0.095 * s), seg=8, rings=4)
        self.cloth("Hips", "Cloth_Suspender_Buttons", btn, [brass])
        def hat(p, xf):  # 软毡帽：低圆顶、帽檐前后微垂
            p.lathe([(0.13 * s, 0.088 * s, 0.103 * s, 0, -0.004), (0.18 * s, 0.087 * s, 0.1 * s, 0, -0.004), (0.215 * s, 0.08 * s, 0.093 * s, 0, -0.004),
                     (0.232 * s, 0.062 * s, 0.072 * s, 0, -0.004), (0.24 * s, 0.03 * s, 0.035 * s, 0, -0.004), (0.237 * s, 0, 0, 0, -0.004)], felt, seg=28, xf=xf)
            self.hat_brim(p, xf, felt, 0.13 * s, (0.088 * s, 0.103 * s), (0.17 * s, 0.19 * s), -0.022 * s, thick=0.009)
            p.lathe([(0.136 * s, 0.0895 * s, 0.1045 * s, 0, -0.004), (0.16 * s, 0.0885 * s, 0.1035 * s, 0, -0.004)], band, seg=28, xf=xf, cap=False)
        self.cloth("Head", "Cloth_SlouchHat", hat, [felt, band])

    def dress_Townswoman(self):
        """镇民（女）：女性骨架；长袖连衣长裙、披肩、遮阳软帽（脸是空白的，帽檐框住它）。"""
        s = self.s
        dress = mc.pbr("CalicoDress", "Fabric063", tile=0.22, tint=(0.62, 0.46, 0.36), normal=0.8)
        shawl = mc.pbr("ShawlWool", "Fabric061", tile=0.2, tint=(0.5, 0.26, 0.2), normal=0.9)
        bonnet = mc.pbr("BonnetCotton", "Fabric032", tile=0.2, tint=(0.74, 0.7, 0.6), normal=0.6)
        boot = mc.pbr("ShoeLeather", "Leather026", tile=0.15, rough_mul=0.7)
        self.torso("Chest", "Cloth_Dress_Bodice", dress, 1.16 * s, 1.5 * s, 0.01, hem_top=False)
        self.torso("Spine", "Cloth_Dress_Waist", dress, 0.99 * s, 1.24 * s, 0.013)
        nk = self.segs["Neck"]
        self.cloth("Neck", "Cloth_Collar", lambda p, xf: p.lathe(
            [(0.025 * s, 0.05 * s, 0.054 * s, 0, -0.004), (0.035 * s, 0.047 * s, 0.05 * s, 0, -0.004), (0.06 * s, 0.043 * s, 0.047 * s, 0, -0.004),
             (0.064 * s, 0.037 * s, 0.04 * s, 0, -0.004)], dress, seg=16, xf=xf), [dress])
        self.sleeves(dress, 0.235, cuff=(dress, False), puff=0.004)
        for sd in "LR":
            self.shoe(sd, boot, boot_top=0.3)
        hz = self.dims["hip_z"]
        def sk(p, xf):  # 长裙到脚面，比内尔的更宽一点（街上走路）
            p.lathe([(0.03 * s - hz, 0.37 * s, 0.37 * s, 0, 0.02 * s), (0.25 * s - hz, 0.325 * s, 0.32 * s, 0, 0.016 * s),
                     (0.55 * s - hz, 0.26 * s, 0.235 * s, 0, 0.01 * s), (0.82 * s - hz, 0.202 * s, 0.155 * s, 0, 0.008 * s),
                     (0.95 * s - hz, 0.183 * s, 0.128 * s, 0, 0.006 * s), (1.04 * s - hz, 0.155 * s, 0.11 * s, 0, 0.002 * s),
                     (1.05 * s - hz, 0.13 * s, 0.1 * s)], dress, seg=32, xf=xf, cap=False)
        self.cloth("Hips", "Cloth_Skirt", sk, [dress])
        # 披肩：盖住肩和上臂，前面敞开，后背垂成三角
        def cape(p, xf):
            cz = self.segs["Chest"]["pivot"].z
            cp = [(1.2 * s - cz, 0.27 * s, 0.17 * s, 0, 0.006), (1.212 * s - cz, 0.274 * s, 0.173 * s, 0, 0.006), (1.3 * s - cz, 0.285 * s, 0.168 * s, 0, 0.002),
                  (1.38 * s - cz, 0.272 * s, 0.15 * s, 0, -0.004), (1.44 * s - cz, 0.252 * s, 0.13 * s, 0, -0.004), (1.48 * s - cz, 0.215 * s, 0.112 * s),
                  (1.503 * s - cz, 0.145 * s, 0.09 * s), (1.515 * s - cz, 0.08 * s, 0.072 * s)]
            vlathe(p, cp, [0.07, 0.07, 0.08, 0.1, 0.16, 0.3, 0.5, 0.7], shawl, 28, xf)
        self.cloth("Chest", "Cloth_Shawl", cape, [shawl])
        self.patch("Chest", "Cloth_Shawl_Point", shawl, 1.04 * s, 1.27 * s, 0.05, math.pi,
                   lambda z: 0.05 + 0.85 * max(0.0, z - 1.04 * s) / (0.23 * s), nz=5, na=6, thick=0.006)
        def bn(p, xf):  # 遮阳软帽：后脑的帽身 + 向前伸出的帽檐筒
            # 一个朝前的兜帽筒：后面收成圆顶，前面伸出脸前 3 cm，下巴下面敞开（局部 Z = 前，局部 Y = 上）
            bx = xf @ T(0, 0, 0.112 * s) @ R("X", 90)
            p.lathe([(-0.128 * s, 0, 0), (-0.122 * s, 0.05 * s, 0.06 * s), (-0.1 * s, 0.088 * s, 0.104 * s), (-0.05 * s, 0.1 * s, 0.122 * s),
                     (0.03 * s, 0.104 * s, 0.128 * s), (0.1 * s, 0.114 * s, 0.14 * s), (0.135 * s, 0.124 * s, 0.152 * s), (0.14 * s, 0.118 * s, 0.146 * s),
                     (0.12 * s, 0.11 * s, 0.136 * s)], bonnet, seg=28, xf=bx, arc=(0.75, 2 * math.pi - 0.75), cap=False)
            # 帽带：下巴下面
            p.lathe([(0.0, 0.07 * s, 0.075 * s), (0.016 * s, 0.07 * s, 0.075 * s)], bonnet, seg=16, xf=xf @ T(0, -0.012 * s, 0.035 * s) @ R("X", 18), cap=False)
        self.cloth("Head", "Cloth_Bonnet", bn, [bonnet])

    def pose_firstperson(self):
        """第一人称：双手抬到胸前（端杯 / 弹琴的高度）。"""
        P = {"L_UpperArm": (-30, 0, -6), "L_LowerArm": (-58, 0, -4), "L_Hand": (-10, 0, 0), "L_Fingers": (0, 25, 0), "L_FingersTip": (0, 30, 0),
             "L_Thumb": (0, 15, 0), "R_UpperArm": (-26, 0, 6), "R_LowerArm": (-64, 0, 4), "R_Hand": (-5, 0, 0), "R_Fingers": (0, -35, 0),
             "R_FingersTip": (0, -40, 0), "R_Thumb": (0, -20, 0)}
        for n, e in P.items():
            self.segs[n]["ob"].rotation_euler = tuple(math.radians(v) for v in e)

    def objects(self):
        return mc.descendants(self.root)

    def pose_test(self):
        """评审用测试姿势：每个关键关节转一下，证明轴心在关节处。"""
        P = {
            "Spine": (8, 0, 6), "Chest": (4, 0, 8), "Head": (-8, 0, 28), "Neck": (6, 0, 0),
            "L_UpperArm": (-75, 0, -10), "L_LowerArm": (-70, 0, 0), "L_Hand": (0, 0, 0), "L_Fingers": (0, 60, 0),
            "L_FingersTip": (0, 50, 0), "L_Thumb": (0, 30, 0),
            "R_UpperArm": (0, 55, 0), "R_LowerArm": (-45, 0, 0), "R_Hand": (-20, 0, 0), "R_Fingers": (0, -20, 0),
            "L_UpperLeg": (-38, 0, 0), "L_LowerLeg": (55, 0, 0), "L_Foot": (-15, 0, 0),
            "R_UpperLeg": (14, 0, 0), "R_LowerLeg": (10, 0, 0), "R_Foot": (8, 0, 0),
        }
        for n, e in P.items():
            self.segs[n]["ob"].rotation_euler = tuple(math.radians(v) for v in e)

    def rest(self):
        for sg in self.segs.values():
            sg["ob"].rotation_euler = (0, 0, 0)


def rig_report(m):
    """关节世界坐标（Unity 约定：x=-Bx, y=Bz, z=-By）与段长。"""
    lines = []
    for n, sg in m.segs.items():
        p = sg["pivot"]
        lines.append((n, (-p.x, p.z, -p.y), sg["len"]))
    return lines


def build(name, offset=(0, 0, 0), coll=None):
    m = Mannequin(name, offset, coll)
    m.dress()
    return m


def stage(coll):
    mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.3)
    mc.studio(coll=coll, key=650, scale=1.4, warm=False)
    return mc.camera("Cam", (-1.7, -3.6, 1.35), (0, 0, 0.92), lens=45, coll=coll)


if LINEUP:
    sc = mc.reset()
    assetc = bpy.data.collections.new("Asset"); sc.collection.children.link(assetc)
    stage = bpy.data.collections.new("Stage"); sc.collection.children.link(stage)
    ms = [build(n, ((i - 1.5) * 0.85, 0, 0), assetc) for i, n in enumerate(VARIANTS[:4])]
    mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.3)
    mc.studio(coll=stage, key=900, scale=1.8)
    mc.camera("Cam", (0.0, -5.6, 1.3), (0, 0, 0.88), lens=40, coll=stage)
    mc.render(mc.REVIEWS / "Mannequin_Lineup.png")
    sys.exit(0)

if LINEUP_TOWN:
    sc = mc.reset()
    assetc = bpy.data.collections.new("Asset"); sc.collection.children.link(assetc)
    stage = bpy.data.collections.new("Stage"); sc.collection.children.link(stage)
    ms = [build(n, ((i - 1) * 0.9, 0, 0), assetc) for i, n in enumerate(TOWN)]
    mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.3)
    mc.studio(coll=stage, key=900, scale=1.8)
    mc.camera("Cam", (0.0, -5.0, 1.3), (0, 0, 0.9), lens=40, coll=stage)
    mc.render(mc.REVIEWS / "Mannequin_TownLineup.png")
    sys.exit(0)

report = {}
for name in VARIANTS:
    if ONLY and name not in ONLY.split(","):
        continue
    sc = mc.reset()
    assetc = bpy.data.collections.new("Asset"); sc.collection.children.link(assetc)
    stage_c = bpy.data.collections.new("Stage"); sc.collection.children.link(stage_c)
    m = build(name, coll=assetc)
    objs = m.objects()
    tris = mc.tri_count(objs)
    body = mc.tri_count([sg["ob"] for sg in m.segs.values()])
    print(f"TRIS Mannequin_{name} total={tris} body={body} cloth={tris - body}")
    assert tris <= 20000, tris
    mc.export_glb(mc.ART / "Characters" / f"Mannequin_{name}.glb", [m.root])
    for n, pos, ln in rig_report(m):
        print(f"RIG {name} {n} unity=({pos[0]:+.3f},{pos[1]:.3f},{pos[2]:+.3f}) len={ln:.3f}")
    if RENDER:
        cam = stage(stage_c)
        mc.render(mc.REVIEWS / f"Mannequin_{name}.png")
        close = mc.camera("CamClose", (-0.55, -1.25, 1.55), (0.02, 0, 1.36), lens=50, coll=stage_c)
        mc.render(mc.REVIEWS / f"Mannequin_{name}_closeup.png")
        bpy.context.scene.camera = cam
        m.pose_test()
        mc.render(mc.REVIEWS / f"Mannequin_{name}_pose.png")
        m.rest()
        if name == "Nell":
            m.pose_firstperson()
            hz = m.dims["head_z"]
            for o in mc.descendants(m.segs["Head"]["ob"]):
                o.hide_render = True
            fp = mc.camera("CamFP", (0, -0.07, hz + 0.08), (0, -0.6, hz - 0.5), lens=22, coll=stage_c)
            mc.render(mc.REVIEWS / "Mannequin_Nell_firstperson.png")
            m.rest()
