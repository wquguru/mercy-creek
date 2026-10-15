"""生成 Mercy Creek 的全部程序合成音频，写到 Game/Assets/_MercyCreek/Audio/。

用法：.venv/bin/python tools/audio/build_audio.py [--only 名字前缀 ...]
确定性：所有随机数都是固定种子，重跑结果逐字节相同。
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import dsp  # noqa: E402
import piano  # noqa: E402
import sfx  # noqa: E402
import town  # noqa: E402

ROOT = HERE.parent.parent
OUT = ROOT / 'Game' / 'Assets' / '_MercyCreek' / 'Audio'


def level(x, mode, db):
    if mode == 'peak':
        return dsp.normalize_peak(x, db)
    if mode == 'rms':
        return dsp.normalize_rms(x, db, peak_ceiling_db=-1.0)
    return x


# (文件名, 生成函数, 电平方式, 目标 dB)
JOBS = [
    ('amb_saloon_loop', sfx.amb_saloon_loop, 'rms', -30.0),
    ('amb_wind_loop', sfx.amb_wind_loop, 'rms', -30.0),
    *[(f'step_wood_{i:02d}', (lambda i=i: sfx.footstep(i)), 'peak', -6.0) for i in range(1, 7)],
    ('clock_tick', lambda: sfx.clock_tick(1.0, 0), 'peak', -6.0),
    ('clock_tock', lambda: sfx.clock_tick(0.86, 1), 'peak', -6.0),
    ('door_open', sfx.door_open, 'peak', -3.0),
    ('door_close', sfx.door_close, 'peak', -2.0),
    ('glass_clink', sfx.glass_clink, 'peak', -6.0),
    ('glass_pour', sfx.glass_pour, 'peak', -8.0),
    ('bottle_set', sfx.bottle_set, 'peak', -5.0),
    ('ui_remember', sfx.ui_remember, 'peak', -6.0),
    ('ui_denied', sfx.ui_denied, 'peak', -8.0),
    ('ui_click', sfx.ui_click, 'peak', -14.0),
    ('reset_sting', sfx.reset_sting, 'peak', -1.5),
    *[(f'typewriter_key_{i:02d}', (lambda i=i: sfx.typewriter_key(i)), 'peak', -6.0) for i in range(1, 5)],
    ('typewriter_bell', sfx.typewriter_bell, 'peak', -8.0),
    ('typewriter_return', sfx.typewriter_return, 'peak', -5.0),
    ('void_hum_loop', sfx.void_hum_loop, 'rms', -30.0),
    ('ending_theme', piano.render_ending, 'peak', -3.0),
    # ---- 主街（第 2 稿起），见 docs/audio_town.md
    ('hooves_walk_loop', town.hooves_walk_loop, 'rms', -26.0),
    ('coach_roll_loop', town.coach_roll_loop, 'rms', -26.0),
    ('coach_stop', town.coach_stop, 'peak', -3.0),
    ('horse_snort_01', lambda: town.horse_snort(1), 'peak', -5.0),
    ('horse_snort_02', lambda: town.horse_snort(2), 'peak', -5.0),
    ('horse_stamp', town.horse_stamp, 'peak', -4.0),
    ('telegraph_loop', town.telegraph_loop, 'peak', -6.0),
    ('church_bell', town.church_bell, 'peak', -3.0),
    ('church_bell_three', town.church_bell_three, 'peak', -4.0),
    ('amb_street_loop', town.amb_street_loop, 'rms', -30.0),
    *[(f'step_dirt_{i:02d}', (lambda i=i: town.step_dirt(i)), 'peak', -6.0) for i in range(1, 7)],
    *[(f'step_boardwalk_{i:02d}', (lambda i=i: town.step_boardwalk(i)), 'peak', -6.0) for i in range(1, 7)],
    ('canvas_tear', town.canvas_tear, 'peak', -2.0),
    ('gate_creak', town.gate_creak, 'peak', -3.0),
]

WALTZ = {'piano_waltz_correct': piano.INTENDED,
         **{f'piano_waltz_{pc}': nm for pc, nm in piano.WRONG.items()}}


def report(name, x):
    print(f'  {name:24s} {len(x) / dsp.SR:6.2f}s  ch={1 if x.ndim == 1 else x.shape[1]}  '
          f'peak={dsp.peak_db(x):6.2f} dBFS  rms={dsp.rms_db(x):6.2f} dBFS', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*', default=None, help='只生成名字以这些前缀开头的文件')
    a = ap.parse_args()
    want = (lambda n: True) if not a.only else (lambda n: any(n.startswith(p) for p in a.only))
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for name, fn, mode, db in JOBS:
        if not want(name):
            continue
        x = level(fn(), mode, db)
        assert np.max(np.abs(x)) <= dsp.db_to_lin(-1.0) + 1e-9, name
        dsp.write_wav(OUT / f'{name}.wav', x)
        report(name, x)
    if any(want(n) for n in WALTZ):
        outs = piano.render_waltz(WALTZ)  # 共享同一个增益，5 个版本只差一个音
        for name, x in outs.items():
            dsp.write_wav(OUT / f'{name}.wav', x)
            report(name, x)
        print(f'  waltz: {piano.BPM} BPM, {piano.N_BARS} bars, loop {piano.LOOP_LEN:.4f}s, '
              f'wrong note at {piano.SPOT_TIME:.4f}s (bar {piano.SPOT_BAR + 1})')
    print(f'done in {time.time() - t0:.1f}s -> {OUT}')


if __name__ == '__main__':
    main()
