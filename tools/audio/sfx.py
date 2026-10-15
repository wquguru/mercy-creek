"""Mercy Creek 的环境音与音效（全部程序合成）。

每个函数返回浮点数组（单声道 (n,) 或立体声 (n, 2)），电平在 build_audio.py 里统一定。
"""
import numpy as np

from dsp import (SR, secs, tvec, rng, noise, pink, brown, lowpass, highpass, bandpass, peaking,
                 conv, modal_ir, modal_hit, click, stick_slip, reverb_ir, add_reverb, fade, place,
                 place_circular, loop_crossfade, shaped_noise, smooth_random, pan, trim_silence,
                 normalize_peak, exp_decay, circular)
import piano

# 酒馆大厅的房间：木头、不大、有点空
SALOON_IR = reverb_ir(1.0, seed=3, stereo=True, predelay=0.007)
SALOON_IR_MONO = reverb_ir(1.0, seed=3, stereo=False, predelay=0.007)
SMALL_IR = reverb_ir(0.55, seed=4, stereo=False, predelay=0.004)


def _wrap_env(env_L, n):
    """周期包络（长度 L）延长到 n（> L）——循环用，保证尾巴和开头的包络一样。"""
    L = len(env_L)
    return env_L[np.arange(n) % L]


# ================================================================ 风

def wind_layer(n_total, gust, seed, lo=200.0, span=700.0, sigma=0.75, whistle=0.0, floor=0.15):
    """gust: 长度 n_total 的 0..1 阵风包络。STFT 域按阵风强度移动带通中心、改变响度。"""
    def gains(times, freqs):
        g = np.interp(times * SR, np.arange(len(gust)), gust)[:, None]
        fc = lo + span * g
        f = np.maximum(freqs[None, :], 1.0)
        shape = np.exp(-np.log(f / fc) ** 2 / (2 * sigma ** 2))
        lvl = floor + g ** 1.6
        out = shape * lvl
        if whistle > 0:
            fw = 2.6 * fc + 120
            out += whistle * (g ** 3) * np.exp(-np.log(f / fw) ** 2 / (2 * 0.035 ** 2))
        return out
    return shaped_noise(n_total, gains, seed)


def amb_wind_loop(L_sec=30.0, X_sec=3.0):
    L, X = secs(L_sec), secs(X_sec)
    n = L + X
    base = smooth_random(L, 0.35, seed=21, periodic=True)
    out = []
    for c in range(2):
        own = smooth_random(L, 0.6, seed=22 + c, periodic=True)
        g = np.clip(0.5 + 0.42 * base + 0.12 * own, 0, 1)
        g = _wrap_env(g, n)
        w = wind_layer(n, g, seed=30 + c, lo=180, span=650, sigma=0.8, whistle=0.06)
        rumble = lowpass(brown(n, 40 + c), 110, 2) * (0.25 + 0.75 * g)
        w = w / np.std(w) + 0.35 * rumble / np.std(rumble)
        out.append(loop_crossfade(w, L))
    x = np.stack(out, axis=1)
    return circular(lambda v: highpass(v, 25, 2), x)


# ================================================================ 木头吱呀

def wood_creak(dur, seed, f_lo=25, f_hi=90, modes=None):
    r = rng(seed)
    a, b = r.uniform(0.2, 0.8), r.uniform(0.2, 0.8)
    rate = lambda t: f_lo + (f_hi - f_lo) * (0.5 + 0.5 * np.sin(2 * np.pi * (a * t / dur + b)))
    amp = lambda t: np.sin(np.pi * min(t / dur, 1.0)) ** 0.7
    ex = stick_slip(dur, rate, seed, jitter=0.12, amp_fn=amp)
    modes = modes or [r.uniform(280, 360), r.uniform(520, 640), r.uniform(820, 980), r.uniform(1250, 1500)]
    ir = modal_ir(modes, [0.06, 0.05, 0.04, 0.03], [1.0, 0.7, 0.45, 0.25], 0.15, seed=seed)
    return conv(ex, ir)


def amb_saloon_loop(L_sec=60.0, X_sec=4.0):
    L, X = secs(L_sec), secs(X_sec)
    n = L + X
    layers = []
    gust = smooth_random(L, 0.2, seed=51, periodic=True)
    for c in range(2):
        # 屋里的底噪：极低的空气声 + 一点点中频（远处的街、房子本身）
        tone = lowpass(brown(n, 60 + c), 160, 2) * 1.0 + lowpass(pink(n, 62 + c), 1200, 2) * 0.10
        # 墙外的风：被墙闷掉，只剩低频起伏
        g = np.clip(0.45 + 0.45 * gust + 0.10 * smooth_random(L, 0.5, seed=53 + c, periodic=True), 0, 1)
        g = _wrap_env(g, n)
        w = wind_layer(n, g, seed=70 + c, lo=140, span=260, sigma=0.6, floor=0.25)
        w = lowpass(w, 700, 2)
        mix = tone / np.std(tone) * 0.55 + w / np.std(w) * 1.0
        layers.append(loop_crossfade(mix, L))
    bed = np.stack(layers, axis=1)
    # 偶尔的木头吱呀：避开接缝，放在循环内部；带房间混响，绕回式放置
    ev = np.zeros((L, 2))
    r = rng(80)
    for i, t0 in enumerate([5.2, 14.6, 23.9, 33.1, 41.7, 49.4, 55.0]):
        cr = wood_creak(r.uniform(0.35, 0.9), seed=81 + i)
        cr = lowpass(cr, 2500, 2)
        st = add_reverb(pan(cr, r.uniform(-0.7, 0.7)), SALOON_IR, wet=0.45)
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=r.uniform(0.25, 0.45))
    # 偶尔房子"咔"一声（木头热胀冷缩）
    for i, t0 in enumerate([9.8, 28.3, 45.2]):
        k = modal_hit([r.uniform(600, 900), r.uniform(1300, 1700)], [0.03, 0.02], [1, 0.5], 0.08, seed=90 + i)
        st = add_reverb(pan(k, r.uniform(-0.8, 0.8)), SALOON_IR, wet=0.5)
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=0.2)
    bed = bed / np.sqrt(np.mean(bed ** 2))
    return circular(lambda v: highpass(v, 22, 2), bed + ev * 3.0)


# ================================================================ 脚步

def footstep(i):
    r = rng(600 + i)
    n = secs(0.5)
    x = np.zeros(n)
    sc = r.uniform(0.88, 1.12)
    board = modal_ir([152 * sc, 236 * sc, 342 * sc, 488 * sc, 693 * sc, 960 * sc, 1400 * sc, 2100 * sc],
                     [0.07, 0.065, 0.06, 0.05, 0.045, 0.04, 0.03, 0.02],
                     [0.5, 0.6, 0.8, 0.8, 0.7, 0.5, 0.35, 0.2], 0.2, seed=610 + i)
    board *= 0.9 / np.abs(np.fft.rfft(board, 1 << 15)).max()  # 共振增益归一，免得板子"嗡"成一个音
    board[0] += 1.0
    # 鞋跟：硬皮跟砸在板上——宽带"咔"敲响木板，再加一个很短的低频"咚"（楼板下的空腔）
    heel = click(0.012, 150, 6000, seed=620 + i, t60=0.006)
    tt = tvec(secs(0.06))
    fth = 95 * sc * (1 + 0.6 * np.exp(-tt / 0.008))
    thump = np.sin(2 * np.pi * np.cumsum(fth) / SR) * np.exp(-tt / 0.016)
    hs = conv(heel / np.max(np.abs(heel)), board)
    hs /= np.max(np.abs(hs))
    hs[:len(thump)] += 0.35 * thump
    x = place(x, hs / np.max(np.abs(hs)), 0.005)
    # 前掌落下：更轻、更钝
    toe_t = r.uniform(0.07, 0.11)
    toe = click(0.014, 150, 3000, seed=630 + i, t60=0.008)
    ts = conv(toe, board)
    x = place(x, ts / np.max(np.abs(ts)), toe_t, gain=r.uniform(0.25, 0.4))
    # 沙粒摩擦
    grit = click(0.035, 2500, 7000, seed=640 + i, t60=0.03)
    x = place(x, grit / np.max(np.abs(grit)), 0.008, gain=0.08)
    # 有的板子会吱一下
    if i in (1, 4):
        cr = wood_creak(r.uniform(0.12, 0.2), seed=650 + i, f_lo=60, f_hi=140)
        x = place(x, cr / np.max(np.abs(cr)), toe_t + 0.02, gain=0.18)
    x = lowpass(x, 6500, 2)
    y = add_reverb(x, SMALL_IR, wet=0.10)
    return trim_silence(y[:secs(0.48)], thresh_db=-60)


# ================================================================ 落地钟

def clock_tick(pitch=1.0, seed=0):
    n = secs(0.25)
    x = np.zeros(n)
    # 擒纵叉撞齿：短促金属声
    met = modal_hit([2650 * pitch, 3920 * pitch, 5310 * pitch, 7150 * pitch],
                    [0.05, 0.035, 0.025, 0.018], [1.0, 0.7, 0.5, 0.3], 0.1, seed=700 + seed)
    tr = click(0.003, 2000, 9000, seed=710 + seed)
    hit = np.zeros(secs(0.1))
    hit += met * 0.6
    hit[:len(tr)] += tr * 0.5
    # 钟壳（木头）共鸣
    case = modal_ir([182 * pitch, 315 * pitch, 523 * pitch, 851 * pitch, 1240 * pitch],
                    [0.12, 0.10, 0.08, 0.06, 0.05], [1.0, 0.8, 0.6, 0.4, 0.25], 0.18, seed=720 + seed)
    body = conv(tr, case)
    x = place(x, hit, 0.004)
    x = place(x, body / np.max(np.abs(body)), 0.004, gain=0.55)
    # 落锁的第二声
    x = place(x, hit, 0.004 + 0.017, gain=0.3)
    y = add_reverb(x, SALOON_IR_MONO, wet=0.10)[:n]
    return fade(y, fout=0.02)


# ================================================================ 门

def hinge_creak(dur, rate_fn, amp_fn, seed):
    ex = stick_slip(dur, rate_fn, seed, jitter=0.03, amp_fn=amp_fn)
    # 共振峰放宽（t60 短）：让滑动的谐波列整体透出来，而不是只在几个固定频率上"啸"
    metal = modal_ir([640, 1190, 1760, 2610, 3420], [0.022, 0.02, 0.018, 0.015, 0.012],
                     [0.8, 1.0, 0.7, 0.5, 0.3], 0.12, seed=seed + 1)
    wood = modal_ir([205, 330, 470], [0.09, 0.07, 0.05], [0.6, 0.5, 0.3], 0.12, seed=seed + 2)
    return conv(ex, metal) + 0.6 * conv(ex, wood)


def latch(seed, pitch=1.0):
    m = modal_hit([1820 * pitch, 3110 * pitch, 4730 * pitch], [0.06, 0.04, 0.03], [1, 0.6, 0.4], 0.1, seed=seed)
    tr = click(0.004, 1500, 8000, seed=seed + 1)
    m[:len(tr)] += tr
    return m


def door_open():
    n = secs(1.6)
    x = np.zeros(n)
    x = place(x, latch(800), 0.01, gain=0.5)
    x = place(x, latch(805, 0.8), 0.06, gain=0.25)
    # 合页：先慢后快再慢，频率上扬又落下——"吱——呀——"
    def rate(t):
        u = t / 1.15
        return 60 + 330 * np.sin(np.pi * min(u, 1) ** 0.8) ** 1.5 + 30 * np.sin(2 * np.pi * 3.1 * t)
    def amp(t):
        u = t / 1.15
        return np.sin(np.pi * min(u, 1)) ** 0.6
    cr = hinge_creak(1.15, rate, amp, seed=810)
    x = place(x, cr / np.max(np.abs(cr)), 0.12, gain=0.6)
    # 门板扫过空气 + 门外漏进来的风
    whoosh = lowpass(noise(n, 820), 450, 2) * np.clip(np.sin(np.pi * (tvec(n) - 0.15) / 1.3), 0, None) ** 2
    x += whoosh / np.max(np.abs(whoosh)) * 0.12
    outside = bandpass(noise(n, 821), 300, 2500) * np.clip((tvec(n) - 0.35) / 1.0, 0, 1) ** 2
    x += outside / np.max(np.abs(outside)) * 0.05
    x = peaking(x, 220, 1.0, 3.0)
    y = add_reverb(x, SALOON_IR, wet=0.22)
    return fade(y[:secs(1.6)], fout=0.25)


def door_close():
    n = secs(0.95)
    x = np.zeros(n)
    rate = lambda t: 260 - 170 * (t / 0.24)
    amp = lambda t: np.sin(np.pi * min(t / 0.24, 1)) ** 0.7
    cr = hinge_creak(0.24, rate, amp, seed=830)
    x = place(x, cr / np.max(np.abs(cr)), 0.0, gain=0.35)
    t0 = 0.27
    # 撞门：厚木门板的低频"砰" + 门框共振 + 门闩落下
    tt = tvec(secs(0.4))
    f = 68 * (1 + 0.6 * np.exp(-tt / 0.012))
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.09)
    slab = modal_ir([108, 167, 251, 388, 541, 760], [0.30, 0.25, 0.2, 0.15, 0.1, 0.07],
                    [1.0, 0.9, 0.7, 0.5, 0.35, 0.2], 0.4, seed=840)
    hit = click(0.012, 150, 5000, seed=841, t60=0.01)
    body = conv(hit, slab)
    x = place(x, boom, t0, gain=0.9)
    x = place(x, body / np.max(np.abs(body)), t0, gain=0.8)
    x = place(x, hit / np.max(np.abs(hit)), t0, gain=0.4)
    x = place(x, latch(850, 0.9), t0 + 0.035, gain=0.35)
    x = place(x, latch(855, 1.15), t0 + 0.09, gain=0.12)  # 门闩轻轻颤一下
    y = add_reverb(x, SALOON_IR, wet=0.28)
    return fade(y[:n], fout=0.2)


# ================================================================ 吧台

def glass_modes(f, seed, t60=(0.9, 0.5, 0.3, 0.2)):
    ratios = [1.0, 2.71, 5.13, 8.2]
    fr, t6, am = [], [], []
    r = rng(seed)
    for k, (rt, d) in enumerate(zip(ratios, t60)):
        for sp in (0.0, r.uniform(0.0015, 0.004)):  # 成对的近频：玻璃不完全圆，会拍
            fr.append(f * rt * (1 + sp))
            t6.append(d)
            am.append((1.0 / (k + 1) ** 1.2) * (1.0 if sp == 0 else 0.6))
    return fr, t6, am


def glass_clink():
    n = secs(1.3)
    x = np.zeros(n)
    for (f, g, t0, sd) in [(2480, 1.0, 0.01, 900), (2960, 0.8, 0.01, 901), (2480, 0.18, 0.062, 902)]:
        fr, t6, am = glass_modes(f, sd)
        rg = modal_hit(fr, t6, am, 1.2, seed=sd)
        tr = click(0.0015, 3000, 14000, seed=sd + 10)
        rg[:len(tr)] += tr * 0.8
        x = place(x, rg * g, t0)
    y = add_reverb(x, SALOON_IR, wet=0.15)
    return fade(highpass(y[:n], 300, 2), fout=0.3)


def glass_pour():
    dur = 2.1
    n = secs(dur)
    t = tvec(n)
    r = rng(910)
    # 液柱的连续声：带通中心随杯子装满而上升（空腔变短）
    fill = np.clip((t - 0.15) / 1.6, 0, 1)
    env = np.clip(t / 0.12, 0, 1) * np.clip((1.78 - t) / 0.15, 0, 1)

    def gains(times, freqs):
        u = np.clip((times - 0.15) / 1.6, 0, 1)[:, None]
        e = np.interp(times, t, env)[:, None]
        fc = 650 + 1100 * u
        f = np.maximum(freqs[None, :], 1)
        res = np.exp(-np.log(f / fc) ** 2 / (2 * 0.18 ** 2))
        broad = np.exp(-np.log(f / 2500) ** 2 / (2 * 0.9 ** 2)) * 0.35
        return (res + broad) * e
    stream = shaped_noise(n, gains, seed=911)
    stream /= np.max(np.abs(stream))
    # 气泡：每个是一个上扬的小正弦（Minnaert 共振），密度随流量
    bub = np.zeros(n)
    tb = 0.1
    while tb < 1.75:
        tb += r.exponential(1 / 140.0)
        f0 = np.exp(r.normal(np.log(1500 + 1200 * np.clip((tb - 0.15) / 1.6, 0, 1)), 0.35))
        d = r.uniform(0.008, 0.03)
        k = secs(d)
        tk = tvec(k)
        ph = 2 * np.pi * np.cumsum(f0 * (1 + 0.6 * tk / d)) / SR
        b = np.sin(ph) * np.exp(-tk / (d / 3)) * r.uniform(0.2, 1.0)
        i = secs(tb)
        if i + k < n:
            bub[i:i + k] += b * np.interp(tb, t, env)
    # 开头酒瓶口"咕"两声，结尾一滴
    for (tg, fg, a) in [(0.05, 380, 0.8), (0.17, 450, 0.6), (1.93, 1250, 0.45)]:
        k = secs(0.06)
        tk = tvec(k)
        g = np.sin(2 * np.pi * np.cumsum(fg * (1 + 1.2 * tk / 0.06)) / SR) * np.exp(-tk / 0.018)
        bub = place(bub, g * a, tg)
    x = stream * 0.7 + bub * 0.5
    x = highpass(x, 200, 2)
    y = add_reverb(x, SALOON_IR_MONO, wet=0.12)[:n]
    return fade(y, fin=0.01, fout=0.1)


def bottle_set():
    n = secs(0.7)
    x = np.zeros(n)
    wood = modal_ir([178, 288, 452, 702, 1010], [0.12, 0.1, 0.08, 0.06, 0.04], [1, 0.8, 0.6, 0.4, 0.2], 0.2, seed=920)
    hit = click(0.006, 200, 6000, seed=921, t60=0.004)
    knock = conv(hit, wood)
    fr, t6, am = glass_modes(1150, 922, t60=(0.3, 0.18, 0.12, 0.08))
    ring = modal_hit(fr, t6, am, 0.4, seed=922)
    for (t0, g) in [(0.01, 1.0), (0.045, 0.35)]:  # 瓶底先一侧着地，再放平
        x = place(x, knock / np.max(np.abs(knock)) * g, t0)
        x = place(x, ring * 0.25 * g, t0)
        x = place(x, hit / np.max(np.abs(hit)) * 0.3 * g, t0)
    # 瓶里的酒晃一下
    k = secs(0.45)
    tk = tvec(k)
    slosh = bandpass(noise(k, 923), 250, 1100) * np.clip(tk / 0.05, 0, 1) * np.exp(-tk / 0.12) * \
        (0.6 + 0.4 * np.sin(2 * np.pi * 7 * tk))
    x = place(x, slosh / np.max(np.abs(slosh)) * 0.12, 0.04)
    y = add_reverb(x, SALOON_IR_MONO, wet=0.15)[:n]
    return fade(y, fout=0.15)


# ================================================================ UI

def bell(f, dur, seed, detune_cents=0.0):
    # 带小三度（1.19）的钟：听起来偏忧伤
    ratios = [0.5, 1.0, 1.19, 1.5, 2.0, 2.52, 2.98, 4.07]
    t60 = [3.0, 2.4, 1.9, 1.5, 1.2, 0.8, 0.6, 0.4]
    amps = [0.35, 1.0, 0.5, 0.35, 0.4, 0.2, 0.15, 0.08]
    fr = [f * rt * 2 ** (detune_cents / 1200) for rt in ratios]
    return modal_hit(fr, t60, amps, dur, seed=seed, attack=0.002)


def ui_remember():
    dur = 2.4
    n = secs(dur)
    hit_t = 0.62
    f = 622.25  # D#5
    b = bell(f, 1.9, 950) + 0.7 * bell(f, 1.9, 951, detune_cents=9)
    b = lowpass(b, 6000, 2)
    ir = reverb_ir(2.2, seed=952, stereo=True, predelay=0.02)
    wet = conv(b, ir[:, 0])
    # 倒放混响做"吸气"：从无到有涌向敲击点
    rev = wet[:secs(1.2)][::-1]
    sw = rev[-secs(hit_t):] * np.linspace(0, 1, secs(hit_t)) ** 2
    x = np.zeros((n, 2))
    sws = pan(sw / np.max(np.abs(sw)), 0.0)
    sws[:, 1] = np.roll(sws[:, 1], 40)
    x = place(x, sws * 0.5, 0.0)
    st = add_reverb(pan(b, 0.0), ir, wet=0.6)
    x = place(x, st / np.max(np.abs(st)), hit_t)
    # 一层很轻的高频气声，"抓住了什么"
    air = bandpass(noise(n, 953), 3000, 9000) * np.exp(-((tvec(n) - hit_t) / 0.35) ** 2)
    x += np.stack([air, np.roll(air, 77)], axis=1) * 0.04
    return fade(x, fin=0.01, fout=0.6)


def ui_denied():
    n = secs(0.6)
    x = np.zeros(n)
    tt = tvec(secs(0.45))
    f = 92 * (1 + 0.35 * np.exp(-tt / 0.02))
    th = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.10)
    bonk = modal_hit([160, 238, 355], [0.18, 0.12, 0.08], [1.0, 0.6, 0.3], 0.3, seed=960)
    x = place(x, th, 0.005, gain=0.9)
    x = place(x, bonk / np.max(np.abs(bonk)), 0.005, gain=0.6)
    soft = lowpass(click(0.03, 100, 2000, seed=961, t60=0.02), 900)
    x = place(x, soft / np.max(np.abs(soft)), 0.005, gain=0.35)
    # 第二下更轻、低半音：像被轻轻推回去
    x = place(x, 0.45 * th * 0.94, 0.16)
    x = lowpass(x, 1400, 2)
    y = add_reverb(x, SMALL_IR, wet=0.12)[:n]
    return fade(y, fout=0.15)


def ui_click():
    n = secs(0.08)
    m = modal_hit([1870, 3240], [0.018, 0.012], [1, 0.4], 0.06, seed=970)
    tr = click(0.002, 2000, 8000, seed=971)
    m[:len(tr)] += tr * 0.6
    x = np.zeros(n)
    x = place(x, m, 0.002)
    return fade(lowpass(x, 7000), fout=0.02)


# ================================================================ 重置

def reset_sting():
    total = 3.6
    n = secs(total)
    t = tvec(n)
    # 1) 华尔兹里的主和弦（F# 大调）加一个 G 的不协和，用同一台走音钢琴弹出来
    tun = piano.Tuning(**piano.WALTZ_TUNING)
    chord = np.zeros(secs(4.0))
    for k, nm in enumerate(['F#2', 'C#3', 'F#3', 'A#3', 'C#4', 'F#4', 'G4']):
        v = 0.75 if nm != 'G4' else 0.45
        nt = piano.piano_note(piano.m(nm), v, 3.5, tun, 990 + k)
        chord = place(chord, nt, 0.003 * k)
    chord = conv(chord, piano.body_ir())[:secs(4.0)]
    # 2) 磁带停转：播放速率从 1 滑到 0，读位置 = 速率积分
    rate = np.ones(n)
    t_s, t_e = 0.35, 2.05
    u = np.clip((t - t_s) / (t_e - t_s), 0, 1)
    rate = (1 - u) ** 1.7
    rate *= 1 + 0.012 * np.sin(2 * np.pi * 5.5 * t) * (t < t_s + 0.4)  # 一点点抖
    pos = np.cumsum(rate) - rate[0]
    stop = np.interp(pos, np.arange(len(chord)), chord)
    stop *= np.sqrt(rate)  # 磁头输出随速度降低
    stop = lowpass(stop, 9000)
    # 3) 上升的噪声涌起（滤波中心从低到高），在轰的那一刻硬切
    boom_t = 2.25
    def gains(times, freqs):
        uu = np.clip((times - 0.4) / (boom_t - 0.4), 0, 1)[:, None]
        fc = 180 * (40 ** uu)
        f = np.maximum(freqs[None, :], 1)
        sh = np.exp(-np.log(f / fc) ** 2 / (2 * 0.5 ** 2))
        return sh * (uu ** 2.2) * (times[:, None] < boom_t)
    swell = shaped_noise(n, gains, seed=995)
    swell = swell / np.max(np.abs(swell))
    cut = secs(boom_t)
    swell[cut - secs(0.004):cut] *= np.linspace(1, 0, secs(0.004))
    swell[cut:] = 0
    # 一条更低的、走音的上行正弦，加深不安
    sw_f = 90 * (8 ** np.clip((t - 0.6) / (boom_t - 0.6), 0, 1))
    sine = np.sin(2 * np.pi * np.cumsum(sw_f) / SR) * np.clip((t - 0.6) / 1.6, 0, 1) ** 2 * (t < boom_t)
    sine[cut - secs(0.004):cut] *= np.linspace(1, 0, secs(0.004))
    # 4) 低沉的轰
    k = secs(1.4)
    tk = tvec(k)
    fb = 34 + 40 * np.exp(-tk / 0.06)
    boom = np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(fb) / SR) * np.exp(-tk / 0.35))
    bn = lowpass(noise(k, 996), 260, 2) * np.exp(-tk / 0.12)
    boom = boom + 0.4 * bn / np.max(np.abs(bn))
    x = np.zeros(n)
    x += stop / np.max(np.abs(stop)) * 0.75
    x += swell * 0.42 + sine * 0.10
    x = place(x, boom / np.max(np.abs(boom)), boom_t, gain=1.0)
    st = add_reverb(pan(x, 0.0), reverb_ir(2.0, seed=997, stereo=True), wet=0.3)[:n]
    # 轰之后迅速归于寂静
    tail = np.clip((3.35 - t) / 1.0, 0, 1) ** 2
    tail[t < boom_t + 0.1] = 1.0
    st *= tail[:, None]
    return st


# ================================================================ 打字机

def typewriter_key(i):
    r = rng(1000 + i)
    n = secs(0.22)
    x = np.zeros(n)
    sc = r.uniform(0.94, 1.06)
    frame = modal_ir([142, 263, 418, 702], [0.07, 0.06, 0.05, 0.04], [1, 0.8, 0.6, 0.4], 0.12, seed=1010 + i)
    # 手指按下键帽
    press = click(0.004, 800, 5000, seed=1020 + i)
    x = place(x, press / np.max(np.abs(press)), 0.002, gain=0.2)
    # 字锤砸在胶辊上：主声
    tbar = modal_hit([1650 * sc, 2480 * sc, 3910 * sc, 5620 * sc], [0.04, 0.03, 0.025, 0.02],
                     [1.0, 0.8, 0.5, 0.3], 0.08, seed=1030 + i)
    tr = click(0.003, 1200, 10000, seed=1040 + i)
    tbar[:len(tr)] += tr * 1.4
    thunk = conv(tr, frame)
    hit_t = 0.022 + r.uniform(0, 0.008)
    x = place(x, tbar, hit_t, gain=0.7)
    x = place(x, thunk / np.max(np.abs(thunk)), hit_t, gain=0.6)
    # 擒纵：字车走一格
    esc = modal_hit([3180 * sc, 4720 * sc], [0.02, 0.015], [1, 0.5], 0.04, seed=1050 + i)
    x = place(x, esc, hit_t + r.uniform(0.03, 0.045), gain=0.25)
    # 键回弹
    ret = click(0.006, 600, 4000, seed=1060 + i)
    x = place(x, ret / np.max(np.abs(ret)), hit_t + r.uniform(0.07, 0.1), gain=0.12)
    y = add_reverb(x, SMALL_IR, wet=0.12)[:n]
    return fade(highpass(y, 90), fout=0.03)


def typewriter_bell():
    n = secs(1.4)
    ratios = [1.0, 2.76, 5.40, 8.93]
    fr, t6, am = [], [], []
    f = 2350
    for k, (rt, d) in enumerate(zip(ratios, [1.2, 0.6, 0.35, 0.2])):
        for sp in (0.0, 0.0035):
            fr.append(f * rt * (1 + sp))
            t6.append(d)
            am.append(1.0 / (k + 1) ** 1.3 * (1 if sp == 0 else 0.7))
    b = modal_hit(fr, t6, am, 1.3, seed=1100)
    tr = click(0.002, 3000, 12000, seed=1101)
    b[:len(tr)] += tr * 0.5
    x = np.zeros(n)
    x = place(x, b, 0.003)
    y = add_reverb(x, SALOON_IR_MONO, wet=0.15)[:n]
    return fade(y, fout=0.25)


def typewriter_return():
    n = secs(1.0)
    x = np.zeros(n)
    r = rng(1200)
    # 推回车杆：换行棘轮"咔嗒"
    for j, t0 in enumerate([0.01, 0.05]):
        k = modal_hit([1380, 2240, 3560], [0.03, 0.025, 0.02], [1, 0.6, 0.4], 0.06, seed=1201 + j)
        x = place(x, k, t0, gain=0.5 if j == 0 else 0.35)
    # 字车滑过：摩擦 + 齿条连串细响
    t1, t2 = 0.09, 0.62
    k = secs(t2 - t1)
    tk = tvec(k)
    env = np.sin(np.pi * tk / (t2 - t1)) ** 0.5
    slide = bandpass(noise(k, 1210), 900, 4500) * env
    x = place(x, slide / np.max(np.abs(slide)) * 0.12, t1)
    tt = t1
    while tt < t2:
        u = (tt - t1) / (t2 - t1)
        tt += 1.0 / (35 + 45 * np.sin(np.pi * u))
        tick = modal_hit([r.uniform(3000, 3600), r.uniform(4800, 5400)], [0.012, 0.01], [1, 0.4], 0.02,
                         seed=int(tt * 10000))
        x = place(x, tick, tt, gain=0.12 * (0.5 + 0.5 * r.random()))
    # 撞到左端止挡：一声结实的"哐"
    frame = modal_ir([118, 205, 330, 520], [0.12, 0.1, 0.08, 0.06], [1, 0.8, 0.6, 0.4], 0.25, seed=1220)
    hit = click(0.008, 150, 7000, seed=1221, t60=0.006)
    body = conv(hit, frame)
    clank = modal_hit([1540, 2380, 3710], [0.06, 0.045, 0.03], [1, 0.6, 0.4], 0.12, seed=1222)
    x = place(x, body / np.max(np.abs(body)), t2, gain=0.9)
    x = place(x, clank, t2, gain=0.45)
    y = add_reverb(x, SMALL_IR, wet=0.14)[:n]
    return fade(highpass(y, 70), fout=0.15)


# ================================================================ 虚空

def void_hum_loop(L_sec=20.0, X_sec=3.0):
    L, X = secs(L_sec), secs(X_sec)
    t = tvec(L)
    # 所有正弦和调制的频率都是 1/20 Hz 的整数倍：在 20 秒里正好走完整数个周期，天然无缝
    hum = np.zeros(L)
    for f, a, mf, ph in [(46.25, 1.0, 0.05, 0.0), (46.60, 0.8, 0.10, 1.1), (92.50, 0.35, 0.15, 2.0),
                         (69.40, 0.25, 0.05, 0.7), (138.75, 0.10, 0.20, 2.9), (185.00, 0.05, 0.10, 0.3)]:
        am = 0.75 + 0.25 * np.sin(2 * np.pi * mf * t + ph)
        hum += a * am * np.sin(2 * np.pi * f * t + ph * 3)
    hum /= np.std(hum)
    # 空气：低通的粉红噪声 + 极淡的高频"嘶"，用交叉淡化接缝
    n = L + X
    air = lowpass(pink(n, 1300), 380, 2)
    air = air / np.std(air)
    hiss = bandpass(noise(n, 1301), 2500, 6000)
    hiss = hiss / np.std(hiss)
    slow = 0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * tvec(n) + 0.4)  # 周期 20s，延长后仍连续
    ns = loop_crossfade(air * slow + 0.04 * hiss, L)
    return circular(lambda v: highpass(v, 25, 2), hum * 0.8 + ns * 0.5)
