"""自动钢琴（1880–1900 年代立式 player piano）+ 圆琴凳。

blender --background --python tools/blender/build_piano.py -- [--no-render] [--samples N] [--out path.glb]
输出：Game/Assets/_MercyCreek/Art/Props/PlayerPiano.glb，评审图 Reviews/blender/PlayerPiano*.png
坐标：正面（琴键一侧）朝 Blender -Y = glTFast 导入后 Unity +Z；Z 向上；原点在琴体落地中心；1 单位 = 1 m。
节点：PlayerPiano（根）/ PianoCase、Keys、Fallboard（铰链处为原点）、PianoRoll（卷轴，原点在轴心，可绕 X 转）、PianoStool。
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bpy
import numpy as np
import mc_common as mc
from mc_common import T, R, S, Part

A = mc.args()
RENDER = "--no-render" not in A
SAMPLES = int(A[A.index("--samples") + 1]) if "--samples" in A else 48
OUT = A[A.index("--out") + 1] if "--out" in A else str(mc.ART / "Props" / "PlayerPiano.glb")

mc.reset()
scene = bpy.context.scene
asset = bpy.data.collections.new("Asset"); scene.collection.children.link(asset)
stage = bpy.data.collections.new("Stage"); scene.collection.children.link(stage)

# ---------- 材质 ----------
CASE = mc.pbr("PianoCase", "Wood066", tile=0.9, tint=(0.40, 0.31, 0.26), rough_mul=0.85, rough_add=0.08, normal=0.8)
PANEL = mc.pbr("PianoPanel", "Wood027", tile=0.7, tint=(0.85, 0.74, 0.66), rough_mul=0.8, rough_add=0.06, normal=0.8)
IVORY = mc.flat("Ivory", (0.70, 0.60, 0.42), rough=0.4)
EBONY = mc.flat("Ebony", (0.025, 0.02, 0.018), rough=0.28)
BRASS = mc.flat("AgedBrass", (0.62, 0.45, 0.2), rough=0.38, metal=1.0)
FELT = mc.flat("RedFelt", (0.28, 0.03, 0.03), rough=0.95)
DARK = mc.flat("CavityDark", (0.03, 0.025, 0.02), rough=0.9)
GLASS = mc.flat("PianoGlass", (0.9, 0.88, 0.8), rough=0.08, transmission=1.0, alpha=0.25, ior=1.5)
VELVET = mc.flat("StoolVelvet", (0.11, 0.018, 0.022), rough=0.95)


def roll_texture():
    """纸卷：米色纸 + 88 轨随机打孔（固定种子）。"""
    path = mc.DERIVED / "piano_roll_paper.png"
    if path.exists():
        return path
    mc.DERIVED.mkdir(parents=True, exist_ok=True)
    w, h = 1024, 512
    rng = np.random.default_rng(1882)
    yy, xx = np.mgrid[0:h, 0:w]
    base = np.array([0.86, 0.80, 0.66]) * (0.95 + 0.05 * np.sin(xx / 37.0 + yy / 53.0))[..., None]
    img = np.ones((h, w, 4), np.float32); img[..., :3] = base
    tracks = 88; tw = w / tracks
    for t in range(tracks):
        y = 0
        while y < h:
            y += int(rng.integers(4, 60))
            ln = int(rng.integers(3, 26))
            if rng.random() < 0.55:
                x0 = int(t * tw + tw * 0.25); x1 = int(x0 + max(2, tw * 0.5))
                img[y:y + ln, x0:x1, :3] = (0.12, 0.09, 0.06)
            y += ln
    img[:, :6, :3] *= 0.7; img[:, -6:, :3] *= 0.7
    im = bpy.data.images.new("roll", w, h, alpha=False)
    im.pixels.foreach_set(img[::-1].ravel())
    im.filepath_raw = str(path); im.file_format = "PNG"; im.save()
    return path


ROLL = mc.image_mat("PianoRollPaper", roll_texture(), rough=0.8)

# ---------- 尺寸 ----------
W, HW = 1.55, 0.775
Y_BACK, Y_FRONT = 0.325, -0.325
KEY_W = 0.0235                     # 白键间距
KEYS_X0 = -52 * KEY_W / 2          # 52 个白键
Z_KEYTOP = 0.725

root = mc.empty("PlayerPiano", collection=asset)
case = Part([CASE])


def raised_panel(cx, cz, w, h, y_face, depth=0.018, mat=PANEL):
    """凸起的倒角芯板 + 四边线脚：远看像雕刻的嵌板。"""
    case.box((w, depth, h), mat, xf=T(cx, y_face + depth / 2, cz), bevel=min(0.03, w * 0.15), bseg=1)
    t = 0.022
    for (dx, dz, sw, sh) in ((0, h / 2 + t / 2, w + 2 * t, t), (0, -h / 2 - t / 2, w + 2 * t, t),
                             (-w / 2 - t / 2, 0, t, h), (w / 2 + t / 2, 0, t, h)):
        case.box((sw, 0.016, sh), CASE, xf=T(cx + dx, y_face + 0.004, cz + dz), bevel=0.006, bseg=2)


def rosette(cx, cz, y_face, r=0.06):
    prof = [(0, 0, 0), (0, r, r), (0.008, r * 1.02, r * 1.02), (0.014, r * 0.8, r * 0.8), (0.012, r * 0.6, r * 0.6),
            (0.022, r * 0.45, r * 0.45), (0.03, r * 0.18, r * 0.18), (0.032, 0, 0)]
    prof = [(z, a, b) for z, a, b in prof]
    # 沿 -Y 向外凸
    case.lathe(sorted(prof, key=lambda p: p[0]), PANEL, seg=16, xf=T(cx, y_face, cz) @ R("X", 90))


# 侧板（落地到顶）
for s in (-1, 1):
    case.box((0.04, Y_BACK + 0.02, 1.31), CASE, xf=T(s * (HW - 0.02), (Y_BACK - 0.02) / 2, 0.655), bevel=0.008, bseg=2)
# 底座、背板
case.box((W, Y_BACK, 0.06), CASE, xf=T(0, Y_BACK / 2, 0.03), bevel=0.005)
case.box((W - 0.08, 0.03, 1.27), CASE, xf=T(0, Y_BACK - 0.015, 0.655))
# 下面板 + 两块凸板
case.box((W - 0.08, 0.03, 0.54), CASE, xf=T(0, 0.015, 0.33))
for cx in (-0.34, 0.34):
    raised_panel(cx, 0.335, 0.5, 0.34, -0.018)
# 键床、前挡条
case.box((W - 0.08, 0.30, 0.05), CASE, xf=T(0, -0.15, 0.625))
case.box((1.25, 0.018, 0.075), CASE, xf=T(0, -0.293, 0.655), bevel=0.006, bseg=2)
case.box((1.24, 0.004, 0.012), FELT, xf=T(0, -0.13, 0.693))  # 键后红呢条
case.box((1.24, 0.03, 0.03), CASE, xf=T(0, -0.11, 0.705))
# 键盘两侧颊木（前端圆角）
for s in (-1, 1):
    case.box((0.115, 0.30, 0.17), CASE, xf=T(s * 0.675, -0.15, 0.715), bevel=0.02, bseg=3)
# 车削琴腿 + 托脚
leg_prof = [(0, 0.035, 0.035), (0.03, 0.035, 0.035), (0.04, 0.026, 0.026), (0.12, 0.022, 0.022), (0.2, 0.03, 0.03),
            (0.27, 0.036, 0.036), (0.33, 0.03, 0.03), (0.41, 0.022, 0.022), (0.45, 0.028, 0.028), (0.47, 0.034, 0.034),
            (0.52, 0.034, 0.034)]
for s in (-1, 1):
    case.lathe(leg_prof, CASE, seg=12, xf=T(s * 0.675, -0.235, 0.08))
    case.box((0.1, 0.33, 0.08), CASE, xf=T(s * 0.675, -0.16, 0.04), bevel=0.012, bseg=2)
    # 托脚下方小卷饰
    case.lathe([(0, 0.0, 0.0), (0.0, 0.03, 0.03), (0.02, 0.036, 0.036), (0.05, 0.02, 0.02), (0.06, 0, 0)], CASE, seg=10,
               xf=T(s * 0.675, -0.235, 0.565))

# 上部琴身：卷轴窗 + 两侧雕板
Y_UP = -0.03
Z0, Z1 = 0.80, 1.285
WX0, WX1, WZ0, WZ1 = -0.36, 0.36, 0.90, 1.20
case.box((W - 0.08, 0.03, WZ0 - Z0), CASE, xf=T(0, Y_UP + 0.015, (Z0 + WZ0) / 2))
case.box((W - 0.08, 0.03, Z1 - WZ1), CASE, xf=T(0, Y_UP + 0.015, (WZ1 + Z1) / 2))
for s in (-1, 1):
    case.box((HW - 0.04 - WX1, 0.03, WZ1 - WZ0), CASE, xf=T(s * (WX1 + (HW - 0.04 - WX1) / 2), Y_UP + 0.015, (WZ0 + WZ1) / 2))
    raised_panel(s * 0.555, (WZ0 + WZ1) / 2, 0.24, 0.27, Y_UP - 0.018)
    rosette(s * 0.555, (WZ0 + WZ1) / 2, Y_UP - 0.018, 0.055)
# 卷轴窗框线脚
for (cx, cz, sw, sh) in ((0, WZ1 + 0.015, WX1 - WX0 + 0.06, 0.03), (0, WZ0 - 0.015, WX1 - WX0 + 0.06, 0.03),
                         (WX0 - 0.015, (WZ0 + WZ1) / 2, 0.03, WZ1 - WZ0), (WX1 + 0.015, (WZ0 + WZ1) / 2, 0.03, WZ1 - WZ0)):
    case.box((sw, 0.03, sh), CASE, xf=T(cx, Y_UP - 0.012, cz), bevel=0.008, bseg=2)
# 窗内腔
case.box((WX1 - WX0, 0.01, WZ1 - WZ0), DARK, xf=T(0, 0.14, (WZ0 + WZ1) / 2))
for s in (-1, 1):
    case.box((0.01, 0.17, WZ1 - WZ0), DARK, xf=T(s * WX1, 0.055, (WZ0 + WZ1) / 2))
case.box((WX1 - WX0, 0.17, 0.01), DARK, xf=T(0, 0.055, WZ0 + 0.005))
case.box((WX1 - WX0, 0.17, 0.01), DARK, xf=T(0, 0.055, WZ1 - 0.005))
# 卷轴支架（黄铜）
for s in (-1, 1):
    case.box((0.012, 0.05, 0.27), BRASS, xf=T(s * 0.335, 0.06, 1.05), bevel=0.003)
# 立柱壁柱 + 顶冠 + 顶盖
for s in (-1, 1):
    case.lathe([(0, 0.0, 0.0), (0, 0.03, 0.022), (0.03, 0.032, 0.024), (0.05, 0.024, 0.018), (0.4, 0.024, 0.018),
                (0.42, 0.032, 0.024), (0.46, 0.032, 0.024), (0.46, 0, 0)], CASE, seg=12, xf=T(s * (HW - 0.045), Y_UP - 0.012, 0.815))
case.box((W + 0.02, 0.05, 0.035), CASE, xf=T(0, Y_UP - 0.01, 1.295), bevel=0.012, bseg=2)
case.box((W + 0.05, Y_BACK - Y_UP + 0.06, 0.04), CASE, xf=T(0, (Y_BACK + Y_UP) / 2 - 0.01, 1.33), bevel=0.012, bseg=2)
# 踏板：两只黄铜小踏板 + 两块折出的风箱踏板（player piano 的标志）
for x in (-0.07, 0.07):
    case.box((0.035, 0.13, 0.016), BRASS, xf=T(x, -0.06, 0.075), bevel=0.006, bseg=2)
for x in (-0.2, 0.2):
    case.box((0.17, 0.26, 0.022), CASE, xf=T(x, -0.15, 0.06) @ R("X", 9), bevel=0.006, bseg=2)
    case.box((0.16, 0.012, 0.01), BRASS, xf=T(x, -0.27, 0.042), bevel=0.003)
case_ob = case.finish("PianoCase", parent=root, collection=asset)

# ---------- 琴键 ----------
keys = Part([IVORY, EBONY])
for i in range(52):
    x = KEYS_X0 + (i + 0.5) * KEY_W
    keys.box((KEY_W - 0.0012, 0.15, 0.022), IVORY, xf=T(x, -0.215, Z_KEYTOP - 0.011), bevel=0.0012)
# A0 起：白键序列 A B C D E F G ... 黑键在 A#、C#、D#、F#、G#
white_names = "ABCDEFG"
for i in range(51):
    n = white_names[i % 7]
    if n in "ACDFG":
        x = KEYS_X0 + (i + 1) * KEY_W
        keys.poly_extrude([(-0.0068, -0.045), (0.0068, -0.045), (0.0058, 0.045), (-0.0058, 0.045)], 0.012, EBONY,
                          xf=T(x, -0.185, Z_KEYTOP) @ R("X", 0))
keys_ob = keys.finish("Keys", parent=root, collection=asset)

# ---------- 翻盖（打开状态，原点在铰链） ----------
fb = Part([CASE])
fb.box((1.24, 0.02, 0.13), CASE, xf=T(0, 0.0, -0.065) @ R("X", -12), bevel=0.006, bseg=2)
fb_ob = fb.finish("Fallboard", parent=root, location=(0, -0.105, 0.86), collection=asset)

# ---------- 纸卷（原点在下卷轴轴心，Unity 里可绕 X 转） ----------
rl = Part([ROLL])
rl.lathe([(-0.31, 0, 0), (-0.31, 0.034, 0.034), (0.31, 0.034, 0.034), (0.31, 0, 0)], ROLL, seg=16, xf=R("Y", 90) @ R("Z", 0))
for s in (-1, 1):
    rl.lathe([(0, 0, 0), (0, 0.045, 0.045), (0.006, 0.045, 0.045), (0.006, 0, 0)], BRASS, seg=16, xf=T(s * 0.316, 0, 0) @ R("Y", 90))
# 上卷轴与纸带
rl.lathe([(-0.31, 0, 0), (-0.31, 0.022, 0.022), (0.31, 0.022, 0.022), (0.31, 0, 0)], ROLL, seg=12, xf=T(0, 0.01, 0.2) @ R("Y", 90))
rl.quad([(-0.3, -0.034, 0.0), (0.3, -0.034, 0.0), (0.3, -0.012, 0.2), (-0.3, -0.012, 0.2)], ROLL)
rl_ob = rl.finish("PianoRoll", parent=root, location=(0, 0.06, 0.95), collection=asset)

# 推拉玻璃门（两扇，前后错开）
gl = Part([CASE, GLASS])
for k, (cx, y) in enumerate(((-0.17, -0.06), (0.17, -0.048))):
    w, h = 0.37, WZ1 - WZ0 - 0.02
    for (dx, dz, sw, sh) in ((0, h / 2 - 0.0125, w, 0.025), (0, -h / 2 + 0.0125, w, 0.025),
                             (-w / 2 + 0.0125, 0, 0.025, h), (w / 2 - 0.0125, 0, 0.025, h)):
        gl.box((sw, 0.012, sh), CASE, xf=T(cx + dx, y, (WZ0 + WZ1) / 2 + dz), bevel=0.003)
    gl.box((w - 0.04, 0.003, h - 0.04), GLASS, xf=T(cx, y, (WZ0 + WZ1) / 2))
gl_ob = gl.finish("RollDoors", parent=root, collection=asset)
gl_ob.visible_shadow = False

# ---------- 琴凳（独立对象） ----------
st = Part([CASE, VELVET, BRASS])
st.lathe([(0.47, 0, 0), (0.47, 0.155, 0.155), (0.478, 0.172, 0.172), (0.495, 0.178, 0.178), (0.512, 0.172, 0.172),
          (0.52, 0.16, 0.16), (0.52, 0, 0)], CASE, seg=24)
st.lathe([(0.518, 0, 0), (0.518, 0.158, 0.158), (0.535, 0.155, 0.155), (0.548, 0.13, 0.13), (0.553, 0.07, 0.07), (0.554, 0, 0)],
         VELVET, seg=24)
st.lathe([(0.2, 0.0, 0.0), (0.2, 0.05, 0.05), (0.23, 0.055, 0.055), (0.26, 0.035, 0.035), (0.34, 0.03, 0.03),
          (0.38, 0.045, 0.045), (0.42, 0.04, 0.04), (0.47, 0.06, 0.06), (0.47, 0, 0)], CASE, seg=12)
for k in range(4):
    a = math.radians(45 + 90 * k)
    top = mc.Vector((math.cos(a) * 0.04, math.sin(a) * 0.04, 0.3)); foot = mc.Vector((math.cos(a) * 0.21, math.sin(a) * 0.21, 0.03))
    d = top - foot
    st.lathe([(0, 0.016, 0.016), (d.length * 0.5, 0.019, 0.019), (d.length, 0.024, 0.024), (d.length, 0, 0)], CASE, seg=8,
             xf=T(*foot) @ mc.orient(d))
    st.sphere(0.026, BRASS, xf=T(foot.x, foot.y, 0.026), seg=10, rings=6)
st_ob = st.finish("PianoStool", parent=root, location=(0, -0.72, 0), collection=asset)

parts = [case_ob, keys_ob, fb_ob, rl_ob, gl_ob, st_ob]
tris = mc.tri_count(parts)
print(f"TRIS PlayerPiano total={tris}", {o.name: mc.tri_count([o]) for o in parts})
assert tris <= 15000, tris
mc.export_glb(OUT, [root])

# ---------- 评审渲染 ----------
if RENDER:
    mc.setup_render(SAMPLES)
    mc.world_hdri(strength=0.25)
    mc.studio(coll=stage, key=500, scale=1.0)
    mc.camera("Cam", (-1.5, -2.6, 1.35), (0.0, 0.0, 0.72), lens=40, coll=stage)
    mc.render(mc.REVIEWS / "PlayerPiano.png")
    mc.camera("CamKeys", (0.55, -0.95, 1.15), (0.0, -0.1, 0.8), lens=35, coll=stage)
    mc.render(mc.REVIEWS / "PlayerPiano_keys.png")
