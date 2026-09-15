# Overview video

Text uses Liberation Sans (metric-compatible with Arial, SIL OFL 1.1; see `fonts/LICENSE-LiberationSans.txt`). CPU-only renderer (PIL frames + libx264); it never touches the GPU. Numbers are read from `website/data`, so the film stays consistent with the page.

```sh
# Layout check with one sample clip in every robot cell (marked LAYOUT PREVIEW; cannot be installed)
python3 video/make_overview.py --preview-clip ~/Downloads/So101_cube.mp4 --output video/build/overview_preview.mp4

# Final: fill the five `src` paths in video/overview.json, then
python3 video/make_overview.py --install   # writes website/media/overview.mp4
python3 website/build.py
```

Robot scenes (`overview.json` → `robot_scenes`): each scene tiles one clip per engine for the same task, trimmed with `start_s`, sped up by `speed`, cropped to `cell`. An arm's `outcome` (`success` / `fail`) shows a badge when its clip ends; set it only after checking the episode's last frame. Success counts come from `website/data/real_robot.json` (`task_index`, 0-based). Strip identifying content (faces, badges, lab signage, screens) from clips before rendering; audio is dropped.
