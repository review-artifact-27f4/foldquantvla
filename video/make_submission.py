#!/usr/bin/env python3
"""Render the ICRA submission video (<= 180 s, <= 20 MB, anonymous).

Builds on make_overview.py: same renderer, fonts and data files, plus the scenes a
reviewer needs that the 93 s web overview leaves out -- the folding contract, the
step-agnostic engine, the full latency comparison against every control, the
per-suite prior-recipe table, the four-checkpoint LIBERO table, the real-robot and
SimplerEnv tables, and a limitations card. Numbers come from website/data and from
the submitted manuscript (tab:success, tab:robot); nothing here is estimated.

  python3 video/make_submission.py --stills            # one PNG per scene for a layout check
  python3 video/make_submission.py                     # writes video/build/submission.mp4
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_overview import (BG, FPS, GREEN, GREY, H, INK, LINE, MUTED, RED, SOFT, W, blend, camera, canvas,  # noqa: E402
                           ease, encode_frames, fade, font, load, robot_scene, scene_fidelity, scene_fold_how,
                           scene_fold_why, scene_libero, scene_method, scene_orin, scene_outro, scene_question,
                           scene_teaser, scene_title, sup_text, text)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGS = HERE / 'figures'
OURS = (229, 240, 233)


def header(dr, a, kicker, title):
    text(dr, (120, 90), kicker, 30, 600, RED, 'la', a)
    size = 58 if dr.textlength(title, font=font(58, 700)) <= 1680 else 48
    text(dr, (120, 132), title, size, 700, INK, 'la', a)


def table(dr, a, t, x0, y0, widths, head, rows, row_h=64, ours=(), reveal=0.35, size=30, align=None, ref=()):
    """Animated table. `rows` is a list of cell-string lists; row i appears at t = reveal * i."""
    x = x0
    for j, (h, w) in enumerate(zip(head, widths)):
        anc = 'lm' if j == 0 else 'mm'
        text(dr, (x + (10 if j == 0 else w // 2), y0 + 28), h, 26, 600, MUTED, anc, a)
        x += w
    dr.line((x0, y0 + 56, x0 + sum(widths), y0 + 56), fill=blend(INK, a), width=2)
    for i, row in enumerate(rows):
        k = a * ease((t - 0.4 - reveal * i) / 0.5)
        y = y0 + 70 + i * row_h
        is_ours, is_ref = i in ours, i in ref
        if is_ours:
            dr.rounded_rectangle((x0, y - 2, x0 + sum(widths), y + row_h - 8), 10, fill=blend(OURS, k))
        x = x0
        for j, (cell, w) in enumerate(zip(row, widths)):
            anc = 'lm' if j == 0 else 'mm'
            bold = 700 if (is_ours and (j == 0 or cell.startswith('*'))) else (600 if j == 0 else 400)
            val = cell.lstrip('*')
            col = GREEN if (is_ours and j > 0 and cell.startswith('*')) else (GREY if is_ref and j > 0 else INK)
            text(dr, (x + (10 if j == 0 else w // 2), y + (row_h - 8) // 2), val, size, bold, col, anc, k)
            x += w
        dr.line((x0, y + row_h - 6, x0 + sum(widths), y + row_h - 6), fill=blend(LINE, k), width=1)


# ------------------------------------------------------------ new scenes

def scene_contract(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Method · the folding contract', 'One transform per activation site, shared by every consumer')
    k1 = a * ease((t - 0.5) / 0.7)
    dr.rounded_rectangle((120, 250, 1800, 400), 18, fill=blend((255, 255, 255), k1), outline=blend(LINE, k1), width=2)
    x = sup_text(dr, (170, 325), [('T = D', False), ('out', True), (' · R · D', False), ('in', True)], 54, INK, k1)
    x = sup_text(dr, (x + 90, 325), [('W', False), ('folded', True), (' = W · T', False), ('-1', True)], 54, GREEN, k1)
    text(dr, (x + 90, 305), 'Diagonal scale, orthogonal rotation, diagonal scale.', 26, 600, INK, 'lm', k1)
    text(dr, (x + 90, 345), 'Its inverse is folded into every weight that reads the site.', 26, 400, MUTED, 'lm', k1)
    cards = [('Calibration, rounding, execution', 'agree on one coordinate system', 'GPTQ rounds in the transformed basis; the kernel applies the same T_v online.'),
             ('Fold-before or fold-after', 'both exact before rounding', 'Scales absorb into RMSNorm gains where a learned gain exists; block Hadamard runs as an FWHT.'),
             ('A mismatched fold is a bug, not noise', 'action cosine 0.9997 → 0.9923', 'One consumer folded with a different T_v on N1.6 dropped the whole expert before any rounding.')]
    for i, (h1, h2, sub) in enumerate(cards):
        k = a * ease((t - 1.6 - 0.9 * i) / 0.6)
        x0 = 120 + i * 570
        dr.rounded_rectangle((x0, 460, x0 + 540, 900), 18, fill=blend(SOFT if i == 2 else (255, 255, 255), k), outline=blend(RED if i == 2 else LINE, k), width=2)
        text(dr, (x0 + 34, 520), f'{i + 1}', 40, 700, RED, 'lm', k)
        text(dr, (x0 + 34, 590), h1, 30, 700, INK, 'la', k)
        text(dr, (x0 + 34, 640), h2, 30, 700, GREEN if i < 2 else RED, 'la', k)
        # wrap the explanation
        words, lines, cur = sub.split(), [], ''
        for wd in words:
            trial = (cur + ' ' + wd).strip()
            if dr.textlength(trial, font=font(24, 400)) > 470:
                lines.append(cur); cur = wd
            else:
                cur = trial
        lines.append(cur)
        for n, ln in enumerate(lines):
            text(dr, (x0 + 34, 710 + n * 34), ln, 24, 400, MUTED, 'la', k)
    text(dr, (120, 1010), 'Proposition 1 in the paper: the transformed graph computes the same function in exact arithmetic.', 22, 400, GREY, 'la', a)
    return img


EXEC_REGIONS = [(0.0, 0.0, 1.0, 0.34), (0.0, 0.40, 1.0, 1.0)]


def scene_exec(t, d, figure):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Method · one engine for every denoising step', 'Dynamic per-token scales, no per-step scale tables')
    vx, vy, vw, vh = 120, 230, 1120, 760
    idx = 0 if t < d * 0.45 else 1
    k = ease((t - (0 if idx == 0 else d * 0.45)) / 0.8)
    prev = EXEC_REGIONS[0]; target = EXEC_REGIONS[idx]
    c0, c1 = camera(figure, prev, vw, vh), camera(figure, target, vw, vh)
    cx, cy, w, h = (c0[i] + (c1[i] - c0[i]) * (k if idx else 1.0) for i in range(4))
    fw, fh = figure.size
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    sx0, sy0, sx1, sy1 = max(0, box[0]), max(0, box[1]), min(fw, box[2]), min(fh, box[3])
    crop = figure.crop((int(sx0), int(sy0), int(sx1), int(sy1)))
    scale = vw / w
    crop = crop.resize((max(1, int((sx1 - sx0) * scale)), max(1, int((sy1 - sy0) * scale))), Image.BILINEAR)
    view = Image.new('RGB', (vw, vh), BG); view.paste(crop, (int((sx0 - box[0]) * scale), int((sy0 - box[1]) * scale)))
    if a < 1:
        view = Image.blend(Image.new('RGB', view.size, BG), view, a)
    img.paste(view, (vx, vy))
    dr.rounded_rectangle((vx - 6, vy - 6, vx + vw + 6, vy + vh + 6), 14, outline=blend(LINE, a), width=2)
    notes = [('Only projection GEMMs change precision', 'Vision encoder, softmax, norms, residuals and the decoder stay floating point.', 0.3),
             ('The action expert runs n_τ times through one engine', 'Each token supplies its own scale, so the engine never looks up a timestep.', 1.2),
             ('Proposition 2', 'With a per-token scale the quantizer is scale-invariant; one calibration minimizes normalized risk across steps under a stated condition.', 2.4),
             ('Selective INT8 keeps everything integer', 'o_proj and down_proj at W8A8: the two inputs with no learned gain to absorb a scale.', d * 0.45 + 0.6)]
    for i, (h1, sub, start) in enumerate(notes):
        k = a * ease((t - start) / 0.6)
        y = 250 + i * 190
        dr.rounded_rectangle((1290, y, 1800, y + 165), 16, fill=blend((255, 255, 255), k), outline=blend(LINE, k), width=2)
        text(dr, (1316, y + 34), h1, 26, 700, INK, 'la', k)
        words, lines, cur = sub.split(), [], ''
        for wd in words:
            trial = (cur + ' ' + wd).strip()
            if dr.textlength(trial, font=font(22, 400)) > 460:
                lines.append(cur); cur = wd
            else:
                cur = trial
        lines.append(cur)
        for n, ln in enumerate(lines[:4]):
            text(dr, (1316, y + 74 + n * 28), ln, 22, 400, MUTED, 'la', k)
    return img


ARM_ORDER = ['Eager PyTorch', 'torch.compile', 'TRT BF16 (float engine)', 'ModelOpt W8A8 SQ', 'ModelOpt W4A16 AWQ',
             'FoldQuant W8A8', 'FoldQuant W4A4', 'FoldQuant W4A4 + o/d INT8']
ARM_SHORT = ['Eager PyTorch', 'torch.compile', 'TRT BF16 (float engine)', 'ModelOpt W8A8 SQ', 'ModelOpt W4A16 AWQ',
             'FoldQuant W8A8 (ours)', 'FoldQuant W4A4 (ours)', 'FoldQuant W4A4 + o/d INT8 (ours)']
ARM_COL = [(185, 195, 189), (150, 162, 155), GREY, (156, 141, 171), (184, 168, 148), (60, 120, 168), (208, 122, 45), GREEN]


def scene_controls(t, d, orin):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Jetson AGX Orin · TensorRT 10.3 · batch 1 · every arm on the same board', 'Compiled float explains most of the speedup; four bits add the rest')
    models = [m for m in orin['models'] if not m['name'].startswith(('Evo', 'Smol'))]
    x0, x1, top, bottom = 470, 1760, 250, 930
    group_h = (bottom - top) / len(models); bar_h = 17
    vmax = 900
    for i, m in enumerate(models):
        by = {r['label']: r for r in m['arms']}
        gy = top + i * group_h
        text(dr, (x0 - 30, gy + group_h / 2 - 12), m['name'].replace('π₀.₅', 'π0.5'), 30, 700, INK, 'rm', a)
        f = by['TRT BF16 (float engine)']['e2e_ms']; q = by['FoldQuant W4A4']['e2e_ms']
        text(dr, (x0 - 30, gy + group_h / 2 + 26), f'W4A4 {f / q:.2f}× vs float engine', 22, 400, GREEN, 'rm', a * ease((t - 1.5 - 0.3 * i) / 0.6))
        for j, lab in enumerate(ARM_ORDER):
            r = by.get(lab)
            if not r:
                continue
            k = a * ease((t - 0.4 - 0.12 * j - 0.25 * i) / 0.6)
            y = gy + 8 + j * (bar_h + 3)
            w = (x1 - x0) * min(r['e2e_ms'], vmax) / vmax * k
            dr.rounded_rectangle((x0, y, x0 + max(w, 3), y + bar_h), 4, fill=blend(ARM_COL[j], a))
            text(dr, (x0 + max(w, 3) + 10, y + bar_h / 2), f'{r["e2e_ms"]:g} ms', 18, 600 if j >= 5 else 400, INK, 'lm', k)
        dr.line((x0, gy + group_h - 2, x1, gy + group_h - 2), fill=blend(LINE, a), width=1)
    dr.line((x0, top, x0, bottom), fill=blend(INK, a), width=2)
    for j, (lab, col) in enumerate(zip(ARM_SHORT, ARM_COL)):
        lx = 120 + (j % 4) * 420; ly = 965 + (j // 4) * 34
        dr.rounded_rectangle((lx, ly - 9, lx + 22, ly + 9), 4, fill=blend(col, a))
        text(dr, (lx + 32, ly), lab, 20, 700 if j >= 5 else 400, INK, 'lm', a)
    text(dr, (120, 1045), 'Observation-to-action latency, lower is better. The float TensorRT engine already removes 83–92% of the eager-to-W4A4 gap; weight-only AWQ is slower than that engine on every checkpoint.', 20, 400, GREY, 'la', a)
    return img


def r1(v):
    return f'{int(v * 10 + 0.5 + 1e-9) / 10:.1f}'


def pct(n):
    return r1(n / 2)


def scene_sota(t, d, compare):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Against prior W4A4 recipes · LIBERO success (%) per suite', 'Real INT4 engines against emulated recipes')
    widths = [520, 130, 130, 130, 130, 150]
    head = ['Method', 'Spatial', 'Object', 'Goal', 'Long', 'Average']
    for p, (px, py) in zip(compare['panels'], [(120, 230), (120, 640)]):
        rows, ours, ref = [], [], []
        for i, r in enumerate(p['rows']):
            s = r['suites']; avg = sum(s) / 8
            name = r['method'] + (' (ours)' if r['kind'] == 'ours' else '') + ('*' if r.get('reported') else '')
            cells = [name] + [pct(v) for v in s] + [r1(avg)]
            if r['kind'] == 'ours':
                ours.append(i); cells = [cells[0]] + ['*' + c for c in cells[1:]]
            if r.get('ref'):
                ref.append(i)
            rows.append(cells)
        text(dr, (px, py - 4), p['name'].replace('π0.5', 'π0.5'), 30, 700, INK, 'lm', a)
        table(dr, a, t - (0 if py < 400 else 1.2), px, py + 14, widths, head, rows, row_h=44 if len(rows) > 5 else 50, ours=ours, ref=ref, reveal=0.22, size=25)
    # right column: how to read it
    x0 = 1330
    notes = [('GR00T N1.7', 'One harness for every quantized arm; NVIDIA per-suite checkpoints, 720-step cap. † = our released emulated implementation of the recipe.'),
             ('π0.5', 'Author-released checkpoint. * = reported by HoloQ-VLA (full W4A4 incl. DiT attention, emulated, 10 trials per task). Our rows: released harness, 20 trials per task.'),
             ('Reading', 'FoldQuant W4A4 and o/d INT8 lead both emulated recipes on N1.7 by 13–21 episodes (p = 0.12–0.22, not significant). On π0.5, HoloQ-VLA reports 98.0 against our 97.8; we do not claim superiority.')]
    for i, (h1, sub) in enumerate(notes):
        k = a * ease((t - 0.8 - 0.8 * i) / 0.6)
        y = 240 + i * 250
        dr.rounded_rectangle((x0, y, 1800, y + 225), 16, fill=blend((255, 255, 255), k), outline=blend(LINE, k), width=2)
        text(dr, (x0 + 26, y + 34), h1, 26, 700, INK, 'la', k)
        words, lines, cur = sub.split(), [], ''
        for wd in words:
            trial = (cur + ' ' + wd).strip()
            if dr.textlength(trial, font=font(21, 400)) > 420:
                lines.append(cur); cur = wd
            else:
                cur = trial
        lines.append(cur)
        for n, ln in enumerate(lines[:6]):
            text(dr, (x0 + 26, y + 72 + n * 26), ln, 21, 400, MUTED, 'la', k)
    return img


TAB5 = [('BF16 PyTorch', [96.25, 96.38, 86.38, 96.50], 'ref'),
        ('TRT BF16 (float engine)', [95.50, 97.75, 86.00, 98.00], 'ref'),
        ('FoldQuant W8A8 (ours)', [95.38, 95.75, 87.12, 97.38], 'ours'),
        ('FoldQuant W4A4 (ours)', [95.38, 95.75, 87.38, 97.12], 'ours'),
        ('FoldQuant W4A4 + o/d INT8 (ours)', [95.00, 96.62, 87.00, 97.62], 'ours')]


def scene_tab5(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Closed loop · LIBERO · 800 episodes per cell · four checkpoints', 'Success stays with the float model at four bits')
    widths = [620, 240, 240, 240, 240]
    rows = [[n] + [('*' if kind == 'ours' else '') + f'{v:.2f}' for v in vals] for n, vals, kind in TAB5]
    table(dr, a, t, 120, 240, widths, ['Method', 'GR00T N1.7', 'GR00T N1.6', 'GR00T N1.5', 'π0.5'], rows, row_h=78, ours=[2, 3, 4], ref=[0, 1], reveal=0.35, size=32)
    k = a * ease((t - 2.8) / 0.7)
    dr.rounded_rectangle((120, 720, 1800, 960), 18, fill=blend(SOFT, k), outline=blend(RED, k), width=2)
    lines = ['48 campaigns, 38,400 episodes, paired per task over 40 tasks with Holm correction: no comparison survives.',
             'Four float TensorRT controls bracket the noise floor at −6, +11, −3 and +12 episodes against BF16.',
             'o/d INT8 against W4A4 on the same preset: +3, +10, −3, +4 episodes (p = 0.17–0.78). Not resolved by simulation; the robot decides.']
    for n, ln in enumerate(lines):
        text(dr, (160, 770 + n * 60), ln, 26, 600 if n == 0 else 400, INK if n == 0 else MUTED, 'la', k)
    text(dr, (120, 1010), 'Non-significant tests do not establish equivalence. Per-suite counts are in the artifact.', 22, 400, GREY, 'la', a)
    return img


def scene_robot_table(t, d, robot):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Real robot · GR00T N1.7 on Jetson AGX Orin · 20 episodes per task and arm', 'Selective INT8 recovers what uniform W4A4 loses, on every task')
    widths = [520, 220, 220, 220, 220, 280]
    head = ['Arm', 'T1 · ALOHA', 'T2 · SO-101', 'T3 · SO-101', 'T4 · SO-101', 'Success / 80']
    rows, ours, ref = [], [], []
    arms = robot['results']['arms']
    order = ['BF16 PyTorch', 'TRT BF16 (float engine)', 'FoldQuant W8A8', 'FoldQuant W4A4', 'FoldQuant W4A4 + o/d INT8', 'ModelOpt W8A8 SmoothQuant']
    for i, lab in enumerate(order):
        r = next(x for x in arms if x['label'].rstrip('*') == lab)
        cells = [f'{v * 5:.0f}%' if isinstance(v, int) else 'n/a' for v in r['tasks']]
        ran = [v for v in r['tasks'] if isinstance(v, int)]
        tot = f'{sum(ran)}/{20 * len(ran)}' + ('' if len(ran) == 4 else ' (T4 only)')
        is_ours = lab.startswith('FoldQuant')
        rows.append([lab + (' (ours)' if is_ours else '')] + (['*' + c for c in cells] if is_ours else cells) + [('*' if is_ours else '') + tot])
        if is_ours:
            ours.append(i)
        if lab in ('BF16 PyTorch', 'TRT BF16 (float engine)'):
            ref.append(i)
    table(dr, a, t, 120, 240, widths, head, rows, row_h=70, ours=ours, ref=ref, reveal=0.3, size=28)
    k = a * ease((t - 3.0) / 0.7)
    dr.rounded_rectangle((120, 760, 1800, 960), 18, fill=blend(SOFT, k), outline=blend(RED, k), width=2)
    text(dr, (160, 805), 'o/d INT8 beats uniform W4A4 on all four tasks: 74 vs 64 of 80 (Fisher exact p = 0.04), for +1 ms on Orin.', 28, 700, INK, 'la', k)
    text(dr, (160, 860), 'ModelOpt SmoothQuant (static per-tensor scales) was stopped after the hardest task: 6/20 with jerky motion that risked the hardware.', 24, 400, MUTED, 'la', k)
    text(dr, (160, 900), 'Logged-observation action cosine vs BF16 on SO-101: W8A8 0.99999 · o/d INT8 0.99983 · W4A4 0.99929 · ModelOpt SQ 0.99862.', 24, 400, MUTED, 'la', k)
    text(dr, (120, 1010), 'T1 banana into pot + lid · T2 banana into pot + lid · T3 all blocks into the cup · T4 blue block on red. Arms interleaved, matched placements; 20 trials per cell resolve only large effects.', 22, 400, GREY, 'la', a)
    return img


def scene_simpler(t, d, simpler):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Second simulator · SimplerEnv Bridge (WidowX) · GR00T N1.6 · 200 episodes per task', 'Mean success is preserved at four bits')
    tasks = ['Spoon', 'Carrot', 'Basket', 'Stack', 'Sink', 'Close dr.', 'Open dr.', 'Mean']
    widths = [400] + [165] * 7 + [125]
    rows, ours = [], []
    for i, r in enumerate(simpler['rows']):
        sr = r['sr']; mean = sum(sr) / len(sr)
        is_ours = r['kind'] == 'ours'
        cells = [r1(v * 100) for v in sr] + [r1(mean * 100)]
        rows.append([r['method'] + (' (ours)' if is_ours else '')] + (['*' + c for c in cells] if is_ours else cells))
        if is_ours:
            ours.append(i)
    table(dr, a, t, 120, 240, widths, ['Arm'] + tasks, rows, row_h=78, ours=ours, ref=[0], reveal=0.35, size=27)
    k = a * ease((t - 2.4) / 0.7)
    text(dr, (120, 700), 'Paired over the seven tasks against BF16: W4A4 −1.0 pp (p = 0.89), o/d INT8 +2.0 pp (p = 0.70).', 28, 600, INK, 'la', k)
    text(dr, (120, 750), 'Per-task swings are larger: W4A4 moves 13.6 pp on average (−34.5 on the basket); o/d INT8 narrows that to 10.1 pp.', 24, 400, MUTED, 'la', k)
    text(dr, (120, 1010), 'Tasks: put spoon on towel · put carrot on plate · put eggplant in basket · stack green cube on yellow · put eggplant in sink · close drawer · open drawer. Success rate (%).', 22, 400, GREY, 'la', a)
    return img


def scene_limits(t, d):
    img = canvas(); dr = ImageDraw.Draw(img); a = fade(t, d)
    header(dr, a, 'Limitations', 'What the evidence does not show')
    items = [('Architecture dependence', 'Consistent folding does not make every VLA work at W4A4: SmolVLA falls to 27% and Evo-1 to 81% in exploratory LIBERO runs.'),
             ('Small robot samples', '20 trials per task; π0.5 on one task. Intervals span ±10 points, so only large effects are visible.'),
             ('Native INT4 verified on Ada and Orin', 'H100 lowers four-bit operands to INT8 arithmetic; its success numbers say nothing about INT4 latency.'),
             ('Attribution is empirical', 'The o/d choice is motivated by missing normalization gains, but that alone does not prove why the sites are sensitive.')]
    for i, (h1, sub) in enumerate(items):
        k = a * ease((t - 0.4 - 0.5 * i) / 0.6)
        x0 = 120 + (i % 2) * 860; y0 = 250 + (i // 2) * 360
        dr.rounded_rectangle((x0, y0, x0 + 820, y0 + 320), 18, fill=blend((255, 255, 255), k), outline=blend(LINE, k), width=2)
        text(dr, (x0 + 36, y0 + 50), h1, 32, 700, INK, 'la', k)
        words, lines, cur = sub.split(), [], ''
        for wd in words:
            trial = (cur + ' ' + wd).strip()
            if dr.textlength(trial, font=font(26, 400)) > 740:
                lines.append(cur); cur = wd
            else:
                cur = trial
        lines.append(cur)
        for n, ln in enumerate(lines):
            text(dr, (x0 + 36, y0 + 120 + n * 38), ln, 26, 400, MUTED, 'la', k)
    text(dr, (120, 1010), 'Code, engines and per-episode records are released anonymously; the project page carries every video.', 22, 400, GREY, 'la', a)
    return img


# ------------------------------------------------------------ assembly

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(HERE / 'submission.json'))
    ap.add_argument('--output', default=str(HERE / 'build' / 'submission.mp4'))
    ap.add_argument('--stills', action='store_true', help='write one mid-scene PNG per scene into build/stills and exit')
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--crf', type=int, default=23)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    meta, orin, compare, robot, simpler = load('metadata'), load('jetson_orin'), load('compare'), load('real_robot'), load('simpler')
    figure = Image.open(FIGS / 'fig_overview.png').convert('RGB')
    exec_fig = Image.open(FIGS / 'fig_excute.png').convert('RGB')
    teaser_rgba = Image.open(FIGS / 'teaser.png').convert('RGBA')
    teaser = Image.new('RGB', teaser_rgba.size, BG); teaser.paste(teaser_rgba, mask=teaser_rgba.split()[3])
    scenes = [('title', 4.5, lambda t, d: scene_title(t, d, meta)),
              ('teaser', 7.0, lambda t, d: scene_teaser(t, d, teaser)),
              ('question', 5.0, scene_question),
              ('fold_why', 6.5, scene_fold_why),
              ('fold_how', 10.0, scene_fold_how),
              ('contract', 10.0, scene_contract),
              ('method', 11.0, lambda t, d: scene_method(t, d, figure)),
              ('exec', 9.0, lambda t, d: scene_exec(t, d, exec_fig)),
              ('orin', 8.0, lambda t, d: scene_orin(t, d, orin)),
              ('controls', 10.0, lambda t, d: scene_controls(t, d, orin)),
              ('libero', 7.5, lambda t, d: scene_libero(t, d, compare)),
              ('sota', 11.0, lambda t, d: scene_sota(t, d, compare)),
              ('tab5', 7.0, scene_tab5),
              ('fidelity', 6.5, scene_fidelity)]
    tail = [('robot_table', 8.0, lambda t, d: scene_robot_table(t, d, robot)),
            ('simpler', 6.0, lambda t, d: scene_simpler(t, d, simpler)),
            ('limits', 5.0, scene_limits),
            ('outro', 4.0, lambda t, d: scene_outro(t, d, meta))]
    robot_cfgs = cfg['robot_scenes']
    total = sum(s[1] for s in scenes + tail) + sum(rc['duration_s'] for rc in robot_cfgs)
    print(f'planned duration {total:.1f} s')
    if total > 180:
        raise SystemExit('over the 180 s ICRA limit')
    if args.stills:
        out = HERE / 'build' / 'stills'; out.mkdir(parents=True, exist_ok=True)
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
            if not all(a.get('src') for a in rc['arms']):
                raise SystemExit(f'robot scene {n} has a missing clip')
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
