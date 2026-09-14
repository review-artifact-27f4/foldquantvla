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
                    f'{sr("int8")}<td>{cos["int8"]:.5f}</td>{sr("int4")}<td>{cos["int4"]:.5f}</td>{sr("arc_sr_before_int8")}</tr>')
    head = ('<thead><tr><th scope="col" rowspan="2">Checkpoint</th><th scope="col" rowspan="2">H</th><th scope="col" rowspan="2">K</th><th scope="colgroup" colspan="2">BF16 SR</th>'
            '<th scope="colgroup" colspan="2">FoldQuant W8A8</th><th scope="colgroup" colspan="2">FoldQuant W4A4</th><th scope="col" rowspan="2">W4A4 + Res INT8 SR</th></tr>'
            '<tr><th scope="col">PyTorch</th><th scope="col">TensorRT</th><th scope="col">SR ↑</th><th scope="col">Median cos ↑</th><th scope="col">SR ↑</th><th scope="col">Median cos ↑</th></tr></thead>')
    return (f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="FoldQuantVLA LIBERO results across six checkpoints">'
            f'<table class="libero-summary">{head}<tbody>{"".join(body)}</tbody></table></div>')


def make_latency_tables(jetson, desktop):
    def ms(v):
        t = f"{v:.2f}".rstrip("0")
        return t + "0" if t.endswith(".") else t
    dash = '<td class="na">—</td>'
    ours = {'int8', 'mixed', 'int4'}
    jsel = jetson['selective_int8']
    jrows = []
    for r in jetson['rows']:
        kind = ' class="ours"' if r['key'] in ours else (' class="baseline"' if r['key'] == 'float' else '')
        gain = ' class="gain"' if r['speedup_vs_float'] > 1 else (' class="loss"' if r['speedup_vs_float'] < 1 else '')
        jrows.append(f'<tr{kind}><th scope="row">{esc(r["label"])}</th><td class="prec">{esc(r["precision"])}</td><td>{ms(r["gpu_ms"])}</td><td><strong>{r["e2e_ms"]}</strong></td>'
                     f'<td>{r["hz"]:.1f}</td><td{gain}><strong>{r["speedup_vs_float"]:.2f}×</strong></td><td>{r["engine_mb"]:,}</td><td>{r["build_s"]:,}</td></tr>')
        if r['key'] == jsel['after']:
            jrows.append(f'<tr class="sub-row pending-row"><th scope="row">↳ {esc(jsel["label"])}</th><td colspan="7" class="na pending-cell">{esc(jsel["status"])}</td></tr>')
    jhead = ('<thead><tr><th scope="col">Configuration</th><th scope="col">Prec.</th><th scope="col">GPU (ms) ↓</th><th scope="col">E2E (ms) ↓</th><th scope="col">Rate (Hz) ↑</th>'
             '<th scope="col">vs TRT BF16 ↑</th><th scope="col">Engine (MB) ↓</th><th scope="col">Build (s)</th></tr></thead>')
    marks = {'smol': '†', 'evo': '‡'}
    sel = desktop['selective_int8']
    head_keys = {'GR00T N1.7': 'n17', 'GR00T N1.6': 'n16', 'GR00T N1.5': 'n15'}
    def ladder(rows, key_of, mark_of, sel_map, fmt, cls):
        out = []
        for r in rows:
            v = sel_map.get(key_of(r))
            pre = sel['preliminary']['e2e_ms' if cls == 'desktop-row' else 'head_ms'].get(key_of(r))
            if v is not None:
                sel_cell = f'<td class="ours-col"><strong>{fmt(v)}</strong></td>'
            elif pre:
                sel_cell = f'<td class="ours-col"><strong>{esc(pre["display"])}</strong></td>'
            else:
                sel_cell = '<td class="na" title="Measurement pending">—</td>'
            out.append(f'<tr class="{cls}"><th scope="row">{esc(r["name"])}<sup>{mark_of(r)}</sup></th><td>{fmt(r["eager"])}</td><td>{fmt(r["torch_compile"])}{"<sup>§</sup>" if r.get("key") == "n17" or (r.get("name") == "GR00T N1.7" and cls == "desktop-row") else ""}</td><td>{fmt(r["trt_bf16"])}</td>'
                       f'<td>{fmt(r["int8"])}</td><td class="ours-col"><strong>{fmt(r["int4"])}</strong></td>{sel_cell}'
                       f'<td class="gain"><strong>{r["eager_speedup"]:.2f}×</strong></td><td class="{"gain" if r["trt_bf16"] / r["int4"] >= 1.005 else ""}"><strong>{r["trt_bf16"] / r["int4"]:.2f}×</strong></td><td>{r["compiled_share_pct"]:.1f}%</td>'
                       f'<td>{"−" if r["int8_to_int4_pct"] < 0 else ""}{abs(r["int8_to_int4_pct"]):.1f}%</td></tr>')
        return out
    drows = ladder(desktop['rows'], lambda r: r['key'], lambda r: marks.get(r['key'], ''), sel['e2e_ms'], ms, 'desktop-row')
    hrows = ladder(desktop['head_rows'], lambda r: head_keys[r['name']], lambda r: '', sel['head_ms'], lambda v: f'{v:.2f}', 'head-row')
    dhead = ('<thead><tr><th scope="col">Checkpoint</th><th scope="col">Eager (ms) ↓</th><th scope="col">torch.compile (ms) ↓</th><th scope="col">TRT BF16 (ms) ↓</th><th scope="col">W8A8 (ms) ↓</th>'
             '<th scope="col" class="ours-col">W4A4 (ms) ↓</th><th scope="col" class="ours-col">W4A4 + o/d INT8 (ms) ↓</th><th scope="col">W4A4 vs eager ↑</th><th scope="col">W4A4 vs TRT BF16 ↑</th><th scope="col">Compile share*</th><th scope="col">8→4 gain</th></tr></thead>')
    def wrap(label, head, rows):
        return (f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="{esc(label)}">'
                f'<table class="results-table">{head}<tbody>{"".join(rows)}</tbody></table></div>')
    return wrap('Jetson AGX Orin latency', jhead, jrows), wrap('Desktop latency ladder', dhead, drows), wrap('Desktop action-head latency', dhead, hrows)


def make_benchmark_preview(data, fidelity):
    panels = []
    for model_key in ('n17', 'pi05'):
        model = next(model for model in data['models'] if model['key'] == model_key)
        rows = {row['key']: row for row in model['rows']}
        selected = [rows['bf16'], rows['int8'], rows['int4']]
        body = []
        for row in selected:
            kind = 'baseline' if row['key'] == 'bf16' else ('ours' if row['key'] == 'int4' else '')
            precision = 'BF16' if row['key'] == 'bf16' else ('W8A8' if row['key'] == 'int8' else 'W4A4')
            cosine = fidelity['models'][model_key][row['key']]
            body.append(
                f'<tr class="{kind}"><th scope="row">{esc(row["label"])}</th><td>{precision}</td>'
                f'<td>{row["successes"]}/800</td><td><strong>{row["rate"]:.2f}%</strong></td>'
                f'<td>{"Reference" if cosine is None else f"{cosine:.5f}"}</td></tr>')
        for method in ('DuQuant', 'HoloQVLA'):
            body.append(
                f'<tr class="pending-row"><th scope="row">{method}</th><td>W4A4</td><td>Evaluation pending</td><td>—</td><td>—</td></tr>')
        panels.append(
            f'<section class="benchmark-panel" id="benchmark-{model_key}" aria-labelledby="benchmark-tab-{model_key}">'
            f'<header><div><h3>{esc(model["name"])}</h3><p>K = {model["k"]} · 40 tasks · 20 initial states</p></div><span>800 episodes / arm</span></header>'
            f'<div class="benchmark-table-scroll" tabindex="0" role="region" aria-label="{esc(model["name"])} LIBERO success comparison">'
            '<table><thead><tr><th scope="col">Method</th><th scope="col">Precision</th><th scope="col">Successes</th><th scope="col">Success rate ↑</th><th scope="col">Median action cosine ↑</th></tr></thead>'
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
    tokens['jetson_summary'], tokens['desktop_summary'], tokens['head_summary'] = make_latency_tables(jetson, desktop)
    tokens['desktop_options'] = ''.join(f'<option value="{r["key"]}">{esc(r["name"])}</option>' for r in desktop['rows'])
    tokens['desktop_table'] = table(['Checkpoint', 'Eager (ms)', 'Compiled (ms)', 'W8A8 (ms)', 'W4A4 (ms)', 'Eager / W4A4', 'Compile share', '8→4 reduction', 'Control'], [[r['name'],number(r['eager']),number(r['compiled']),number(r['int8']),number(r['int4']),f'{r["eager_speedup"]:.2f}×',f'{r["compiled_share_pct"]:.1f}%',f'{r["int8_to_int4_pct"]:.1f}%',r['control']] for r in desktop['rows']], 'Table II · Desktop end-to-end precision ladder')
    tokens['head_table'] = table(['Checkpoint','Eager (ms)','Compiled float (ms)','W8A8 (ms)','W4A4 (ms)'], [[r['name']]+[f'{r[k]:.2f}' for k in ('eager','compiled','int8','int4')] for r in desktop['head_rows']], 'Table II · Action-head-only latency')
    tokens['desktop_protocol'] = esc(desktop['protocol'])
    tokens['libero_summary'] = make_libero_summary(libero, fidelity)
    tokens['benchmark_preview'] = make_benchmark_preview(libero, fidelity)
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
