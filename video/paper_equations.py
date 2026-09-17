#!/usr/bin/env python3
"""Render single labelled equations of the manuscript to PNG (video/figures/paper/eq_<name>.png),
numbered as in the paper, for the figure-plus-formula scenes of the submission video.

  python3 video/paper_equations.py --paper ~/Work/VLAOpt\\(1\\)/overleaft_paper
"""
import argparse
import re
from pathlib import Path

from paper_excerpts import OUT, macros, render

# label -> (file name, paper equation number)
EQUATIONS = {'eq:fold': ('fold', 2), 'eq:family': ('family', 3), 'eq:norm': ('norm', 4), 'eq:quant': ('quant', 5), 'eq:gptq': ('gptq', 7)}

PREAMBLE = r'''\documentclass[12pt]{article}
\usepackage[paperwidth=6.2in,paperheight=6in,margin=0.2in]{geometry}
\usepackage{times,amsmath,amssymb,amsthm}
\pagestyle{empty}
%s
\begin{document}
\Large
%s
\end{document}
'''


def equation_block(src, label):
    j = src.index('\\label{' + label + '}')
    i = max(src.rfind('\\begin{equation}', 0, j), src.rfind('\\begin{align}', 0, j))
    env = 'equation' if src.startswith('\\begin{equation}', i) else 'align'
    k = src.index('\\end{' + env + '}', j) + len('\\end{' + env + '}')
    return src[i:k]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paper', required=True)
    ap.add_argument('--dpi', type=int, default=400)
    args = ap.parse_args()
    src = (Path(args.paper).expanduser() / 'main.tex').read_text(encoding='utf-8')
    mac = macros(src)
    OUT.mkdir(parents=True, exist_ok=True)
    for label, (name, number) in EQUATIONS.items():
        body = equation_block(src, label)
        body = re.sub(r'\\label\{[^}]*\}', '', body)
        body = '\n'.join(ln for ln in body.splitlines() if ln.strip())  # no paragraph break inside the display
        tex = PREAMBLE % (mac, f'\\setcounter{{equation}}{{{number - 1}}}\n' + body)
        print(name, render(tex, OUT / f'eq_{name}.png', args.dpi))


if __name__ == '__main__':
    main()
