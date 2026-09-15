# gh-pages

Source for the A&S RTX Patcher website, served by GitHub Pages.

This branch only holds the static site (no build step):

| File | Purpose |
| :--- | :--- |
| `index.html` | Page markup |
| `style.css` | Styles |
| `main.js` | Latest-release lookup, showcase player, lightbox, mobile nav |
| `assets/` | Logo, BetterRTX banner and showcase media |
| `.nojekyll` | Serves files as-is, without Jekyll processing |

## Preview locally

```bash
npx serve .
```

## Publish

Repository **Settings → Pages → Build and deployment**: Source *Deploy from a branch*, branch `gh-pages`, folder `/ (root)`.
