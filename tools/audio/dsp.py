"""Mercy Creek 音频合成的公共 DSP 工具。

全部是自写的程序化合成：不读取任何采样或音色库。所有随机数都来自固定种子，
同一份代码每次跑出逐字节相同的 WAV。
"""
import warnings
import wave

import numpy as np
from scipy import signal

SR = 48000


def rng(seed):
    return np.random.default_rng(seed)


def secs(n):
    return int(round(n * SR))


def tvec(n):
    return np.arange(n) / SR


# ---------------------------------------------------------------- 电平

def db_to_lin(db):
    return 10.0 ** (db / 20.0)


def peak_db(x):
    p = np.max(np.abs(x))
    return -np.inf if p == 0 else 20 * np.log10(p)


def rms_db(x):
    r = np.sqrt(np.mean(np.square(x)))
    return -np.inf if r == 0 else 20 * np.log10(r)


def normalize_peak(x, target_db):
    p = np.max(np.abs(x))
    return x if p == 0 else x * (db_to_lin(target_db) / p)


def normalize_rms(x, target_db, peak_ceiling_db=-1.0):
    """按 RMS 定电平；若峰值会超过上限，就整体压低到上限（宁可小声也不削波）。"""
    y = x * (db_to_lin(target_db) / max(np.sqrt(np.mean(np.square(x))), 1e-12))
    p = np.max(np.abs(y))
    ceil = db_to_lin(peak_ceiling_db)
    if p > ceil:
        y *= ceil / p
    return y


def write_wav(path, x, dither_seed=12345):
    """写 48kHz 16-bit PCM；x 为 (n,) 或 (n, 2) 的浮点。固定种子 TPDF 抖动。"""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    r = rng(dither_seed)
    d = (r.random(x.shape) - r.random(x.shape))  # ±1 LSB TPDF
    q = np.round(x * 32767.0 + d)
    q = np.clip(q, -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(q.tobytes())


# ---------------------------------------------------------------- 滤波

def _sos(kind, f, order=2):
    return signal.butter(order, f, btype=kind, fs=SR, output='sos')


def lowpass(x, f, order=2):
    return signal.sosfilt(_sos('lowpass', f, order), x, axis=0)


def highpass(x, f, order=2):
    return signal.sosfilt(_sos('highpass', f, order), x, axis=0)


def bandpass(x, lo, hi, order=2):
    return signal.sosfilt(_sos('bandpass', [lo, hi], order), x, axis=0)


def peaking(x, f, q, gain_db):
    """RBJ 峰值 EQ，用来给音色加一点"体"。"""
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return signal.lfilter(b, a, x, axis=0)


def conv(x, ir):
    """线性卷积，输出长度 = len(x) + len(ir) - 1。"""
    if x.ndim == 1:
        return signal.fftconvolve(x, ir)
    return np.stack([signal.fftconvolve(x[:, c], ir if ir.ndim == 1 else ir[:, c])
                     for c in range(x.shape[1])], axis=1)


# ---------------------------------------------------------------- 包络 / 片段

def exp_decay(n, t60):
    """t60 秒内衰减 60 dB 的指数包络。"""
    return np.exp(-6.907755 * tvec(n) / t60)


def fade(x, fin=0.0, fout=0.0):
    x = x.copy()
    a, b = secs(fin), secs(fout)
    if a > 0:
        x[:a] *= (np.sin(np.linspace(0, np.pi / 2, a)) ** 2).reshape(-1, *([1] * (x.ndim - 1)))
    if b > 0:
        x[-b:] *= (np.cos(np.linspace(0, np.pi / 2, b)) ** 2).reshape(-1, *([1] * (x.ndim - 1)))
    return x


def place(buf, x, t, gain=1.0):
    """把片段 x 加到 buf 的 t 秒处（超出部分截掉）。"""
    i = secs(t)
    if i >= len(buf):
        return buf
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += gain * x[:n]
    return buf


def place_circular(buf, x, t, gain=1.0):
    """同 place，但超出尾部的部分绕回开头——用于无缝循环。"""
    L = len(buf)
    i = secs(t) % L
    pos = 0
    while pos < len(x):
        n = min(len(x) - pos, L - i)
        buf[i:i + n] += gain * x[pos:pos + n]
        pos += n
        i = 0
    return buf


def fold_tail(x, L):
    """长度 > L 的渲染结果，把 L 之后的尾巴叠回开头，得到严格周期 L 的循环。"""
    out = x[:L].copy()
    pos = L
    while pos < len(x):
        n = min(L, len(x) - pos)
        out[:n] += x[pos:pos + n]
        pos += n
    return out


def loop_crossfade(x, L):
    """x 长度为 L + X：把多出来的 X 个尾样本按等功率曲线淡入开头，得到长度 L 的无缝循环。

    对互不相关的噪声，等功率曲线让接缝处响度不塌；接缝两侧样本本来就是连续信号
    （开头 = 头的淡入 + 尾的延续），所以不会有咔哒。"""
    X = len(x) - L
    out = x[:L].copy()
    th = np.linspace(0, np.pi / 2, X)
    gin, gout = np.sin(th), np.cos(th)
    if x.ndim == 2:
        gin, gout = gin[:, None], gout[:, None]
    out[:X] = x[:X] * gin + x[L:L + X] * gout
    return out


def pan(x, p):
    """等功率声像，p ∈ [-1, 1]。返回 (n, 2)。"""
    th = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=1)


def to_stereo(x):
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


# ---------------------------------------------------------------- 发生器

def noise(n, seed):
    return rng(seed).standard_normal(n)


def pink(n, seed):
    """FFT 整形的粉红噪声（1/f 功率）。"""
    w = rng(seed).standard_normal(n)
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    W /= np.sqrt(f)
    y = np.fft.irfft(W, n)
    return y / np.std(y)


def brown(n, seed):
    w = rng(seed).standard_normal(n)
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    W /= f
    y = np.fft.irfft(W, n)
    return y / np.std(y)


def smooth_random(n, rate_hz, seed, periodic=False):
    """平滑随机控制曲线（0 附近、约 ±1）。periodic=True 时首尾严格衔接（循环用）。"""
    r = rng(seed)
    if periodic:
        # 只在整数周期的低频上放随机相位，保证 n 个样本后完全回到起点
        dur = n / SR
        kmax = max(1, int(rate_hz * dur))
        t = tvec(n)
        y = np.zeros(n)
        for k in range(1, kmax + 1):
            amp = 1.0 / (1 + (k / max(kmax / 3, 1)) ** 2)
            y += amp * np.sin(2 * np.pi * k * t / dur + r.uniform(0, 2 * np.pi))
        return y / (np.max(np.abs(y)) + 1e-12)
    m = max(4, int(n / SR * rate_hz) + 4)
    pts = r.standard_normal(m)
    xs = np.linspace(0, n, m)
    y = np.interp(np.arange(n), xs, pts)
    # 再平滑一下去掉折线感
    k = max(3, int(SR / rate_hz / 2))
    y = np.convolve(y, np.hanning(k) / np.hanning(k).sum(), mode='same')
    return y / (np.max(np.abs(y)) + 1e-12)


def shaped_noise(n, gain_fn, seed, nfft=2048, hop=512, src=None):
    """STFT 域按时间-频率增益整形噪声，用来做随时间变化的滤波（风、气流、液体）。

    gain_fn(times[F], freqs[K]) -> 增益矩阵 (F, K)。"""
    pad = nfft
    x = rng(seed).standard_normal(n + 2 * pad) if src is None else np.concatenate([np.zeros(pad), src, np.zeros(pad)])
    f, t, Z = signal.stft(x, fs=SR, nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=True)
    # scipy 的 t 是帧中心时间；减掉前面垫的 pad 就是输出时间轴
    G = gain_fn(t - pad / SR, f).T  # (K, F)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # 两端 NOLA 不满足的部分在 pad 里，会被裁掉
        _, y = signal.istft(Z * G, fs=SR, nperseg=nfft, noverlap=nfft - hop, boundary=False)
    y = y[pad:pad + n]
    if len(y) < n:
        y = np.pad(y, (0, n - len(y)))
    return y


def modal_ir(freqs, t60s, amps, dur, seed=0):
    """一组阻尼正弦（模态）组成的冲激响应：木板、玻璃、金属、钟体共振都用它。"""
    n = secs(dur)
    t = tvec(n)
    ph = rng(seed).uniform(0, 2 * np.pi, len(freqs))
    y = np.zeros(n)
    for f, d, a, p in zip(freqs, t60s, amps, ph):
        if f >= SR / 2 * 0.95:
            continue
        y += a * np.sin(2 * np.pi * f * t + p) * np.exp(-6.907755 * t / d)
    return y


def modal_hit(freqs, t60s, amps, dur, seed=0, attack=0.0005):
    """敲击：模态 IR 开头加极短的上升，避免 0 相位以外的阶跃。"""
    y = modal_ir(freqs, t60s, amps, dur, seed)
    a = max(1, secs(attack))
    y[:a] *= np.linspace(0, 1, a)
    return y


def click(dur, lo, hi, seed, t60=None):
    """一小段带通噪声冲击，模拟硬物接触瞬态。"""
    n = secs(dur)
    x = noise(n, seed) * exp_decay(n, t60 or dur)
    a = max(2, secs(0.0004))
    x[:a] *= np.linspace(0, 1, a)
    return bandpass(x, lo, hi)


def stick_slip(dur, rate_fn, seed, jitter=0.15, amp_fn=None):
    """摩擦"粘-滑"脉冲串：吱呀声的激励。rate_fn(t)->每秒脉冲数，amp_fn(t)->幅度。"""
    r = rng(seed)
    n = secs(dur)
    y = np.zeros(n)
    t = 0.0
    while True:
        rate = max(1.0, float(rate_fn(t)))
        t += (1.0 / rate) * (1 + jitter * r.standard_normal())
        if t >= dur:
            break
        i = int(t * SR)
        a = (amp_fn(t) if amp_fn else 1.0) * (0.6 + 0.4 * r.random())
        # 每个脉冲是一个很短的不对称尖峰
        k = min(n - i, 24)
        y[i:i + k] += a * np.exp(-np.arange(k) / 4.0) * np.where(np.arange(k) < 2, 1, -0.35)
    return y


# ---------------------------------------------------------------- 混响

def reverb_ir(rt60, dur=None, seed=0, predelay=0.008, bright=6000, dark=1500,
              early=None, stereo=False, width=1.0):
    """合成房间冲激响应：几条早期反射 + 指数衰减噪声尾；高频比低频衰减更快。

    stereo=True 时左右用不同种子的噪声（去相关），但单声道相加不会抵消。"""
    dur = dur or rt60 * 1.1
    n = secs(dur)
    chans = []
    for c in range(2 if stereo else 1):
        r = rng(seed + 101 * c)
        t = tvec(n)
        w = r.standard_normal(n)
        # 把噪声分成高低两段，高段衰减更快——木头房间吸高频
        lo = lowpass(w, dark, 2)
        hi = w - lo
        hi = lowpass(hi, bright, 2)
        tail = lo * np.exp(-6.907755 * t / rt60) + 0.7 * hi * np.exp(-6.907755 * t / (rt60 * 0.45))
        ramp = np.clip(t / 0.02, 0, 1)  # 尾巴 20ms 内渐起，让早期反射先出
        tail *= ramp
        ir = np.zeros(n)
        pd = secs(predelay)
        ir[pd:] += 0.25 * tail[:n - pd]
        refl = early if early is not None else [(0.011, 0.5), (0.017, 0.38), (0.023, 0.3),
                                                 (0.031, 0.24), (0.043, 0.18), (0.057, 0.12)]
        for (d, g) in refl:
            j = secs(d * (1 + 0.07 * c * width) + 0.0013 * r.standard_normal() * width)
            if 0 < j < n:
                ir[j] += g * (1 if r.random() > 0.3 else -1)
        chans.append(ir)
    ir = np.stack(chans, axis=1) if stereo else chans[0]
    return ir / np.sqrt(np.sum(np.square(ir)) / (2 if stereo else 1))


def add_reverb(x, ir, wet, dry=1.0):
    """x 单声道或立体声；ir 单或双声道。输出长度含混响尾。"""
    if ir.ndim == 2 and x.ndim == 1:
        x = to_stereo(x)
    w = conv(x, ir)
    if x.ndim == 2 and w.ndim == 1:
        w = to_stereo(w)
    out = np.zeros_like(w)
    out[:len(x)] += dry * x
    return out + wet * w


def trim_silence(x, thresh_db=-70, keep=0.02):
    """去掉尾部低于阈值的静音（保留少许），再做 5ms 淡出。"""
    a = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)
    th = db_to_lin(thresh_db) * np.max(a)
    idx = np.nonzero(a > th)[0]
    end = min(len(x), (idx[-1] if len(idx) else len(x)) + secs(keep))
    return fade(x[:end], fout=0.005)


def circular(fn, x):
    """对循环信号做因果滤波：先拼两遍再取后一遍，滤波器的起始状态就等于循环尾巴的状态。"""
    L = len(x)
    return fn(np.concatenate([x, x], axis=0))[L:]
