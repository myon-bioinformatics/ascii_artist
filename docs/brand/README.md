# Project artwork

`icon.png` is cropped directly from the user-supplied project artwork sheet (2026-10-23), with its colors and light background preserved. `favicon.png` is `icon.png` resampled to 64x64 px (a multiple of 8) with the same background colour (#fafafa); it is not a redrawn or AI-generated replacement.

The root README previews the project icon and links to both PNG assets. A README cannot change GitHub’s browser-tab favicon.

## GitHub Pages wiring

The repository-owned `icon.png` is used for the visible page identity and Apple touch icon, and `favicon.png` for the browser tab. Both come from this directory. Like Ironmate, the published HTML references same-origin assets shipped with the site, rather than README image links. Generated report sites copy both PNGs to their output directory; web-ui serves these canonical files directly. Generic library-generated consumer documents remain unbranded.

♻️ The images themselves now live in [CaChereCyCle](https://github.com/myon-bioinformatics/CaChereCyCle) as `ascii_artist.icon` / `ascii_artist.favicon` (the same bytes; the sha256 here still match), and Pages publishes them as [`icon.png`](https://myon-bioinformatics.github.io/ascii_artist/icon.png) / [`favicon.png`](https://myon-bioinformatics.github.io/ascii_artist/favicon.png).
