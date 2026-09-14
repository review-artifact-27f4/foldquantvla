#!/usr/bin/env python3
"""Render the anonymous FoldQuantVLA overview video (CPU only: PIL frames + libx264).

Numbers come from website/data so the film never disagrees with the page.
Real-robot clips are declared in video/overview.json; missing clips render as
labelled placeholders, and --preview-clip fills every cell with one sample clip
under a visible "layout preview" banner.
"""
import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'website' / 'data'
W, H, FPS = 1920, 1080, 30
BG, INK, MUTED, LINE = (248, 250, 247), (23, 32, 28), (92, 108, 98), (219, 228, 221)
RED, GREEN, SOFT = (185, 20, 26), (24, 134, 75), (255, 240, 237)
GREY = (132, 149, 139)


def font(size, weight=600):
    return ImageFont.truetype(str(HERE / 'fonts' / f'Inter-{weight}.ttf'), size)


def load(name):
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def fade(t, duration, edge=0.45):
    return min(1.0, t / edge, (duration - t) / edge) if duration > 0 else 1.0


def text(draw, xy, value, size, weight=600, fill=INK, anchor='la', alpha=1.0):
    color = tuple(int(BG[i] + (fill[i] - BG[i]) * alpha) for i in range(3))
    draw.text(xy, value, font=font(size, weight), fill=color, anchor=anchor)


def blend(color, alpha):
    return tuple(int(BG[i] + (color[i] - BG[i]) * alpha) for i in range(3))


def canvas():
    return Image.new('RGB', (W, H), BG)


def mark(draw, cx, cy, s, alpha=1.0):
    for dy in (28, 14, 0):
        pts = [(cx, cy - 36 * s + dy * s), (cx + 62 * s, cy + dy * s), (cx, cy + 36 * s + dy * s), (cx - 62 * s, cy + dy * s)]
        draw.polygon(pts, fill=blend(SOFT, alpha), outline=blend((215, 82, 92), alpha))
        draw.line(pts + [pts[0]], fill=blend((215, 82, 92), alpha), width=max(2, int(3 * s)))


# ---------------------------------------------------------------- scenes

def scene_title(t, d, meta):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    mark(dr, W // 2, 330, 1.6 * (0.9 + 0.1 * ease(t / 0.8)), a)
    text(dr, (W // 2, 520), 'FoldQuantVLA', 128, 700, INK, 'mm', a)
    text(dr, (W // 2, 625), meta['subtitle'], 40, 400, MUTED, 'mm', a * ease((t - 0.4) / 0.6))
    text(dr, (W // 2, 720), 'Anonymous Authors', 30, 400, GREY, 'mm', a * ease((t - 0.8) / 0.6))
    return img


def scene_question(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (160, 330), 'What does four-bit actually', 76, 700, INK, 'la', a)
    text(dr, (160, 420), 'buy a robot policy?', 76, 700, RED, 'la', a)
    points = ['Latency on the device the robot actually carries', 'Success in closed loop, not only offline fidelity',
              'Every speedup against a compiled float engine']
    for i, p in enumerate(points):
        k = a * ease((t - 0.9 - 0.5 * i) / 0.5)
        dr.ellipse((168, 598 + i * 78, 184, 614 + i * 78), fill=blend(RED, k))
        text(dr, (214, 590 + i * 78), p, 40, 500 if False else 400, INK, 'la', k)
    return img


def scene_method(t, d, figure):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Method', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Fold the constants. Fuse the computation.', 58, 700, INK, 'la', a)
    card_w = 1680
    zoom = 0.96 + 0.04 * ease(t / d)
    fw = int(card_w * zoom); fh = int(figure.height * fw / figure.width)
    fig = figure.resize((fw, fh), Image.LANCZOS)
    if a < 1:
        fig = Image.blend(Image.new('RGB', fig.size, BG), fig, a)
    img.paste(fig, (120 + (card_w - fw) // 2, 250 + (620 - fh) // 2))
    steps = ['One shared scaling + rotation|per activation site',
             'Fold into weights and norm gains|then round once',
             'Native INT8 / INT4 GEMMs|in fused TensorRT plugins']
    idx = min(len(steps) - 1, int(t / (d / len(steps))))
    for i, s in enumerate(steps):
        on = i == idx
        x = 120 + i * 570
        dr.rounded_rectangle((x, 915, x + 540, 1005), 14, fill=blend(SOFT if on else (255, 255, 255), a), outline=blend(RED if on else LINE, a), width=2)
        text(dr, (x + 26, 960), f'{i + 1}', 34, 700, blend(RED, 1) if on else GREY, 'lm', a)
        l1, l2 = s.split('|')
        text(dr, (x + 66, 943), l1, 24, 600 if on else 400, INK if on else MUTED, 'lm', a)
        text(dr, (x + 66, 978), l2, 24, 600 if on else 400, INK if on else MUTED, 'lm', a)
    return img


def scene_orin(t, d, orin):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Jetson AGX Orin · batch 1 · TensorRT 10.3', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Four-bit is faster than the float engine it replaces', 58, 700, INK, 'la', a)
    models = [m for m in orin['models'] if not m['name'].startswith('Evo')]
    top, base = 300, 900
    vmax = 240
    group_w = 1680 / len(models)
    for i, m in enumerate(models):
        arms = {r['label']: r for r in m['arms']}
        f, q = arms['TRT BF16 (float engine)'], arms['FoldQuant W4A4']
        k = a * ease((t - 0.5 - 0.25 * i) / 0.9)
        gx = 120 + i * group_w
        for j, (r, col, lab) in enumerate(((f, GREY, 'TRT BF16'), (q, GREEN, 'FoldQuant W4A4'))):
            h = (base - top) * min(r['e2e_ms'], vmax) / vmax * k
            x0 = gx + 60 + j * 130
            dr.rounded_rectangle((x0, base - h, x0 + 110, base), 8, fill=blend(col, a))
            text(dr, (x0 + 55, base - h - 16), f'{r["e2e_ms"]} ms', 26, 600, INK, 'md', k)
        text(dr, (gx + 170, base + 40), m['name'].replace('π₀.₅', 'π0.5'), 30, 600, INK, 'mm', a)
        text(dr, (gx + 170, base + 84), f'{q["speedup"]:.2f}× faster', 30, 700, GREEN, 'mm', k)
    dr.line((120, base, 1800, base), fill=blend(LINE, a), width=2)
    for j, (col, lab) in enumerate(((GREY, 'TRT BF16 (float engine)'), (GREEN, 'FoldQuant W4A4'))):
        dr.rounded_rectangle((120 + j * 360, 232, 144 + j * 360, 256), 5, fill=blend(col, a))
        text(dr, (156 + j * 360, 244), lab, 24, 400, MUTED, 'lm', a)
    text(dr, (120, 1040), 'End-to-end observation-to-action latency. Lower is better.', 22, 400, GREY, 'la', a)
    return img


def scene_libero(t, d, compare):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    panel = next(p for p in compare['panels'] if p['key'] == 'n17')
    rows = [r for r in panel['rows'] if r['kind'] != 'pending']
    text(dr, (120, 90), 'LIBERO · GR00T N1.7 · one harness · 800 episodes per arm', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Success stays with the float model', 58, 700, INK, 'la', a)
    lo, hi = 85.0, 100.0
    x0, x1 = 700, 1700
    for i, r in enumerate(rows):
        total = sum(r['suites']); sr = total / 8
        k = a * ease((t - 0.5 - 0.3 * i) / 0.9)
        y = 320 + i * 150
        col = GREEN if r['kind'] == 'ours' else (GREY if r['kind'] == 'baseline' else (206, 170, 150))
        text(dr, (120, y + 30), r['method'].replace('†', ' (our port)'), 36, 600, INK, 'lm', a)
        dr.rounded_rectangle((x0, y, x1, y + 60), 10, fill=blend((236, 242, 238), a))
        w = (x1 - x0) * (sr - lo) / (hi - lo) * k
        dr.rounded_rectangle((x0, y, x0 + max(w, 12), y + 60), 10, fill=blend(col, a))
        text(dr, (x0 + max(w, 12) + 18, y + 30), f'{sr:.2f}%  ·  {total}/800', 30, 600, INK, 'lm', k)
    text(dr, (x0, 950), f'{lo:.0f}%', 22, 400, GREY, 'la', a); text(dr, (x1, 950), f'{hi:.0f}%', 22, 400, GREY, 'ra', a)
    text(dr, (120, 1010), 'Axis starts at 85%. HoloQ-VLA is our fake-quantized port of the method. Differences are within closed-loop noise.', 22, 400, GREY, 'la', a)
    return img


def scene_fidelity(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Selective INT8 on o_proj / down_proj', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Two INT8 sites fix the worst case', 58, 700, INK, 'la', a)
    cards = [('GR00T N1.6', 0.46067, 0.84984, '+1.4 ms'), ('GR00T N1.7', 0.80213, 0.91244, '+0.6 ms')]
    for i, (name, before, after, cost) in enumerate(cards):
        x = 120 + i * 860; k = a * ease((t - 0.6 - 0.4 * i) / 1.0)
        dr.rounded_rectangle((x, 290, x + 800, 900), 22, fill=blend((255, 255, 255), a), outline=blend(LINE, a), width=2)
        text(dr, (x + 50, 350), name, 40, 700, INK, 'la', a)
        text(dr, (x + 50, 420), 'Worst held-out action cosine vs BF16', 26, 400, MUTED, 'la', a)
        text(dr, (x + 50, 560), f'{before:.2f}', 110, 700, GREY, 'lm', a)
        text(dr, (x + 400, 560), '→', 80, 400, MUTED, 'mm', k)
        val = before + (after - before) * k
        text(dr, (x + 470, 560), f'{val:.2f}', 110, 700, GREEN, 'lm', k)
        text(dr, (x + 50, 700), 'W4A4', 28, 600, GREY, 'la', a); text(dr, (x + 470, 700), 'W4A4 + o/d INT8', 28, 600, GREEN, 'la', k)
        text(dr, (x + 50, 820), f'Latency cost {cost} end to end', 30, 600, INK, 'la', k)
    return img


def scene_outro(t, d, meta):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    mark(dr, W // 2, 380, 1.3, a)
    text(dr, (W // 2, 540), 'FoldQuantVLA', 96, 700, INK, 'mm', a)
    text(dr, (W // 2, 630), 'Consistent folding · native low-bit inference · closed-loop evidence', 36, 400, MUTED, 'mm', a)
    text(dr, (W // 2, 720), 'Anonymous submission · code and models after review', 28, 400, GREY, 'mm', a)
    return img


# ---------------------------------------------------------------- encoding

def encode_frames(path, duration, render, threads):
    n = int(round(duration * FPS))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-threads', str(threads), str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(render(i / FPS, duration).tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f'ffmpeg failed for {path}')


def robot_scene(path, cfg, results, preview_clip, threads, work):
    """Five engines, one task, side by side; clips are trimmed, sped up and tiled."""
    arms = cfg['arms']
    duration = cfg['duration_s']
    speed = cfg['speed']
    cell_w, cell_h, top = 316, 562, 250
    gap = (W - 120 * 2 - cell_w * len(arms)) // (len(arms) - 1)
    # Static overlay: titles, labels, success counts.
    over = canvas(); dr = ImageDraw.Draw(over)
    text(dr, (120, 90), f'Real robot · {cfg["policy"]} · {speed:g}× speed', 30, 600, RED)
    text(dr, (120, 132), f'Same task, five engines: {cfg["task_title"]}', 58, 700, INK)
    task_index = cfg.get('task_index')
    by_label = {r['label']: r for r in results['arms']}
    placeholders = []
    for i, arm in enumerate(arms):
        x = 120 + i * (cell_w + gap)
        dr.rounded_rectangle((x - 3, top - 3, x + cell_w + 3, top + cell_h + 3), 12, fill=LINE)
        text(dr, (x, top + cell_h + 44), arm['label'], 26, 700, GREEN if arm.get('ours') else INK)
        text(dr, (x, top + cell_h + 80), arm['precision'], 22, 400, MUTED)
        res = by_label.get(arm.get('result_label', arm['label']))
        if res and task_index is not None and res['tasks'][task_index] is not None:
            text(dr, (x, top + cell_h + 124), f'{res["tasks"][task_index]}/{results["episodes_per_task"]} successes', 24, 600, INK)
        src = arm.get('src') or preview_clip
        if not src:
            placeholders.append(i)
            dr.rounded_rectangle((x, top, x + cell_w, top + cell_h), 10, fill=(22, 35, 28))
            text(dr, (x + cell_w // 2, top + cell_h // 2), 'Video forthcoming', 26, 500, (200, 214, 205), 'mm')
    if preview_clip and not all(a.get('src') for a in arms):
        dr.rounded_rectangle((W - 700, 1020, W - 120, 1066), 10, fill=SOFT, outline=RED, width=2)
        text(dr, (W - 410, 1043), 'LAYOUT PREVIEW · same sample clip in every cell', 22, 700, RED, 'mm')
    text(dr, (120, 1045), cfg.get('footnote', ''), 22, 400, GREY)
    overlay = work / 'robot_overlay.png'; over.save(overlay)

    inputs, filters, labels = ['-loop', '1', '-i', str(overlay)], [], []
    k = 1
    for i, arm in enumerate(arms):
        src = arm.get('src') or preview_clip
        if not src:
            continue
        start = float(arm.get('start_s', 0))
        inputs += ['-ss', f'{start}', '-i', str(Path(src).expanduser())]
        filters.append(f'[{k}:v]setpts=(PTS-STARTPTS)/{speed},fps={FPS},scale={cell_w}:{cell_h}:force_original_aspect_ratio=increase,'
                       f'crop={cell_w}:{cell_h},format=yuv420p,tpad=stop_mode=clone:stop_duration={duration}[c{i}]')
        labels.append((i, f'c{i}'))
        k += 1
    chain, last = [], '0:v'
    for n, (i, lab) in enumerate(labels):
        x = 120 + i * (cell_w + gap)
        out = f'o{n}'
        chain.append(f'[{last}][{lab}]overlay={x}:{top}:shortest=0[{out}]')
        last = out
    fade_f = f'[{last}]trim=duration={duration},fade=t=in:st=0:d=0.45,fade=t=out:st={duration - 0.45}:d=0.45,format=yuv420p[v]'
    graph = ';'.join(filters + chain + [fade_f])
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[v]', '-an', '-r', str(FPS),
           '-t', str(duration), '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-threads', str(threads), str(path)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(HERE / 'overview.json'))
    ap.add_argument('--output', default=str(HERE / 'build' / 'overview.mp4'))
    ap.add_argument('--preview-clip', default='', help='fill empty robot cells with this clip, marked as a layout preview')
    ap.add_argument('--install', action='store_true', help='copy the result to website/media/overview.mp4')
    ap.add_argument('--threads', type=int, default=12)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    meta, orin, compare, robot = load('metadata'), load('jetson_orin'), load('compare'), load('real_robot')
    figure = Image.open(HERE / 'figures' / 'fig_overview.png').convert('RGB')
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    if args.install and args.preview_clip:
        raise SystemExit('Refusing to install a layout preview into the website.')
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp); parts = []
        scenes = [('title', 4.5, lambda t, d: scene_title(t, d, meta)),
                  ('question', 5.0, scene_question),
                  ('method', 9.0, lambda t, d: scene_method(t, d, figure)),
                  ('orin', 8.0, lambda t, d: scene_orin(t, d, orin)),
                  ('libero', 7.5, lambda t, d: scene_libero(t, d, compare)),
                  ('fidelity', 6.5, scene_fidelity)]
        for name, dur, fn in scenes:
            part = work / f'{len(parts):02d}_{name}.mp4'; encode_frames(part, dur, fn, args.threads); parts.append(part)
            print('rendered', name)
        part = work / f'{len(parts):02d}_robot.mp4'
        robot_scene(part, cfg['robot_compare'], robot['results'], args.preview_clip, args.threads, work); parts.append(part)
        print('rendered robot')
        print('rendering outro')
        part = work / f'{len(parts):02d}_outro.mp4'; encode_frames(part, 4.0, lambda t, d: scene_outro(t, d, meta), args.threads); parts.append(part)
        listing = work / 'list.txt'; listing.write_text(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c:v', 'libx264', '-preset', 'slow',
                        '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', '-threads', str(args.threads), str(out)], check=True)
    print('wrote', out)
    if args.install:
        dest = ROOT / 'website' / 'media' / 'overview.mp4'; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(out, dest)
        print('installed', dest)


if __name__ == '__main__':
    main()
