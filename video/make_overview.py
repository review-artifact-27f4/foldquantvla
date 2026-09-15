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
    # Liberation Sans is metric-compatible with Arial, matching the website's Arial stack.
    face = 'Bold' if weight >= 600 else 'Regular'
    return ImageFont.truetype(str(HERE / 'fonts' / f'LiberationSans-{face}.ttf'), size)


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
    # Full paper subtitle on two lines so it stays inside the frame.
    head, tail = meta['subtitle'].split(' Vision-', 1) if ' Vision-' in meta['subtitle'] else (meta['subtitle'], '')
    k = a * ease((t - 0.4) / 0.6)
    text(dr, (W // 2, 625), head, 44, 400, MUTED, 'mm', k)
    if tail:
        text(dr, (W // 2, 683), 'Vision-' + tail, 44, 400, MUTED, 'mm', k)
    return img


def scene_teaser(t, d, teaser):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'FoldQuantVLA at a glance · GR00T N1.7', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Four-bit speed, float-level success', 58, 700, INK, 'la', a)
    box_h = 760
    zoom = 0.97 + 0.03 * ease(t / d)
    fh = int(box_h * zoom); fw = int(teaser.width * fh / teaser.height)
    fig = teaser.resize((fw, fh), Image.LANCZOS)
    if a < 1:
        fig = Image.blend(Image.new('RGB', fig.size, BG), fig, a)
    img.paste(fig, ((W - fw) // 2, 250 + (box_h - fh) // 2))
    return img


def scene_question(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (160, 330), 'What does low-bit actually', 76, 700, INK, 'la', a)
    text(dr, (160, 420), 'buy a robot policy?', 76, 700, RED, 'la', a)
    points = ['Latency on the device the robot actually carries', 'Success in closed loop, not only offline fidelity',
              'Every speedup against a compiled float engine']
    for i, p in enumerate(points):
        k = a * ease((t - 0.9 - 0.5 * i) / 0.5)
        dr.ellipse((168, 598 + i * 78, 184, 614 + i * 78), fill=blend(RED, k))
        text(dr, (214, 590 + i * 78), p, 40, 500 if False else 400, INK, 'la', k)
    return img


# Figure regions as fractions of fig_overview.png (x0, y0, x1, y1): A = basis, B = offline, C = online.
FIG_REGIONS = [(0.004, 0.04, 0.478, 0.94), (0.508, 0.04, 0.992, 0.495), (0.508, 0.505, 0.992, 0.965)]
FIG_FULL = (0.0, 0.0, 1.0, 1.0)


def camera(figure, region, view_w, view_h):
    """Rectangle (in figure pixels) with the view's aspect that contains `region`, clamped to the figure."""
    fw, fh = figure.size
    x0, y0, x1, y1 = region[0] * fw, region[1] * fh, region[2] * fw, region[3] * fh
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) * 1.04, (y1 - y0) * 1.04
    aspect = view_w / view_h
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    return cx, cy, w, h


def scene_method(t, d, figure):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Method', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Fold the constants. Fuse the computation.', 58, 700, INK, 'la', a)
    vx, vy, vw, vh = 120, 240, 1680, 640
    # Timeline: whole figure, then zoom to A, B, C in step with the three captions.
    lead, span = 1.4, (d - 1.4) / 3
    idx = -1 if t < lead else min(2, int((t - lead) / span))
    local = 0.0 if idx < 0 else (t - lead - idx * span)
    prev = FIG_FULL if idx <= 0 else FIG_REGIONS[idx - 1]
    target = FIG_FULL if idx < 0 else FIG_REGIONS[idx]
    k = 1.0 if idx < 0 else ease(local / 0.9)
    c0, c1 = camera(figure, prev, vw, vh), camera(figure, target, vw, vh)
    cx, cy, w, h = (c0[i] + (c1[i] - c0[i]) * k for i in range(4))
    view = Image.new('RGB', (vw, vh), BG)
    fw, fh = figure.size
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    sx0, sy0, sx1, sy1 = max(0, box[0]), max(0, box[1]), min(fw, box[2]), min(fh, box[3])
    crop = figure.crop((int(sx0), int(sy0), int(sx1), int(sy1)))
    scale = vw / w
    crop = crop.resize((max(1, int((sx1 - sx0) * scale)), max(1, int((sy1 - sy0) * scale))), Image.BILINEAR)
    view.paste(crop, (int((sx0 - box[0]) * scale), int((sy0 - box[1]) * scale)))
    # Dim everything outside the active panel so the eye follows the caption.
    if idx >= 0:
        rx0, ry0, rx1, ry1 = target
        px0, py0 = int((rx0 * fw - box[0]) * scale), int((ry0 * fh - box[1]) * scale)
        px1, py1 = int((rx1 * fw - box[0]) * scale), int((ry1 * fh - box[1]) * scale)
        mask = Image.new('L', (vw, vh), int(150 * k)); ImageDraw.Draw(mask).rectangle((px0, py0, px1, py1), fill=0)
        view = Image.composite(Image.new('RGB', (vw, vh), BG), view, mask)
        ImageDraw.Draw(view).rounded_rectangle((px0 - 6, py0 - 6, px1 + 6, py1 + 6), 14, outline=blend(RED, k), width=4)
    if a < 1:
        view = Image.blend(Image.new('RGB', view.size, BG), view, a)
    img.paste(view, (vx, vy))
    steps = ['One shared scaling + rotation|per activation site (A)',
             'Fold into weights, round once|stored as packed integers (B)',
             'Native INT8 / INT4 GEMMs|in fused TensorRT plugins (C)']
    for i, s_ in enumerate(steps):
        on = i == idx
        x = 120 + i * 570
        dr.rounded_rectangle((x, 915, x + 540, 1005), 14, fill=blend(SOFT if on else (255, 255, 255), a), outline=blend(RED if on else LINE, a), width=2)
        text(dr, (x + 26, 960), f'{i + 1}', 34, 700, RED if on else GREY, 'lm', a)
        l1, l2 = s_.split('|')
        text(dr, (x + 66, 943), l1, 24, 600 if on else 400, INK if on else MUTED, 'lm', a)
        text(dr, (x + 66, 978), l2, 24, 600 if on else 400, INK if on else MUTED, 'lm', a)
    return img


# Illustrative activation magnitudes for one site: two outlier channels dominate the range.
CHANNELS = [0.16, 0.11, 0.19, 0.09, 0.14, 0.21, 0.12, 1.00, 0.17, 0.10, 0.15, 0.13, 0.20, 0.08, 0.18, 0.12,
            0.16, 0.10, 0.14, 0.19, 0.11, 0.78, 0.13, 0.17, 0.09, 0.15, 0.20, 0.12, 0.18, 0.10, 0.14, 0.16]
LEVELS = 7  # positive INT4 levels


def channel_chart(dr, box, values, a, quant_k=0.0, scale_max=None):
    """Bars for activation magnitudes, the INT4 grid spanning their range, and (optionally) the rounded values."""
    x0, y0, x1, y1 = box
    vmax = scale_max or max(values)
    step = vmax / LEVELS
    full = 1.0 if scale_max is None else max(values) / scale_max
    for lv in range(1, LEVELS + 1):
        y = y1 - (y1 - y0) * lv * step / vmax * 0.92
        for xx in range(x0, x1, 22):
            dr.line((xx, y, xx + 11, y), fill=blend(RED if lv == LEVELS else (226, 187, 187), a * 0.9), width=2)
    text(dr, (x1 + 14, y1 - (y1 - y0) * 0.92), 'INT4 max', 22, 600, RED, 'lm', a)
    n = len(values); bw = (x1 - x0) / n
    for i, v in enumerate(values):
        h = (y1 - y0) * v / vmax * 0.92
        bx = x0 + i * bw + bw * 0.18
        col = RED if CHANNELS[i] > 0.5 else GREY  # the outlier channels stay marked through every step
        dr.rectangle((bx, y1 - h, bx + bw * 0.64, y1), fill=blend(col if not quant_k else (205, 214, 208), a))
        if quant_k:
            qv = round(v / step) * step
            qh = (y1 - y0) * qv / vmax * 0.92
            dr.rectangle((bx - 2, y1 - qh, bx + bw * 0.64 + 2, y1), outline=blend(GREEN, a * quant_k), width=3)
    dr.line((x0, y1, x1, y1), fill=blend(INK, a), width=2)


def sup_text(dr, xy, parts, size, fill, a):
    """Draw text with superscripts: parts is a list of (string, is_superscript)."""
    x, y = xy
    for value, sup in parts:
        f = font(int(size * (0.6 if sup else 1)), 700)
        dy = -size * 0.38 if sup else 0
        dr.text((x, y + dy), value, font=f, fill=blend(fill, a), anchor='lm')
        x += dr.textlength(value, font=f) + (4 if sup else 0)
    return x


def scene_fold_why(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Why naive low-bit breaks', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'A few outlier channels stretch the INT4 grid', 58, 700, INK, 'la', a)
    grow = ease(t / 1.4)
    vals = [v * grow + 1e-3 for v in CHANNELS]
    qk = a * ease((t - 2.6) / 0.8)
    channel_chart(dr, (160, 300, 1500, 880), vals, a, qk, scale_max=1.0)
    text(dr, (160, 930), 'Activation magnitude per channel (illustrative)', 26, 400, MUTED, 'la', a)
    k = a * ease((t - 3.4) / 0.7)
    dr.rounded_rectangle((1560, 420, 1820, 720), 16, fill=blend(SOFT, k), outline=blend(RED, k), width=2)
    text(dr, (1690, 490), '2 channels', 34, 700, RED, 'mm', k)
    text(dr, (1690, 540), 'set the range', 26, 400, INK, 'mm', k)
    text(dr, (1690, 610), '30 channels', 34, 700, INK, 'mm', k)
    text(dr, (1690, 660), 'round to one level', 26, 400, INK, 'mm', k)
    return img


def scene_fold_how(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Method · consistent folding', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Change the basis once, then round once', 58, 700, INK, 'la', a)
    mean = sum(CHANNELS) / len(CHANNELS)
    k1, k2 = ease((t - 0.6) / 2.2), ease((t - 3.4) / 2.2)
    scaled = [v + ((v ** 0.5) * mean ** 0.5 - v) * k1 for v in CHANNELS]
    rotated = [v + (mean * 1.35 + (v - mean) * 0.18 - v) * k2 for v in scaled]
    qk = a * ease((t - 6.0) / 0.8)
    channel_chart(dr, (160, 300, 1060, 800), rotated, a, qk)
    text(dr, (160, 850), 'Same channels after scaling and rotation', 26, 400, MUTED, 'la', a)
    steps = [('1', 'Channel scaling S', 'tames outlier channels', 0.0),
             ('2', 'Shared rotation R', 'spreads energy across channels', 3.0),
             ('3', 'Fold into weights, round once', 'native INT8 / INT4 GEMMs', 6.0)]
    for i, (num, head, sub, start) in enumerate(steps):
        on = t >= start and (i == len(steps) - 1 or t < steps[i + 1][3])
        k = a * ease((t - start) / 0.5)
        y = 300 + i * 150
        dr.rounded_rectangle((1180, y, 1800, y + 120), 16, fill=blend(SOFT if on else (255, 255, 255), k), outline=blend(RED if on else LINE, k), width=2)
        text(dr, (1220, y + 60), num, 44, 700, RED if on else GREY, 'lm', k)
        text(dr, (1280, y + 42), head, 32, 700, INK, 'lm', k)
        text(dr, (1280, y + 84), sub, 24, 400, MUTED, 'lm', k)
    k = a * ease((t - 6.4) / 0.7)
    dr.rounded_rectangle((160, 900, 1800, 1030), 18, fill=blend((255, 255, 255), k), outline=blend(LINE, k), width=2)
    x = sup_text(dr, (220, 965), [('W x  =  ', False), ('(W S', False), ('-1', True), (' R', False), ('T', True), (')', False)], 48, INK, k)
    x = sup_text(dr, (x, 965), [('  ·  ', False)], 48, MUTED, k)
    x = sup_text(dr, (x, 965), [('(R S x)', False)], 48, GREEN, k)
    text(dr, (x + 60, 945), 'Exact before rounding.', 28, 700, INK, 'lm', k)
    text(dr, (x + 60, 988), 'Weights folded offline; activations transformed online.', 24, 400, MUTED, 'lm', k)
    return img


def scene_orin(t, d, orin):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Jetson AGX Orin · batch 1 · TensorRT 10.3', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Native low-bit beats the float engine it replaces', 58, 700, INK, 'la', a)
    models = [m for m in orin['models'] if not m['name'].startswith('Evo')]
    top, base = 300, 900
    vmax = 240
    group_w = 1680 / len(models)
    for i, m in enumerate(models):
        arms = {r['label']: r for r in m['arms']}
        f, q = arms['TRT BF16 (float engine)'], arms['FoldQuant W4A4']
        k = a * ease((t - 0.5 - 0.25 * i) / 0.9)
        gx = 120 + i * group_w
        for j, (r, col, lab) in enumerate(((f, GREY, 'TRT BF16'), (q, GREEN, 'FoldQuant W4A4 (ours)'))):
            h = (base - top) * min(r['e2e_ms'], vmax) / vmax * k
            x0 = gx + 60 + j * 130
            dr.rounded_rectangle((x0, base - h, x0 + 110, base), 8, fill=blend(col, a))
            text(dr, (x0 + 55, base - h - 16), f'{r["e2e_ms"]} ms', 26, 600, INK, 'md', k)
        text(dr, (gx + 170, base + 40), m['name'].replace('π₀.₅', 'π0.5'), 30, 600, INK, 'mm', a)
        text(dr, (gx + 170, base + 84), f'{q["speedup"]:.2f}× faster', 30, 700, GREEN, 'mm', k)
    dr.line((120, base, 1800, base), fill=blend(LINE, a), width=2)
    for j, (col, lab) in enumerate(((GREY, 'TRT BF16 (float engine)'), (GREEN, 'FoldQuant W4A4 (ours)'))):
        dr.rounded_rectangle((120 + j * 360, 232, 144 + j * 360, 256), 5, fill=blend(col, a))
        text(dr, (156 + j * 360, 244), lab, 24, 400, MUTED, 'lm', a)
    text(dr, (120, 1040), 'End-to-end observation-to-action latency. Lower is better.', 22, 400, GREY, 'la', a)
    return img


def scene_libero(t, d, compare):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    panel = next(p for p in compare['panels'] if p['key'] == 'n17')
    rows = [r for r in panel['rows'] if r['kind'] != 'pending']
    text(dr, (120, 90), 'LIBERO · GR00T N1.7 · success rate · 800 episodes per arm', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Success stays with the float model', 58, 700, INK, 'la', a)
    lo, hi = 85.0, 100.0
    x0, x1 = 840, 1700
    for i, r in enumerate(rows):
        total = sum(r['suites']); sr = total / 8
        k = a * ease((t - 0.5 - 0.3 * i) / 0.9)
        y = 320 + i * 150
        col = GREEN if r['kind'] == 'ours' else (GREY if r['kind'] == 'baseline' else (206, 170, 150))
        ours = r['kind'] == 'ours'
        text(dr, (120, y + 30), r['method'] + (' (ours)' if ours else ''), 36, 700 if ours else 400, INK, 'lm', a)
        dr.rounded_rectangle((x0, y, x1, y + 60), 10, fill=blend((236, 242, 238), a))
        w = (x1 - x0) * (sr - lo) / (hi - lo) * k
        dr.rounded_rectangle((x0, y, x0 + max(w, 12), y + 60), 10, fill=blend(col, a))
        text(dr, (x0 + max(w, 12) + 18, y + 30), f'{sr:.2f}%', 30, 600, INK, 'lm', k)
    text(dr, (120, 1010), 'Axis starts at 85%. † Emulated implementations. Differences are within closed-loop noise.', 22, 400, GREY, 'la', a)
    return img


def scene_fidelity(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    text(dr, (120, 90), 'Selective INT8 on o_proj / down_proj', 30, 600, RED, 'la', a)
    text(dr, (120, 132), 'Two INT8 sites fix the worst case', 58, 700, INK, 'la', a)
    cards = [('GR00T N1.6', 0.46067, 0.84984, '+1.3 ms'), ('GR00T N1.7', 0.80213, 0.91244, '+1.8 ms')]
    for i, (name, before, after, cost) in enumerate(cards):
        x = 120 + i * 860; k = a * ease((t - 0.6 - 0.4 * i) / 1.0)
        dr.rounded_rectangle((x, 290, x + 800, 900), 22, fill=blend((255, 255, 255), a), outline=blend(LINE, a), width=2)
        text(dr, (x + 50, 350), name, 40, 700, INK, 'la', a)
        text(dr, (x + 50, 420), 'Worst held-out action cosine vs BF16', 26, 400, MUTED, 'la', a)
        text(dr, (x + 50, 560), f'{before:.2f}', 110, 700, GREY, 'lm', a)
        text(dr, (x + 400, 560), '→', 80, 400, MUTED, 'mm', k)
        val = before + (after - before) * k
        text(dr, (x + 470, 560), f'{val:.2f}', 110, 700, GREEN, 'lm', k)
        text(dr, (x + 50, 700), 'W4A4 (ours)', 28, 700, GREY, 'la', a); text(dr, (x + 470, 700), 'W4A4 + o/d INT8 (ours)', 28, 700, GREEN, 'la', k)
        text(dr, (x + 50, 820), f'Latency cost {cost} end to end', 30, 600, INK, 'la', k)
    return img


def scene_outro(t, d, meta):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    mark(dr, W // 2, 380, 1.3, a)
    text(dr, (W // 2, 540), 'FoldQuantVLA', 96, 700, INK, 'mm', a)
    text(dr, (W // 2, 630), 'Consistent folding · native low-bit inference · real robots: 4 tasks, 2 platforms', 36, 400, MUTED, 'mm', a)
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


def probe_duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def badge(path, ok, label):
    """Outcome badge drawn with shapes (the font has no check/cross glyphs)."""
    f = font(30, 700)
    tw = int(ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(label, font=f))
    img = Image.new('RGBA', (tw + 96, 60), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    col = GREEN if ok else RED
    dr.rounded_rectangle((0, 0, img.width - 1, 59), 30, fill=col + (235,))
    if ok:
        dr.line((24, 31, 36, 43, 56, 19), fill=(255, 255, 255), width=6, joint='curve')
    else:
        dr.line((24, 18, 50, 42), fill=(255, 255, 255), width=6); dr.line((50, 18, 24, 42), fill=(255, 255, 255), width=6)
    dr.text((72, 30), label, font=f, fill=(255, 255, 255), anchor='lm')
    img.save(path)
    return img.size


def robot_scene(path, cfg, results, preview_clip, threads, work, tag):
    """Engines side by side on one task; clips are trimmed, sped up and tiled; outcome badges appear when a clip ends."""
    arms = cfg['arms']
    duration, speed = cfg['duration_s'], cfg['speed']
    cell_w, cell_h = cfg['cell']
    top = cfg.get('top', 250)
    gap = (W - 120 * 2 - cell_w * len(arms)) // max(1, len(arms) - 1)
    over = canvas(); dr = ImageDraw.Draw(over)
    text(dr, (120, 90), f'{cfg["kicker"]} · {speed:g}× speed', 30, 600, RED)
    text(dr, (120, 132), cfg['title'], 58, 700, INK)
    for i, arm in enumerate(arms):
        x = 120 + i * (cell_w + gap)
        dr.rounded_rectangle((x - 4, top - 4, x + cell_w + 4, top + cell_h + 4), 14, fill=RED if arm.get('outcome') == 'fail' else (GREEN if arm.get('ours') else LINE))
        text(dr, (x, top + cell_h + 44), arm['label'] + (' (ours)' if arm.get('ours') else ''), 32, 700 if arm.get('ours') else 400, GREEN if arm.get('ours') else INK)
        text(dr, (x, top + cell_h + 86), arm['precision'], 24, 400, MUTED)
        if arm.get('note'):
            text(dr, (x, top + cell_h + 122), arm['note'], 24, 600, RED if arm.get('outcome') == 'fail' else INK)
        if not (arm.get('src') or preview_clip):
            dr.rounded_rectangle((x, top, x + cell_w, top + cell_h), 10, fill=(22, 35, 28))
            text(dr, (x + cell_w // 2, top + cell_h // 2), 'Video forthcoming', 26, 500, (200, 214, 205), 'mm')
    if preview_clip and not all(a.get('src') for a in arms):
        dr.rounded_rectangle((W - 700, 1020, W - 120, 1066), 10, fill=SOFT, outline=RED, width=2)
        text(dr, (W - 410, 1043), 'LAYOUT PREVIEW · same sample clip in every cell', 22, 700, RED, 'mm')
    text(dr, (120, 1045), cfg.get('footnote', ''), 22, 400, GREY)
    overlay = work / f'{tag}_overlay.png'; over.save(overlay)

    inputs, filters, layers = ['-loop', '1', '-i', str(overlay)], [], []
    k = 1
    for i, arm in enumerate(arms):
        src = arm.get('src') or preview_clip
        if not src:
            continue
        src = Path(src).expanduser()
        start = float(arm.get('start_s', 0))
        turn = {'cw': 'transpose=1,', 'ccw': 'transpose=2,'}.get(arm.get('rotate', ''), '')
        inputs += ['-ss', f'{start}', '-i', str(src)]
        filters.append(f'[{k}:v]setpts=(PTS-STARTPTS)/{speed},fps={FPS},{turn}scale={cell_w}:{cell_h}:force_original_aspect_ratio=increase,'
                       f'crop={cell_w}:{cell_h},format=yuv420p,tpad=stop_mode=clone:stop_duration={duration}[c{i}]')
        x = 120 + i * (cell_w + gap)
        layers.append((f'c{i}', x, top, ''))
        k += 1
        if arm.get('outcome') in ('success', 'fail'):
            ends = min(duration - 1.0, (probe_duration(src) - start) / speed)
            bpath = work / f'{tag}_badge{i}.png'
            bw, _ = badge(bpath, arm['outcome'] == 'success', 'Success' if arm['outcome'] == 'success' else 'Failed')
            inputs += ['-loop', '1', '-i', str(bpath)]
            layers.append((f'{k}:v', x + cell_w - bw - 18, top + 18, f":enable='gte(t,{ends:.2f})'"))
            k += 1
    chain, last = [], '0:v'
    for n, (lab, x, y, enable) in enumerate(layers):
        out = f'o{n}'
        chain.append(f'[{last}][{lab}]overlay={x}:{y}:shortest=0{enable}[{out}]')
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
    # Paper Fig. 1, rendered from teaser.pdf (pdftoppm -r 600) onto the video background.
    teaser_rgba = Image.open(HERE / 'figures' / 'teaser.png').convert('RGBA')
    teaser = Image.new('RGB', teaser_rgba.size, BG); teaser.paste(teaser_rgba, mask=teaser_rgba.split()[3])
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    if args.install and args.preview_clip:
        raise SystemExit('Refusing to install a layout preview into the website.')
    robot_cfgs = cfg['robot_scenes']
    for rc in robot_cfgs:
        if args.install and any(a.get('src') for a in rc['arms']) and not all(a.get('src') for a in rc['arms']):
            raise SystemExit('Refusing to install a robot comparison with missing engine clips.')
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp); parts = []
        scenes = [('title', 4.5, lambda t, d: scene_title(t, d, meta)),
                  ('teaser', 7.0, lambda t, d: scene_teaser(t, d, teaser)),
                  ('question', 5.0, scene_question),
                  ('fold_why', 6.5, scene_fold_why),
                  ('fold_how', 10.0, scene_fold_how),
                  ('method', 11.0, lambda t, d: scene_method(t, d, figure)),
                  ('orin', 8.0, lambda t, d: scene_orin(t, d, orin)),
                  ('libero', 7.5, lambda t, d: scene_libero(t, d, compare)),
                  ('fidelity', 6.5, scene_fidelity)]
        for name, dur, fn in scenes:
            part = work / f'{len(parts):02d}_{name}.mp4'; encode_frames(part, dur, fn, args.threads); parts.append(part)
            print('rendered', name)
        for n, rc in enumerate(robot_cfgs):
            if not (args.preview_clip or any(a.get('src') for a in rc['arms'])):
                print('skipped robot scene', n, '(no clips yet)')
                continue
            part = work / f'{len(parts):02d}_robot{n}.mp4'
            robot_scene(part, rc, robot['results'], args.preview_clip, args.threads, work, f'robot{n}'); parts.append(part)
            print('rendered robot scene', n)
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
