#!/usr/bin/env python3
"""Build the anonymous project page using only the Python standard library."""
import argparse
import html
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CORE = ('bf16', 'int8', 'mixed', 'int4')
COLORS = {'bf16': '#84958b', 'trt_bf16': '#66776d', 'float': '#84958b', 'eager': '#b9c3bd', 'compiled': '#84958b', 'int8': '#507b68', 'mixed': '#b57a34', 'int4': '#d72e3b', 'sq': '#74828b', 'awq': '#9b8582', 'arc': '#bd5861', 'cascade': '#bd5861'}
SHORT = {'bf16': 'BF16', 'int8': 'W8A8', 'mixed': 'Head W4A4 + LLM W8A8', 'int4': 'W4A4'}
VIDEO_TYPES = {'.mp4': 'video/mp4', '.webm': 'video/webm'}
POSTER_TYPES = {'.avif', '.jpg', '.jpeg', '.png', '.webp'}


def esc(value):
    return html.escape(str(value), quote=True)


def load(name):
    return json.loads((ROOT / 'data' / (name + '.json')).read_text(encoding='utf-8'))


def number(value, digits=2):
    return f'{value:.{digits}f}'.rstrip('0').rstrip('.')


def table(headers, rows, label, attributes=None):
    head = ''.join(f'<th scope="col">{esc(x)}</th>' for x in headers)
    body = []
    for i, row in enumerate(rows):
        attr = attributes[i] if attributes else ''
        cells = ''.join(f'<{ "th scope=\"row\"" if j == 0 else "td"}>{esc(cell)}</{ "th" if j == 0 else "td"}>' for j, cell in enumerate(row))
        body.append(f'<tr {attr}>{cells}</tr>')
    return f'<div class="table-scroll" role="region" aria-label="{esc(label)}" tabindex="0"><table><caption>{esc(label)}</caption><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def bar_chart(rows, field, unit, title, chart_id, max_value=None):
    maximum = max_value or max(r[field] for r in rows)
    content = []
    for i, row in enumerate(rows):
        value = row[field]
        label = row.get('label', row.get('name', ''))
        tip_id = f'{chart_id}-tip-{i}'
        tooltip = f'{label}: {number(value)} {unit}'
        width = value / maximum * 100
        content.append(f'<div class="chart-row" tabindex="0" aria-describedby="{tip_id}"><div class="bar-label"><span>{esc(label)}</span><strong>{esc(number(value))}<small> {esc(unit)}</small></strong></div><div class="bar-track"><span class="bar-fill {esc(row["key"])}" style="--bar-width:{width:.3f}%;--bar-color:{COLORS[row["key"]]}"></span></div><span class="chart-tooltip" id="{tip_id}" role="tooltip">{esc(tooltip)}</span></div>')
    return f'<figure class="bar-chart"><figcaption><h4>{esc(title)}</h4><span>Lower is better</span></figcaption>{"".join(content)}<div class="chart-axis"><span>0</span><span>{number(maximum)} {esc(unit)}</span></div></figure>'


def make_desktop(data):
    sections = []
    for row in data['rows']:
        bars = [dict(key=key, label=label, latency=row[key]) for key, label in [('eager', 'Eager PyTorch'), ('compiled', 'Compiled float'), ('int8', 'FoldQuant W8A8'), ('int4', 'FoldQuant W4A4')]]
        chart = bar_chart(bars, 'latency', 'ms', row['name'], 'desktop-' + row['key'])
        notes = f'<p class="result-note">{esc(row["note"])}</p>' if row['note'] else ''
        sections.append(f'<div class="desktop-model" data-model="{row["key"]}"><div class="desktop-layout">{chart}<div class="desktop-takeaway"><span class="source-note">Compiled control: {esc(row["control"])}</span><p class="takeaway-value">{row["compiled_share_pct"]:.1f}<span>%</span></p><h4>of the eager-to-W4A4 reduction is already delivered by compilation.</h4><p>W4A4: <strong>{number(row["int4"])} ms</strong> per chunk.<br>W8A8: {number(row["int8"])} ms per chunk.</p><p class="source-note">Eager-relative speedup: {row["eager_speedup"]:.2f}×. Full chunk time, not amortized time per executed action.</p></div></div>{notes}</div>')
    return '\n'.join(sections)


def make_libero(data):
    cards = []
    for model in data['models']:
        row_map = {r['key']: r for r in model['rows']}
        parts = []
        keys = list(CORE) + [k for k in row_map if k not in CORE]
        for key in keys:
            row = row_map.get(key)
            label = SHORT.get(key, row['label'] if row else key)
            extra = ' hidden' if key not in CORE else ''
            attrs = f'data-config="{key}" data-core="{str(key in CORE).lower()}"'
            if row is None:
                parts.append(f'<div class="success-row missing" {attrs}{extra}><span class="success-label">{esc(label)}</span><span class="missing-value">— <small>Not evaluated</small></span></div>')
                continue
            # A common 0–100 scale prevents magnifying small within-checkpoint gaps.
            x = lambda pct: 4 + pct * 2.30
            low, high, mean = x(row['ci_low']), x(row['ci_high']), x(row['rate'])
            tip = f'{model["key"]}-{key}-tip'
            desc = f'{row["label"]}: {row["successes"]}/800 successes; {row["rate"]:.2f}%; 95% Wilson interval {row["ci_low"]:.1f}–{row["ci_high"]:.1f}%.'
            color = COLORS.get(key, '#bd5861')
            svg = f'<svg class="interval-plot" viewBox="0 0 240 28" aria-hidden="true"><path d="M4 14H234" stroke="#e0e6e1"/><path d="M4 11v6M119 11v6M234 11v6" stroke="#b4c1b8"/><path d="M{low:.2f} 14H{high:.2f}M{low:.2f} 9v10M{high:.2f} 9v10" stroke="{color}" stroke-width="2"/><circle cx="{mean:.2f}" cy="14" r="4.2" fill="{color}"/></svg>'
            parts.append(f'<div class="success-row" {attrs} tabindex="0" aria-describedby="{tip}"{extra}><span class="success-label">{esc(label)}</span>{svg}<strong>{row["rate"]:.2f}<small>%</small></strong><span class="chart-tooltip" role="tooltip" id="{tip}">{esc(desc)}</span></div>')
        cards.append(f'<article class="success-card" data-model="{model["key"]}"><div class="success-heading"><h4>{esc(model["name"])}</h4><span>K = {model["k"]}</span></div>{"".join(parts)}<div class="success-axis"><span>0</span><span>50</span><span>100%</span></div></article>')
    return ''.join(cards)


def make_libero_summary(data, fidelity):
    body = []
    for model in data['models']:
        rows = {r['key']: r for r in model['rows']}
        cos = fidelity['models'][model['key']]
        def sr(key):
            row = rows.get(key)
            if row is None:
                return '<td class="na">—</td>'
            loss = ' class="loss"' if key == 'int4' and model['key'] in ('smol', 'evo') else ''
            return f'<td{loss}><strong>{row["rate"]:.2f}%</strong><small>{row["successes"]}/800</small></td>'
        body.append(f'<tr><th scope="row">{esc(model["name"])}</th><td>{model["chunk_length"]}</td><td>{model["k"]}</td>{sr("bf16")}{sr("trt_bf16")}'
                    f'{sr("int8")}<td>{cos["int8"]:.5f}</td>{sr("int4")}<td>{cos["int4"]:.5f}</td>{('<td class="na pending-cell">Measuring…</td>' if model['key'] == 'n17' else sr("arc_sr_before_int8"))}{"<td class=\"na\">—</td>" if cos.get("res8") is None else f"<td>{cos['res8']:.5f}</td>"}</tr>')
    head = ('<thead><tr><th scope="col" rowspan="2">Checkpoint</th><th scope="col" rowspan="2">H</th><th scope="col" rowspan="2">K</th><th scope="colgroup" colspan="2">BF16 SR</th>'
            '<th scope="colgroup" colspan="2">FoldQuant W8A8</th><th scope="colgroup" colspan="2">FoldQuant W4A4</th><th scope="colgroup" colspan="2">FoldQuant W4A4 + o/d INT8</th></tr>'
            '<tr><th scope="col">PyTorch</th><th scope="col">TensorRT</th><th scope="col">SR ↑</th><th scope="col">Median cos ↑</th><th scope="col">SR ↑</th><th scope="col">Median cos ↑</th><th scope="col">SR ↑</th><th scope="col">Median cos ↑</th></tr></thead>')
    return (f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="FoldQuantVLA LIBERO results across six checkpoints">'
            f'<table class="libero-summary">{head}<tbody>{"".join(body)}</tbody></table></div>')


def make_latency_tables(jetson, desktop):
    def ms(v):
        t = f"{v:.2f}".rstrip("0")
        return t + "0" if t.endswith(".") else t
    def slug(name):
        return re.sub(r'[^a-z0-9]+', '-', name.lower().replace('π₀.₅', 'pi05')).strip('-')
    def ratio(x):
        cls = 'gain' if x >= 1.005 else ('loss' if x <= 0.995 else '')
        return f'<td class="{cls}"><strong>{x:.2f}×</strong></td>'
    def switcher(group, names):
        opts = ''.join(f'<option value="{slug(n)}">{esc(n)}</option>' for n in names)
        return (f'<div class="family-switch enhanced-control" hidden><label for="{group}-family">Model family'
                f'<select id="{group}-family" data-family-group="{group}">{opts}</select></label></div>')
    def panel(group, name, head, rows, foot=''):
        return (f'<div class="family-panel" data-family-group="{group}" data-family="{slug(name)}"><h4 class="family-name">{esc(name)}</h4>'
                f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="{esc(name)} latency">'
                f'<table class="results-table">{head}<tbody>{"".join(rows)}</tbody></table></div>{foot}</div>')

    # Jetson AGX Orin
    orin = load('jetson_orin')
    jhead = ('<thead><tr><th scope="col">Arm</th><th scope="col">Prec.</th><th scope="col">GPU (ms) ↓</th><th scope="col">E2E (ms) ↓</th>'
             '<th scope="col">Rate (Hz) ↑</th><th scope="col">vs TRT BF16 ↑</th><th scope="col">cos vs sm89 ↑</th></tr></thead>')
    jpanels = []
    for model in orin['models']:
        rows = []
        for r in model['arms']:
            kind = f' class="{r["kind"]}"' if r['kind'] else ''
            rows.append(f'<tr{kind}><th scope="row">{esc(r["label"])}</th><td class="prec">{esc(r["precision"])}</td><td>{r["gpu_ms"]:.1f}</td>'
                        f'<td><strong>{r["e2e_ms"]}</strong></td><td>{r["hz"]:.1f}</td>{"<td class=\"na\">ref</td>" if r["precision"] == "bf16" else ratio(r["speedup"])}<td>{r["cos"]:.5f}</td></tr>')
            if r['label'] == 'FoldQuant W4A4':
                rows.append('<tr class="ours"><th scope="row">FoldQuant W4A4 + o/d INT8</th><td class="prec">int4</td><td colspan="5" class="na pending-cell">Measuring…</td></tr>')
        jpanels.append(panel('jetson', model['name'], jhead, rows))
    jetson_html = switcher('jetson', [m['name'] for m in orin['models']]) + '<div class="family-panels">' + ''.join(jpanels) + '</div>'

    # Desktop: end-to-end and action head in one table per family
    sel = desktop['selective_int8']
    marks = {'smol': '†', 'evo': '‡'}
    heads = {r['name']: r for r in desktop['head_rows']}
    head_keys = {'GR00T N1.7': 'n17', 'GR00T N1.6': 'n16', 'GR00T N1.5': 'n15'}
    dpanels = []
    for r in desktop['rows']:
        key, h = r['key'], heads.get(r['name'])
        e_pre = sel['preliminary']['e2e_ms'].get(key)
        h_pre = sel['preliminary']['head_ms'].get(key)
        def sel_value(paper, pre):
            if paper is not None:
                return paper, None
            if pre and pre['display'] != 'measuring':
                return float(pre['display']), pre
            return None, pre
        e_sel, e_src = sel_value(sel['e2e_ms'].get(key), e_pre)
        h_sel, h_src = sel_value(sel['head_ms'].get(key) if h else None, h_pre)
        arms = [('Eager PyTorch', 'eager', 'baseline'), ('torch.compile', 'torch_compile', ''), ('TRT BF16 (float engine)', 'trt_bf16', ''),
                ('FoldQuant W8A8', 'int8', 'ours'), ('FoldQuant W4A4', 'int4', 'ours')]
        rows = []
        for label, field, kind in arms:
            e = r[field]
            mark = '<sup>§</sup>' if field == 'torch_compile' and key == 'n17' else ''
            head_cell = f'<td>{h[field]:.2f}</td>' if h else ''
            rows.append(f'<tr class="{kind}"><th scope="row">{label}</th><td><strong>{ms(e)}</strong>{mark}</td>{head_cell}'
                        +                         (('<td class="na">ref</td>' if field == 'eager' else ratio(r["eager"] / e))
                         + ('<td class="na">ref</td>' if field == 'trt_bf16' else ('<td class="na">—</td>' if field in ('eager', 'torch_compile') else ratio(r["trt_bf16"] / e))))
                        + '</tr>')
        if e_sel is None:
            status = 'Measuring…' if (e_pre and e_pre['display'] == 'measuring') else '—'
            rows.append(f'<tr class="ours"><th scope="row">FoldQuant W4A4 + o/d INT8</th><td colspan="{4 if h else 3}" class="na pending-cell">{status}</td></tr>')
        else:
            head_cell = (f'<td>{h_sel:.2f}</td>' if h_sel is not None else '<td class="na">—</td>') if h else ''
            if e_src is None:
                rows.append(f'<tr class="ours"><th scope="row">FoldQuant W4A4 + o/d INT8</th><td><strong>{ms(e_sel)}</strong></td>{head_cell}'
                            f'{ratio(r["eager"] / e_sel)}{ratio(r["trt_bf16"] / e_sel)}</tr>')
            else:
                rows.append(f'<tr class="ours"><th scope="row">FoldQuant W4A4 + o/d INT8</th><td><strong>{ms(e_sel)}</strong></td>{head_cell}'
                            '<td class="na">—</td><td class="na">—</td></tr>')
        facts = [('Compile share', f'{r["compiled_share_pct"]:.1f}%'),
                 ('8→4 gain', f'{"−" if r["int8_to_int4_pct"] < 0 else ""}{abs(r["int8_to_int4_pct"]):.1f}%')]
        if e_sel is not None:
            m = re.search(r'same runs? W4A4 ([0-9.]+)', e_src['note']) if e_src else None
            base = float(m.group(1)) if m else (r['int4'] if e_src is None else None)
            if base is not None:
                facts.append(('o/d INT8 costs', f'+{e_sel - base:.1f} ms over W4A4 in the same run'))
        bits = [f'{k} {v}' for k, v in facts]
        if r.get('note'):
            bits.append(f'{marks.get(key, "")} {r["note"]}'.strip())
        foot = f'<p class="family-note">{esc(" · ".join(bits))}</p>'
        dhead = ('<thead><tr><th scope="col">Arm</th><th scope="col">End-to-end (ms) ↓</th>' + ('<th scope="col">Action head (ms) ↓</th>' if h else '')
                 + '<th scope="col">vs eager ↑</th><th scope="col">vs TRT BF16 ↑</th></tr></thead>')
        dpanels.append(panel('desktop', r['name'], dhead, rows, foot))
    desktop_html = switcher('desktop', [r['name'] for r in desktop['rows']]) + '<div class="family-panels">' + ''.join(dpanels) + '</div>'
    return jetson_html, desktop_html, ''


def make_benchmark_preview(compare):
    panels = []
    for panel in compare['panels']:
        body = []
        for row in panel['rows']:
            if row['kind'] == 'pending':
                body.append(f'<tr class="pending-row"><th scope="row">{esc(row["method"])}</th><td>{esc(row["precision"])}</td>'
                            f'<td colspan="6" class="pending-cell">{esc(row["status"].capitalize())}…</td></tr>')
                continue
            total = sum(row['suites'])
            suites = ''.join(f'<td>{n}</td>' for n in row['suites'])
            cos = 'Reference' if row.get('ref') else ('—' if row['cos'] is None else f'{row["cos"]:.5f}')
            body.append(f'<tr class="{row["kind"]}"><th scope="row">{esc(row["method"])}</th><td>{esc(row["precision"])}</td>{suites}'
                        f'<td><strong>{total / 8:.2f}%</strong><small>{total}/800</small></td><td>{cos}</td></tr>')
        panels.append(
            f'<section class="benchmark-panel" id="benchmark-{panel["key"]}" aria-labelledby="benchmark-tab-{panel["key"]}">'
            f'<header><div><h3>{esc(panel["name"])}</h3><p>{esc(panel["meta"])}</p></div><span>200 episodes / suite</span></header>'
            f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="{esc(panel["name"])} LIBERO comparison">'
            '<table class="compare-table"><thead><tr><th scope="col">Method</th><th scope="col">Precision</th><th scope="col">Spatial</th><th scope="col">Object</th>'
            f'<th scope="col">Goal</th><th scope="col">Long</th><th scope="col">Success rate ↑</th><th scope="col">Median cos ↑<small>{esc(panel["cos_label"])}</small></th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></section>')
    return ''.join(panels)


def make_resources(data):
    icons = {'code': '&lt;/&gt;', 'models': '◇', 'appendix': 'A+', 'bibtex': 'B'}
    items = []
    for item in data['items']:
        icon = icons.get(item['key'], '↗')
        content = (f'<span class="resource-icon" aria-hidden="true">{icon}</span>'
                   f'<span><strong>{esc(item["label"])}</strong><small>{esc(item["detail"])}</small></span>')
        href = item.get('href', '')
        if not href:
            items.append(f'<span class="resource-link pending" aria-disabled="true">{content}</span>')
            continue
        if not href.startswith('#'):
            parsed = urlparse(href)
            if parsed.scheme != 'https' or not parsed.netloc:
                raise ValueError(f'Public resource links must use HTTPS: {href}')
            attrs = ' target="_blank" rel="noopener noreferrer"'
        else:
            attrs = ''
        items.append(f'<a class="resource-link" href="{esc(href)}"{attrs}>{content}</a>')
    return ''.join(items)


def safe_media_path(value, allowed_suffixes):
    """Return a safe path below media/real-robot, or None for an empty slot."""
    if not value:
        return None
    if not isinstance(value, str) or '\\' in value or not re.fullmatch(r'[A-Za-z0-9._/-]+', value):
        raise ValueError('Real-robot media paths may contain only letters, numbers, dots, slashes, underscores, and hyphens.')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.suffix.lower() not in allowed_suffixes:
        raise ValueError(f'Unsafe or unsupported real-robot media path: {value}')
    source = ROOT / 'media' / 'real-robot' / Path(*path.parts)
    if not source.is_file():
        raise ValueError(f'Referenced real-robot media does not exist: {value}')
    return path


def make_robot_trials(data):
    trials, task_tabs, media = [], [], []
    seen = set()
    for trial_index, trial in enumerate(data['trials'], start=1):
        key = trial['key']
        if key in seen or not re.fullmatch(r'[a-z0-9-]+', key):
            raise ValueError('Real-robot trial keys must be unique lowercase slugs.')
        seen.add(key)
        views = trial['views']
        if len(views) != 1:
            raise ValueError('Each real-robot task must contain exactly one evaluation video.')
        rendered_views = []
        for view_index, view in enumerate(views, start=1):
            src = safe_media_path(view.get('src'), set(VIDEO_TYPES))
            poster = safe_media_path(view.get('poster'), POSTER_TYPES)
            if src:
                media.append(src)
                media_path = f'media/real-robot/{src.as_posix()}'
                poster_attr = ''
                if poster:
                    media.append(poster)
                    poster_attr = f' poster="media/real-robot/{esc(poster.as_posix())}"'
                screen = (f'<video controls playsinline preload="metadata" aria-label="{esc(view["label"])} for {esc(trial["title"])}"{poster_attr}>'
                          f'<source src="{esc(media_path)}" type="{VIDEO_TYPES[src.suffix.lower()]}">'
                          'This browser cannot play the experiment video.</video>')
                state = 'has-video'
            else:
                screen = ('<div class="robot-placeholder" role="img" aria-label="Video forthcoming">'
                          '<span class="placeholder-message"><i aria-hidden="true">▶</i><strong>Video forthcoming</strong></span></div>')
                state = 'is-placeholder'
            rendered_views.append(f'<div class="robot-screen {state}">{screen}</div>')
        platform = trial['platform']
        name = trial['title'].split('·')[-1].strip()
        trials.append(
            f'<article class="robot-card" id="robot-{esc(key)}" data-robot-task="robot-{esc(key)}">'
            f'{rendered_views[0]}'
            f'<div class="robot-card-body"><h3>{esc(platform)} · {esc(name)}</h3>'
            f'<span class="robot-tag">{esc(platform)}</span>'
            f'<p>{esc(trial["instruction"])}</p></div></article>')
    return ''.join(trials), ''.join(task_tabs), media


def make_robot_results(data):
    res = data['results']
    head = ''.join(f'<th scope="col">{esc(t["platform"])} · {esc(t["title"].split("·")[-1].strip())}</th>' for t in data['trials'])
    body = []
    for arm in res['arms']:
        cells, done, total = [], 0, 0
        for n in arm['tasks']:
            if n is None:
                cells.append('<td class="na pending-cell">Measuring…</td>')
            else:
                cells.append(f'<td>{n}/{res["episodes_per_task"]}</td>'); done += n; total += res['episodes_per_task']
        lo, hi = arm['wilson']
        scope = '' if total == res['episodes_per_task'] * len(arm['tasks']) else '<small>tasks 1–3</small>'
        kind = f' class="{arm["kind"]}"' if arm['kind'] else ''
        body.append(f'<tr{kind}><th scope="row">{esc(arm["label"])}</th>{"".join(cells)}'
                    f'<td><strong>{100 * done / total:.1f}%</strong><small>{done}/{total} · [{lo:.1f}, {hi:.1f}]</small>{scope}</td></tr>')
    return (f'<div class="benchmark-panel robot-results"><header><div><h3>Real-robot success</h3><p>{esc(res["policy"])} · {res["episodes_per_task"]} episodes per task</p></div><span class="source-tag">Real robot</span></header>'
            f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="Real-robot success"><table class="results-table">'
            f'<thead><tr><th scope="col">Arm</th>{head}<th scope="col">Success ↑ · Wilson 95%</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>'
            '<p class="latency-note">Logged-observation action cosine against BF16 PyTorch — ALOHA: W8A8 0.99999 · W4A4 0.99930 · W4A4 + o/d INT8 0.99966; '
            'SO-101: 0.99999 · 0.99929 · 0.99983; TRT BF16 0.99999. π₀.₅ real-robot runs on three SO-101 tasks are in progress.</p></div>')


def make_overview_media():
    source = ROOT / 'media' / 'overview.mp4'
    shell = '<span class="video-kicker"><i aria-hidden="true"></i> Overview film</span>'
    if source.is_file():
        video = ('<video controls playsinline preload="metadata" aria-label="FoldQuantVLA overview video">'
                 '<source src="media/overview.mp4" type="video/mp4">'
                 'This browser cannot play the overview video.</video>')
        return f'<div class="overview-video-frame has-video">{shell}{video}</div>', source
    placeholder = ('<span class="overview-play" aria-hidden="true">▶</span>'
                   '<div><strong>Fold once. Execute natively.</strong><span>Overview video forthcoming</span></div>')
    return f'<div class="overview-video-frame" role="img" aria-label="Overview video forthcoming">{shell}{placeholder}</div>', None


def build(output, base_url=''):
    meta, jetson, desktop, libero, fidelity, real_robot, resources = [load(n) for n in ('metadata', 'jetson', 'desktop', 'libero', 'fidelity', 'real_robot', 'resources')]
    campaigns = sum(len(m['rows']) for m in libero['models'])
    if campaigns != 59 or campaigns * libero['episodes_per_run'] != 47200 or len(libero['models']) != 6:
        raise ValueError('Reconcile the campaign totals before changing the published highlights.')
    if base_url:
        parsed = urlparse(base_url)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('--base-url must be an absolute HTTP(S) site URL without query or fragment.')
        base_url = base_url.rstrip('/') + '/'
    tokens = {k: esc(v) for k, v in meta.items()}
    tokens.update(social_image=esc(base_url + 'assets/social-card.png'), canonical=f'<link rel="canonical" href="{esc(base_url)}">' if base_url else '', speedup=f'{jetson["rows"][3]["speedup_vs_float"]:.2f}', compression=f'{jetson["rows"][0]["engine_mb"] / jetson["rows"][3]["engine_mb"]:.2f}', episode_count=f'{campaigns * libero["episodes_per_run"]:,}', campaign_count=str(campaigns), comparison_count=str(libero['comparison_count']), significant_loss_count=str(libero['significant_loss_count']), stable_comparison_count=str(libero['comparison_count'] - libero['significant_loss_count']))
    tokens['resource_links'] = make_resources(resources)
    tokens['jetson_charts'] = bar_chart(jetson['rows'], 'e2e_ms', 'ms', 'Observation-to-action latency', 'jetson-latency', 200) + bar_chart(jetson['rows'], 'engine_mb', 'MB', 'Serialized engine size', 'jetson-size', 6000)
    tokens['jetson_table'] = table(['Configuration', 'GPU (ms)', 'E2E (ms)', 'Hz', 'vs float', 'Engine (MB)', 'Build (s)'], [[r['label'], number(r['gpu_ms']),r['e2e_ms'],f'{r["hz"]:.1f}',f'{r["speedup_vs_float"]:.2f}×',f'{r["engine_mb"]:,}',f'{r["build_s"]:,}'] for r in jetson['rows']], 'Table IV · Jetson AGX Orin / GR00T N1.6')
    tokens['jetson_summary'], tokens['desktop_summary'], _ = make_latency_tables(jetson, desktop)
    tokens['desktop_options'] = ''.join(f'<option value="{r["key"]}">{esc(r["name"])}</option>' for r in desktop['rows'])
    tokens['desktop_table'] = table(['Checkpoint', 'Eager (ms)', 'Compiled (ms)', 'W8A8 (ms)', 'W4A4 (ms)', 'Eager / W4A4', 'Compile share', '8→4 reduction', 'Control'], [[r['name'],number(r['eager']),number(r['compiled']),number(r['int8']),number(r['int4']),f'{r["eager_speedup"]:.2f}×',f'{r["compiled_share_pct"]:.1f}%',f'{r["int8_to_int4_pct"]:.1f}%',r['control']] for r in desktop['rows']], 'Table II · Desktop end-to-end precision ladder')
    tokens['head_table'] = table(['Checkpoint','Eager (ms)','Compiled float (ms)','W8A8 (ms)','W4A4 (ms)'], [[r['name']]+[f'{r[k]:.2f}' for k in ('eager','compiled','int8','int4')] for r in desktop['head_rows']], 'Table II · Action-head-only latency')
    tokens['desktop_protocol'] = esc(desktop['protocol'])
    tokens['libero_summary'] = make_libero_summary(libero, fidelity)
    tokens['benchmark_preview'] = make_benchmark_preview(load('compare'))
    tokens['libero_options'] = ''.join(f'<option value="{m["key"]}">{esc(m["name"])}</option>' for m in libero['models'])
    config_labels = {}
    table_rows, attrs = [], []
    for model in libero['models']:
        for row in model['rows']:
            config_labels[row['key']] = row['label']
            table_rows.append([model['name'],model['k'],row['label'],f'{row["successes"]}/800',f'{row["rate"]:.2f}%',f'[{row["ci_low"]:.1f}, {row["ci_high"]:.1f}]'])
            attrs.append(f'data-model="{model["key"]}" data-config="{row["key"]}"')
    tokens['libero_config_options'] = ''.join(f'<option value="{esc(k)}">{esc(v)}</option>' for k,v in config_labels.items())
    tokens['libero_table'] = table(['Checkpoint','K','Configuration','Successes','Success rate','95% CI (%)'],table_rows,'Table V · All 59 closed-loop LIBERO campaigns',attrs)
    tokens['robot_intro'] = esc(real_robot['intro'])
    tokens['robot_trials'], tokens['robot_task_tabs'], robot_media = make_robot_trials(real_robot)
    tokens['robot_results'] = make_robot_results(real_robot)
    tokens['overview_media'], overview_media = make_overview_media()
    tokens['bibtex'] = esc('@misc{anonymous2026foldquantvla,\n  title  = {' + meta['title'] + '},\n  author = {{Anonymous Authors}},\n  year   = {2026},\n  note   = {Anonymous ICRA submission}\n}')
    page = (ROOT / 'index.template.html').read_text(encoding='utf-8')
    for key,value in tokens.items():
        page = page.replace('{{' + key + '}}',value)
    # Only template markers (not the nested braces in BibTeX) are invalid.
    if re.search(r'\{\{[a-z_]+\}\}',page):
        raise ValueError('Unfilled template token')
    def version_asset(match):
        attr, path = match.groups()
        if path.endswith(('.css', '.js', '.svg', '.png')):
            digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()[:12]
            return f'{attr}="{path}?v={digest}"'
        return match.group(0)
    page = re.sub(r'(src|srcset|href)="(assets/[^"]+)"', version_asset, page)
    output = Path(output)
    if output.resolve() == ROOT or ROOT in output.resolve().parents:
        raise ValueError('Build output must be outside the website source directory.')
    output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT / 'assets',output / 'assets',dirs_exist_ok=True)
    for path in dict.fromkeys(robot_media):
        source = ROOT / 'media' / 'real-robot' / Path(*path.parts)
        destination = output / 'media' / 'real-robot' / Path(*path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if overview_media:
        destination = output / 'media' / 'overview.mp4'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(overview_media, destination)
    (output/'index.html').write_text(page,encoding='utf-8')
    (output/'.nojekyll').write_text('',encoding='utf-8')
    (output/'robots.txt').write_text('User-agent: *\nDisallow: /\n',encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT.parent / 'dist' / 'website'))
    parser.add_argument('--base-url',default='')
    args = parser.parse_args()
    print(f'Built anonymous project page: {build(args.output,args.base_url)}')
