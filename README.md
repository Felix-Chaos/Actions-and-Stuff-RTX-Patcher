# gh-pages

Source for the A&S RTX Patcher website, served by GitHub Pages.

This branch only holds the static site (no build step):

| File | Purpose |
| :--- | :--- |
| `index.html` | Landing page |
| `wiki.html` | Wiki / full feature guide, hand-written from `docs/WIKI.md` on the main branch |
| `style.css` | Styles for both pages, reusing the patcher app's components |
| `main.js` | Latest-release lookup, channel switch, showcase player, lightbox, nav, wiki tabs and contents |
| `assets/` | Logo, link preview image (`og-image.jpg`), BetterRTX banner and showcase media |

When `docs/WIKI.md` changes, update `wiki.html` to match.
| `.nojekyll` | Serves files as-is, without Jekyll processing |

## Preview locally

```bash
npx serve .
```

## Publish

Repository **Settings → Pages → Build and deployment**: Source *Deploy from a branch*, branch `gh-pages`, folder `/ (root)`.
