"""音频评审：给每个 WAV 出"波形 + 频谱"图到 Reviews/audio/，用 ffmpeg astats 量峰值 / RMS，
检查循环接缝，并核对华尔兹 5 个版本只在错音处不同。

用法：.venv/bin/python tools/audio/review_audio.py
"""
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import piano  # noqa: E402

ROOT = HERE.parent.parent
AUDIO = ROOT / 'Game' / 'Assets' / '_MercyCreek' / 'Audio'
REV = ROOT / 'Reviews' / 'audio'
SR = 48000
LOOPS = ['amb_saloon_loop', 'amb_wind_loop', 'void_hum_loop', 'piano_waltz_correct', 'piano_waltz_E']


def read(p):
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 32768
        return x.reshape(-1, w.getnchannels())


def write(p, x):
    q = np.clip(np.round(x * 32768), -32768, 32767).astype('<i2')
    with wave.open(str(p), 'wb') as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(q.tobytes())


def picture(src, dst, title):
    # showspectrumpic 带坐标时左右各多 142px（1200 -> 1484），波形按同样留边对齐时间轴
    fc = ("[0:a]asplit[a][b];"
          "[a]showwavespic=s=1200x220:split_channels=1:colors=0x3b6ea8|0xa85a3b:scale=lin,"
          "pad=1484:220:142:0:black[w];"
          "[b]showspectrumpic=s=1200x360:legend=1:color=intensity:scale=log:fscale=log:start=30:stop=16000[s];"
          "[w][s]vstack[o]")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-filter_complex', fc, '-map', '[o]',
                    '-frames:v', '1', str(dst)], check=True)


def astats(src):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(src), '-af',
                        'astats=measure_perchannel=none:measure_overall=Peak_level+RMS_level', '-f', 'null', '-'],
                       capture_output=True, text=True)
    pk = re.findall(r'Peak level dB: (-?[\d.inf]+)', r.stderr)
    rm = re.findall(r'RMS level dB: (-?[\d.inf]+)', r.stderr)
    return float(pk[-1]), float(rm[-1])


def seam(name, x):
    """把循环拼两遍，看接缝处的样本跳变与短时能量是否异常。"""
    L = len(x)
    xx = np.concatenate([x, x])
    d = np.abs(np.diff(xx, axis=0)).max(axis=1)
    jump = d[L - 1]
    typical = np.percentile(d, 99.9)
    w = SR // 100  # 10ms 能量
    e = np.sqrt(np.convolve(np.mean(xx ** 2, axis=1), np.ones(w) / w, mode='same'))
    around = e[L - SR // 2:L + SR // 2]
    ratio = around.max() / max(np.median(e), 1e-12)
    ratio_all = np.percentile(e, 99.9) / max(np.median(e), 1e-12)
    seg = xx[L - SR:L + SR]
    write(REV / f'{name}__seam.wav', seg)
    picture(REV / f'{name}__seam.wav', REV / f'{name}__seam.png', f'{name} seam (center = loop point)')
    (REV / f'{name}__seam.wav').unlink()
    ok = jump <= typical * 1.05 and ratio <= ratio_all * 1.05
    print(f'  seam {name:22s} jump={jump:.5f} (p99.9 step {typical:.5f})  '
          f'energy@seam/median={ratio:.2f} (p99.9 overall {ratio_all:.2f})  {"OK" if ok else "CHECK"}')


def main():
    REV.mkdir(parents=True, exist_ok=True)
    files = sorted(AUDIO.glob('*.wav'))
    print(f'{"file":26s} {"dur":>7s} {"ch":>2s} {"peak":>8s} {"rms":>8s}')
    for f in files:
        x = read(f)
        pk, rm = astats(f)
        print(f'{f.stem:26s} {len(x) / SR:7.2f} {x.shape[1]:2d} {pk:8.2f} {rm:8.2f}'
              + ('  !! >-1dBFS' if pk > -1.0 else '') + ('  !! silent' if rm < -60 else ''))
        picture(f, REV / f'{f.stem}.png', f.stem)
    print('loop seams:')
    for n in LOOPS:
        seam(n, read(AUDIO / f'{n}.wav'))
    print('waltz variants (first differing sample vs correct):')
    ref = read(AUDIO / 'piano_waltz_correct.wav')
    for pc in piano.WRONG:
        v = read(AUDIO / f'piano_waltz_{pc}.wav')
        diff = np.nonzero(np.abs(v - ref).max(axis=1) > 2 / 32768)[0]
        print(f'  {pc}: first diff at {diff[0] / SR:.4f}s (spec {piano.SPOT_TIME:.4f}s), '
              f'last diff at {diff[-1] / SR:.2f}s')
    # 错音附近 4 秒的特写，五个版本竖排
    clips = []
    for nm in ['correct'] + list(piano.WRONG):
        x = read(AUDIO / f'piano_waltz_{nm}.wav')
        a = int((piano.SPOT_TIME - 1.0) * SR)
        p = REV / f'_spot_{nm}.wav'
        write(p, x[a:a + 4 * SR])
        picture(p, REV / f'_spot_{nm}.png', f'waltz {nm}: {piano.SPOT_TIME - 1:.2f}s..+4s (wrong note at +1.00s)')
        p.unlink()
        clips.append(REV / f'_spot_{nm}.png')
    args = sum([['-i', str(c)] for c in clips], [])
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *args, '-filter_complex',
                    f'vstack=inputs={len(clips)}', str(REV / 'waltz_spot_compare.png')], check=True)
    for c in clips:
        c.unlink()


if __name__ == '__main__':
    main()
