"""Mercy Creek 主街的音效（第 2 稿起世界扩展到街道）：马、驿站马车、电报机、教堂钟、街道环境、
户外脚步、画布撕裂、墓地栅栏门。全部程序合成，固定种子。说明见 docs/audio_town.md。

每个函数返回浮点数组（单声道 (n,) 或立体声 (n, 2)），电平在 build_audio.py 里统一定。
3D 声源（马、马车、电报机、钟、门、画布、脚步）一律单声道；只有街道环境和"远处三声钟"是立体声。
"""
import numpy as np

from dsp import (SR, secs, tvec, rng, noise, pink, brown, lowpass, highpass, bandpass, peaking,
                 conv, modal_ir, modal_hit, click, stick_slip, reverb_ir, add_reverb, fade, place,
                 place_circular, loop_crossfade, fold_tail, smooth_random, pan, trim_silence,
                 exp_decay, circular)
from sfx import wind_layer, wood_creak, _wrap_env

# 户外：没有房间混响，只有对街门脸的几次稀疏回声 + 很短很暗的尾巴
STREET_IR = reverb_ir(0.7, seed=1401, predelay=0.012, bright=4500, dark=1100,
                      early=[(0.019, 0.35), (0.034, 0.22), (0.052, 0.16), (0.083, 0.10), (0.121, 0.06)])
STREET_IR_ST = reverb_ir(0.8, seed=1402, predelay=0.012, bright=4500, dark=1100, stereo=True,
                         early=[(0.021, 0.3), (0.036, 0.2), (0.058, 0.14), (0.09, 0.09)])
# 电报局：小木屋
OFFICE_IR = reverb_ir(0.45, seed=1403, predelay=0.003)
# 钟声在空旷处的长尾巴（远山、整条街的回声），很暗
FAR_IR_ST = reverb_ir(3.2, seed=1404, predelay=0.04, bright=2500, dark=700, stereo=True,
                      early=[(0.09, 0.3), (0.17, 0.22), (0.31, 0.18), (0.46, 0.12), (0.62, 0.08)])
BELL_IR = reverb_ir(2.4, seed=1405, predelay=0.02, bright=3500, dark=900,
                    early=[(0.035, 0.3), (0.07, 0.2), (0.13, 0.15), (0.21, 0.1)])


def _norm(x):
    p = np.max(np.abs(x))
    return x if p == 0 else x / p


def _reverb_loop(dry, ir, wet):
    """循环用：混响尾巴折回开头（dry 本身是长度 L 的周期信号）。"""
    return dry + wet * fold_tail(conv(dry, ir), len(dry))


# ================================================================ 颗粒（砂石、纤维）

_GRAIN_K = None


def grain_train(n, rate, seed, sigma=0.9):
    """泊松颗粒流：rate 为每秒颗粒数（标量或长度 n 的数组），颗粒幅度对数正态、正负随机。
    每粒是 ~0.5 ms 的小衰减噪声，再由调用者带通——砂石、碎石被压碎的"沙沙/咔嚓"。"""
    global _GRAIN_K
    r = rng(seed)
    p = np.broadcast_to(np.asarray(rate, dtype=float), (n,)) / SR
    hit = r.random(n) < p
    imp = np.zeros(n)
    k = int(hit.sum())
    # 对数正态的长尾截掉：偶发的超大颗粒会变成一下孤立的爆音
    imp[hit] = np.minimum(r.lognormal(0, sigma, k), np.exp(2.2 * sigma)) * np.where(r.random(k) < 0.5, -1, 1)
    if _GRAIN_K is None:
        _GRAIN_K = noise(28, 7) * np.exp(-np.arange(28) / 6.0)
    return np.convolve(imp, _GRAIN_K)[:n]


def gravel_burst(dur, seed, rate0=4000, tau=0.02, lo=1500, hi=7000, sigma=0.9):
    n = secs(dur)
    t = tvec(n)
    g = grain_train(n, rate0 * np.exp(-t / tau), seed, sigma)
    return bandpass(g, lo, hi)


# ================================================================ 马具

def jingle(seed, count=3, spread=0.05, dur=0.3):
    """挽具链环、扣环、马衔铁环碰一下：几个短促、互不成谐的小金属声。"""
    r = rng(seed)
    x = np.zeros(secs(dur))
    for j in range(count):
        f = r.uniform(2300, 5600)
        fr = [f, f * r.uniform(2.3, 2.6), f * r.uniform(3.7, 4.2), f * r.uniform(0.55, 0.62)]
        t6 = [r.uniform(0.05, 0.14), 0.05, 0.03, 0.06]
        ping = modal_hit(fr, t6, [1.0, 0.5, 0.25, 0.3], 0.2, seed=seed * 7 + j)
        tr = click(0.0015, 2500, 10000, seed=seed * 7 + j + 3)
        ping[:len(tr)] += tr * 0.6
        place(x, ping, r.uniform(0, spread), gain=r.uniform(0.35, 1.0))
    return highpass(x, 1200, 2)


def leather_creak(dur, seed, f_lo=30, f_hi=75, wood=0.0):
    """皮带受力"咯吱"：慢速粘-滑激励 + 阻尼很大的皮革共振（比木头更闷）。"""
    r = rng(seed)
    a = r.uniform(0.2, 0.8)
    rate = lambda t: f_lo + (f_hi - f_lo) * np.sin(np.pi * min(t / dur, 1) * (0.8 + 0.4 * a)) ** 2
    amp = lambda t: np.sin(np.pi * min(t / dur, 1.0)) ** 0.8
    ex = stick_slip(dur, rate, seed, jitter=0.2, amp_fn=amp)
    modes = [r.uniform(170, 220), r.uniform(320, 380), r.uniform(560, 660), r.uniform(900, 1100)]
    ir = modal_ir(modes, [0.025, 0.02, 0.016, 0.012], [1.0, 0.8, 0.5, 0.3], 0.08, seed=seed + 1)
    y = conv(ex, ir)
    if wood > 0:
        wc = _norm(wood_creak(dur, seed + 2, f_lo=f_lo, f_hi=f_hi + 30))
        y = _norm(y)
        m = min(len(y), len(wc))
        y = y[:m] + wood * wc[:m]
    return lowpass(y, 3500, 2)


# ================================================================ 马蹄

def hoof(seed, weight=1.0, sc=1.0, crunch=1.0, clink_p=0.12):
    """一只钉了铁掌的蹄子落在压实的土路上：
    低频"噗"（土面受压）+ 蹄壳的"嗒"（几个阻尼很大的中频模态）+ 压碎的砂砾 + 偶尔铁掌磕到石子。"""
    r = rng(seed)
    n = secs(0.3)
    x = np.zeros(n)
    tt = tvec(secs(0.14))
    f = 105 * sc * (1 + 0.8 * np.exp(-tt / 0.006))
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (0.02 * np.sqrt(weight)))
    ex = noise(secs(0.03), seed) * exp_decay(secs(0.03), 0.014)
    ex[:24] *= np.linspace(0, 1, 24)
    ex = lowpass(ex, 3500, 2)
    clop_ir = modal_ir([sc * r.uniform(320, 380), sc * r.uniform(540, 640), sc * r.uniform(880, 1030),
                        sc * r.uniform(1400, 1700), sc * r.uniform(2300, 2700)],
                       [0.03, 0.026, 0.02, 0.014, 0.01], [1.0, 0.8, 0.5, 0.3, 0.15], 0.08, seed=seed + 1)
    clop = _norm(conv(ex, clop_ir))
    puff = lowpass(noise(secs(0.06), seed + 2) * exp_decay(secs(0.06), 0.035), 700, 2)
    grit = gravel_burst(0.07, seed + 3, rate0=3500, tau=0.018)
    place(x, thump, 0.002, gain=0.6 * weight)
    place(x, clop, 0.002, gain=0.85)
    place(x, _norm(puff), 0.002, gain=0.3)
    place(x, _norm(grit), 0.003, gain=0.16 * crunch)
    if r.random() < clink_p:
        m = modal_hit([r.uniform(2600, 3000), r.uniform(4200, 4700), r.uniform(6000, 6800)],
                      [0.035, 0.025, 0.018], [1, 0.5, 0.3], 0.08, seed=seed + 4)
        place(x, m, 0.003, gain=0.09)
    return lowpass(x, 6000, 2)


def hooves_walk_loop(L_sec=8.0):
    """两匹拉车的马慢步走：四拍步法（左后-左前-右后-右前，间隔各 1/4 步），步周期 8/7 s
    ≈ 每匹 3.5 次落蹄/秒；两匹马相位不同且缓慢漂移，加上随机 ±12 ms 抖动，避免机械感。"""
    L = secs(L_sec)
    buf = np.zeros(L)
    r = rng(1500)
    T = L_sec / 7
    seq = [(0.0, False), (0.25, True), (0.5, False), (0.75, True)]  # (步内相位, 是否前蹄)
    sid = 1510
    for h, (sc, ph0, hg) in enumerate([(0.95, 0.0, 1.0), (1.08, 0.37, 0.82)]):
        for k in range(7):
            for j, (fr, fore) in enumerate(seq):
                u = (k + fr) / 7  # 循环内位置 0..1，漂移用整周期正弦保证无缝
                drift = 0.05 * np.sin(2 * np.pi * u + 1.3 * h) if h else 0.0
                t = ((k + fr + ph0 + drift) * T + r.normal(0, 0.012)) % L_sec
                g = hg * (1.0 if fore else 0.7) * r.uniform(0.8, 1.1)
                sid += 1
                place_circular(buf, hoof(sid, weight=1.15 if fore else 0.9, sc=sc * r.uniform(0.97, 1.03),
                                         crunch=r.uniform(0.6, 1.3)), t, gain=g)
                if not fore:
                    # 后蹄落地前轻轻拖一下土
                    sc_n = secs(0.05)
                    drag = bandpass(noise(sc_n, sid + 900), 500, 3000) * np.sin(np.pi * tvec(sc_n) / 0.05)
                    place_circular(buf, _norm(drag), t - 0.045, gain=0.035 * hg)
                else:
                    if r.random() < 0.65:  # 前蹄着地，身体一颠，挽链 / 扣环碰响
                        place_circular(buf, _norm(jingle(sid + 2000, count=r.integers(2, 5), spread=0.06)),
                                       t + r.uniform(0.015, 0.04), gain=hg * r.uniform(0.05, 0.1))
                    if j == 1 and r.random() < 0.6:  # 每步一次轭具 / 颈圈皮带受力
                        cr = leather_creak(r.uniform(0.14, 0.24), sid + 3000)
                        place_circular(buf, _norm(cr), t + 0.03, gain=hg * r.uniform(0.03, 0.06))
    y = _reverb_loop(buf, STREET_IR, 0.12)
    return circular(lambda v: highpass(v, 35, 2), y)


# ================================================================ 马车

COACH_BODY = None


def _coach_body():
    global COACH_BODY
    if COACH_BODY is None:
        COACH_BODY = modal_ir([66, 101, 148, 219, 305, 452, 640], [0.25, 0.2, 0.16, 0.12, 0.09, 0.06, 0.04],
                              [1.0, 0.9, 0.8, 0.6, 0.45, 0.3, 0.2], 0.35, seed=1601)
        COACH_BODY = COACH_BODY / np.abs(np.fft.rfft(COACH_BODY, 1 << 15)).max()
    return COACH_BODY


def wheel_bump(seed, size=1.0):
    """木轮铁箍压过轮辋接缝 / 一颗石子：短促的低频"咚" + 碎石声；车厢共振由调用方加。"""
    r = rng(seed)
    n = secs(0.12)
    tt = tvec(n)
    f = r.uniform(70, 95) * (1 + 0.5 * np.exp(-tt / 0.01))
    th = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / (0.018 + 0.012 * size))
    gr = gravel_burst(0.12, seed + 1, rate0=2500 * size, tau=0.025, lo=700, hi=5000)
    return th * size + 0.25 * _norm(gr) * size ** 0.5


def rattle(seed, count=3, spread=0.07):
    """车门 / 窗框 / 行李架松动的几下"咔嗒"。"""
    r = rng(seed)
    x = np.zeros(secs(spread + 0.1))
    for j in range(count):
        m = modal_hit([r.uniform(420, 560), r.uniform(900, 1200), r.uniform(1800, 2300)],
                      [0.03, 0.02, 0.015], [1, 0.6, 0.3], 0.06, seed=seed * 5 + j)
        tr = click(0.003, 400, 5000, seed=seed * 5 + j + 2, t60=0.002)
        m[:len(tr)] += tr * 0.5
        place(x, m, r.uniform(0, spread), gain=r.uniform(0.4, 1.0))
    return x


def _coach_layers(n, v, rough, seed, circ):
    """马车行驶的各层。v: 长度 n 的速度 0..1（1 = 慢步速度），rough: 路面粗糙度 -1..1。
    circ=True 时 n 就是循环长度，所有滤波都按循环处理。"""
    filt = (lambda fn, x: circular(fn, x)) if circ else (lambda fn, x: fn(x))
    r = rng(seed)
    # 1) 车轮滚动的低频隆隆：棕噪声 × 速度 × 路面
    mod = v ** 1.2 * (0.65 + 0.35 * rough)
    # 2) 铁箍碾碎石：细颗粒密集、粗颗粒稀疏
    fine = filt(lambda s: bandpass(s, 2000, 7000), grain_train(n, 1100 * v * (0.7 + 0.3 * rough), seed + 1, 0.8))
    coarse = filt(lambda s: bandpass(s, 450, 2200), grain_train(n, 140 * v * (0.6 + 0.4 * rough), seed + 2, 1.1))
    # 3) 轮辋接缝 / 石子 / 轮毂松动 → 激励车厢
    bumps = np.zeros(n)
    ev = np.zeros(n)
    dur = n / SR
    # 轮子转角 = 速度积分；前轮 0.5 转/s（6 段轮辋），后轮 0.375 转/s（7 段），左右各一
    pos = np.cumsum(v) / SR
    for w, (rev, segs, off) in enumerate([(0.5, 6, 0.0), (0.5, 6, 0.41), (0.375, 7, 0.17), (0.375, 7, 0.63)]):
        ang = pos * rev * segs + off
        idx = np.nonzero(np.diff(np.floor(ang)) > 0)[0]
        for i in idx:
            t = i / SR + r.normal(0, 0.004)
            g = r.uniform(0.15, 0.45) * (0.7 if w < 2 else 1.0) * v[i]
            (place_circular if circ else place)(bumps, wheel_bump(seed * 3 + w * 100 + int(i % 997), r.uniform(0.6, 1.0)), t % dur if circ else t, gain=g)
        # 后轮每转一圈轮毂"咯噔"一下（轴有旷量）
        if w >= 2:
            idx = np.nonzero(np.diff(np.floor(pos * rev + off)) > 0)[0]
            for i in idx:
                k = modal_hit([r.uniform(380, 450), r.uniform(760, 840), r.uniform(1250, 1400), r.uniform(2050, 2250)],
                              [0.05, 0.035, 0.025, 0.02], [1, 0.6, 0.4, 0.25], 0.1, seed=seed + 50 + w * 10 + int(i % 991))
                (place_circular if circ else place)(ev, k, i / SR, gain=0.08 * v[i])
    # 几颗大一点的石头：更重的颠簸 + 车身零件松动的咔嗒
    stones = [0.9, 2.6, 4.15, 5.7, 7.2] if circ else list(np.arange(0.5, dur, 1.6))
    for j, t in enumerate(stones):
        i = min(int(t * SR), n - 1)
        if v[i] < 0.15:
            continue
        g = r.uniform(0.5, 0.9) * v[i]
        (place_circular if circ else place)(bumps, wheel_bump(seed + 400 + j, 1.4), t, gain=g)
        (place_circular if circ else place)(ev, _norm(rattle(seed + 450 + j, r.integers(2, 4))), t + 0.03, gain=0.12 * g)
    return mod, fine, coarse, bumps, ev


def _rms(x):
    return np.sqrt(np.mean(np.square(x))) + 1e-12


def _coach_mix(rum, grind, fine, coarse, body, ev, creak, ref):
    """各层按"隆隆声 RMS = 1"定相对电平：连续层用 RMS（ref = 匀速段的切片），稀疏事件用峰值。"""
    R = _rms(rum[ref])
    return (rum / R + 0.45 * grind / _rms(grind[ref]) + 0.28 * fine / _rms(fine[ref])
            + 0.42 * coarse / _rms(coarse[ref]) + 3.2 * _norm(body) + 1.6 * _norm(ev) + 2.2 * creak)


def _grind(n, seed, env):
    """木轮铁箍滚过硬土的中频"沙——"：粉红噪声带通，跟着速度 / 路面起伏。"""
    g = bandpass(pink(n, seed), 220, 1300)
    return g * env


def coach_roll_loop(L_sec=8.0, X_sec=2.0):
    """驿站马车在土路上慢行：木轮隆隆 + 铁箍碾碎石 + 轮辋接缝颠簸激励车厢 + 吊带（皮带悬挂）
    随车身前后摇晃的咯吱声。所有周期都是 8 s 的整数分之一，噪声床用交叉淡化，事件绕回放置。"""
    L, X = secs(L_sec), secs(X_sec)
    n = L + X
    r = rng(1600)
    rough = smooth_random(L, 2.5, seed=1602, periodic=True)
    v = np.ones(L)
    mod, fine, coarse, bumps, ev = _coach_layers(L, v, rough, 1610, circ=True)
    rum = lowpass(brown(n, 1620), 220, 2)
    rum = rum / np.std(rum) * _wrap_env(mod, n)
    rum = loop_crossfade(rum, L)
    body = fold_tail(conv(bumps, _coach_body()), L)
    body_rum = circular(lambda s: peaking(peaking(s, 100, 1.2, 4.0), 150, 1.5, 3.0), rum)
    grind = loop_crossfade(_grind(n, 1621, _wrap_env(mod, n)), L)
    # 吊带咯吱：车身前后摇晃周期 1.6 s（每 8 s 5 次），每个摆幅端点有一定概率吱一声
    creak = np.zeros(L)
    for k in range(10):
        if r.random() < 0.75:
            t = k * 0.8 + r.uniform(0.05, 0.25)
            cr = leather_creak(r.uniform(0.25, 0.45), 1630 + k, f_lo=22, f_hi=60, wood=0.35)
            place_circular(creak, _norm(cr), t, gain=r.uniform(0.35, 0.7))
    x = _coach_mix(body_rum, grind, fine, coarse, body, ev, creak, slice(None))
    y = _reverb_loop(x, STREET_IR, 0.10)
    return circular(lambda s: lowpass(highpass(s, 30, 2), 9000, 2), y)


def brake_squeal(dur, seed, v_fn):
    """木刹车块压在铁箍上：高速粘-滑 → 尖锐的"吱——"，随车速降低音高下滑、最后颤几下停住。"""
    r = rng(seed)
    rate = lambda t: 380 + 520 * v_fn(t) ** 0.7 + 40 * np.sin(2 * np.pi * 5.3 * t)
    def amp(t):
        a = min(t / 0.12, 1.0) * (0.55 + 0.45 * np.sin(2 * np.pi * 2.1 * t + 0.5) ** 2)
        return a * min((dur - t) / 0.08, 1.0)
    ex = stick_slip(dur, rate, seed, jitter=0.05, amp_fn=amp)
    tyre = modal_ir([690, 1180, 1735, 2390, 3150, 4020], [0.05, 0.045, 0.04, 0.03, 0.025, 0.02],
                    [0.7, 1.0, 0.9, 0.6, 0.4, 0.25], 0.15, seed=seed + 1)
    shoe = modal_ir([340, 610, 930], [0.04, 0.03, 0.02], [1, 0.7, 0.4], 0.15, seed=seed + 2)
    env = np.interp(tvec(secs(dur)), tvec(secs(dur))[::480], [amp(t) for t in tvec(secs(dur))[::480]])
    scrape = bandpass(noise(secs(dur), seed + 3), 1500, 6000) * env
    y = conv(ex, tyre) + 0.5 * conv(ex, shoe)
    y = _norm(y)
    y[:len(scrape)] += 0.08 * scrape / (np.max(np.abs(scrape)) + 1e-12)
    return y


def coach_stop():
    """马车减速停下（无人声）：马蹄渐慢 → 拉刹车杆（棘轮咔咔）→ 刹车吱——随车速下滑 →
    停住时车厢在吊带上往前一冲再荡回（两声大的咯吱 + 车身一磕）→ 马甩头，挽具叮当。约 3.3 s。"""
    dur = 3.4
    n = secs(dur)
    t = tvec(n)
    r = rng(1700)
    t_stop = 2.1
    v = np.clip(0.5 + 0.5 * np.cos(np.pi * np.clip((t - 0.15) / (t_stop - 0.15), 0, 1)), 0, 1)
    v_fn = lambda tt: float(np.interp(tt, t, v))
    rough = smooth_random(n, 2.5, seed=1701)
    mod, fine, coarse, bumps, ev = _coach_layers(n, v, rough, 1710, circ=False)
    rum = lowpass(brown(n, 1720), 220, 2)
    rum = peaking(peaking(rum / np.std(rum) * mod, 100, 1.2, 4.0), 150, 1.5, 3.0)
    body = conv(bumps, _coach_body())[:n]
    grind = _grind(n, 1721, mod)
    x = _coach_mix(rum, grind, fine, coarse, body, ev, np.zeros(n), slice(0, secs(0.4)))
    x *= 0.32  # 以下各事件的增益都相对这个电平（隆隆声 RMS ≈ 0.32）
    # 马蹄：两匹马的四拍步法，步频随速度放慢，停住后各自挪一两步
    for h, (sc, ph0, hg) in enumerate([(0.95, 0.0, 1.0), (1.08, 0.37, 0.82)]):
        ph = ph0 * 0.25 + np.cumsum(3.5 * np.maximum(v, 0.0) ** 0.6) / SR
        idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
        for c, i in enumerate(idx):
            if i / SR > t_stop - 0.05:
                break
            fore = (c + h) % 2 == 1
            g = hg * (1.0 if fore else 0.7) * r.uniform(0.8, 1.05) * (0.6 + 0.4 * v[i])
            place(x, hoof(1730 + 10 * h + c, weight=1.15 if fore else 0.9, sc=sc), i / SR + r.normal(0, 0.01), gain=1.5 * g)
    for j, (tt, h) in enumerate([(2.28, 0), (2.52, 1), (2.95, 0)]):
        place(x, hoof(1790 + j, weight=0.8, sc=(0.95, 1.08)[h], crunch=0.7), tt, gain=0.8)
    # 刹车：杆 + 棘轮
    lever = modal_hit([1450, 2330, 3610], [0.05, 0.035, 0.025], [1, 0.6, 0.3], 0.1, seed=1740)
    for j, tt in enumerate([0.32, 0.355, 0.385]):
        pawl = modal_hit([r.uniform(2700, 3100), r.uniform(4300, 4800)], [0.02, 0.015], [1, 0.5], 0.05, seed=1741 + j)
        place(x, pawl, tt, gain=0.12)
        place(x, click(0.003, 1500, 8000, seed=1745 + j), tt, gain=0.08)
    place(x, lever, 0.3, gain=0.1)
    sq0, sq1 = 0.5, t_stop + 0.04
    sq = brake_squeal(sq1 - sq0, 1750, lambda tt: v_fn(sq0 + tt))
    place(x, sq, sq0, gain=0.5)
    # 停住：车身往前冲再荡回
    for j, (tt, g, d) in enumerate([(t_stop + 0.02, 0.5, 0.45), (t_stop + 0.62, 0.3, 0.4), (t_stop + 1.05, 0.12, 0.3)]):
        cr = leather_creak(d, 1760 + j, f_lo=20, f_hi=55, wood=0.5)
        place(x, _norm(cr), tt, gain=g)
    knock = conv(click(0.01, 100, 3000, seed=1765, t60=0.008), _coach_body())
    place(x, _norm(knock), t_stop + 0.08, gain=0.35)
    place(x, _norm(rattle(1766, 3)), t_stop + 0.1, gain=0.08)
    # 马甩头、挽链叮当
    for j, (tt, c) in enumerate([(t_stop + 0.05, 4), (t_stop + 0.35, 3), (t_stop + 0.9, 5)]):
        place(x, _norm(jingle(1770 + j, count=c, spread=0.12, dur=0.35)), tt, gain=0.1)
    y = add_reverb(x, STREET_IR, wet=0.12)[:n]
    y = lowpass(highpass(y, 30, 2), 9000, 2)
    return fade(y, fin=0.02, fout=0.3)


# ================================================================ 马（单独）

def _flutter_am(n, f_fn, seed, sharp=3.0, jitter=0.12):
    """鼻翼 / 嘴唇颤动：一串不太规则的脉冲包络（每周期幅度随机）。"""
    r = rng(seed)
    t = tvec(n)
    f = np.array([f_fn(tt) for tt in t[::240]]).repeat(240)[:n]
    f = f * (1 + jitter * smooth_random(n, 40, seed + 1))
    ph = np.cumsum(f) / SR
    cyc = np.floor(ph).astype(int)
    amps = r.uniform(0.5, 1.0, cyc.max() + 2)[cyc]
    return amps * (0.5 + 0.5 * np.cos(2 * np.pi * ph)) ** sharp


def _breath(n, seed, formants, bw=0.35):
    """呼气湍流：白噪声经几个宽共振峰（马的鼻腔很长，共振偏低）。"""
    x = noise(n, seed)
    y = np.zeros(n)
    for f, a in formants:
        y += a * bandpass(x, f * (1 - bw), f * (1 + bw))
    return y


def horse_snort(i):
    r = rng(1800 + i)
    if i == 1:
        # 短促的打响鼻：轻吸一口 → 鼻孔里"噗噜噜"猛地喷出
        dur = 1.0
        n = secs(dur)
        x = np.zeros(n)
        k = secs(0.22)
        inh = _breath(k, 1801, [(600, 1.0), (1500, 0.6), (3200, 0.3)]) * np.sin(np.pi * tvec(k) / 0.22) ** 2
        place(x, _norm(inh), 0.02, gain=0.07)
        k = secs(0.55)
        tk = tvec(k)
        env = np.clip(tk / 0.012, 0, 1) * np.exp(-tk / 0.16)
        fl = _flutter_am(k, lambda tt: 34 - 14 * tt / 0.55, 1802, sharp=2.5)
        br = _breath(k, 1803, [(280, 0.9), (650, 1.0), (1400, 0.7), (2700, 0.35), (4500, 0.15)])
        body = br * env * (0.3 + 0.7 * fl)
        # 鼻腔低频"噗"（鼻翼拍打的低频成分）
        lo = lowpass(noise(k, 1804), 180, 2) * env * fl
        ex = body / np.std(body) + 0.45 * lo / np.std(lo)
        place(x, ex, 0.33)
        x = add_reverb(x, STREET_IR, wet=0.12)[:n]
        return fade(highpass(x, 60, 2), fout=0.15)
    # 放松地长长"噗噜噜"一口（嘴唇 + 鼻孔一起颤），最后甩一下头，马衔叮当
    dur = 1.2
    n = secs(dur)
    x = np.zeros(n)
    k = secs(0.8)
    tk = tvec(k)
    env = np.clip(tk / 0.05, 0, 1) * np.clip((0.8 - tk) / 0.35, 0, 1) ** 1.5
    fl = _flutter_am(k, lambda tt: 22 - 8 * tt / 0.8, 1812, sharp=3.5, jitter=0.18)
    br = _breath(k, 1813, [(220, 1.0), (520, 0.9), (1150, 0.55), (2400, 0.25)])
    lo = lowpass(noise(k, 1814), 160, 2)
    ex = (br / np.std(br) * (0.3 + 0.7 * fl) + 0.6 * lo / np.std(lo) * fl) * env
    place(x, ex, 0.03)
    place(x, _norm(jingle(1815, count=4, spread=0.15, dur=0.35)), 0.8, gain=0.12)
    place(x, _norm(leather_creak(0.15, 1816)), 0.78, gain=0.06)
    x = add_reverb(x, STREET_IR, wet=0.12)[:n]
    return fade(highpass(x, 50, 2), fout=0.15)


def horse_stamp():
    """不耐烦地跺一下蹄：抬高再砸下（比走路重），蹄子再落稳一下；随之挽具叮当、皮带咯吱。"""
    n = secs(0.9)
    x = np.zeros(n)
    place(x, _norm(hoof(1901, weight=1.6, sc=0.92, crunch=1.6, clink_p=1.0)), 0.01, gain=1.0)
    place(x, _norm(hoof(1902, weight=0.7, sc=0.95, crunch=0.6, clink_p=0.0)), 0.085, gain=0.3)
    sp = gravel_burst(0.15, 1903, rate0=1500, tau=0.05, lo=1200, hi=6000)  # 溅起的碎石落回地面
    place(x, _norm(sp), 0.04, gain=0.06)
    place(x, _norm(jingle(1904, count=5, spread=0.1, dur=0.4)), 0.03, gain=0.18)
    place(x, _norm(leather_creak(0.2, 1905)), 0.04, gain=0.08)
    y = add_reverb(x, STREET_IR, wet=0.12)[:n]
    return fade(highpass(y, 35, 2), fout=0.2)


# ================================================================ 电报机

# 美式（铁路）莫尔斯码，1880 年代美国有线电报实际使用的码；'L' 是长划，' ' 是字母内部的间隔
AMERICAN_MORSE = {
    'A': '.-', 'B': '-...', 'C': '.. .', 'D': '-..', 'E': '.', 'F': '.-.', 'G': '--.', 'H': '....',
    'I': '..', 'J': '-.-.', 'K': '-.-', 'L': 'L', 'M': '--', 'N': '-.', 'O': '. .', 'P': '.....',
    'Q': '..-.', 'R': '. ..', 'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '.-..',
    'Y': '.. ..', 'Z': '... .',
}
TELEGRAPH_TEXT = 'DRAFT VOID STOP REWRITE STOP'
TELEGRAPH_UNIT = 0.044  # 一个点长 ≈ 44 ms（约 25 字/分，熟练的铁路报务员）


def morse_events(text, unit, seed):
    """→ [(t_down, t_up, 字母)]。美式码时值：点 1、划 2、长划 4、元素间 1、字母内空 2、字母间 3（实际放宽到 3.4，避免和 C/O/R 等字母内空混淆）、词间 6–8。
    报务员的"手法"：整体速度缓慢漂移 ±6%，每个时值再抖 ±8%，词间偶尔犹豫一下。"""
    r = rng(seed)
    ev = []
    t = 0.0
    tempo = lambda tt: 1 + 0.06 * np.sin(2 * np.pi * tt / 5.3 + 0.7)
    jit = lambda: 1 + 0.08 * r.standard_normal()
    for wi, word in enumerate(text.split(' ')):
        if wi:
            t += unit * (6 + r.uniform(0, 2)) * tempo(t)
        for li, ch in enumerate(word):
            if li:
                t += unit * 3.4 * tempo(t) * (1 + 0.04 * r.standard_normal())  # 字母间隔要比字母内的空（2）清楚地长
            code = AMERICAN_MORSE[ch]
            for ei, el in enumerate(code):
                if el == ' ':
                    t += unit * 1 * tempo(t) * jit()  # 再加一个元素间隔 = 共 2
                    continue
                if ei:
                    t += unit * tempo(t) * jit()
                on = {'.': 1.0, '-': 2.2, 'L': 4.2}[el] * unit * tempo(t) * jit()
                ev.append((t, t + on, ch))
                t += on
    return ev, t


def _sounder_click(seed, down):
    """电报音响器：衔铁（黄铜）砸到下止点 = 较响较沉的"嗒"，被弹簧拉回上止点 = 较轻较亮的"咔"。
    木底座给"嗒"一点木头的厚度。"""
    r = rng(seed)
    sc = r.uniform(0.985, 1.015)
    if down:
        met = modal_hit([1320 * sc, 2410 * sc, 3760 * sc, 5550 * sc, 8100 * sc],
                        [0.035, 0.028, 0.02, 0.014, 0.009], [1.0, 0.75, 0.55, 0.35, 0.2], 0.08, seed=seed)
        base = modal_ir([205, 372, 640, 1030], [0.05, 0.04, 0.03, 0.02], [1, 0.8, 0.5, 0.3], 0.08, seed=seed + 1)
        tr = click(0.002, 800, 10000, seed=seed + 2)
        wood = conv(tr, base)
        x = 0.55 * met + 0.8 * _norm(wood)[:len(met)]
        x[:len(tr)] += 0.6 * tr / np.max(np.abs(tr))
        return x
    met = modal_hit([1980 * sc, 3170 * sc, 4630 * sc, 6880 * sc], [0.025, 0.02, 0.014, 0.01],
                    [1.0, 0.7, 0.45, 0.25], 0.06, seed=seed)
    tr = click(0.0015, 1500, 11000, seed=seed + 2)
    x = 0.5 * met
    x[:len(tr)] += 0.45 * tr / np.max(np.abs(tr))
    return x


def telegraph_loop(L_sec=12.0):
    """电报局里的音响器自己咔哒作响：一整遍"DRAFT VOID STOP REWRITE STOP"（美式莫尔斯），
    然后静默约 2–3 s 再重来。点/划由"嗒"与"咔"之间的间隔区分，没有任何音调。"""
    L = secs(L_sec)
    buf = np.zeros(L)
    ev, end = morse_events(TELEGRAPH_TEXT, TELEGRAPH_UNIT, 2001)
    t0 = 0.45
    assert t0 + end < L_sec - 1.8, end
    r = rng(2002)
    for k, (a, b, _) in enumerate(ev):
        place_circular(buf, _sounder_click(2100 + 2 * k, True), t0 + a, gain=r.uniform(0.85, 1.0))
        place_circular(buf, _sounder_click(2101 + 2 * k, False), t0 + b, gain=r.uniform(0.5, 0.62))
    # 极轻的屋内底噪，让静默段不是数字静音
    n = L + secs(2)
    room = loop_crossfade(lowpass(pink(n, 2003), 900, 2), L)
    x = buf + 0.004 * room / np.std(room)
    y = _reverb_loop(x, OFFICE_IR, 0.15)
    return circular(lambda s: highpass(s, 80, 2), y)


# ================================================================ 教堂钟

BELL_NOMINAL = 622.25  # D#5；与"记住了"的钟同音，小三度音色同族


def church_bell_strike(seed, strength=1.0, dur=9.0):
    """一口小号青铜钟（边疆教堂的约 30 英寸铸钟）被铁钟锤敲一下。
    分音按钟的标准结构（相对 nominal）：hum 0.25、prime 0.5、tierce 0.6（prime 上的小三度）、
    quint 0.75、nominal 1、再往上 deciem 1.25、undecime 1.33、superquint 1.5、octave nominal 2……
    小镇铸钟没调准：各分音略偏几到二十几音分。钟不正圆，每个分音分成相距零点几 Hz 的两支，产生"哇——哇"的拍。"""
    r = rng(seed)
    N = BELL_NOMINAL
    #           比值   音分偏差 幅度  t60(s)
    parts = [(0.25, -18, 0.3, 11.0),    # hum
             (0.5, 6, 0.55, 7.5),       # prime
             (0.6, -9, 0.7, 6.0),       # tierce（小三度）
             (0.75, 22, 0.18, 3.8),     # quint（真钟里本来就弱）
             (1.0, 0, 1.0, 4.6),        # nominal（击音）
             (1.25, 14, 0.32, 2.6),     # deciem
             (1.335, -20, 0.18, 2.2),   # undecime
             (1.5, 9, 0.38, 2.0),       # superquint
             (2.0, 16, 0.25, 1.4),      # octave nominal
             (2.52, -30, 0.14, 0.9),
             (3.03, 25, 0.09, 0.6),
             (3.6, -15, 0.05, 0.4)]
    fr, t6, am = [], [], []
    for (ratio, cents, a, d) in parts:
        f = N * ratio * 2 ** (cents / 1200)
        split = r.uniform(0.3, 1.3)
        for s, g in ((0.0, 1.0), (split, r.uniform(0.15, 0.4))):
            fr.append(f + s)
            # 敲得重，高分音相对更强、衰得更快
            t6.append(d * r.uniform(0.92, 1.08))
            am.append(a * g * (strength ** (0.6 * max(ratio - 0.5, 0))))
    x = modal_hit(fr, t6, am, dur, seed=seed + 1, attack=0.001)
    # 铁锤砸铜：一下宽带"当" + 一团快速消失的高频非谐分音（金属的"嚓"）
    hi_f = r.uniform(2500, 7000, 14)
    hi = modal_hit(list(hi_f), list(r.uniform(0.08, 0.35, 14)), list(r.uniform(0.2, 1.0, 14)), 0.5, seed=seed + 2)
    tr = click(0.004, 600, 9000, seed=seed + 3, t60=0.003)
    x = x / np.max(np.abs(x))
    x[:len(hi)] += 0.12 * strength * hi / np.max(np.abs(hi))
    x[:len(tr)] += 0.25 * strength * tr / np.max(np.abs(tr))
    return x


def church_bell():
    """单独一声（近处 / 3D 声源放在钟楼上）：钟本体 + 中等户外混响，约 9 s 衰减。"""
    n = secs(9.5)
    x = np.zeros(n)
    place(x, church_bell_strike(2201, 1.0, 9.4), 0.01)
    y = add_reverb(lowpass(x, 9000, 2), BELL_IR, wet=0.22)[:n]
    return fade(highpass(y, 60, 2), fout=1.2)


def church_bell_three():
    """开场"远处教堂敲三下"：每下间隔 3.2 s，空气吸收（低通 ~2 kHz、高频再多压一点）、
    直达声小、长而暗的立体声尾巴，外加一道远处山 / 街尽头的回声。总长 14 s。"""
    n = secs(14.0)
    x = np.zeros(n)
    for k, (t0, s) in enumerate([(0.08, 1.0), (3.28, 0.93), (6.48, 0.97)]):
        place(x, church_bell_strike(2210 + k, s, 7.5), t0, gain=s)
    x = lowpass(x, 2200, 2)
    x = peaking(x, 4000, 0.7, -6.0)
    x = highpass(x, 90, 2)
    echo = np.zeros(n)
    place(echo, lowpass(x, 1200, 2), 0.42, gain=0.18)
    y = add_reverb(pan(x + echo, 0.08), FAR_IR_ST, wet=0.9, dry=0.45)[:n]
    return fade(y, fin=0.005, fout=2.5)


# ================================================================ 街道环境

def _bird_phrase(seed):
    """远处一只鸟：两三个快速下滑 / 上挑的哨音，带颤音与谐波（不是纯正弦），距离滤波后很淡。"""
    r = rng(seed)
    x = np.zeros(secs(1.6))
    t = 0.0
    for j in range(r.integers(2, 5)):
        d = r.uniform(0.08, 0.28)
        k = secs(d)
        tk = tvec(k)
        f0, f1 = r.uniform(2600, 4200), r.uniform(1800, 3600)
        f = f0 + (f1 - f0) * (tk / d) ** r.uniform(0.6, 1.6)
        f *= 1 + 0.03 * np.sin(2 * np.pi * r.uniform(25, 45) * tk)
        ph = 2 * np.pi * np.cumsum(f) / SR
        env = np.sin(np.pi * tk / d) ** 1.5
        s = (np.sin(ph) + 0.18 * np.sin(2 * ph + 0.4) + 0.05 * np.sin(3 * ph)) * env
        s += 0.03 * bandpass(noise(k, seed + j), 1500, 6000) * env
        place(x, s, t, gain=r.uniform(0.6, 1.0))
        t += d + r.uniform(0.03, 0.14)
    return lowpass(x, 5000, 2)


def _cicada(dur, seed):
    """远处的蝉 / 草蜢：~4.5 kHz 一带的噪声按 ~150 Hz 脉冲调制，整体缓慢涌起再落下。"""
    n = secs(dur)
    t = tvec(n)
    r = rng(seed)
    pulse = (0.5 + 0.5 * np.cos(2 * np.pi * (r.uniform(130, 170) * t + 0.3 * smooth_random(n, 3, seed)))) ** 4
    car = bandpass(noise(n, seed + 1), 3800, 5600, 2)
    env = np.sin(np.pi * t / dur) ** 2 * (0.7 + 0.3 * smooth_random(n, 1.5, seed + 2))
    return car * pulse * env


def amb_street_loop(L_sec=36.0, X_sec=4.0):
    """午后主街：干燥的阵风（比 amb_wind_loop 更有起伏，强阵风里夹扬沙的"沙沙"）、
    远处偶尔的木头 / 招牌吱呀、很淡的远处鸟叫和虫鸣。立体声，36 s 无缝。"""
    L, X = secs(L_sec), secs(X_sec)
    n = L + X
    base = smooth_random(L, 0.28, seed=2301, periodic=True)
    out = []
    for c in range(2):
        own = smooth_random(L, 0.55, seed=2302 + c, periodic=True)
        g = np.clip(0.42 + 0.5 * base + 0.12 * own, 0.12, 1)
        gw = _wrap_env(g, n)
        w = wind_layer(n, gw, seed=2310 + c, lo=170, span=780, sigma=0.85, whistle=0.02, floor=0.3)
        sand = bandpass(noise(n, 2320 + c), 2500, 9000) * np.clip(gw - 0.45, 0, None) ** 2.2
        sand *= 1 + 0.5 * smooth_random(n, 9, seed=2322 + c)  # 沙粒打在墙板上，颗粒感
        rumble = lowpass(brown(n, 2324 + c), 100, 2) * (0.3 + 0.7 * gw)
        mix = w / np.std(w) + 0.5 * sand / (np.std(sand) + 1e-12) * 0.35 + 0.3 * rumble / np.std(rumble)
        out.append(loop_crossfade(mix, L))
    bed = np.stack(out, axis=1)
    bed = bed / np.sqrt(np.mean(bed ** 2))
    ev = np.zeros((L, 2))
    r = rng(2330)
    # 远处木头吱呀（栈道、门廊柱、拴马桩），跟阵风走：选阵风较强的时刻
    gL = np.clip(0.42 + 0.5 * base, 0, 1)
    for i, t0 in enumerate([3.6, 9.1, 15.8, 22.4, 27.9, 33.0]):
        cr = lowpass(wood_creak(r.uniform(0.4, 1.0), seed=2340 + i), 1800, 2)
        st = add_reverb(pan(cr, r.uniform(-0.8, 0.8)), STREET_IR_ST, wet=0.6)
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=r.uniform(0.18, 0.3) * (0.5 + gL[secs(t0)]))
    # 挂着的招牌在铁钩上晃：两三下细小的金属吱声
    for i, t0 in enumerate([6.4, 19.7, 30.2]):
        sg = np.zeros(secs(1.6))
        for j in range(r.integers(2, 4)):
            d = r.uniform(0.15, 0.3)
            rate = lambda tt, a=r.uniform(260, 380): a * (1 + 0.3 * np.sin(np.pi * tt / d))
            amp = lambda tt: np.sin(np.pi * min(tt / d, 1)) ** 1.2
            ex = stick_slip(d, rate, 2350 + 10 * i + j, jitter=0.06, amp_fn=amp)
            m = modal_ir([1150, 1870, 2630, 3540], [0.03, 0.025, 0.02, 0.015], [1, 0.8, 0.5, 0.3], 0.08, seed=2360 + i)
            place(sg, _norm(conv(ex, m)), j * r.uniform(0.45, 0.6))
        sg = lowpass(sg, 3000, 2)
        st = add_reverb(pan(sg, r.uniform(-0.6, 0.6)), STREET_IR_ST, wet=0.7)
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=0.05)
    # 远处鸟叫（三处）、虫鸣（两段）
    for i, t0 in enumerate([3.9, 16.9, 31.4]):  # 放在阵风间歇里，不被风盖住
        b = _bird_phrase(2370 + i)
        st = add_reverb(pan(b, r.uniform(-0.9, 0.9)), STREET_IR_ST, wet=0.8)
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=0.035)
    for i, (t0, d) in enumerate([(1.5, 6.0), (17.0, 5.0)]):
        cz = _cicada(d, 2380 + i)
        st = pan(cz, r.uniform(-0.7, 0.7))
        place_circular(ev, st / np.max(np.abs(st)), t0, gain=0.012)
    y = bed + ev * 6.0
    return circular(lambda v: highpass(v, 25, 2), y)


# ================================================================ 户外脚步

def step_dirt(i):
    """女式皮靴（小方跟）踩压实的土路 + 碎石：鞋跟"噗"一下（土不共振）+ 砂砾被碾，
    前掌落下再碾一点；偶尔跟磕到小石子"嗒"一下，或者轻轻蹭地。"""
    r = rng(2400 + i)
    n = secs(0.5)
    x = np.zeros(n)
    tt = tvec(secs(0.06))
    f = r.uniform(120, 150) * (1 + 0.5 * np.exp(-tt / 0.005))
    thud = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.011)
    heel = lowpass(noise(secs(0.04), 2410 + i) * exp_decay(secs(0.04), 0.018), 900, 2)
    heel[:24] *= np.linspace(0, 1, 24)
    tap = click(0.006, 600, 4000, seed=2420 + i, t60=0.004)
    place(x, thud, 0.004, gain=0.55)
    place(x, _norm(heel), 0.004, gain=0.6)
    place(x, _norm(tap), 0.004, gain=0.3)
    place(x, _norm(gravel_burst(0.08, 2430 + i, rate0=r.uniform(2500, 4500), tau=0.02)), 0.005,
          gain=r.uniform(0.4, 0.55))
    place(x, _norm(gravel_burst(0.06, 2440 + i, rate0=600, tau=0.03, lo=500, hi=2500, sigma=1.1)), 0.006, gain=0.28)
    toe_t = r.uniform(0.075, 0.11)
    toe = lowpass(noise(secs(0.04), 2450 + i) * exp_decay(secs(0.04), 0.02), 1200, 2)
    place(x, _norm(toe), toe_t, gain=r.uniform(0.2, 0.3))
    place(x, _norm(gravel_burst(0.1, 2460 + i, rate0=2200, tau=0.035)), toe_t, gain=r.uniform(0.3, 0.42))
    if i in (2, 5):  # 跟磕到一颗石子
        st = modal_hit([r.uniform(2200, 2800), r.uniform(3800, 4500)], [0.02, 0.014], [1, 0.4], 0.04, seed=2470 + i)
        place(x, st, 0.005, gain=0.12)
    if i in (3, 6):  # 抬脚时鞋尖蹭一下土
        k = secs(0.07)
        sc = bandpass(noise(k, 2480 + i), 800, 4500) * np.sin(np.pi * tvec(k) / 0.07) ** 2
        place(x, _norm(sc), toe_t + r.uniform(0.12, 0.18), gain=0.08)
    x = lowpass(x, 7500, 2)
    y = add_reverb(x, STREET_IR, wet=0.07)
    return trim_silence(highpass(y[:secs(0.48)], 50, 2), thresh_db=-60)


def step_boardwalk(i):
    """户外栈道：厚松木板架在离地一尺多的横梁上，下面是空的——比室内地板更低、更"空"（板下空腔的
    "咚"更长），板子跨度大、模态更低；有的板没钉牢，踩下去另一头磕一下横梁"嗒"；板面有沙；
    户外没有房间混响，只有对街的回声。"""
    r = rng(2500 + i)
    n = secs(0.5)
    x = np.zeros(n)
    sc = r.uniform(0.9, 1.1)
    plank = modal_ir([94 * sc, 147 * sc, 211 * sc, 300 * sc, 428 * sc, 611 * sc, 870 * sc, 1290 * sc],
                     [0.11, 0.1, 0.09, 0.075, 0.06, 0.05, 0.035, 0.02],
                     [0.45, 0.6, 0.9, 1.0, 0.8, 0.55, 0.35, 0.18], 0.3, seed=2510 + i)
    plank *= 0.9 / np.abs(np.fft.rfft(plank, 1 << 15)).max()
    plank[0] += 1.0
    heel = click(0.012, 150, 5000, seed=2520 + i, t60=0.006)
    tt = tvec(secs(0.12))
    fth = 72 * sc * (1 + 0.5 * np.exp(-tt / 0.01))
    cav = np.sin(2 * np.pi * np.cumsum(fth) / SR) * np.exp(-tt / 0.028)
    hs = _norm(conv(heel / np.max(np.abs(heel)), plank))
    hs[:len(cav)] += 0.45 * cav
    place(x, _norm(hs), 0.005)
    toe_t = r.uniform(0.07, 0.11)
    ts = conv(click(0.014, 150, 2500, seed=2530 + i, t60=0.008), plank)
    place(x, _norm(ts), toe_t, gain=r.uniform(0.25, 0.38))
    if i in (1, 3, 6):  # 松动的板：另一头翘起再磕回横梁
        rt = r.uniform(0.02, 0.035)
        k = conv(click(0.006, 300, 4000, seed=2540 + i, t60=0.004), plank)
        place(x, _norm(k), rt, gain=0.3)
        place(x, _norm(k), toe_t + rt * 0.8, gain=0.15)
    if i == 4:  # 钉子在木头里吱一声
        cr = wood_creak(0.12, seed=2550 + i, f_lo=90, f_hi=180)
        place(x, _norm(cr), toe_t + 0.02, gain=0.15)
    grit = gravel_burst(0.05, 2560 + i, rate0=2500, tau=0.012, lo=2500, hi=7500)
    place(x, _norm(grit), 0.006, gain=0.09)
    x = lowpass(x, 6000, 2)
    y = add_reverb(x, STREET_IR, wet=0.10)
    return trim_silence(highpass(y[:secs(0.48)], 45, 2), thresh_db=-60)


# ================================================================ 画布撕裂

def canvas_tear():
    """撕开那块 12 m 高的厚帆布：先绷紧（几根纤维"嘣"断）→ 第一段快撕 → 卡一下 →
    第二段长撕、越撕越快 → 最后一下断开，大块帆布"呼"地松开、在风里扑腾几下。
    撕裂 = 纤维一根根断开的密集冲击串（速率随撕裂速度、幅度对数正态）× 不规则的"嘶啦"调制，
    经帆布的宽共振；另加低频的布面振动。约 2.6 s。"""
    dur = 2.7
    n = secs(dur)
    t = tvec(n)
    r = rng(2600)
    # 撕裂速度曲线（0..1）
    def seg(a, b, p0, p1, shape=1.0):
        u = np.clip((t - a) / (b - a), 0, 1)
        return np.where((t >= a) & (t < b), p0 + (p1 - p0) * u ** shape, 0)
    speed = seg(0.16, 0.52, 0.55, 0.9) + seg(0.52, 0.66, 0.25, 0.15) + seg(0.66, 1.95, 0.45, 1.0, 1.6)
    speed = np.convolve(speed, np.hanning(secs(0.02)) / np.hanning(secs(0.02)).sum(), mode='same')
    zz = np.clip(0.55 + 0.45 * smooth_random(n, 55, seed=2601), 0, 1) ** 1.5  # "嘶啦"粗糙的颤动
    rate = 600 + 5200 * speed
    imp = grain_train(n, rate * (speed > 0.02), 2602, sigma=1.0) * zz * (0.4 + 0.6 * speed)
    # 绷紧时的几下纤维断裂
    for j, tt in enumerate([0.02, 0.07, 0.11, 0.135]):
        i = secs(tt)
        imp[i] += r.uniform(2.5, 4.5) * (1 if j % 2 else -1)
    mid = peaking(peaking(bandpass(imp, 350, 5000), 700, 1.0, 5.0), 1900, 1.4, 3.0)
    hiss = bandpass(noise(n, 2603), 1500, 7000) * speed * zz
    body = lowpass(imp, 250, 2)
    flap_t = 1.97
    x = mid / np.std(mid[speed > 0.3]) + 0.3 * hiss / np.std(hiss[speed > 0.3]) + 0.3 * body / np.std(body[speed > 0.3])
    x *= np.clip((2.0 - t) / 0.03, 0, 1)  # 断开那一刻撕裂声骤停
    # 断开："啪"+ 大块帆布松开的低频"呼"，随后在风里扑腾
    k = secs(0.7)
    tk = tvec(k)
    whump = lowpass(noise(k, 2604), 300, 2) * np.clip(tk / 0.01, 0, 1) * np.exp(-tk / 0.12)
    snap = gravel_burst(0.05, 2605, rate0=9000, tau=0.01, lo=600, hi=6000)
    place(x, _norm(whump), flap_t, gain=2.2)
    place(x, _norm(snap), flap_t, gain=1.6)
    fl = np.zeros(k)
    for j, (tt, g) in enumerate([(0.18, 1.0), (0.36, 0.6), (0.52, 0.35)]):
        m = secs(0.12)
        f = lowpass(noise(m, 2610 + j), 500, 2) * np.sin(np.pi * tvec(m) / 0.12) ** 2
        place(fl, _norm(f), tt, gain=g)
    place(x, fl, flap_t, gain=0.9)
    x = highpass(x, 40, 2)
    y = add_reverb(x, STREET_IR, wet=0.18)[:n]
    return fade(y, fin=0.003, fout=0.25)


# ================================================================ 墓地栅栏门

def gate_creak():
    """墓地的旧木栅栏门：抬起门闩（铁 + 木"咔哒"）→ 两只生锈的带状合页吱吱嘎嘎（锈蚀让粘-滑
    时断时续、音高不稳），上下两只合页音高不同 → 门慢下来，轻轻碰到篱笆桩，栅板晃两下。约 2 s。"""
    dur = 2.1
    n = secs(dur)
    x = np.zeros(n)
    r = rng(2700)
    lat = modal_hit([1430, 2570, 3880], [0.05, 0.035, 0.025], [1, 0.6, 0.35], 0.1, seed=2701)
    wood = conv(click(0.006, 200, 4000, seed=2702, t60=0.004),
                modal_ir([300, 520, 830], [0.05, 0.04, 0.03], [1, 0.7, 0.4], 0.08, seed=2703))
    place(x, lat, 0.02, gain=0.35)
    place(x, _norm(wood), 0.02, gain=0.4)
    place(x, lat * 0.8, 0.075, gain=0.15)
    strap = [780, 1460, 2210, 3050, 4300]
    gw = modal_ir([180, 290, 460, 700], [0.08, 0.07, 0.05, 0.04], [1, 0.8, 0.5, 0.3], 0.15, seed=2704)
    t_a, t_b = 0.2, 1.72
    D = t_b - t_a
    for h, (base, top, g, sd) in enumerate([(70, 300, 1.0, 2710), (110, 420, 0.5, 2720)]):
        stut = smooth_random(secs(D), 7, seed=sd + 1)
        def rate(tt, base=base, top=top, stut=stut):
            u = tt / D
            return base + (top - base) * np.sin(np.pi * min(u, 1) ** 0.7) ** 1.3 + 50 * stut[min(int(tt * SR), len(stut) - 1)]
        def amp(tt, stut=stut):
            u = tt / D
            a = np.sin(np.pi * min(u, 1)) ** 0.6
            s = stut[min(int(tt * SR), len(stut) - 1)]
            return a * np.clip(0.6 + 0.9 * s, 0.05, 1.0)  # 锈：时不时"卡"住几乎不响
        ex = stick_slip(D, rate, sd, jitter=0.09, amp_fn=amp)
        m = modal_ir([f * (1 + 0.06 * h) for f in strap], [0.025, 0.022, 0.018, 0.014, 0.01],
                     [0.8, 1.0, 0.7, 0.45, 0.25], 0.15, seed=sd + 2)
        y = conv(ex, m) + 0.5 * conv(ex, gw)
        place(x, _norm(y), t_a, gain=0.55 * g)
    # 门板扫过的一点风声
    k = secs(D)
    sw = lowpass(noise(k, 2730), 500, 2) * np.sin(np.pi * tvec(k) / D) ** 2
    place(x, _norm(sw), t_a, gain=0.04)
    # 碰到篱笆桩：软软的"咚"+ 栅板晃
    hit = conv(click(0.01, 120, 3000, seed=2740, t60=0.008), gw)
    place(x, _norm(hit), 1.76, gain=0.45)
    for j, tt in enumerate([1.8, 1.86, 1.95]):
        k2 = conv(click(0.004, 300, 4000, seed=2745 + j, t60=0.003),
                  modal_ir([r.uniform(380, 480), r.uniform(800, 950)], [0.03, 0.02], [1, 0.5], 0.05, seed=2748 + j))
        place(x, _norm(k2), tt, gain=0.12 / (j + 1))
    x = peaking(x, 250, 1.0, 2.0)
    y = add_reverb(x, STREET_IR, wet=0.14)[:n]
    return fade(highpass(y, 50, 2), fout=0.2)
