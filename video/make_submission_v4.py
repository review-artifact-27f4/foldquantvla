#!/usr/bin/env python3
"""ICRA submission video, fourth cut: v3's footage-first structure plus the paper's own
equations as short subtitled excerpts, the desktop latency panel, a storage/memory chart,
Success/Fail badges on the robot grids (from outcomes.json; cells without an entry get no
badge) and a closing card in success-rate percent. No audio.

  python3 video/make_submission_v4.py --stills    # one PNG per static scene + a grid sample
  python3 video/make_submission_v4.py             # video/build/submission_v4.mp4
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_overview import (FPS, GREEN, GREY, INK, LINE, MUTED, RED, W, blend, canvas, ease, encode_frames, fade,  # noqa: E402
                           font, load, probe_duration, scene_outro, scene_title, text)
from make_submission_v2 import paste_faded, scene_figure  # noqa: E402
from make_submission_v3 import BLUE, scene_reveal  # noqa: E402
import make_submission_v3 as v3  # noqa: E402

v3.PANELS = [(v3.PANELS[0][0], 'Scaling:  one shared channel scaling + rotation per activation site moves the outliers into the weights'),
             (v3.PANELS[1][0], 'Offline:  fold the transform into every consumer, round once with GPTQ, store packed INT4'),
             (v3.PANELS[2][0], 'Online:  fused transform + per-token quantization, native INT8 / INT4 GEMM, one output rescale')]

HERE = Path(__file__).resolve().parent
MEDIA = HERE.parent / 'website' / 'media' / 'real-robot'
PAPER = HERE / 'figures' / 'paper'
OUTCOMES = json.loads((HERE / 'outcomes.json').read_text(encoding='utf-8'))


def draw_badge(dr, xy, ok):
    """Small Success/Fail pill at the top-left corner of a cell (shapes, not glyphs)."""
    x, y = xy
    label = 'Success' if ok else 'Fail'
    f = font(20, 700); tw = int(dr.textlength(label, font=f))
    w, h = tw + 58, 36
    dr.rounded_rectangle((x, y, x + w, y + h), 18, fill=(GREEN if ok else RED) + (235,))
    if ok:
        dr.line((x + 14, y + 19, x + 21, y + 26, x + 33, y + 11), fill=(255, 255, 255, 255), width=4, joint='curve')
    else:
        dr.line((x + 15, y + 11, x + 31, y + 26), fill=(255, 255, 255, 255), width=4)
        dr.line((x + 31, y + 11, x + 15, y + 26), fill=(255, 255, 255, 255), width=4)
    dr.text((x + 42, y + h // 2), label, font=f, fill=(255, 255, 255, 255), anchor='lm')


def grid_scene(path, task, rows, arms, threads, work, tag, duration=11.0, base_speed=4):
    """Trial rows × engines, labels under each cell; badges fade in for the last BADGE_AT seconds."""
    n = len(arms)
    gap = 14
    margin = 60 if n >= 7 else 120
    cell_w = (W - 2 * margin - gap * (n - 1)) // n
    max_h = (1060 - 190 - 96 * len(rows)) // len(rows)
    if len(rows) == 1:
        cell_w = min(cell_w, 440)
    cell_w = min(cell_w, int(max_h * 4 / 3)); cell_h = int(cell_w * 3 / 4)
    row_h = cell_h + 96
    top0 = 160 + (1060 - 160 - row_h * len(rows)) // 2 + 30
    clips, extra = {}, 1.0
    for r in rows:
        for arm in arms:
            p = MEDIA / task['key'] / (f'scene-{r}' if r else '') / f'{arm["key"]}.mp4'
            if not p.exists():
                raise SystemExit(f'missing clip {p}')
            clips[(r, arm['key'])] = (p, probe_duration(p))
            extra = max(extra, probe_duration(p) / (duration - 1.2))
    speed_note = f'{base_speed * extra:.0f}× speed' if extra > 1.02 else f'{base_speed}× speed'
    policy = 'π0.5' if 'π0.5' in task['title'] else 'GR00T N1.7'
    over = canvas(); dr = ImageDraw.Draw(over)
    badge_layers = []   # (path, x, y, appears_at): one small badge per cell, shown when that clip ends
    text(dr, (120, 70), task['title'], 40, 700, INK, 'lm')
    text(dr, (120, 118), f'Prompt: “{task["prompt"]}”   ·   {policy} on Jetson AGX Orin   ·   {speed_note}', 22, 400, MUTED, 'lm')
    x_left = (W - (cell_w * n + gap * (n - 1))) // 2
    over_path = work / f'{tag}_overlay.png'
    inputs, filters, layers = ['-loop', '1', '-i', str(over_path)], [], []
    k = 1
    known = OUTCOMES.get(task['key'], {})
    for ri, r in enumerate(rows):
        top = top0 + ri * row_h
        if r:
            text(dr, (x_left, top - 22), f'Trial {r}', 24, 700, BLUE, 'lm')
        for ai, arm in enumerate(arms):
            x = x_left + ai * (cell_w + gap)
            ours = arm['key'].startswith('foldquant')
            dr.rounded_rectangle((x - 3, top - 3, x + cell_w + 3, top + cell_h + 3), 8, fill=GREEN if ours else LINE)
            lab = arm['label'].replace('*', '') + (' (ours)' if ours else '')
            size = 22 if n <= 5 else 19
            while dr.textlength(lab, font=font(size, 700)) > cell_w and size > 14:
                size -= 1
            text(dr, (x + cell_w // 2, top + cell_h + 28), lab, size, 700 if ours else 400, INK, 'mm')
            verified = task.get('outcomes', {}).get(str(r or 0), {}).get(arm['key'])  # from the page's mapping table
            outcome = known.get(str(r or 0), {}).get(arm['key'], {'success': True, 'fail': False}.get(verified, OUTCOMES.get('_default_by_arm', {}).get(arm['key'], OUTCOMES.get('_default'))))
            p, dur = clips[(r, arm['key'])]
            if outcome is not None:
                b = Image.new('RGBA', (200, 48), (0, 0, 0, 0)); draw_badge(ImageDraw.Draw(b), (2, 2), outcome)
                bpath = work / f'{tag}_badge_{ri}_{ai}.png'; b.save(bpath)
                badge_layers.append((bpath, x + 8, top + 8, min(dur / extra, duration - 1.0)))
            inputs += ['-i', str(p)]
            filters.append(f'[{k}:v]setpts=(PTS-STARTPTS)/{extra:.4f},fps={FPS},scale={cell_w}:{cell_h}:force_original_aspect_ratio=increase,'
                           f'crop={cell_w}:{cell_h},format=yuv420p,tpad=stop_mode=clone:stop_duration={duration}[c{ri}_{ai}]')
            layers.append((f'c{ri}_{ai}', x, top)); k += 1
    over.save(over_path)
    chain, last = [], '0:v'
    for i, (lab, x, y) in enumerate(layers):
        chain.append(f'[{last}][{lab}]overlay={x}:{y}:shortest=0[o{i}]'); last = f'o{i}'
    for j, (bpath, x, y, at) in enumerate(badge_layers):
        inputs += ['-loop', '1', '-i', str(bpath)]
        chain.append(f'[{k}:v]format=rgba,fade=t=in:st={at:.2f}:d=0.3:alpha=1[b{j}]')
        chain.append(f'[{last}][b{j}]overlay={x}:{y}:shortest=0[ob{j}]'); last = f'ob{j}'; k += 1
    fade_f = f'[{last}]trim=duration={duration},fade=t=in:st=0:d=0.4,fade=t=out:st={duration - 0.4}:d=0.4,format=yuv420p[v]'
    graph = ';'.join(filters + chain + [fade_f])
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[v]', '-an', '-r', str(FPS), '-t', str(duration),
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-threads', str(threads), str(path)]
    subprocess.run(cmd, check=True)


def scene_pair(t, d, panel, eqs, kicker, lines):
    """One Fig. 2 panel on the left, the paper's numbered equations on the right, and the
    explanation appearing line by line underneath (each line is one step, like the captions in v3)."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 78), kicker, 26, 600, RED, 'lm', a)
    # left: the panel, fitted into 1040 x 560
    bw, bh = 1040, 560
    sc = min(bw / panel.width, bh / panel.height)
    pw, ph = int(panel.width * sc), int(panel.height * sc)
    px, py = 120 + (bw - pw) // 2, 130 + (bh - ph) // 2
    paste_faded(img, panel.resize((pw, ph), Image.LANCZOS), (px, py), a)
    # right: equations, one under the other, each sliding in
    ex0, ew = 1200, 600
    y = 130 + (bh - sum(min(int(e.height * ew / e.width), 260) for e, _ in eqs) - 40 * (len(eqs) - 1)) // 2
    for i, (e, tag) in enumerate(eqs):
        k = a * ease((t - 0.5 - 0.7 * i) / 0.7)
        ss = min(ew / e.width, 260 / e.height)
        w, h = int(e.width * ss), int(e.height * ss)
        text(dr, (ex0, y - 14), tag, 20, 700, MUTED, 'lm', k)
        paste_faded(img, e.resize((w, h), Image.LANCZOS), (ex0 + int(30 * (1 - k)), y), k)
        y += h + 40
    # explanation, numbered, one line at a time
    starts = [0.4 + i * (d - 3.5) / len(lines) for i in range(len(lines))]
    for i, ln in enumerate(lines):
        k = a * ease((t - starts[i]) / 0.7)
        on = t >= starts[i] and (i == len(lines) - 1 or t < starts[i + 1])
        text(dr, (120, 750 + i * 50), f'{i + 1}.  {ln}', 28, 700 if on else 400, INK if on else MUTED, 'lm', k)
    return img


def hbar_group(dr, a, k, y, title, rows, x0=700, x1=1720, vmax=None, unit='MB'):
    """One titled group of horizontal bars: rows = [(label, value, ours)]."""
    text(dr, (120, y), title, 28, 700, INK, 'lm', a)
    vmax = vmax or max(v for _, v, _ in rows)
    for i, (lab, v, ours) in enumerate(rows):
        yy = y + 44 + i * 58
        text(dr, (120, yy + 20), lab + (' (ours)' if ours else ''), 26, 700 if ours else 400, INK, 'lm', a)
        dr.rounded_rectangle((x0, yy, x1, yy + 40), 8, fill=blend((236, 242, 238), a))
        w = (x1 - x0) * v / vmax * k
        dr.rounded_rectangle((x0, yy, x0 + max(w, 8), yy + 40), 8, fill=blend(GREEN if ours else GREY, a))
        text(dr, (x0 + max(w, 8) + 14, yy + 20), f'{v:,} {unit}', 24, 700, INK, 'lm', a * k)
    return y + 44 + len(rows) * 58


def scene_memory(t, d):
    """Storage and resident memory, GR00T N1.6 (paper Sec. VI, 'Storage and resident memory')."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d); k = ease((t - 0.3) / 0.9)
    text(dr, (120, 78), 'Storage and resident memory · GR00T N1.6 (paper Sec. VI)', 26, 600, RED, 'lm', a)
    y = hbar_group(dr, a, k, 150, 'Quantized weight storage', [('Float TensorRT', 3802, False), ('FoldQuant W8A8', 2104, True), ('FoldQuant W4A4', 1011, True), ('FoldQuant W4A4 + o/d INT8', 1189, True)], vmax=6400)
    y = hbar_group(dr, a, k, y + 26, 'Serialized TensorRT plan (kernels + workspace included)', [('Float TensorRT', 5325, False), ('FoldQuant W4A4', 2525, True)], vmax=6400)
    y = hbar_group(dr, a, k, y + 26, 'Resident GPU memory, replaced weights never materialized', [('Float TensorRT', 6349, False), ('FoldQuant W4A4', 4673, True)], vmax=6400, unit='MiB')
    text(dr, (120, 1000), 'Weights 3.8× smaller and the plan 2.1× smaller at W4A4; resident memory falls by 1.7 GiB (6349 → 4673 MiB).', 25, 400, MUTED, 'lm', a)
    return img


def scene_summary(t, d, robot):
    """Success rate in percent across the four real-robot tasks, one bar per engine."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 78), 'Real robot · GR00T N1.7 on Jetson AGX Orin · 4 tasks × 20 episodes · success rate', 26, 600, RED, 'lm', a)
    order = ['BF16 PyTorch', 'TRT BF16 (float engine)', 'FoldQuant W8A8', 'FoldQuant W4A4', 'FoldQuant W4A4 + o/d INT8']
    arms = {r['label'].rstrip('*'): r for r in robot['results']['arms']}
    x0, x1 = 760, 1700
    for i, lab in enumerate(order):
        r = arms[lab]; tot = sum(v for v in r['tasks'] if isinstance(v, int)); pct = tot / 80 * 100
        ours = lab.startswith('FoldQuant'); k = a * ease((t - 0.4 - 0.3 * i) / 0.8)
        y = 190 + i * 112
        text(dr, (120, y + 30), lab + (' (ours)' if ours else ''), 34, 700 if ours else 400, INK, 'lm', a)
        dr.rounded_rectangle((x0, y, x1, y + 60), 10, fill=blend((236, 242, 238), a))
        w = (x1 - x0) * pct / 100 * k
        dr.rounded_rectangle((x0, y, x0 + max(w, 12), y + 60), 10, fill=blend(GREEN if ours else GREY, a))
        text(dr, (x0 + max(w, 12) - 16, y + 30), f'{pct:.1f}%', 30, 700, (255, 255, 255), 'rm', k)
    pi = {r['label']: r['n'] for r in robot['results_pi05']['arms']}
    text(dr, (120, 800), f'π0.5 · SO-101 blue on red: BF16 PyTorch {pi["BF16 PyTorch"] / 20 * 100:.0f}% · TRT BF16 {pi["TRT BF16 (float engine)"] / 20 * 100:.0f}% · FoldQuant W4A4 {pi["FoldQuant W4A4"] / 20 * 100:.0f}%.', 27, 400, INK, 'lm', a)
    text(dr, (120, 850), 'Orin latency for N1.7: float engine 146 ms · W8A8 127 ms · W4A4 119 ms · W4A4 + o/d INT8 120 ms.', 27, 400, INK, 'lm', a)
    partial = [r for r in robot['results']['arms'] if any(not isinstance(v, int) for v in r['tasks'])]
    note = ' · '.join(f"{r['label'].rstrip('*')} {[v for v in r['tasks'] if isinstance(v, int)][0]}/20" for r in partial)
    text(dr, (120, 900), f'Run on the hardest task only (SO-101 blue on red): {note}; not in the totals.', 24, 400, MUTED, 'lm', a)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', default=str(HERE / 'build' / 'submission_v4.mp4'))
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--crf', type=int, default=23)
    args = ap.parse_args()
    meta, robot = load('metadata'), load('real_robot')
    P = lambda n: Image.open(PAPER / f'{n}.png').convert('RGB')  # noqa: E731
    fig_teaser, fig_over, fig_exec, fig_lat = (P(n) for n in ('teaser', 'fig_overview', 'fig_excute', 'latency'))
    panel = {n: P(f'fig_overview_{n}') for n in 'ABC'}
    eq = {n: P(f'eq_{n}') for n in ('fold', 'family', 'norm', 'quant', 'gptq')}
    fig_over.thumbnail((7400, 2500))
    fig_exec_a = fig_exec.crop((0, 0, fig_exec.width, int(fig_exec.height * 0.345)))
    fig_exec_b = fig_exec.crop((0, int(fig_exec.height * 0.37), fig_exec.width, fig_exec.height))
    comps = {c['key']: c for c in robot['comparisons'] + robot.get('comparisons_pi05', [])}
    FULL = (0.0, 0.0, 1.0, 1.0)
    head = [('title', 4.5, lambda t, d: scene_title(t, d, meta)),
            ('reveal', 10.0, lambda t, d: scene_reveal(t, d, fig_over)),
            ('basis', 12.0, lambda t, d: scene_pair(t, d, panel['A'], [(eq['fold'], 'Consistent fold, Eq. (2)'), (eq['family'], 'Transform family, Eq. (3)')],
                                                   'Paper Fig. 2(A) + Sec. III-B/C · outliers: one shared basis per activation site',
                                                   ['Channel scaling moves the activation outliers into the weights: the columns of W absorb S.',
                                                    'The orthogonal rotation R spreads the remaining peaks across channels (toy example: max/RMS 26.9 → 3.1).',
                                                    'Every consumer of the site folds the inverse transform (Eq. 2), so the product WX is unchanged before rounding.'])),
            ('runtime', 12.0, lambda t, d: scene_pair(t, d, panel['C'], [(eq['gptq'], 'Offline rounding, Eq. (7)'), (eq['quant'], 'Per-token activation quantization, Eq. (5)')],
                                                     'Paper Fig. 2(C) + Sec. III-E/F · fold for the runtime: fused prologue, native integer GEMM',
                                                     ['Offline: folded weights rounded once with GPTQ (Eq. 7), stored as packed INT4 with one scale per output channel.',
                                                      'Online: one fused prologue applies the rotation and scaling, then quantizes each token with its own scale (Eq. 5).',
                                                      'Native INT8 / INT4 GEMM in the TensorRT plugin: INT32 accumulation, one rescale, no dequantized weights, no extra pass.'])),
            ('teaser', 6.0, lambda t, d: scene_figure(t, d, fig_teaser, 'Paper Fig. 1 · GR00T N1.7', [(FULL, 1.0, None)],
                                                    'Faster than the float TensorRT engine on Jetson AGX Orin; real-robot success at the float level.')),
            ('latency', 12.0, lambda t, d: scene_figure(t, d, fig_lat, 'Paper Fig. 4 · observation-to-action latency · batch 1', [(FULL, 1.0, None)],
                                                     '(a) RTX 4070 Ti SUPER, (b) Jetson AGX Orin. W4A4 is 1.25–1.52× (desktop) and 1.20–1.33× (Orin) faster than the compiled float engine.')),
            ('memory', 6.0, scene_memory)]
    grids = [('so101-blue-on-red', [1, 3]), ('so101-blue-on-red', [2, 4]),
             ('so101-banana', [1, 2]), ('so101-banana', [3, 5]),
             ('so101-blocks-cup', [1, 2]), ('so101-blocks-cup', [3, 4]),
             ('aloha-banana', [1, 2]),
             ('pi05-so101-blue-on-red', [1, 3])]
    tail = [('summary', 6.0, lambda t, d: scene_summary(t, d, robot)),
            ('outro', 4.0, lambda t, d: scene_outro(t, d, meta))]
    grid_d = 12.0
    total = sum(s[1] for s in head + tail) + grid_d * len(grids)
    print(f'planned duration {total:.1f} s')
    if total > 180:
        raise SystemExit('over 180 s')
    if args.stills:
        out = HERE / 'build' / 'stills_v4'; out.mkdir(parents=True, exist_ok=True)
        for name, dur, fn in head + tail:
            fn(dur * 0.6, dur).save(out / f'{name}.png')
        with tempfile.TemporaryDirectory() as tmp:
            key, rows = grids[0]
            grid_scene(Path(tmp) / 'g.mp4', comps[key], rows, comps[key]['arms'], args.threads, Path(tmp), 'g', grid_d)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(grid_d - 1), '-i', str(Path(tmp) / 'g.mp4'), '-frames:v', '1', str(out / 'grid_sample.png')], check=True)
        print('stills in', out); return
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp); parts = []
        def render(name, dur, fn):
            part = work / f'{len(parts):02d}_{name}.mp4'; encode_frames(part, dur, fn, args.threads); parts.append(part); print('rendered', name)
        for name, dur, fn in head:
            render(name, dur, fn)
        for i, (key, rows) in enumerate(grids):
            part = work / f'{len(parts):02d}_grid{i}.mp4'
            grid_scene(part, comps[key], rows, comps[key]['arms'], args.threads, work, f'grid{i}', grid_d); parts.append(part); print('rendered grid', key, rows)
        for name, dur, fn in tail:
            render(name, dur, fn)
        listing = work / 'list.txt'; listing.write_text(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c:v', 'libx264', '-preset', 'slow',
                        '-crf', str(args.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-threads', str(args.threads), str(out)], check=True)
    print(f'wrote {out} ({out.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
