# FoldQuantVLA project page

An anonymous, self-contained research page. Its only links navigate within the page. The manuscript PDF and source repository are deliberately not linked or packaged.

The review build includes `noindex`/`nofollow` metadata and a restrictive `robots.txt` to reduce accidental search-engine discovery. Remove both only after the double-anonymous review period ends.

## Preview

From the repository root, with Python 3.12 or later:

```sh
python3 website/build.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/website
```

Open `http://127.0.0.1:8765/`. The output can also be opened directly as an HTML file: no runtime data fetches are required. Clipboard access may require HTTP localhost or HTTPS; otherwise the citation is selected for manual copying.

## Checks

```sh
python3 -m unittest discover -s website/tests -v
node --check website/assets/app.js
```

The tests independently check Wilson intervals and success percentages, manuscript headline denominators, missing SmolVLA arms, anonymous metadata, internal anchors, bundled assets, and the complete static fallback.

## Source layout

- `data/metadata.json`: paper title and anonymous metadata.
- `data/{desktop,jetson,libero}.json`: transcribed manuscript Tables II, IV, and V, respectively. Provenance, units, hardware, and baseline are part of the data.
- `data/resources.json`: release-safe slots for Code, Models, Appendix, and BibTeX. Add HTTPS URLs here after review.
- `data/real_robot.json`: trial captions and camera-view manifest for the real-robot experiment reel.
- `media/real-robot/`: release-ready MP4/WebM recordings and optional posters. See its README for the two-step upload flow.
- `media/overview.mp4`: optional hero overview film. Add this file and rebuild; the upload-ready placeholder is replaced automatically.
- `index.template.html`: narrative and page structure.
- `build.py`: dependency-free HTML/table/chart generator. Does not import FoldQuant or require GPU libraries.
- `assets/`: styles, progressive enhancements, original SVG diagrams, social preview image .

Typography uses the system Arial stack (Helvetica / Liberation Sans fallbacks); no web fonts are loaded. The diagrams are original adaptations of the paper's method, not copied reference-site assets.

## Publication

The `Project website` workflow checks pushes and pull requests and uploads a Pages artifact. **It does not publish automatically.** After visual approval:

1. Enable GitHub Pages with **GitHub Actions** as the source in the repository settings.
2. Run the workflow manually on `main` with **Publish the reviewed website** enabled.

The deploy job is restricted to a manual run on `main` and uses the `github-pages` environment. Only `dist/website` is uploaded; model repositories, manuscript files, tests, and data-source notes are excluded.

The workflow supplies the standard project Pages URL to `--base-url` for absolute social-image and canonical URLs. If a custom domain is added later, change `SITE_URL` in the workflow. No analytics, CDN fonts, external scripts, or author profiles are used.

Only real-robot media referenced by `data/real_robot.json` is copied into the published artifact. This keeps unused takes and local notes out of GitHub Pages.

## Content policy

See `DATA_NOTES.md` before replacing numbers or adding claims. Update JSON first and rebuild; do not edit generated tables. Update the social-card image if any of its three highlights change.
