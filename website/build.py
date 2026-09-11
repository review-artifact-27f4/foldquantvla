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
COLORS = {'bf16': '#84958b', 'float': '#84958b', 'eager': '#b9c3bd', 'compiled': '#84958b', 'int8': '#507b68', 'mixed': '#b57a34', 'int4': '#d72e3b', 'sq': '#74828b', 'awq': '#9b8582', 'arc': '#bd5861', 'arc_shg': '#bd5861', 'cascade': '#bd5861'}
SHORT = {'bf16': 'BF16', 'int8': 'W8A8', 'mixed': 'Head 4 / LM 8', 'int4': 'W4A4'}
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
            svg = f'<svg class="interval-plot" viewBox="0 0 240 28" aria-hidden="true"><path d="M4 14H234" stroke="#e0e6e1"/><path d="M4 11v6M119 11v6M234 11v6" stroke="#b4c1b8"/><path d="M{low:.2f} 14H{high:.2f}M{low:.2f} 9v10M{high:.2f} 9v10" stroke="{COLORS[key]}" stroke-width="2"/><circle cx="{mean:.2f}" cy="14" r="4.2" fill="{COLORS[key]}"/></svg>'
            parts.append(f'<div class="success-row" {attrs} tabindex="0" aria-describedby="{tip}"{extra}><span class="success-label">{esc(label)}</span>{svg}<strong>{row["rate"]:.2f}<small>%</small></strong><span class="chart-tooltip" role="tooltip" id="{tip}">{esc(desc)}</span></div>')
        cards.append(f'<article class="success-card" data-model="{model["key"]}"><div class="success-heading"><h4>{esc(model["name"])}</h4><span>K = {model["k"]}</span></div>{"".join(parts)}<div class="success-axis"><span>0</span><span>50</span><span>100%</span></div></article>')
    return ''.join(cards)


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
    trials, media = [], []
    seen = set()
    for trial_index, trial in enumerate(data['trials'], start=1):
        key = trial['key']
        if key in seen or not re.fullmatch(r'[a-z0-9-]+', key):
            raise ValueError('Real-robot trial keys must be unique lowercase slugs.')
        seen.add(key)
        views = trial['views']
        if not 1 <= len(views) <= 3:
            raise ValueError('Each real-robot trial must contain one to three camera views.')
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
                          '<svg class="robot-schematic" viewBox="0 0 280 180" aria-hidden="true">'
                          '<path d="M58 151h164M90 148l12-29 38-8 25-37 38 11"/>'
                          '<circle cx="102" cy="119" r="8"/><circle cx="140" cy="111" r="8"/>'
                          '<circle cx="165" cy="74" r="8"/><path d="m203 85 18-12m-18 12 16 8"/>'
                          '</svg><span class="focus-corner top-left"></span><span class="focus-corner top-right"></span>'
                          '<span class="focus-corner bottom-left"></span><span class="focus-corner bottom-right"></span>'
                          '<span class="placeholder-message"><i aria-hidden="true">▶</i><strong>Video forthcoming</strong></span></div>')
                state = 'is-placeholder'
            rendered_views.append(
                f'<figure class="robot-view {state}{" primary-view" if view_index == 1 else ""}">'
                f'<div class="robot-screen"><span class="camera-id"><i aria-hidden="true"></i> CAM {view_index:02d}</span>{screen}</div>'
                f'<figcaption><strong>{esc(view["label"])}</strong><span>{esc(view["detail"])}</span></figcaption></figure>')
        primary = rendered_views[0]
        secondary = ''.join(rendered_views[1:])
        media_class = 'robot-media-grid single-view' if len(views) == 1 else 'robot-media-grid'
        secondary_html = '' if len(views) == 1 else f'<div class="robot-secondary{" one-view" if len(views) == 2 else ""}">{secondary}</div>'
        status = 'Experiment video' if any(view.get('src') for view in views) else 'Media slot ready'
        trials.append(
            f'<article class="robot-trial" id="robot-{esc(key)}">'
            f'<header class="robot-trial-header"><div><span>Trial {trial_index:02d}</span><h3>{esc(trial["title"])}</h3>'
            f'<p>{esc(trial["instruction"])}</p></div><div class="robot-trial-meta"><span>{esc(trial["policy"])}</span>'
            f'<strong><i aria-hidden="true"></i>{status}</strong></div></header>'
            f'<div class="{media_class}">{primary}{secondary_html}</div></article>')
    return ''.join(trials), media


def build(output, base_url=''):
    meta, jetson, desktop, libero, real_robot = [load(n) for n in ('metadata', 'jetson', 'desktop', 'libero', 'real_robot')]
    campaigns = sum(len(m['rows']) for m in libero['models'])
    if campaigns != 40 or len(libero['models']) != 6:
        raise ValueError('Reconcile the campaign totals before changing the published highlights.')
    if base_url:
        parsed = urlparse(base_url)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('--base-url must be an absolute HTTP(S) site URL without query or fragment.')
        base_url = base_url.rstrip('/') + '/'
    tokens = {k: esc(v) for k, v in meta.items()}
    tokens.update(social_image=esc(base_url + 'assets/social-card.png'), canonical=f'<link rel="canonical" href="{esc(base_url)}">' if base_url else '', speedup=f'{jetson["rows"][3]["speedup_vs_float"]:.2f}', compression=f'{jetson["rows"][0]["engine_mb"] / jetson["rows"][3]["engine_mb"]:.2f}', episode_count=f'{campaigns * libero["episodes_per_run"]:,}')
    tokens['jetson_charts'] = bar_chart(jetson['rows'], 'e2e_ms', 'ms', 'Observation-to-action latency', 'jetson-latency', 200) + bar_chart(jetson['rows'], 'engine_mb', 'MB', 'Serialized engine size', 'jetson-size', 6000)
    tokens['jetson_table'] = table(['Configuration', 'GPU (ms)', 'E2E (ms)', 'Hz', 'vs float', 'Engine (MB)', 'Build (s)'], [[r['label'], number(r['gpu_ms']),r['e2e_ms'],f'{r["hz"]:.1f}',f'{r["speedup_vs_float"]:.2f}×',f'{r["engine_mb"]:,}',f'{r["build_s"]:,}'] for r in jetson['rows']], 'Table III · Jetson AGX Orin / GR00T N1.6')
    tokens['desktop_charts'] = make_desktop(desktop)
    tokens['desktop_options'] = ''.join(f'<option value="{r["key"]}">{esc(r["name"])}</option>' for r in desktop['rows'])
    tokens['desktop_table'] = table(['Checkpoint', 'Eager (ms)', 'Compiled (ms)', 'W8A8 (ms)', 'W4A4 (ms)', 'Eager / W4A4', 'Compile share', '8→4 reduction', 'Control'], [[r['name'],number(r['eager']),number(r['compiled']),number(r['int8']),number(r['int4']),f'{r["eager_speedup"]:.2f}×',f'{r["compiled_share_pct"]:.1f}%',f'{r["int8_to_int4_pct"]:.1f}%',r['control']] for r in desktop['rows']], 'Table II · Desktop end-to-end precision ladder')
    tokens['head_table'] = table(['Checkpoint','Eager (ms)','Compiled float (ms)','W8A8 (ms)','W4A4 (ms)'], [[r['name']]+[f'{r[k]:.2f}' for k in ('eager','compiled','int8','int4')] for r in desktop['head_rows']], 'Table II · Action-head-only latency')
    tokens['desktop_protocol'] = esc(desktop['protocol'])
    tokens['libero_charts'] = make_libero(libero)
    tokens['libero_options'] = ''.join(f'<option value="{m["key"]}">{esc(m["name"])}</option>' for m in libero['models'])
    config_labels = {}
    table_rows, attrs = [], []
    for model in libero['models']:
        for row in model['rows']:
            config_labels[row['key']] = row['label']
            table_rows.append([model['name'],model['k'],row['label'],f'{row["successes"]}/800',f'{row["rate"]:.2f}%',f'[{row["ci_low"]:.1f}, {row["ci_high"]:.1f}]'])
            attrs.append(f'data-model="{model["key"]}" data-config="{row["key"]}"')
    tokens['libero_config_options'] = ''.join(f'<option value="{esc(k)}">{esc(v)}</option>' for k,v in config_labels.items())
    tokens['libero_table'] = table(['Checkpoint','K','Configuration','Successes','Success rate','95% CI (%)'],table_rows,'Table IV · All 40 closed-loop LIBERO campaigns',attrs)
    tokens['robot_intro'] = esc(real_robot['intro'])
    tokens['robot_trials'], robot_media = make_robot_trials(real_robot)
    tokens['bibtex'] = esc('@misc{anonymous2026foldquantvla,\n  title = {' + meta['title'] + '},\n  author = {{Anonymous Authors}},\n  year = {2026},\n  note = {Anonymous manuscript}\n}')
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
