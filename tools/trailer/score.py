"""宣传片配乐与混音：python tools/trailer/score.py <镜头目录> <输出 wav>

全部是自己的素材：游戏里的华尔兹 / 结局曲 / 钟声 / 打字机（tools/audio 合成），每个镜头录下的游戏声，
以及这里现场合成的低音重击、铺底、心跳脉冲、上升音和磁带停转。时间点全部来自 edl.py。
第一幕：华尔兹（外景时像从屋里传出来）→ 错音 → 磁带停转；
第二幕：一秒一下的心跳 + 嗡鸣，华尔兹的开头动机放慢成一音一镜，最后一个音弹错；
第三幕：越来越快的钟摆 + 上升音，在 SILENCE 一刀切断；打字机；片名重击 + 结局曲。
"""
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audio"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import piano  # noqa: E402
from dsp import (SR, secs, tvec, rng, lowpass, highpass, bandpass, conv, reverb_ir, fade,  # noqa: E402
                 place, pan, to_stereo, noise, pink, shaped_noise)
import edl  # noqa: E402

AUDIO = ROOT / "Game/Assets/_MercyCreek/Audio"
N = secs(edl.END + 0.5)


def wav(name):
    with wave.open(str(AUDIO / f"{name}.wav")) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        assert w.getframerate() == SR
        return to_stereo(x.reshape(-1, w.getnchannels())[:, 0]) if w.getnchannels() == 1 else x.reshape(-1, 2)


def buf():
    return np.zeros((N, 2))


def put(b, x, t, g=1.0):
    return place(b, to_stereo(x), t, g)


def big_verb(x, rt=3.5, wet=0.45, seed=7):
    x = to_stereo(x)
    return (x + wet * conv(x, reverb_ir(rt, seed=seed, stereo=True, predelay=0.02))[:len(x)])


# ---------------------------------------------------------------- 合成音色

def sub_hit(dur=3.5, f_hi=70, f_lo=31, seed=1, bright=1.0):
    """低音重击：快速下滑的正弦 + 低通噪声的"轰" + 一点饱和。"""
    n = secs(dur)
    t = tvec(n)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.09)
    body = np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t / 0.9)
    thud = lowpass(noise(n, seed), 180 * bright, 2) * np.exp(-t / 0.08)
    crack = highpass(noise(n, seed + 1), 2500) * np.exp(-t / 0.012) * 0.25 * bright
    x = body + 0.6 * thud / (np.max(np.abs(thud)) + 1e-9) + crack
    return x / np.max(np.abs(x))


def braam(dur=4.0, root=39.0, seed=3):
    """低铜管似的轰鸣：几组失谐锯齿波（根音、八度、五度），低通从暗到亮再回暗。"""
    n = secs(dur)
    t = tvec(n)
    x = np.zeros(n)
    r = rng(seed)
    for mul, a in ((1, 1.0), (2, 0.7), (3, 0.35), (4, 0.25)):
        for det in (-9, -3, 4, 10):
            ff = root * mul * 2 ** (det / 1200)
            ph = 2 * np.pi * ff * t + r.uniform(0, 6.28)
            x += a * (2 * ((ph / (2 * np.pi)) % 1) - 1)
    env = np.minimum(t / 0.04, 1) * np.exp(-t / 1.6)
    # 时变低通：分段处理再拼接（滤波器截止频率随包络走）
    out = np.zeros(n)
    seg = secs(0.05)
    for i in range(0, n, seg):
        tt = i / SR
        fc = 180 + 1500 * np.exp(-((tt - 0.25) / 0.5) ** 2)
        lo = max(0, i - secs(0.02))
        y = lowpass(x[lo:i + seg], fc, 2)
        out[i:i + seg] = y[i - lo:i - lo + seg]
    out *= env
    return out / np.max(np.abs(out))


def thump(f=52, seed=0):
    """心跳似的低音脉冲。"""
    n = secs(0.6)
    t = tvec(n)
    ff = f + 30 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t / 0.16) * np.minimum(t / 0.003, 1)
    return x


def riser(t0, t1, seed=11):
    """噪声扫频 + 一组同时上滑的正弦，响度一路涨到 t1，在 t1 硬切。"""
    n = secs(t1 - t0)
    t = tvec(n)
    u = t / (t1 - t0)

    def gains(times, freqs):
        uu = np.clip(times / (t1 - t0), 0, 1)[:, None]
        fc = 250 * (24 ** uu)
        f = np.maximum(freqs[None, :], 1)
        return np.exp(-np.log(f / fc) ** 2 / (2 * 0.6 ** 2)) * (uu ** 2.0)
    nz = shaped_noise(n, gains, seed=seed)
    nz /= np.max(np.abs(nz)) + 1e-9
    tone = np.zeros(n)
    for k, base in enumerate((55.0, 82.4, 110.0, 164.8)):
        f = base * (2.4 ** u)
        tone += np.sin(2 * np.pi * np.cumsum(f) / SR + k) * (0.6 if k == 0 else 0.3)
    tone *= u ** 1.6
    x = 0.55 * nz + 0.25 * tone / (np.max(np.abs(tone)) + 1e-9)
    x[-secs(0.004):] *= np.linspace(1, 0, secs(0.004))
    return x


def pad(chords, t_end):
    """铺底：每个和弦一组缓慢起落的失谐正弦 / 三角，低通后放远（结局曲的做法）。"""
    b = np.zeros(N)
    t = tvec(N)
    out = buf()
    for k, (t0, t1, notes) in enumerate(chords):
        env = np.clip((t - t0 + 0.8) / 2.0, 0, 1) * np.clip((t1 + 0.8 - t) / 2.0, 0, 1)
        env = np.sin(env * np.pi / 2) ** 2
        idx = env > 0
        for j, nm in enumerate(notes):
            f = 440 * 2 ** ((piano.m(nm) - 69) / 12)
            for c, det in enumerate((-5.0, 5.0)):
                ph = 2 * np.pi * f * 2 ** (det / 1200) * t[idx] + j + c
                tone = np.sin(ph) + 0.2 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
                out[idx, c] += env[idx] * tone * 0.05
    out = lowpass(out, 900, 2)
    return out + 0.5 * conv(out, reverb_ir(3.0, seed=31, stereo=True))[:N]


def tape_stop(x, t0, dur):
    """x 从 t0 起播放速率从 1 滑到 0（读位置 = 速率积分），之后静音。"""
    i0 = secs(t0)
    n = secs(dur)
    u = np.arange(n) / n
    rate = (1 - u) ** 1.6
    pos = i0 + np.cumsum(rate)
    out = x.copy()
    for c in range(2):
        seg = np.interp(pos, np.arange(len(x)), x[:, c]) * np.sqrt(rate)
        out[i0:i0 + n, c] = lowpass(seg, 8000)
    out[i0 + n:] = 0
    return out


# ---------------------------------------------------------------- 混音

def diegetic(shots):
    """每个镜头录下的游戏声，按剪辑表摆好，剪辑点 20ms 交叉。"""
    out = buf()
    gain = {"coach_canvas": 1.6, "coach_arrive": 2.2, "crane_door": 1.8, "telegraph": 1.4, "tear": 1.0,
            "typewriter": 1.6, "dusk": 1.0, "town_wide": 2.2, "street_east": 2.2}
    for (a, b, name, src, opt) in edl.CLIPS:
        raw = np.fromfile(shots / f"{name}.f32", np.float32).astype(np.float64).reshape(-1, 2)
        i = secs(src)
        seg = raw[i:i + secs(b - a)]
        g = gain.get(name, 1.3)
        if a >= 57.0 and name not in ("typewriter", "dusk"):
            g *= 0.5   # 第三幕让给配乐
        seg = fade(seg, 0.02, 0.02)
        if "ramp" in opt:   # 画面减速停下时，环境声一起沉下去
            r0, r1 = opt["ramp"]
            t = a + np.arange(len(seg)) / SR
            seg = seg * np.clip((r1 - t) / (r1 - r0), 0, 1)[:, None]
        put(out, seg, a, g)
    return out


def waltz():
    x = wav("piano_waltz_C")
    i = secs(edl.WALTZ_IN)
    x = np.concatenate([x[i:], x])   # 循环一次，够长
    b = buf()
    put(b, x, edl.W0)
    b = fade(b, 0, 0)
    # 外景：像从酒馆里传出来——低通、压低；进门（hall_shafts）时打开
    ext_end = [c for c in edl.CLIPS if c[2] == "street_east"][0][1]
    muff = lowpass(b, 750, 2) * 0.45
    t = tvec(N)
    k = np.clip((t - ext_end) / 0.25, 0, 1)[:, None]
    b = muff * (1 - k) + b * k
    w0 = secs(edl.W0)
    b[w0:w0 + secs(0.4)] *= np.linspace(0, 1, secs(0.4))[:, None]
    b = tape_stop(b, edl.TAPE_STOP, 1.25)
    return b * 0.85


def act1_fx():
    b = buf()
    tick, tock = wav("clock_tick"), wav("clock_tock")
    for k, t in enumerate(np.arange(0.4, 5.0, 1.0)):
        put(b, tock if k % 2 else tick, t, 0.55)
    keys = [wav(f"typewriter_key_0{i}") for i in range(1, 5)]
    for (t0, t1, kind, text) in edl.TEXTS:
        if kind in ("type_card", "type"):
            vis = 0
            for ch in text:
                if ch != " ":
                    put(b, keys[vis % 4], t0 + vis * edl.TYPE_RATE, 0.6 if kind == "type_card" else 0.7)
                vis += 1
    put(b, wav("church_bell_three"), 5.0, 0.55)
    return b


def act2():
    b = buf()
    a0, a1 = 26.4, 56.8
    # 嗡鸣
    hum = wav("void_hum_loop")
    hum = np.concatenate([hum] * 3)[:secs(a1 - a0 + 1)]
    hum = fade(hum, 3.0, 1.5)
    put(b, hum, a0, 0.35)
    # 铺底：D#m → B → F# → C#
    b += 0.3 * pad([(28.4, 35.4, ['D#3', 'A#3', 'F#4']), (35.4, 42.9, ['B2', 'F#3', 'D#4']),
                    (42.9, 48.4, ['F#3', 'C#4', 'A#3']), (48.4, 54.4, ['C#3', 'G#3', 'E#4'])], a1)
    # 心跳：一秒一下，跟剪辑点对齐
    tick = wav("clock_tick")
    tk = lowpass(tick[:, 0], 2500) if tick.ndim == 2 else tick
    for k, t in enumerate(np.arange(28.4, 54.4, 1.0)):
        put(b, thump(50 if k % 2 == 0 else 46), t, 0.3 if k % 2 == 0 else 0.18)
        put(b, big_verb(tk, 1.6, 0.6, seed=40), t, 0.35)
    # 华尔兹开头的动机，放慢到一音一镜；最后该弹 G#4 的地方弹成 C5（第 12 稿的错音）
    tun = piano.Tuning(**piano.WALTZ_TUNING)
    mel = [(28.4, 'F#4'), (32.4, 'A#4'), (35.4, 'C#5'), (39.9, 'D#5'), (42.9, 'C#5'), (45.4, 'A#4'),
           (48.4, 'B4'), (51.4, 'A#4'), (54.7, 'C5')]
    bass = [(28.4, 'D#2'), (35.4, 'B1'), (42.9, 'F#2'), (48.4, 'C#2'), (54.7, 'C#2')]
    ev = [(t - 26.0, 2.6, piano.m(n), 0.5, 0.05, 700 + k) for k, (t, n) in enumerate(mel)]
    ev += [(t - 26.0, 4.0, piano.m(n), 0.42, -0.2, 800 + k) for k, (t, n) in enumerate(bass)]
    _ = None
    pn = piano.render(ev, a1 - 26.0 + 2, tun, circular=False, tail=6.0, room_rt=3.2, room_wet=0.42,
                      room_seed=41, bright=0.75)
    put(b, pn, 26.0, 0.9)
    # 字卡重击
    for t in edl.CARD_HITS:
        put(b, big_verb(sub_hit(4.0, seed=int(t)), 3.0, 0.5), t, 0.32)
        put(b, big_verb(braam(4.5, 38.9, seed=int(t)), 3.5, 0.5), t, 0.16)
    return b


def act3():
    b = buf()
    s0, s1 = 57.0, edl.SILENCE
    put(b, riser(s0, s1), s0, 0.75)
    # 越来越快的钟摆：间隔 0.5 → 0.07 s
    tick, tock = wav("clock_tick"), wav("clock_tock")
    t, k = s0, 0
    while t < s1 - 0.05:
        u = (t - s0) / (s1 - s0)
        put(b, tock if k % 2 else tick, t, 0.45 + 0.35 * u)
        t += 0.5 * (0.14 ** u)
        k += 1
    # 每个剪辑点一下重击，稿数闪现时加一下更亮的
    for (a, _, name, _, _) in edl.CLIPS:
        if s0 <= a < s1:
            put(b, sub_hit(2.0, 90, 36, seed=int(a * 10)), a, 0.55)
    for t in edl.DRAFT_HITS:
        put(b, big_verb(sub_hit(2.5, 120, 40, seed=int(t * 10), bright=2.0), 2.0, 0.35), t, 0.6)
        put(b, highpass(noise(secs(0.12), int(t)), 3000) * np.exp(-tvec(secs(0.12)) / 0.03), t, 0.18)
    tear = [c for c in edl.CLIPS if c[2] == "tear"][0]
    put(b, wav("canvas_tear"), tear[0] + (0.6 - tear[3]), 0.9)
    # 华尔兹在第三幕里只剩一个回声：错音那一下，倒放着吸进静默
    x = wav("piano_waltz_C")
    i = secs(24.1071)
    note = x[i:i + secs(2.2)][::-1]
    put(b, big_verb(note, 2.5, 0.6), s1 - 2.2, 0.7)
    b[secs(s1):] = 0
    b[secs(s1) - secs(0.005):secs(s1)] *= np.linspace(1, 0, secs(0.005))[:, None]
    return b


def act4():
    """打字机 + 片名 + 结局曲。"""
    b = buf()
    keys = [wav(f"typewriter_key_0{i}") for i in range(1, 5)]
    r = rng(5)
    t = 66.75
    while t < 67.45:   # 字出来之前，打字机先自己敲了几下
        put(b, keys[r.integers(4)], t, 0.7)
        t += r.uniform(0.09, 0.2)
    last = [x for x in edl.TEXTS if x[3].startswith("……")][0]
    end_t = last[0] + len(last[3]) * edl.TYPE_RATE
    put(b, wav("typewriter_bell"), end_t + 0.25, 0.7)
    put(b, wav("typewriter_return"), end_t + 0.9, 0.45)
    # 片名：重击 + 结局曲（第一个音正落在重击上）
    put(b, big_verb(sub_hit(6.0, 60, 28, seed=99), 4.5, 0.6), edl.TITLE, 0.4)
    put(b, big_verb(braam(6.0, 34.6, seed=98), 4.5, 0.6), edl.TITLE, 0.2)
    end = wav("ending_theme")
    end = fade(end[:secs(edl.END - edl.TITLE + 1.0)], 0.0, 2.5)
    put(b, end, edl.TITLE - 1.0, 1.0)
    return b


def main():
    shots = Path(sys.argv[1])
    out = Path(sys.argv[2])
    stems = {"dia": diegetic(shots) * 1.0, "waltz": waltz(), "fx1": act1_fx(), "act2": act2(),
             "act3": act3(), "act4": act4()}
    mix = sum(stems.values())
    mix = highpass(mix, 22, 2)
    # 软限幅：只削最尖的几个峰，真正的响度交给 loudnorm
    pk = np.max(np.abs(mix))
    mix = mix / pk * 0.89
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)
    mix *= 0.89
    out.parent.mkdir(parents=True, exist_ok=True)
    mix.astype(np.float32).tofile(str(out) + ".f32")
    for k, v in stems.items():
        (v.astype(np.float32)).tofile(str(out.parent / f"stem_{k}.f32"))
    print("score", out, f"{len(mix) / SR:.2f}s peak {20 * np.log10(np.max(np.abs(mix))):.2f} dBFS")


if __name__ == "__main__":
    main()
