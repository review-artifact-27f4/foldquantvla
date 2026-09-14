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


def cut(inputs, dest, speed, height, threads):
    dest.parent.mkdir(parents=True, exist_ok=True)
    args, labels = [], []
    for i, src in enumerate(inputs):
        args += ['-i', str(src)]
        labels.append(f'[{i}:v]setpts=(PTS-STARTPTS)/{speed},scale=-2:{height},setsar=1[v{i}]')
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
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    report = {}
    for task in cfg['tasks']:
        base = (ROOT / task['dataset_root']).resolve()
        for arm in task['arms']:
            ep = f'episode_{int(arm.get("episode", task["episode"])):06d}.mp4'
            srcs = [base / arm['dir'] / 'videos' / 'chunk-000' / cam / ep for cam in task['cameras']]
            dest = OUT / task['key'] / f'{arm["key"]}.mp4'
            if not all(ok(s) for s in srcs):
                report[f'{task["key"]}/{arm["key"]}'] = 'missing'
                continue
            cut(srcs, dest, task['speed'], task['height'], args.threads)
            report[f'{task["key"]}/{arm["key"]}'] = f'{dest.stat().st_size / 1e6:.1f} MB'
    for k, v in report.items():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
