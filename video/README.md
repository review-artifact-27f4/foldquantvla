# Overview video

CPU-only renderer (PIL frames + libx264); it never touches the GPU. Numbers are read from `website/data`, so the film stays consistent with the page.

```sh
# Layout check with one sample clip in every robot cell (marked LAYOUT PREVIEW; cannot be installed)
python3 video/make_overview.py --preview-clip ~/Downloads/So101_cube.mp4 --output video/build/overview_preview.mp4

# Final: fill the five `src` paths in video/overview.json, then
python3 video/make_overview.py --install   # writes website/media/overview.mp4
python3 website/build.py
```

Robot comparison (`overview.json` → `robot_compare`): one clip per engine for the same task and initial layout, trimmed with `start_s` and sped up by `speed`. Success counts come from `website/data/real_robot.json` (`task_index`, 0-based). Strip identifying content (faces, badges, lab signage, screens) from clips before rendering; audio is dropped.
