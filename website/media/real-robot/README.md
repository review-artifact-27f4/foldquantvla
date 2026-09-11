# Real-robot experiment media

Place release-ready real-robot recordings and poster images in this directory. The website build publishes only files referenced by `website/data/real_robot.json`; this README and unused recordings are never copied into the GitHub Pages artifact.

Recommended formats:

- Video: H.264 MP4 for broad browser support, or WebM.
- Poster: WebP, JPEG, or PNG with the same aspect ratio as the video.
- Filenames: lowercase letters, numbers, hyphens, and dots; for example `pick-cup-external.mp4` and `pick-cup-external.webp`.

For each camera view, set `src` and optionally `poster` in `website/data/real_robot.json`:

```json
{
  "label": "Robot camera 01",
  "detail": "Primary onboard view",
  "src": "pick-cup-camera-01.mp4",
  "poster": "pick-cup-camera-01.webp"
}
```

To add another experiment, duplicate a trial object and give it a unique `key`. Keep the two robot-camera views for each trial. Keep all public text anonymous and remove audio from recordings unless it is required for interpreting the experiment.

Rebuild and preview the site after changing the manifest:

```sh
python3 website/build.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/website
```
