# Anonymous project website

This repository contains the anonymous research page and its reproducible static-site build. It intentionally excludes author identities, affiliations, acknowledgments, unpublished repository links, and the manuscript PDF.

## Build and check

```sh
python3 -m unittest discover -s website/tests -v
node --check website/assets/app.js
python3 website/build.py
```

The generated Pages artifact is written to `dist/website`. Publishing remains a deliberate manual workflow action during anonymous review.
