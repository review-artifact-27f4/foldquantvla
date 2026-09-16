#!/usr/bin/env python3
"""ICRA submission video, second cut: the paper's own typesetting instead of slide cards.

Method and results are shown as excerpts rendered from main.tex (paper_excerpts.py):
equations, Proposition 2 with its proof, and the manuscript's tables, panned slowly at
reading size. Figures are the paper's PDFs at 600 dpi. Overlay text is limited to a
small kicker and one takeaway line per scene, so nothing on screen is invented.

  python3 video/paper_excerpts.py --paper <overleaf dir>     # once, after the paper changes
  python3 video/make_submission_v2.py --stills                # layout check
  python3 video/make_submission_v2.py                         # video/build/submission_v2.mp4
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_overview import (BG, GREY, INK, LINE, MUTED, RED, W, H, blend, camera, canvas, ease, encode_frames, fade,  # noqa: E402
                           font, load, robot_scene, scene_outro, scene_title, text)

HERE = Path(__file__).resolve().parent
PAPER = HERE / 'figures' / 'paper'
CONTENT = (120, 150, 1800, 990)   # x0, y0, x1, y1 of the content area


def frame(dr, a, kicker, takeaway=None):
    text(dr, (120, 78), kicker, 26, 600, RED, 'lm', a)
    dr.line((120, 108, 1800, 108), fill=blend(LINE, a), width=1)
    if takeaway:
        dr.line((120, 1008, 1800, 1008), fill=blend(LINE, a), width=1)
        size = 26
        while size > 19 and dr.textlength(takeaway, font=font(size, 400)) > 1680:
            size -= 1
        text(dr, (120, 1042), takeaway, size, 400, INK, 'lm', a)


def paste_faded(img, piece, xy, a):
    if a < 1:
        piece = Image.blend(Image.new('RGB', piece.size, BG), piece, a)
    img.paste(piece, xy)


def scene_excerpt(t, d, ex, kicker, takeaway):
    """A manuscript excerpt at reading size; tall excerpts pan from top to bottom."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    x0, y0, x1, y1 = CONTENT
    vw, vh = x1 - x0, y1 - y0
    scale = min(vw / ex.width, 1640 / ex.width)
    sw, sh = int(ex.width * scale), int(ex.height * scale)
    small = ex.resize((sw, sh), Image.LANCZOS) if sh <= vh else None
    if small is not None:
        paste_faded(img, small, (x0 + (vw - sw) // 2, y0 + (vh - sh) // 2), a)
    else:
        # read from the top, pause, then glide to the bottom
        p = ease((t - 0.2 * d) / (0.6 * d))
        top = int((sh - vh) * p)
        crop = ex.resize((sw, sh), Image.LANCZOS).crop((0, top, sw, top + vh))
        paste_faded(img, crop, (x0 + (vw - sw) // 2, y0), a)
    frame(dr, a, kicker, takeaway)
    return img


def scene_figure(t, d, fig, kicker, shots, takeaway=None, view=None):
    """Camera moves between `shots` = [(region, until_fraction, caption)] over the figure."""
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    x0, y0, x1, y1 = view or CONTENT
    vw, vh = x1 - x0, y1 - y0
    frac = t / d
    idx = next((i for i, s in enumerate(shots) if frac < s[1]), len(shots) - 1)
    start = 0.0 if idx == 0 else shots[idx - 1][1]
    k = ease((frac - start) * d / 0.9) if idx else 1.0
    prev = shots[max(0, idx - 1)][0]; target = shots[idx][0]
    c0, c1 = camera(fig, prev, vw, vh), camera(fig, target, vw, vh)
    cx, cy, w, h = (c0[i] + (c1[i] - c0[i]) * k for i in range(4))
    fw, fh = fig.size
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    sx0, sy0, sx1, sy1 = max(0, box[0]), max(0, box[1]), min(fw, box[2]), min(fh, box[3])
    scale = vw / w
    crop = fig.crop((int(sx0), int(sy0), int(sx1), int(sy1)))
    crop = crop.resize((max(1, int((sx1 - sx0) * scale)), max(1, int((sy1 - sy0) * scale))), Image.BILINEAR)
    piece = Image.new('RGB', (vw, vh), (255, 255, 255)); piece.paste(crop, (int((sx0 - box[0]) * scale), int((sy0 - box[1]) * scale)))
    paste_faded(img, piece, (x0, y0), a)
    cap = shots[idx][2]
    frame(dr, a, kicker, cap or takeaway)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(HERE / 'submission.json'))
    ap.add_argument('--output', default=str(HERE / 'build' / 'submission_v2.mp4'))
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--crf', type=int, default=23)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    meta, robot = load('metadata'), load('real_robot')
    P = lambda n: Image.open(PAPER / f'{n}.png').convert('RGB')  # noqa: E731
    ex = {n: P(f'ex_{n}') for n in ('fold', 'transforms', 'norm', 'quant', 'rounding', 'selective')}
    tab = {n: P(f'tab_{n}') for n in ('sota', 'success', 'ablation', 'robot', 'robot_pi', 'simpler')}
    fig_teaser, fig_over, fig_exec, fig_lat, fig_fid, fig_tasks = (P(n) for n in ('teaser', 'fig_overview', 'fig_excute', 'latency', 'fidelity', 'fig_real_tasks_compact'))
    fig_over.thumbnail((7400, 2500))  # 14.8k px wide is more than the camera ever needs
    FULL = (0.0, 0.0, 1.0, 1.0)
    scenes = [
        ('title', 4.5, lambda t, d: scene_title(t, d, meta)),
        ('teaser', 6.0, lambda t, d: scene_figure(t, d, fig_teaser, 'Fig. 1 · FoldQuantVLA at a glance · GR00T N1.7', [(FULL, 1.0, None)],
                                                 'Four-bit engines on Jetson AGX Orin: faster than the float engine, real-robot success at the float level.')),
        ('arch', 6.0, lambda t, d: scene_figure(t, d, fig_exec, 'Fig. 3(a) · Policy execution', [((0.0, 0.0, 1.0, 0.34), 1.0, None)],
                                               'Only the projection GEMMs of the language backbone and the action expert run in low bits; one engine serves every denoising step.')),
        ('fold', 9.0, lambda t, d: scene_excerpt(t, d, ex['fold'], 'Method · Sec. III-B · A consistent fold',
                                                 'One transform per activation site, and every consumer folds its inverse: calibration, rounding and execution share one basis.')),
        ('transforms', 8.0, lambda t, d: scene_excerpt(t, d, ex['transforms'], 'Method · Sec. III-C · Transforms supported by the runtime',
                                                       'Diagonal scale, orthogonal rotation, diagonal scale (Eq. 3); fold-before and fold-after are both exact before rounding.')),
        ('overview', 11.0, lambda t, d: scene_figure(t, d, fig_over, 'Fig. 2 · Fold offline, execute in low bits',
                                                    [(FULL, 0.2, None), ((0.004, 0.04, 0.478, 0.94), 0.47, '(A) Channel scaling migrates outliers into the weights; the shared rotation spreads the remaining peaks.'),
                                                     ((0.508, 0.04, 0.992, 0.495), 0.74, '(B) Offline: the folded weight is rounded once to INT4 with per-row scales and nibble-packed.'),
                                                     ((0.508, 0.505, 0.992, 0.965), 1.0, '(C) Online: the fused prologue quantizes per token, the integer GEMM accumulates in INT32, the output is rescaled.')])),
        ('norm', 8.0, lambda t, d: scene_excerpt(t, d, ex['norm'], 'Method · Sec. III-D · Normalization gains and the block Hadamard transform',
                                                'Scales absorb into the RMSNorm gain where one exists; the 64-wide block Hadamard runs as an FWHT inside the plugin.')),
        ('quant', 10.0, lambda t, d: scene_excerpt(t, d, ex['quant'], 'Method · Sec. III-E · Per-token quantizer and Proposition 2',
                                                  'Each token supplies its own scale, so one calibration and one engine serve every denoising step; no per-step scale tables.')),
        ('rounding', 7.0, lambda t, d: scene_excerpt(t, d, ex['rounding'], 'Method · Sec. III-F · Rounding and native execution',
                                                    'GPTQ rounds in the transformed coordinates; CUTLASS INT4 and INT8 GEMMs run inside fused TensorRT plugins.')),
        ('selective', 7.0, lambda t, d: scene_excerpt(t, d, ex['selective'], 'Method · Sec. III-G · Selective INT8 at o_proj and down_proj',
                                                     'Two projection types stay at W8A8; everything remains on the integer GEMM path, with no floating-point fallback.')),
        ('latency', 10.0, lambda t, d: scene_figure(t, d, fig_lat, 'Fig. 4 · Observation-to-action latency at batch 1',
                                                   [((0.0, 0.0, 0.5, 0.86), 0.5, 'RTX 4070 Ti SUPER: W4A4 is 1.25–1.52× faster than the float TensorRT engine and 10–15% faster than W8A8.'),
                                                    ((0.5, 0.0, 1.0, 0.86), 1.0, 'Jetson AGX Orin: 1.20–1.33× over the float engine; the compiled float engine already explains 83–92% of the eager-to-W4A4 gap.')],
                                                   view=(500, 150, 1420, 990))),
        ('sota', 9.0, lambda t, d: scene_excerpt(t, d, tab['sota'], 'Table I · Prior W4A4 recipes against FoldQuant · LIBERO per suite',
                                                 'Real INT4 engines against emulated recipes: FoldQuant leads our HoloQ-VLA and DuQuant ports on N1.7; on π0.5, HoloQ-VLA reports 98.0 against our 97.8.')),
        ('success', 7.0, lambda t, d: scene_excerpt(t, d, tab['success'], 'Table II · LIBERO P3 · 800 episodes per cell · four checkpoints',
                                                   '48 campaigns and 38,400 episodes: no arm differs significantly from its float reference after Holm correction.')),
        ('ablation', 7.0, lambda t, d: scene_excerpt(t, d, tab['ablation'], 'Table IV · Design ablations · one choice per row',
                                                    'Scale granularity and fold consistency are the only choices whose failure appears in closed loop; the rest are kernel-speed choices.')),
        ('fidelity', 6.0, lambda t, d: scene_figure(t, d, fig_fid, 'Fig. 6 · Held-out action fidelity · 32 observations', [(FULL, 1.0, None)],
                                                   'Holding o_proj and down_proj at INT8 raises the worst-case cosine from 0.46 to 0.85 on N1.6 and from 0.80 to 0.91 on N1.7.')),
        ('tasks', 6.0, lambda t, d: scene_figure(t, d, fig_tasks, 'Fig. 5 · Real-robot tasks', [(FULL, 1.0, None)],
                                                'T1 ALOHA banana into the pot and lid; T2–T4 on SO-101: banana and lid, all blocks into the cup, blue block on red.')),
    ]
    tail = [
        ('robot', 8.0, lambda t, d: scene_excerpt(t, d, tab['robot'], 'Table V · GR00T N1.7 on SO-101 · 20 episodes per task and arm',
                                                 'o/d INT8 beats uniform W4A4 on every task (74 vs 64 of 80 across all four); ModelOpt SmoothQuant was stopped after T4 at 30%.')),
        ('robot_pi', 6.0, lambda t, d: scene_excerpt(t, d, tab['robot_pi'], 'Tables VI–VII · ALOHA and π0.5',
                                                    'On ALOHA, o/d INT8 reaches 95% against 75% for uniform W4A4; the π0.5 W4A4 engine matches its own BF16 reference on SO-101.')),
        ('simpler', 6.0, lambda t, d: scene_excerpt(t, d, tab['simpler'], 'Table III · SimplerEnv Bridge (WidowX) · GR00T N1.6 · 200 episodes per task',
                                                   'Mean success is preserved at four bits; o/d INT8 narrows the per-task swings of uniform W4A4.')),
        ('outro', 4.0, lambda t, d: scene_outro(t, d, meta)),
    ]
    robot_cfgs = cfg['robot_scenes']
    total = sum(s[1] for s in scenes + tail) + sum(rc['duration_s'] for rc in robot_cfgs)
    print(f'planned duration {total:.1f} s')
    if total > 180:
        raise SystemExit('over the 180 s ICRA limit')
    if args.stills:
        out = HERE / 'build' / 'stills_v2'; out.mkdir(parents=True, exist_ok=True)
        for name, dur, fn in scenes + tail:
            fn(dur * 0.6, dur).save(out / f'{name}.png')
        print('stills in', out); return
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp); parts = []
        def render(name, dur, fn):
            part = work / f'{len(parts):02d}_{name}.mp4'; encode_frames(part, dur, fn, args.threads); parts.append(part); print('rendered', name)
        for name, dur, fn in scenes:
            render(name, dur, fn)
        for n, rc in enumerate(robot_cfgs):
            part = work / f'{len(parts):02d}_robot{n}.mp4'
            robot_scene(part, rc, robot['results'], '', args.threads, work, f'robot{n}'); parts.append(part); print('rendered robot scene', n)
        for name, dur, fn in tail:
            render(name, dur, fn)
        listing = work / 'list.txt'; listing.write_text(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c:v', 'libx264', '-preset', 'slow',
                        '-crf', str(args.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-threads', str(args.threads), str(out)], check=True)
    size = out.stat().st_size / 1e6
    print(f'wrote {out} ({size:.1f} MB)')
    if size > 20:
        print('WARNING: above the 20 MB ICRA limit; re-run with a higher --crf')


if __name__ == '__main__':
    main()
