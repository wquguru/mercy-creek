"""Mercy Creek 独立资产（钢琴 / 人偶 / 道具 / 街景）共用的 Blender 工具。

- 贴图：从 art/source/ambientcg 的 2K 原图派生 1K（或 2K）JPG 到 art/source/_derived/，可选乘色调、混合、粗糙度缩放。
  色调在派生阶段烘进贴图，因为 glTF 导出器不认 Mix 节点，Unity 里看到的必须和 Blender 一样。
- 材质：Principled BSDF + Image Texture，法线贴图走 Normal Map 节点（glTF 可导出）。
- 网格：Part 累积多个基本体（车削 / 圆角盒 / 球）到一个对象，创建时直接写 UV（按米平铺）。
- 坐标：独立资产让正面朝 Blender -Y（= glTF +Z = glTFast 导入后的 Unity +Z），Z 向上，原点在落地中心。
"""
import bpy, bmesh, math, pathlib, sys
from mathutils import Vector, Matrix
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "art" / "source"
DERIVED = SRC / "_derived"
ART = ROOT / "Game" / "Assets" / "_MercyCreek" / "Art"
REVIEWS = ROOT / "Reviews" / "blender"


def args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


# ------------------------------------------------------------------ 贴图派生
def _src_tex(asset, kind):
    d = SRC / "ambientcg" / asset
    f = next(d.glob(f"*_{kind}.jpg"), None)
    return f


def derive(asset, kind, size=1024, tint=None, mul=None, add=0.0, mix=None, key=""):
    """把 ambientCG 贴图缩放到 size，并可选：tint 乘色（sRGB 0..1）、mul/add 线性缩放（粗糙度）、
    mix=(asset2, kind2, amount, mask_fn) 与另一张贴图按遮罩混合。返回派生文件路径（缓存）。"""
    src = _src_tex(asset, kind)
    if src is None:
        return None
    tag = key or ""
    if tint: tag += "_t" + "".join(f"{int(c * 100):02d}" for c in tint)
    if mul is not None: tag += f"_m{int(mul * 100)}"
    if add: tag += f"_a{int(add * 100)}"
    out = DERIVED / f"{asset}_{kind}_{size}{tag}.jpg"
    if out.exists():
        return out
    DERIVED.mkdir(parents=True, exist_ok=True)
    img = bpy.data.images.load(str(src))
    if kind != "Color":
        img.colorspace_settings.name = "Non-Color"
    img.scale(size, size)
    px = np.empty(size * size * 4, np.float32); img.pixels.foreach_get(px)
    px = px.reshape(size, size, 4)
    if mix:
        a2, k2, amount, maskfn = mix
        im2 = bpy.data.images.load(str(_src_tex(a2, k2))); im2.scale(size, size)
        p2 = np.empty(size * size * 4, np.float32); im2.pixels.foreach_get(p2); p2 = p2.reshape(size, size, 4)
        yy, xx = np.mgrid[0:size, 0:size] / size
        m = np.clip(maskfn(xx, yy), 0, 1)[..., None] * amount
        px[..., :3] = px[..., :3] * (1 - m) + p2[..., :3] * m
        bpy.data.images.remove(im2)
    if tint:
        px[..., :3] *= np.array(tint, np.float32)
    if mul is not None or add:
        px[..., :3] = px[..., :3] * (1.0 if mul is None else mul) + add
    px[..., :3] = np.clip(px[..., :3], 0, 1)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(out); img.file_format = "JPEG"
    img.save(filepath=str(out), quality=90)
    bpy.data.images.remove(img)
    return out


def image_tex(nodes, path, non_color=False):
    t = nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        t.image.colorspace_settings.name = "Non-Color"
    return t


def pbr(name, asset, tile=1.0, size=1024, tint=None, rough_mul=None, rough_add=0.0, metal=0.0,
        normal=1.0, rough=None, mix=None, mixkey=""):
    """ambientCG 照片材质（glTF 友好）。tile = 一张贴图覆盖的米数。rough=常数时不用粗糙度贴图。"""
    m = bpy.data.materials.new(name)
    n = m.node_tree.nodes; l = m.node_tree.links
    b = n["Principled BSDF"]
    col = derive(asset, "Color", size, tint=tint, mix=mix, key=mixkey)
    l.new(image_tex(n, col).outputs[0], b.inputs["Base Color"])
    rp = None if rough is not None else derive(asset, "Roughness", size, mul=rough_mul, add=rough_add)
    if rp:
        l.new(image_tex(n, rp, True).outputs[0], b.inputs["Roughness"])
    else:
        b.inputs["Roughness"].default_value = 0.6 if rough is None else rough
    b.inputs["Metallic"].default_value = metal
    npth = derive(asset, "NormalGL", size)
    if npth and normal > 0:
        nm = n.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal
        l.new(image_tex(n, npth, True).outputs[0], nm.inputs["Color"]); l.new(nm.outputs[0], b.inputs["Normal"])
    m["tile"] = tile
    return m


def image_mat(name, path, rough=0.7, metal=0.0, alpha=False, tile=1.0, normal_path=None, emission=0.0):
    """用自己生成的贴图（Pillow / numpy）做材质。"""
    m = bpy.data.materials.new(name)
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    t = image_tex(n, path)
    l.new(t.outputs[0], b.inputs["Base Color"])
    if alpha:
        l.new(t.outputs[1], b.inputs["Alpha"])
        m.blend_method = "CLIP" if hasattr(m, "blend_method") else None
    if emission:
        l.new(t.outputs[0], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emission
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if normal_path:
        nm = n.new("ShaderNodeNormalMap")
        l.new(image_tex(n, normal_path, True).outputs[0], nm.inputs["Color"]); l.new(nm.outputs[0], b.inputs["Normal"])
    m["tile"] = tile
    return m


def flat(name, color, rough=0.6, metal=0.0, transmission=0.0, alpha=1.0, ior=1.45, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["IOR"].default_value = ior
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        try: m.surface_render_method = "BLENDED"
        except Exception: pass
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = emit_strength
    m["tile"] = 1.0
    return m


# ------------------------------------------------------------------ 网格
def orient(direction):
    """把局部 +Z 转到 direction 的旋转矩阵（4x4）。"""
    d = Vector(direction).normalized()
    return Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()


def T(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation((x, y, z))


def R(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def S(x, y=None, z=None):
    y = x if y is None else y; z = x if z is None else z
    m = Matrix.Identity(4); m[0][0], m[1][1], m[2][2] = x, y, z
    return m


class Part:
    """把多个基本体累积进一个网格对象。每个基本体创建时写 UV（按米 / tile），材质用槽序号。"""

    def __init__(self, mats):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.mats = list(mats)

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _take(self, faces, mat, smooth):
        mi = self._mi(mat)
        for f in faces:
            f.material_index = mi; f.smooth = smooth

    # 车削：profile = [(z, rx, ry[, ox, oy])]，绕局部 Z；rx=0 的端点收成一个极点
    def lathe(self, profile, mat, seg=16, xf=Matrix.Identity(4), smooth=True, arc=None, cap=True, uv_rot=0.0, swap_uv=False):
        bm, uvl = self.bm, self.uv
        tile = mat.get("tile", 1.0)
        a0, a1 = (0.0, 2 * math.pi) if arc is None else arc
        full = arc is None
        nseg = seg if full else seg + 1
        rings = []
        for p in profile:
            z, rx, ry = p[0], p[1], p[2]
            ox, oy = (p[3], p[4]) if len(p) > 3 else (0.0, 0.0)
            if rx <= 1e-6 and ry <= 1e-6:
                rings.append([bm.verts.new(xf @ Vector((ox, oy, z)))])
            else:
                ring = []
                for j in range(nseg):
                    a = a0 + (a1 - a0) * j / seg + uv_rot
                    ring.append(bm.verts.new(xf @ Vector((ox + rx * math.sin(a), oy - ry * math.cos(a), z))))
                rings.append(ring)
        # 沿轮廓的弧长（v）与平均周长（u）
        vs = [0.0]
        for i in range(1, len(profile)):
            dz = profile[i][0] - profile[i - 1][0]; dr = profile[i][1] - profile[i - 1][1]
            vs.append(vs[-1] + math.hypot(dz, dr))
        rmax = max(max(p[1], p[2]) for p in profile)
        circ = (a1 - a0) * rmax
        faces = []
        for i in range(len(rings) - 1):
            A, B = rings[i], rings[i + 1]
            for j in range(seg):
                jn = (j + 1) % nseg if full else j + 1
                u0, u1 = j / seg * circ / tile, (j + 1) / seg * circ / tile
                v0, v1 = vs[i] / tile, vs[i + 1] / tile
                if len(A) == 1:
                    vv = [A[0], B[jn], B[j]]; uvs = [((u0 + u1) / 2, v0), (u1, v1), (u0, v1)]
                elif len(B) == 1:
                    vv = [A[j], A[jn], B[0]]; uvs = [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)]
                else:
                    vv = [A[j], A[jn], B[jn], B[j]]; uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                try:
                    f = bm.faces.new(vv)
                except ValueError:
                    continue
                for lp, uvv in zip(f.loops, uvs):
                    lp[uvl].uv = (uvv[1], uvv[0]) if swap_uv else uvv
                faces.append(f)
        if cap and full:
            for ring, top in ((rings[0], False), (rings[-1], True)):
                if len(ring) > 2:
                    f = bm.faces.new(ring if top else list(reversed(ring)))
                    for lp in f.loops:
                        co = lp.vert.co; lp[uvl].uv = (co.x / tile, co.y / tile)
                    faces.append(f)
        # 统一朝外：车削的绕序按 sin/-cos 生成，面法线朝外
        self._take(faces, mat, smooth)
        return faces

    def box(self, size, mat, xf=Matrix.Identity(4), bevel=0.0, bseg=1, smooth=False):
        bm, uvl = self.bm, self.uv
        tile = mat.get("tile", 1.0)
        before = set(bm.faces)
        ret = bmesh.ops.create_cube(bm, size=1.0)
        verts = ret["verts"]
        bmesh.ops.scale(bm, vec=Vector(size), verts=verts)
        if bevel > 0:
            fs = {f for v in verts for f in v.link_faces}
            edges = list({e for f in fs for e in f.edges})
            bmesh.ops.bevel(bm, geom=edges + list(verts), offset=min(bevel, 0.49 * min(size)), segments=bseg,
                            affect="EDGES", profile=0.5, clamp_overlap=True)
        faces = [f for f in bm.faces if f not in before]
        bmesh.ops.transform(bm, matrix=xf, verts=list({v for f in faces for v in f.verts}))
        bm.normal_update()
        for f in faces:
            nrm = f.normal; ax = max(range(3), key=lambda i: abs(nrm[i]))
            for lp in f.loops:
                p = lp.vert.co
                u, v = [(p.y, p.z), (p.x, p.z), (p.x, p.y)][ax]
                lp[uvl].uv = (u / tile, v / tile)
        self._take(faces, mat, smooth)
        return faces

    def sphere(self, r, mat, xf=Matrix.Identity(4), seg=16, rings=10, sx=1.0, sy=1.0, sz=1.0):
        prof = []
        for i in range(rings + 1):
            t = math.pi * i / rings
            prof.append((-math.cos(t) * r * sz, math.sin(t) * r * sx, math.sin(t) * r * sy))
        return self.lathe(prof, mat, seg=seg, xf=xf)

    def poly_extrude(self, pts2d, depth, mat, xf=Matrix.Identity(4), smooth=False):
        """平面多边形（XY）沿 Z 挤出 depth（以 z=0 为底）。"""
        bm, uvl = self.bm, self.uv
        tile = mat.get("tile", 1.0)
        bot = [bm.verts.new(Vector((x, y, 0))) for x, y in pts2d]
        top = [bm.verts.new(Vector((x, y, depth))) for x, y in pts2d]
        faces = [bm.faces.new(list(reversed(bot))), bm.faces.new(top)]
        n = len(pts2d)
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new([bot[i], bot[j], top[j], top[i]]))
        bmesh.ops.transform(bm, matrix=xf, verts=bot + top)
        bm.normal_update()
        for f in faces:
            nrm = f.normal; ax = max(range(3), key=lambda i: abs(nrm[i]))
            for lp in f.loops:
                p = lp.vert.co
                u, v = [(p.y, p.z), (p.x, p.z), (p.x, p.y)][ax]
                lp[uvl].uv = (u / tile, v / tile)
        self._take(faces, mat, smooth)
        return faces

    def quad(self, corners, mat, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        """单面四边形，UV 0..1（贴图上整图，如招牌 / 纸张）。"""
        vv = [self.bm.verts.new(Vector(c)) for c in corners]
        f = self.bm.faces.new(vv)
        for lp, uv in zip(f.loops, uvs):
            lp[self.uv].uv = uv
        self._take([f], mat, False)
        return [f]

    def finish(self, name, parent=None, location=(0, 0, 0), collection=None, smooth_angle=40.0):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me); self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception:
            pass
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        ob.location = location
        return ob


def empty(name, parent=None, location=(0, 0, 0), collection=None):
    ob = bpy.data.objects.new(name, None)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.parent = parent; ob.location = location
    ob.empty_display_size = 0.05
    return ob


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get(); n = 0
    for o in objs:
        if o.type == "MESH":
            ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles(); n += len(me.loop_triangles); ev.to_mesh_clear()
    return n


def descendants(root):
    return [root, *root.children_recursive]


def export_gltf(path, **kw):
    """导出 .gltf + .bin，贴图放进共用的 Art/Textures（同名贴图自动去重；Unity 按平台压缩，见 TextureImportRules.cs）。
    path 写成 .glb 也行，会改成 .gltf，并删掉旧的 .glb。"""
    import os
    path = pathlib.Path(path).with_suffix(".gltf"); path.parent.mkdir(parents=True, exist_ok=True)
    tex = ART / "Textures"; tex.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE",
                              export_texture_dir=os.path.relpath(tex, path.parent),
                              use_selection=True, export_lights=False, export_cameras=False, export_apply=True,
                              export_yup=True, export_image_format="AUTO", **kw)
    for old in (path.with_suffix(".glb"), path.with_suffix(".glb.meta")):
        if old.exists(): old.unlink()
    print("exported", path, f"{path.with_suffix('.bin').stat().st_size / 1e6:.1f} MB bin")


def export_glb(path, roots):
    bpy.ops.object.select_all(action="DESELECT")
    for r in roots:
        for o in descendants(r):
            o.select_set(True)
    export_gltf(path, export_tangents=True, export_animations=False)


# ------------------------------------------------------------------ 评审渲染
def setup_render(samples=48, res=(960, 540), exposure=0.0):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"; prefs.get_devices()
        for d in prefs.devices: d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:
        print("GPU unavailable:", e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 16
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = exposure
    return sc


def world_hdri(name="goegap_road", strength=0.6, rot=140):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("World"); sc.world = w
    wn = w.node_tree.nodes; wl = w.node_tree.links
    env = wn.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(SRC / "polyhaven" / "hdris" / f"{name}_2k.exr"), check_existing=True)
    mp = wn.new("ShaderNodeMapping"); tc = wn.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value[2] = math.radians(rot)
    wl.new(tc.outputs["Generated"], mp.inputs["Vector"]); wl.new(mp.outputs[0], env.inputs[0])
    bg = wn["Background"]; bg.inputs["Strength"].default_value = strength
    wl.new(env.outputs[0], bg.inputs[0])
    return w


def area(name, loc, target, energy, size=1.0, color=(1, 1, 1), coll=None):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = energy; ld.size = size; ld.color = color
    lo = bpy.data.objects.new(name, ld); (coll or bpy.context.scene.collection).objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


def studio(coll=None, floor_color=(0.22, 0.18, 0.15), key=600, scale=1.0, warm=True):
    """无缝背景 + 三点光。scale 按物体大小缩放灯距。"""
    p = Part([flat("Backdrop", floor_color, rough=0.85)])
    # L 形弯曲背景：地面向 +Y 延伸后上弯
    prof = []
    for i in range(13):
        a = math.pi / 2 * i / 12
        prof.append((0, 4 + 2 * math.sin(a), 2 - 2 * math.cos(a)))
    bm = p.bm
    rows = []
    for (x0, y, z) in [(0, -8, 0)] + prof + [(0, 6, 8)]:
        rows.append([bm.verts.new((sx * 12 * scale, y * scale, z * scale)) for sx in (-1, 1)])
    for a, b in zip(rows, rows[1:]):
        f = bm.faces.new([a[0], a[1], b[1], b[0]]); f.smooth = True
    bd = p.finish("Backdrop", collection=coll)
    s = scale
    c = (1.0, 0.86, 0.72) if warm else (1, 1, 1)
    area("Key", (-2.2 * s, -2.6 * s, 2.8 * s), (0, 0, 0.8 * s), key * s * s, size=1.6 * s, color=c, coll=coll)
    area("Fill", (2.8 * s, -2.0 * s, 1.4 * s), (0, 0, 0.8 * s), key * 0.25 * s * s, size=2.5 * s, color=(0.8, 0.88, 1.0), coll=coll)
    area("Rim", (1.0 * s, 2.5 * s, 2.6 * s), (0, 0, 1.0 * s), key * 0.6 * s * s, size=1.2 * s, color=(1.0, 0.9, 0.8), coll=coll)
    return bd


def camera(name, loc, target, lens=50, coll=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36
    co = bpy.data.objects.new(name, cd); (coll or bpy.context.scene.collection).objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def render(path):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("rendered", path)
