"""下载 CC0 资产：Poly Haven 模型（glTF 2k）、HDRI（2k exr）、ambientCG 材质（2K JPG）。
用法：python3 -I tools/fetch_assets.py   （已存在的文件跳过，可重复执行）
"""
import json, os, sys, urllib.request, zipfile, io, pathlib, concurrent.futures as cf

ROOT = pathlib.Path(__file__).resolve().parent.parent / "art" / "source"

PH_MODELS = [
    "Barrel_01", "wine_barrel_01", "wooden_barrels_01", "wine_bottles_01",
    "WoodenTable_01", "WoodenTable_02", "round_wooden_table_01", "round_wooden_table_02",
    "WoodenChair_01", "painted_wooden_chair_02", "wooden_stool_01", "wooden_stool_02", "bar_chair_round_01", "Rockingchair_01",
    "Lantern_01", "wooden_lantern_01", "vintage_grandfather_clock_01", "mantel_clock_01",
    "ornate_mirror_01", "wooden_crate_01", "wooden_crate_02", "wooden_bucket_01", "wooden_ladder",
    "wooden_display_shelves_01", "dartboard", "hanging_picture_frame_03", "barrel_stove",
]
PH_HDRIS = ["goegap_road", "plains_sunset", "aarfontein_pan"]
AC_MATERIALS = ["WoodFloor041", "WoodFloor043", "Planks037A", "Planks021", "WoodSiding011", "WoodSiding013", "Wallpaper002A", "Wallpaper002B",
                # 人偶 / 钢琴 / 道具 / 街景（tools/blender/build_{mannequin,piano,props,street}.py）
                "Wood050", "Wood092", "Wood066", "Wood027", "Fabric032", "Fabric061", "Fabric063", "Fabric066",
                "Fabric040", "Fabric022", "Fabric026", "Fabric028", "Leather037", "Leather030", "Leather026",
                "Metal027", "Paper005", "Ground054", "Ground080", "Ground033", "WoodSiding009", "WoodSiding002",
                "WoodSiding004", "WoodSiding010", "PaintedWood009C", "PaintedWood008B", "Planks012",
                # 街道两头：教堂地基、枯树（tools/blender/build_edges.py）
                "Rock030", "Bark007"]
# SIL OFL 字体：只用来把招牌文字栅格化成贴图（字体文件本身不进工程）
FONTS = {"Rye-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/rye/Rye-Regular.ttf",
         "Rye-OFL.txt": "https://github.com/google/fonts/raw/main/ofl/rye/OFL.txt",
         # 墓碑刻字 / 手写"待写"纸条（tools/gen_edge_textures.py）
         "IMFeENsc28P.ttf": "https://github.com/google/fonts/raw/main/ofl/imfellenglishsc/IMFeENsc28P.ttf",
         "IMFell-OFL.txt": "https://github.com/google/fonts/raw/main/ofl/imfellenglishsc/OFL.txt",
         "Zeyada.ttf": "https://github.com/google/fonts/raw/main/ofl/zeyada/Zeyada.ttf",
         "Zeyada-OFL.txt": "https://github.com/google/fonts/raw/main/ofl/zeyada/OFL.txt"}

UA = {"User-Agent": "mercy-creek-asset-fetch/1.0"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def save(url, dest):
    dest = pathlib.Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(get(url))
    tmp.rename(dest)


def ph_model(asset_id):
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset_id}"))
    g = files["gltf"]["2k"]["gltf"]
    base = ROOT / "polyhaven" / "models" / asset_id
    gltf_path = base / os.path.basename(g["url"])
    save(g["url"], gltf_path)
    for rel, info in g["include"].items():
        url = info["url"]
        if rel.endswith(".bin"):
            # API 有时把 .bin 指到 8k 目录下的旧版本，和 2k 的 .gltf 对不上：改用 .gltf 同目录
            url = g["url"].rsplit("/", 1)[0] + "/" + rel
        save(url, base / rel)
    for b in json.loads(gltf_path.read_text())["buffers"]:
        p = base / b["uri"]
        if p.stat().st_size != b["byteLength"]:
            p.unlink()
            raise RuntimeError(f"{p.name} size {p.stat().st_size if p.exists() else 0} != {b['byteLength']}")
    return asset_id


def ph_hdri(asset_id):
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset_id}"))
    h = files["hdri"]["2k"]["exr"]
    save(h["url"], ROOT / "polyhaven" / "hdris" / f"{asset_id}_2k.exr")
    return asset_id


def ac_material(asset_id):
    dest = ROOT / "ambientcg" / asset_id
    if dest.exists() and any(dest.iterdir()):
        return asset_id
    data = get(f"https://ambientcg.com/get?file={asset_id}_2K-JPG.zip")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            # 只取贴图，拒绝任何带路径的条目
            if "/" in n or "\\" in n or not n.lower().endswith((".jpg", ".png")):
                continue
            (dest / n).write_bytes(z.read(n))
    return asset_id


def font(name):
    save(FONTS[name], ROOT / "fonts" / name)
    return name


def main():
    jobs = [(ph_model, a) for a in PH_MODELS] + [(ph_hdri, a) for a in PH_HDRIS] + [(ac_material, a) for a in AC_MATERIALS] + [(font, f) for f in FONTS]
    failed = []
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(f, a): a for f, a in jobs}
        for fu in cf.as_completed(futs):
            a = futs[fu]
            try:
                fu.result(); print("ok  ", a)
            except Exception as e:
                failed.append(a); print("FAIL", a, e, file=sys.stderr)
    print(f"done, {len(jobs) - len(failed)}/{len(jobs)} ok")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
