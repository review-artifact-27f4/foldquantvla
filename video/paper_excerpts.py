#!/usr/bin/env python3
"""Render excerpts of the submitted manuscript (equations, propositions, tables) and its
figures to PNG for the submission video, so the film shows the paper's own typesetting.

  python3 video/paper_excerpts.py --paper ~/Work/VLAOpt\\(1\\)/overleaft_paper

Excerpts are cut from main.tex between anchor strings, so they track the manuscript.
Cross-references that leave an excerpt are replaced by the paper's numbers (REFS below).
"""
import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figures' / 'paper'

# (name, start anchor, end anchor [exclusive], equation counter before the excerpt)
EXCERPTS = [
    ('fold', r'\subsection{A consistent fold}', r'\subsection{Transforms supported by the runtime}', 1),
    ('transforms', r'\subsection{Transforms supported by the runtime}', r'\subsection{Normalization gains}', 2),
    ('norm', r'\subsection{Normalization gains}', r'\subsection{Offline parameters and runtime computation}', 3),
    ('quant', r'\subsection{Offline parameters and runtime computation}', r'\begin{figure}[!t]', 4),
    ('rounding', r'\subsection{Rounding and native execution}', r'\subsection{Selective INT8 at output projections}', 6),
    ('selective', r'\subsection{Selective INT8 at output projections}', r'\section{Experimental Protocol}', 7),
]
TABLES = ['tab:sota', 'tab:success', 'tab:ablation', 'tab:robot', 'tab:robot_pi', 'tab:simpler']
FIGURES = ['teaser', 'fig_overview', 'fig_excute', 'latency', 'fidelity', 'fig_real_tasks_compact']
# Paper numbering, for references that point outside an excerpt.
REFS = {'eq:policy': '1', 'eq:fold': '2', 'eq:family': '3', 'eq:norm': '4', 'eq:quant': '5', 'eq:gptq': '7',
        'prop:homog': '2', 'fig:teaser': '1', 'fig:fold': '2', 'fig:arch': '3', 'fig:latency': '4', 'fig:real_tasks': '5', 'fig:fidelity': '6',
        'tab:sota': 'I', 'tab:success': 'II', 'tab:simpler': 'III', 'tab:ablation': 'IV', 'tab:robot': 'V', 'tab:robot_aloha': 'VI', 'tab:robot_pi': 'VII',
        'sec:threats': 'IX', 'sec:sota': 'V', 'sec:fold': 'III-B'}

PREAMBLE = r'''\documentclass[11pt]{article}
\usepackage[paperwidth=7.6in,paperheight=40in,margin=0.3in]{geometry}
\usepackage{times,amsmath,amssymb,amsthm,booktabs,array,graphicx}
\usepackage[dvipsnames]{xcolor}
\pagestyle{empty}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\setlength{\columnwidth}{\textwidth}
%s
\begin{document}
%s
\end{document}
'''


def macros(src):
    keep = []
    for ln in src.splitlines():
        if ln.startswith(('\\newtheorem', '\\DeclareMathOperator', '\\newcommand')):
            keep.append(ln)
    return '\n'.join(keep)


def between(src, start, end):
    i = src.index(start); j = src.index(end, i)
    return src[i:j]


def table_block(src, label):
    j = src.index('\\label{' + label + '}')
    i = src.rfind('\\begin{table}', 0, j); k = src.index('\\end{table}', j) + len('\\end{table}')
    block = src[i:k]
    # a float in a one-page document: keep it in place, without the placement option
    block = re.sub(r'\\begin\{table\}\[[^\]]*\]', r'\\begin{table}[H]', block)
    return block


def clean(body, defined):
    body = re.sub(r'~?\\cite\{[^}]*\}', '', body)
    def ref(m):
        key = m.group(2)
        if key in defined:
            return m.group(0)
        return REFS.get(key, '?')
    body = re.sub(r'\\(eqref|ref)\{([^}]*)\}', lambda m: ('(' + REFS[m.group(2)] + ')') if (m.group(1) == 'eqref' and m.group(2) not in defined and m.group(2) in REFS) else ref(m), body)
    body = body.replace('\\needspace{6\\baselineskip}', '')
    return body


def render(tex, dest, dpi=300):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'x.tex'; p.write_text(tex, encoding='utf-8')
        for _ in range(2):
            r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'x.tex'], cwd=tmp, capture_output=True, text=True)
        if r.returncode:
            log = (Path(tmp) / 'x.log').read_text(errors='ignore')
            raise SystemExit(f'LaTeX failed for {dest.name}:\n' + '\n'.join(l for l in log.splitlines() if l.startswith('!'))[:2000])
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', 'x.pdf', 'page'], cwd=tmp, check=True)
        img = Image.open(Path(tmp) / 'page.png').convert('RGB')
    bg = Image.new('RGB', img.size, (255, 255, 255))
    bbox = ImageChops.difference(img, bg).getbbox()
    img = img.crop((bbox[0] - 40, bbox[1] - 40, bbox[2] + 40, bbox[3] + 40))
    img.save(dest)
    return img.size


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paper', required=True, help='directory holding main.tex and figures/')
    ap.add_argument('--dpi', type=int, default=300)
    args = ap.parse_args()
    paper = Path(args.paper).expanduser()
    src = (paper / 'main.tex').read_text(encoding='utf-8')
    mac = macros(src) + '\n\\usepackage{float}'
    OUT.mkdir(parents=True, exist_ok=True)
    for name, start, end, eqn in EXCERPTS:
        body = between(src, start, end)
        defined = set(re.findall(r'\\label\{([^}]*)\}', body))
        body = clean(body, defined)
        body = re.sub(r'\\subsection\{([^}]*)\}', r'{\\large\\bfseries \1}\\par\\vspace{2pt}', body)
        tex = PREAMBLE % (mac, f'\\setcounter{{equation}}{{{eqn}}}\n\\setcounter{{proposition}}{{1}}\n' + body)
        print(name, render(tex, OUT / f'ex_{name}.png', args.dpi))
    for label in TABLES:
        body = table_block(src, label)
        defined = set(re.findall(r'\\label\{([^}]*)\}', body))
        body = clean(body, defined)
        n = ["I", "II", "III", "IV", "V", "VI", "VII"].index(REFS[label])
        head = '\\renewcommand{\\thetable}{\\Roman{table}}\\setlength{\\columnwidth}{5.6in}\\setcounter{table}{%d}\n\\begin{center}\\begin{minipage}{5.6in}\n' % n
        tex = PREAMBLE % (mac, head + body + '\n\\end{minipage}\\end{center}')
        print(label, render(tex, OUT / f'{label.replace(":", "_")}.png', args.dpi))
    for fig in FIGURES:
        pdf = paper / 'figures' / f'{fig}.pdf'
        subprocess.run(['pdftoppm', '-r', '600', '-png', '-singlefile', str(pdf), str(OUT / fig)], check=True)
        print(fig, Image.open(OUT / f'{fig}.png').size)


if __name__ == '__main__':
    main()
