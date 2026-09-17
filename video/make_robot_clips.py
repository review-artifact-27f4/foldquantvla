#!/usr/bin/env python3
"""Cut web clips for the real-robot comparison from local LeRobot recordings (CPU only).

ALOHA: robot cameras (high | wrist) side by side. SO-101: one external camera.
Raw recordings stay local (gitignored); only the short, sped-up clips land in
website/media/real-robot/. Arms whose recordings are missing or empty are skipped.
"""
import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'website' / 'media' / 'real-robot'


def ok(path):
    return path.is_file() and path.stat().st_size > 0


def cut(inputs, dest, speed, height, threads, aspect=None, rotate='', start=None, end=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    args, labels = [], []
    # Optional centre crop (e.g. "4:3") so the clip fills its page cell instead of letterboxing.
    crop = ''
    if aspect:
        w, h = (int(x) for x in aspect.split(':'))
        crop = f'crop=w=\'2*trunc(min(iw,ih*{w}/{h})/2)\':h=\'2*trunc(min(ih,iw*{h}/{w})/2)\','
    for i, src in enumerate(inputs):
        # Optional source trim in seconds (e.g. to drop an operator's hand entering the frame).
        trim = (['-ss', f'{start:.2f}'] if start else []) + (['-t', f'{end - (start or 0):.2f}'] if end else [])
        args += [*trim, '-i', str(src)]
        # rotate: "cw" / "ccw" for phone recordings saved in portrait.
        turn = {'cw': 'transpose=1,', 'ccw': 'transpose=2,'}.get(rotate, '')
        labels.append(f'[{i}:v]setpts=(PTS-STARTPTS)/{speed},{turn}{crop}scale=-2:{height},setsar=1[v{i}]')
    stack = ''.join(f'[v{i}]' for i in range(len(inputs)))
    graph = ';'.join(labels) + (f';{stack}hstack=inputs={len(inputs)},fps=30[out]' if len(inputs) > 1 else ';[v0]fps=30[out]')
    cmd = ['ffmpeg', '-v', 'error', '-y', *args, '-filter_complex', graph, '-map', '[out]', '-an',
           '-c:v', 'libx264', '-preset', 'slow', '-crf', '27', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
           '-threads', str(threads), str(dest)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(HERE / 'robot_clips.json'))
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--only', nargs='*', help='task keys to render (default: all)')
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    report = {}
    for task in cfg['tasks']:
        if args.only and task['key'] not in args.only:
            continue
        for arm in task['arms']:
            if 'src' in arm:  # one external-camera recording (e.g. an iPhone .MOV)
                srcs = [Path(arm['src']).expanduser()]
            else:
                base = (ROOT / task['dataset_root']).resolve()
                ep = f'episode_{int(arm.get("episode", task["episode"])):06d}.mp4'
                srcs = [base / arm['dir'] / 'videos' / 'chunk-000' / cam / ep for cam in task['cameras']]
            # "scene": N writes to <key>/scene-N/, the page's per-scene layout.
            folder = OUT / task['key'] / (f'scene-{task["scene"]}' if 'scene' in task else '')
            dest = folder / f'{arm["key"]}.mp4'
            if not all(ok(s) for s in srcs):
                report[str(dest.relative_to(OUT))] = 'missing'
                continue
            cut(srcs, dest, task['speed'], task['height'], args.threads, task.get('aspect'), arm.get('rotate', ''),
                arm.get('start_s'), arm.get('end_s'))
            report[str(dest.relative_to(OUT))] = f'{dest.stat().st_size / 1e6:.1f} MB'
    for k, v in report.items():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
