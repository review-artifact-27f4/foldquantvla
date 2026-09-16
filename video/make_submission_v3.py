#!/usr/bin/env python3
"""ICRA submission video, third cut: mostly footage, very little text.

Structure (about 150 s): title; the paper's Fig. 2 revealed step by step with one short
caption per step; Fig. 3; Fig. 1 and the Orin latency panel; then side-by-side real-robot
grids, two trials per screen, every engine in its own cell, task name on top and engine
name under each cell; a compact success summary; outro. No audio.

  python3 video/make_submission_v3.py --stills    # one PNG per static scene + one grid overlay
  python3 video/make_submission_v3.py             # video/build/submission_v3.mp4
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_overview import (BG, FPS, GREEN, GREY, INK, LINE, MUTED, RED, W, blend, canvas, ease, encode_frames, fade,  # noqa: E402
                           font, load, probe_duration, scene_outro, scene_title, text)
from make_submission_v2 import paste_faded, scene_figure  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MEDIA = ROOT / 'website' / 'media' / 'real-robot'
PAPER = HERE / 'figures' / 'paper'
BLUE = (28, 70, 170)

# Fig. 2 panels as fractions of the figure (A basis, B offline, C online) and their captions.
PANELS = [((0.004, 0.04, 0.478, 0.94), '1.  One shared scaling and rotation per activation site; every consumer folds its inverse'),
          ((0.508, 0.04, 0.992, 0.495), '2.  Fold into the weights offline, round once with GPTQ, store packed INT4'),
          ((0.508, 0.505, 0.992, 0.965), '3.  Online: fused transform + per-token quantization, native INT8 / INT4 GEMM in a TensorRT plugin')]


def scene_reveal(t, d, fig):
    """Fig. 2 appears panel by panel, in place, with a numbered caption for each step."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 78), 'Method · consistent folding (paper Fig. 2)', 26, 600, RED, 'lm', a)
    vw = 1760; vh = int(fig.height * vw / fig.width); vx, vy = 80, 150
    view = fig.resize((vw, vh), Image.LANCZOS)
    starts = [0.4, 0.4 + (d - 3) / 3, 0.4 + 2 * (d - 3) / 3]
    cover = Image.new('RGB', (vw, vh), (255, 255, 255)); cd = ImageDraw.Draw(cover)
    mask = Image.new('L', (vw, vh), 0); md = ImageDraw.Draw(mask)
    for i, ((rx0, ry0, rx1, ry1), _) in enumerate(PANELS):
        k = ease((t - starts[i]) / 0.8)
        box = (int(rx0 * vw) - 8, int(ry0 * vh) - 8, int(rx1 * vw) + 8, int(ry1 * vh) + 8)
        md.rectangle(box, fill=int(255 * (1 - k)))
    view = Image.composite(cover, view, mask)
    paste_faded(img, view, (vx, vy), a)
    for i, (_, cap) in enumerate(PANELS):
        k = a * ease((t - starts[i]) / 0.8)
        on = t >= starts[i] and (i == 2 or t < starts[i + 1])
        text(dr, (120, vy + vh + 70 + i * 52), cap, 30, 700 if on else 400, INK if on else MUTED, 'lm', k)
    return img


def wrap(dr, s, size, width):
    words, lines, cur = s.split(), [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if dr.textlength(trial, font=font(size, 400)) > width:
            lines.append(cur); cur = w
        else:
            cur = trial
    lines.append(cur)
    return lines


def grid_scene(path, task, rows, arms, threads, work, tag, duration=12.0, base_speed=4):
    """Two (or one) trial rows, one clip per engine, labels under each cell; longest clip fits `duration`."""
    n = len(arms)
    gap = 14
    cell_w = (W - 240 - gap * (n - 1)) // n
    cell_h = int(cell_w * 3 / 4)
    # never taller than the space under the header (two trial rows plus labels)
    max_h = (1060 - 190 - 96 * len(rows)) // len(rows)
    if len(rows) == 1:
        cell_w = min(cell_w, 440)
    cell_w = min(cell_w, int(max_h * 4 / 3)); cell_h = int(cell_w * 3 / 4)
    row_h = cell_h + 96
    top0 = 160 + (1060 - 160 - row_h * len(rows)) // 2 + 30
    # per-row extra speed so the longest clip finishes inside the screen time
    clips = {}
    extra = 1.0
    for r in rows:
        for arm in arms:
            p = MEDIA / task['key'] / (f'scene-{r}' if r else '') / f'{arm["key"]}.mp4'
            if not p.exists():
                raise SystemExit(f'missing clip {p}')
            clips[(r, arm['key'])] = (p, probe_duration(p))
            extra = max(extra, probe_duration(p) / (duration - 0.8))
    speed_note = f'{base_speed * extra:.0f}× speed' if extra > 1.02 else f'{base_speed}× speed'
    over = canvas(); dr = ImageDraw.Draw(over)
    text(dr, (120, 70), f'{task["title"]}', 40, 700, INK, 'lm')
    text(dr, (120, 118), f'Prompt: “{task["prompt"]}”   ·   GR00T N1.7 on Jetson AGX Orin   ·   {speed_note}' if 'π0.5' not in task['title'] else
         f'Prompt: “{task["prompt"]}”   ·   π0.5 on Jetson AGX Orin   ·   {speed_note}', 22, 400, MUTED, 'lm')
    x_left = (W - (cell_w * n + gap * (n - 1))) // 2
    layers, inputs, filters = [], ['-loop', '1', '-i', str(over_path := work / f'{tag}_overlay.png')], []
    k = 1
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
            p, dur = clips[(r, arm['key'])]
            inputs += ['-i', str(p)]
            filters.append(f'[{k}:v]setpts=(PTS-STARTPTS)/{extra:.4f},fps={FPS},scale={cell_w}:{cell_h}:force_original_aspect_ratio=increase,'
                           f'crop={cell_w}:{cell_h},format=yuv420p,tpad=stop_mode=clone:stop_duration={duration}[c{ri}_{ai}]')
            layers.append((f'c{ri}_{ai}', x, top)); k += 1
    over.save(over_path)
    chain, last = [], '0:v'
    for i, (lab, x, y) in enumerate(layers):
        chain.append(f'[{last}][{lab}]overlay={x}:{y}:shortest=0[o{i}]'); last = f'o{i}'
    fade_f = f'[{last}]trim=duration={duration},fade=t=in:st=0:d=0.4,fade=t=out:st={duration - 0.4}:d=0.4,format=yuv420p[v]'
    graph = ';'.join(filters + chain + [fade_f])
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[v]', '-an', '-r', str(FPS), '-t', str(duration),
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-threads', str(threads), str(path)]
    subprocess.run(cmd, check=True)
    return over


def scene_summary(t, d, robot):
    """Successes out of 80 across the four real-robot tasks, one bar per engine."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 78), 'Real robot · GR00T N1.7 on Jetson AGX Orin · 4 tasks × 20 episodes', 26, 600, RED, 'lm', a)
    order = ['BF16 PyTorch', 'TRT BF16 (float engine)', 'FoldQuant W8A8', 'FoldQuant W4A4', 'FoldQuant W4A4 + o/d INT8']
    arms = {r['label'].rstrip('*'): r for r in robot['results']['arms']}
    x0, x1 = 760, 1700
    for i, lab in enumerate(order):
        r = arms[lab]; tot = sum(v for v in r['tasks'] if isinstance(v, int))
        ours = lab.startswith('FoldQuant'); k = a * ease((t - 0.4 - 0.3 * i) / 0.8)
        y = 240 + i * 120
        text(dr, (120, y + 30), lab + (' (ours)' if ours else ''), 34, 700 if ours else 400, INK, 'lm', a)
        dr.rounded_rectangle((x0, y, x1, y + 60), 10, fill=blend((236, 242, 238), a))
        w = (x1 - x0) * tot / 80 * k
        dr.rounded_rectangle((x0, y, x0 + max(w, 12), y + 60), 10, fill=blend(GREEN if ours else GREY, a))
        text(dr, (x0 + max(w, 12) - 16, y + 30), f'{tot}/80', 30, 700, (255, 255, 255), 'rm', k)
    text(dr, (120, 880), 'Orin latency for N1.7: float engine 146 ms · W8A8 127 ms · W4A4 119 ms · W4A4 + o/d INT8 120 ms.', 26, 400, INK, 'lm', a)
    text(dr, (120, 930), 'ModelOpt W8A8 SmoothQuant reached 6/20 on the hardest task and was stopped; not in the totals.', 24, 400, MUTED, 'lm', a)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', default=str(HERE / 'build' / 'submission_v3.mp4'))
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--crf', type=int, default=23)
    args = ap.parse_args()
    meta, robot = load('metadata'), load('real_robot')
    P = lambda n: Image.open(PAPER / f'{n}.png').convert('RGB')  # noqa: E731
    fig_teaser, fig_over, fig_exec, fig_lat = (P(n) for n in ('teaser', 'fig_overview', 'fig_excute', 'latency'))
    fig_over.thumbnail((7400, 2500))
    # Fig. 3 as two separate images, so the camera cannot show one panel's edge behind the other
    fig_exec_a = fig_exec.crop((0, 0, fig_exec.width, int(fig_exec.height * 0.345)))
    fig_exec_b = fig_exec.crop((0, int(fig_exec.height * 0.37), fig_exec.width, fig_exec.height))
    comps = {c['key']: c for c in robot['comparisons'] + robot.get('comparisons_pi05', [])}
    FULL = (0.0, 0.0, 1.0, 1.0)
    head = [('title', 4.5, lambda t, d: scene_title(t, d, meta)),
            ('reveal', 16.0, lambda t, d: scene_reveal(t, d, fig_over)),
            ('arch_a', 5.0, lambda t, d: scene_figure(t, d, fig_exec_a, 'Paper Fig. 3(a) · policy execution', [(FULL, 1.0, None)],
                                                    'Only the projection GEMMs of the language backbone and the action expert run in low bits.')),
            ('arch_b', 8.0, lambda t, d: scene_figure(t, d, fig_exec_b, 'Paper Fig. 3(b) · one transform per activation site', [(FULL, 1.0, None)],
                                                    'Offline: one T per site, every consumer folded and packed. Online: one fused prologue, one shared quantized activation.')),
            ('teaser', 8.0, lambda t, d: scene_figure(t, d, fig_teaser, 'Paper Fig. 1 · GR00T N1.7', [(FULL, 1.0, None)],
                                                    'Faster than the float TensorRT engine on Jetson AGX Orin; real-robot success at the float level.')),
            ('latency', 8.0, lambda t, d: scene_figure(t, d, fig_lat, 'Paper Fig. 4(b) · Jetson AGX Orin · batch 1', [((0.5, 0.0, 1.0, 0.86), 1.0, None)],
                                                     'W4A4 is 1.20–1.33× faster than the float engine; weight-only AWQ is slower than it.', view=(500, 150, 1420, 990)))]
    grids = [('so101-blue-on-red', [1, 2]), ('so101-blue-on-red', [3, 4]),
             ('so101-banana', [1, 2]), ('so101-banana', [3, 4]),
             ('so101-blocks-cup', [1, 2]), ('so101-blocks-cup', [3, 4]),
             ('aloha-banana', [None]),
             ('pi05-so101-blue-on-red', [1, 2])]
    tail = [('summary', 7.0, lambda t, d: scene_summary(t, d, robot)),
            ('outro', 4.0, lambda t, d: scene_outro(t, d, meta))]
    grid_d = 12.0
    total = sum(s[1] for s in head + tail) + grid_d * len(grids)
    print(f'planned duration {total:.1f} s')
    if total > 180:
        raise SystemExit('over 180 s')
    if args.stills:
        out = HERE / 'build' / 'stills_v3'; out.mkdir(parents=True, exist_ok=True)
        for name, dur, fn in head + tail:
            fn(dur * 0.6, dur).save(out / f'{name}.png')
        with tempfile.TemporaryDirectory() as tmp:
            key, rows = grids[0]
            grid_scene(Path(tmp) / 'g.mp4', comps[key], rows, comps[key]['arms'], args.threads, Path(tmp), 'g', grid_d)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '6', '-i', str(Path(tmp) / 'g.mp4'), '-frames:v', '1', str(out / 'grid_sample.png')], check=True)
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
    size = out.stat().st_size / 1e6
    print(f'wrote {out} ({size:.1f} MB)')


if __name__ == '__main__':
    main()
