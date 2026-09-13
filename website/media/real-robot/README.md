# Real-robot experiment media

Place release-ready real-robot recordings and poster images in this directory. The website build publishes only files referenced by `website/data/real_robot.json`; this README and unused recordings are never copied into the GitHub Pages artifact.

Recommended formats:

- Video: H.264 MP4 for broad browser support, or WebM.
- Poster: WebP, JPEG, or PNG with the same aspect ratio as the video.
- Filenames: lowercase letters, numbers, hyphens, and dots; for example `pick-cup-external.mp4` and `pick-cup-external.webp`.

For each task video, set `src` and optionally `poster` in `website/data/real_robot.json`:

```json
{
  "label": "Evaluation video",
  "detail": "SO101 · Task 01",
  "src": "so101-task-01.mp4",
  "poster": "so101-task-01.webp"
}
```

To add another experiment, duplicate a trial object and give it a unique `key`. Keep one evaluation video for each task. Keep all public text anonymous and remove audio from recordings unless it is required for interpreting the experiment.

Rebuild and preview the site after changing the manifest:

```sh
python3 website/build.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/website
```
