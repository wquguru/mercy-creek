"""合成的老式走音立式钢琴（honky-tonk），以及两首原创曲：《Mercy Creek 华尔兹》与结局曲。

音色模型（全部程序合成，不用采样）：
- 每个键 1–3 根弦，各自失谐几到十几音分（honky-tonk 的"合唱"感），整架琴每个键再随机跑调
- 弦的泛音带非谐性 f_n = n·f0·sqrt(1 + B·n²)，高泛音衰减更快，两段式衰减（瞬态 + 余音）
- 击弦位置梳状滤波 + 力度控制亮度；击弦噪声（毡锤 + 键底撞击）
- 音板 / 琴箱：短模态卷积；再进一个小木头房间的卷积混响
"""
import numpy as np

from dsp import (SR, secs, tvec, rng, bandpass, lowpass, highpass, peaking, conv, modal_ir,
                 reverb_ir, fold_tail, fade, normalize_peak)

NOTE_IDX = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'E#': 5, 'F': 5, 'F#': 6,
            'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'B#': 12}


def m(name):
    """'F#4' -> 66（C4 = 60）。E#、B# 按升号拼写处理。"""
    pc, octv = name[:-1], int(name[-1])
    return 12 * (octv + 1) + NOTE_IDX[pc]


class Tuning:
    """一架琴的"跑调档案"：每个键的整体偏差和各根弦的失谐。固定种子，所有版本共用。"""

    def __init__(self, seed, key_spread=6.0, string_spread=(5.0, 11.0), sour=None, max_strings=3):
        r = rng(seed)
        self.key = {k: r.normal(0, key_spread) for k in range(21, 109)}
        self.strings = {}
        for k in range(21, 109):
            ns = 1 if k < 34 else (2 if k < 46 else 3)
            ns = min(ns, max_strings)
            s = r.uniform(*string_spread)
            offs = [0.0, -s, s * r.uniform(0.6, 1.0)][:ns]
            if ns == 2:
                offs = [-s / 2, s / 2]
            self.strings[k] = offs
        for k, c in (sour or {}).items():
            self.key[k] += c


def piano_note(midi, vel, hold, tuning, seed, bright=1.0):
    """渲染一个音（单声道）。hold = 按键时长（秒），之后制音器落下。"""
    r = rng(seed)
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    B = 3.0e-4 * 2 ** ((midi - 60) / 18) + 4.0e-4 * max(0.0, (40 - midi) / 20)
    T60 = float(np.clip(12.0 * 2 ** (-(midi - 36) / 16), 1.0, 14.0))  # 基音余音
    rel = 0.09 + 0.10 * max(0.0, (60 - midi) / 30)  # 低音制音慢一点
    n = secs(min(hold + 6 * rel + 0.05, hold + T60))
    t = tvec(n)
    fc = (1400 + 5200 * vel ** 2) * bright  # 力度越大越亮
    y = np.zeros(n)
    energy = 0.0
    strike = 7.3 + r.uniform(-0.3, 0.3)  # 击弦点约在弦长 1/7
    for k in range(1, 48):
        fk_base = k * f0 * np.sqrt(1 + B * k * k)
        if fk_base > 11000:
            break
        amp = (1.0 / k ** 0.85) * (0.15 + abs(np.sin(np.pi * k / strike))) * np.exp(-fk_base / fc)
        if k == 1:  # 中高音区基音要站得住，低音区让给二、三次泛音（小立式琴低音发虚）
            amp *= 0.9 if midi < 48 else 1.6
        elif k == 2:
            amp *= 1.15
        if amp < 1e-4:
            continue
        energy += amp * amp
        Tk = T60 / (1 + (fk_base / 1800.0) ** 1.1 + 0.03 * k)
        # 两段式衰减：起音后快速掉一截（"prompt sound"），剩下慢慢唱（"aftersound"）
        env = 0.62 * np.exp(-6.9 * t / (Tk * 0.22)) + 0.38 * np.exp(-6.9 * t / Tk)
        osc = np.zeros(n)
        for c in tuning.strings[midi]:
            fk = fk_base * 2 ** ((tuning.key[midi] + c) / 1200)
            osc += np.sin(2 * np.pi * fk * t + r.uniform(0, 2 * np.pi))
        y += amp * env * osc / len(tuning.strings[midi])
    # 每个音按泛音总能量归一：否则低音几十个泛音叠起来会比旋律响 10 dB
    y /= np.sqrt(energy)
    # 起音：毡锤接触约 1–2ms
    a = secs(0.0015 if midi > 50 else 0.0025)
    y[:a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    # 击弦噪声：毡锤的"噗"和键底撞击的"咚"
    hn = secs(0.04)
    hnoise = r.standard_normal(hn) * np.exp(-tvec(hn) / 0.006) * np.clip(tvec(hn) / 0.0006, 0, 1)
    hnoise = bandpass(hnoise, 400, min(2500 + 2.5 * f0, 9000)) * 0.10 * vel
    thump = np.sin(2 * np.pi * 62 * tvec(hn)) * np.exp(-tvec(hn) / 0.012) * 0.06 * vel
    y[:hn] += hnoise + thump
    # 制音器
    h = secs(hold)
    if h < n:
        y[h:] *= np.exp(-(t[h:] - t[h]) / rel)
    return y * vel


def body_ir():
    """立式钢琴音板 + 琴箱的短 IR：直达 + 一串低中频木头模态。"""
    fr = [92, 138, 201, 287, 404, 553, 761, 1043, 1480, 2110]
    t6 = [0.30, 0.24, 0.20, 0.16, 0.13, 0.11, 0.09, 0.07, 0.05, 0.04]
    am = [0.050, 0.060, 0.055, 0.050, 0.042, 0.035, 0.026, 0.020, 0.014, 0.010]
    ir = modal_ir(fr, t6, am, 0.35, seed=77)
    # 模态的共振增益要按频响峰值归一，否则正好落在模态上的低音（F#2≈92Hz）会被放大 30 dB
    H = np.abs(np.fft.rfft(ir, 1 << 16))
    ir *= 0.8 / H.max()
    ir[0] += 1.0
    return ir


def render(events, length, tuning, circular=False, tail=8.0, body=True, room_rt=1.0, room_wet=0.18,
           room_seed=5, bright=1.0, cabinet=True):
    """events: [(t, hold, midi, vel, pan, seed)]。circular=True 时尾巴绕回开头（无缝循环）。

    返回 (dry_stereo_before_room, final_stereo)。"""
    L = secs(length)
    buf = np.zeros((L + secs(tail), 2))
    for (t0, hold, midi, vel, pn, sd) in events:
        x = piano_note(midi, vel, hold, tuning, sd, bright)
        th = (pn + 1) * np.pi / 4
        i = secs(t0)
        n = min(len(x), len(buf) - i)
        buf[i:i + n, 0] += x[:n] * np.cos(th)
        buf[i:i + n, 1] += x[:n] * np.sin(th)
    return finish(buf, L, circular, body, room_rt, room_wet, room_seed, cabinet)


def finish(buf, L, circular, body=True, room_rt=1.0, room_wet=0.18, room_seed=5, cabinet=True):
    x = fold_tail(buf, L) if circular else buf
    if body:
        x = conv(x, body_ir())
        x = fold_tail(x, L) if circular else x[:len(buf)]
    if cabinet:
        x = highpass(x, 38, 2)
        x = peaking(x, 240, 0.9, 2.0)  # 立式琴的"箱子"味
        x = peaking(x, 2800, 1.2, 1.5)  # 旧琴锤变硬，有点"铛"
        x = lowpass(x, 7800, 2)
    ir = reverb_ir(room_rt, seed=room_seed, stereo=True, predelay=0.006)
    w = conv(x, ir)
    if circular:
        w = fold_tail(w, L)
        out = x + room_wet * w
    else:
        out = room_wet * w[:len(x)]
        out += x
    return out


# ================================================================ 《Mercy Creek 华尔兹》

BPM = 112
BEAT = 60.0 / BPM
BAR = 3 * BEAT
N_BARS = 36
SPOT_BAR = 15  # 错音所在小节（A' 段第 4 小节，半终止，V 和弦上的长音）
SPOT_TIME = SPOT_BAR * BAR
LOOP_LEN = N_BARS * BAR

# 每小节和弦（F# 大调）
CHORDS = (['I', 'IV', 'I', 'V7'] +                                 # 0–3 前奏（只有左手）
          ['I', 'vi', 'ii', 'V', 'I', 'IV', 'V7', 'I'] +             # 4–11  A
          ['I', 'vi', 'ii', 'V', 'I', 'IV', 'V7', 'I'] +             # 12–19 A'（第 15 小节 = 错音处）
          ['vi', 'iii', 'IV', 'I', 'vi', 'ii', 'V', 'V7'] +          # 20–27 B
          ['I', 'vi', 'ii', 'V', 'I', 'IV', 'V7', 'I'])              # 28–35 A''
# 和弦 -> (低音, 交替低音, 2/3 拍的中音区和弦)
VOICING = {
    'I': ('F#2', 'C#2', ['F#3', 'A#3', 'C#4']),
    'vi': ('D#2', 'A#1', ['F#3', 'A#3', 'D#4']),
    'ii': ('G#2', 'D#2', ['G#3', 'B3', 'D#4']),
    'V': ('C#2', 'G#2', ['E#3', 'G#3', 'C#4']),
    'V7': ('C#2', 'G#2', ['E#3', 'G#3', 'B3']),
    'IV': ('B1', 'F#2', ['F#3', 'B3', 'D#4']),
    'iii': ('A#1', 'E#2', ['A#3', 'C#4', 'E#4']),
}

A_HEAD = [[('F#4', 1), ('A#4', 1), ('C#5', 1)],
          [('D#5', 2), ('C#5', 1)],
          [('A#4', 1), ('B4', 1), ('A#4', 1)],
          [('G#4', 3)]]
MELODY = (
    [[]] * 4 +
    A_HEAD + [[('F#4', 1), ('A#4', 1), ('C#5', 1)], [('F#5', 2), ('D#5', 1)],
              [('C#5', 1), ('B4', 1), ('G#4', 1)], [('F#4', 3)]] +
    A_HEAD + [[('F#4', 1), ('A#4', 1), ('C#5', 1)], [('B4', 1), ('D#5', 1), ('F#5', 1)],
              [('E#5', 1.5), ('D#5', 0.5), ('C#5', 1)], [('F#5', 2), ('C#5', 1)]] +
    [[('A#4', 1), ('D#5', 1), ('F#5', 1)], [('E#5', 2), ('C#5', 1)],
     [('D#5', 1), ('C#5', 1), ('B4', 1)], [('A#4', 3)],
     [('A#4', 1), ('D#5', 1), ('F#5', 1)], [('G#5', 2), ('F#5', 1)],
     [('E#5', 1), ('D#5', 1), ('C#5', 1)], [('B4', 2), ('C#5', 1)]] +
    A_HEAD + [[('F#4', 1), ('A#4', 1), ('C#5', 1)], [('F#5', 2), ('D#5', 1)],
              [('C#5', 1), ('G#4', 1), ('A#4', 1)], [('F#4', 3)]]
)
assert len(MELODY) == N_BARS and len(CHORDS) == N_BARS

INTENDED = 'G#4'
# 错音：取离 G#4 最近的那个八度；每个都与 C# 和弦里的某个音只差半音（C↔C#、A↔G#、G↔G#、E↔E#）
WRONG = {'C': 'C5', 'A': 'A4', 'G': 'G4', 'E': 'E4'}

WALTZ_TUNING = dict(seed=1882, key_spread=7.0, string_spread=(6.0, 13.0),
                    sour={m('D#5'): 14.0, m('A#3'): -12.0, m('B4'): 9.0})


def pan_for(midi):
    return float(np.clip((midi - 62) / 40.0, -0.45, 0.45))


def waltz_events():
    """返回 (除错音外的全部事件, 错音事件模板)。人性化随机数按固定顺序取，与音高无关，
    所以 5 个版本除了那一个音之外逐样本相同。"""
    r = rng(314)
    ev = []
    spot = None
    seed = 1000
    prev_chord = None
    for bar in range(N_BARS):
        t_bar = bar * BAR
        ch = CHORDS[bar]
        root, alt, mid = VOICING[ch]
        bass = alt if (ch == prev_chord) else root
        prev_chord = ch
        # 左手：嘭（低音）—恰—恰
        jit = r.normal(0, 0.006)
        ev.append((t_bar + max(0, jit), BEAT * 0.92, m(bass), 0.46 + r.normal(0, 0.03), -0.25, seed)); seed += 1
        for b, v in ((1, 0.27), (2, 0.24)):
            jit = r.normal(0, 0.007)
            vv = v + r.normal(0, 0.03)
            for k, nm in enumerate(mid):
                # 和弦三个音不完全同时落下
                ev.append((t_bar + b * BEAT + jit + 0.004 * k * r.random(), BEAT * 0.55, m(nm),
                           vv, pan_for(m(nm)) - 0.1, seed)); seed += 1
        # 右手旋律
        pos = 0.0
        notes = MELODY[bar]
        for i, (nm, d) in enumerate(notes):
            jit = r.normal(0, 0.008)
            accent = 0.08 if pos == 0 else 0.0
            vel = 0.72 + accent + r.normal(0, 0.035)
            hold = d * BEAT * (0.97 if d >= 1 else 0.9)
            t0 = t_bar + pos * BEAT + jit
            if bar == SPOT_BAR and pos == 0:
                # 错音处：时间精确落在小节线上，便于游戏对字幕
                spot = (t_bar, hold, None, 0.84, pan_for(m(INTENDED)), seed)
            else:
                ev.append((max(0.0, t0), hold, m(nm), vel, pan_for(m(nm)), seed))
            seed += 1
            pos += d
        assert abs(pos - 3) < 1e-9 or pos == 0, (bar, pos)
    return ev, spot


def render_waltz(variants):
    """variants: {文件名: 音名}。返回 {文件名: 立体声}、增益统一。"""
    tun = Tuning(**WALTZ_TUNING)
    ev, spot = waltz_events()
    common = dict(circular=True, room_rt=0.95, room_wet=0.20, room_seed=11)
    base = render(ev, LOOP_LEN, tun, **common)
    outs = {}
    for name, note in variants.items():
        t0, hold, _, vel, pn, sd = spot
        one = render([(t0, hold, m(note), vel, pn, sd)], LOOP_LEN, tun, **common)
        outs[name] = base + one
    g = 10 ** (-3.0 / 20) / max(np.max(np.abs(v)) for v in outs.values())
    return {k: v * g for k, v in outs.items()}


# ================================================================ 结局曲

def render_ending():
    """约 45 秒：D# 小调、3/4、50 BPM，稀疏钢琴 + 柔和铺底。旋律化用华尔兹开头的动机，
    并在第 4 小节停在 V 和弦上的 G#4——华尔兹里那个"被弹错的音"，这一次弹对了。"""
    bpm = 50
    beat = 60.0 / bpm
    bar = 3 * beat
    total = 45.0
    tun = Tuning(seed=1914, key_spread=2.5, string_spread=(1.5, 3.5), max_strings=2)
    chords = ['D#m', 'B', 'F#', 'C#', 'D#m', 'G#m', 'B', 'C#sus', 'D#m', 'B', 'D#m']
    lh = {'D#m': ['D#2', 'A#2', 'F#3'], 'B': ['B1', 'F#2', 'D#3'], 'F#': ['F#2', 'C#3', 'A#3'],
          'C#': ['C#2', 'G#2', 'E#3'], 'G#m': ['G#1', 'D#2', 'B2'], 'C#sus': ['C#2', 'G#2', 'F#3']}
    mel = [[('A#4', 0, 2), ('F#4', 2, 1)],
           [('D#5', 0, 3)],
           [('C#5', 0, 1.5), ('A#4', 1.5, 1.5)],
           [('G#4', 0, 3)],
           [('A#4', 0, 1), ('D#5', 1, 1), ('F#5', 2, 1)],
           [('F#5', 0, 2), ('D#5', 2, 1)],
           [('D#5', 0, 1.5), ('C#5', 1.5, 1.5)],
           [('F#4', 0, 2), ('E#4', 2, 1)],
           [('D#4', 0, 1), ('F#4', 1, 1), ('A#4', 2, 1)],
           [('D#5', 0, 3)],
           [('A#4', 0, 3), ('D#5', 1.5, 1.5)]]
    r = rng(2718)
    ev = []
    sd = 50000
    for b, ch in enumerate(chords):
        t_bar = 1.0 + b * bar
        last = b == len(chords) - 1
        ped = (bar + 0.25) if not last else (total - t_bar)  # 踏板：一小节一换
        for k, nm in enumerate(lh[ch]):
            # 左手分解：根音在 1 拍，五度和三音轻轻跟上
            ev.append((t_bar + k * beat * 0.5 + r.normal(0, 0.01), ped - k * beat * 0.5, m(nm),
                       0.36 - 0.05 * k + r.normal(0, 0.02), pan_for(m(nm)), sd)); sd += 1
        for nm, p, d in mel[b]:
            hold = ped - p * beat if not last else total - t_bar - p * beat
            ev.append((t_bar + p * beat + r.normal(0, 0.015), hold, m(nm),
                       0.42 + r.normal(0, 0.03), pan_for(m(nm)), sd)); sd += 1
        if last:
            ev.append((t_bar + 2.2 * beat, total - t_bar - 2.2 * beat, m('A#5'), 0.22, 0.3, sd)); sd += 1
    piano = render(ev, total, tun, circular=False, tail=0.0, room_rt=2.6, room_wet=0.34,
                   room_seed=23, bright=0.8)
    # 铺底：每个和弦一组缓慢起落的失谐正弦/三角，低通后放远
    n = len(piano)
    t = tvec(n)
    pad = np.zeros((n, 2))
    pad_notes = {'D#m': ['D#3', 'A#3', 'F#4'], 'B': ['B2', 'F#3', 'D#4'], 'F#': ['F#3', 'C#4', 'A#3'],
                 'C#': ['C#3', 'G#3', 'E#4'], 'G#m': ['G#2', 'D#3', 'B3'], 'C#sus': ['C#3', 'G#3', 'F#4']}
    for b, ch in enumerate(chords):
        t0 = 1.0 + b * bar - 0.6
        t1 = t0 + bar + 1.2 if b < len(chords) - 1 else total
        env = np.clip((t - t0) / 1.8, 0, 1) * np.clip((t1 - t) / 1.8, 0, 1)
        env = np.sin(env * np.pi / 2) ** 2
        idx = env > 0
        for k, nm in enumerate(pad_notes[ch]):
            f = 440 * 2 ** ((m(nm) - 69) / 12)
            for c, det in enumerate((-4.0, 4.5)):
                ff = f * 2 ** (det / 1200)
                ph = 2 * np.pi * ff * t[idx] + 1.3 * k + c
                tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
                pad[idx, c] += env[idx] * tone * 0.05
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.11 * t)
    pad = lowpass(pad * lfo[:, None], 1100, 2)
    pad = conv(pad, reverb_ir(3.2, seed=29, stereo=True))[:n] * 0.35 + pad * 0.5
    mix = piano + pad * 0.55
    mix = fade(mix, fin=0.02, fout=9.0)
    return normalize_peak(mix, -3.0)
