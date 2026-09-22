# 📚 Patch Library (maintainers only)

How patches reach users, and how to publish a new one.

Patches are **not** shipped inside the patcher any more. They live in a separate repo,
[**AS-RTX-Patch-Library**](https://github.com/Felix-Chaos/AS-RTX-Patch-Library), and the patcher
downloads them on demand. Publishing a patch therefore needs **no patcher release**: no installer,
no version bump, no updater entry. Users get it at their next launch.

Nothing here touches the patcher's own release flow. The two repos have separate release lists and
never interact.

---

## Table of Contents

- [Why it works this way](#why-it-works-this-way)
- [Publish a patch from inside the patcher](#publish-a-patch-from-inside-the-patcher)
- [Publish a patch by hand](#publish-a-patch-by-hand)
- [Retire a patch](#retire-a-patch)
- [The bundled fallback](#the-bundled-fallback)
- [How users receive it](#how-users-receive-it)
- [Troubleshooting](#troubleshooting)

---

## Why it works this way

Every patch is roughly 25 MB per variant, and both variants shipped inside every installer. With
nine versions that was **254 MB of the download**, growing with each release, and shipping a new
patch meant shipping a whole new patcher.

Now the installer carries one patch as an offline fallback and everything else is fetched when
it is actually needed, verified by SHA-256 before use, and cached for offline reuse.

### The moving parts

```
AS-RTX-Patch-Library
  Patches/                                  <- the only thing you edit
    Actions & Stuff for RTX 1.11.1 V0.1/
      encrypted.vcdiff        applied to a Marketplace (premium cache) pack
      decrypted.vcdiff        applied to an extracted / zip pack
      patch_config.json       pack + patch version, file counts, logo hash
  patch_index.json                          <- generated, never hand-edited
  release "patch-library"                   <- permanent asset store
```

`Patches/` is the single source of truth. On every push, CI hashes the payloads, uploads them to
the `patch-library` release, regenerates `patch_index.json`, and commits it back. The patcher reads
that catalogue and downloads what it needs.

> [!IMPORTANT]
> The `patch-library` release is not a version of anything. It is a permanent file store, created
> once. Never delete it or its assets: every installed patcher reads from it.

---

## Publish a patch from inside the patcher

The easiest route, and the one to use by default.

**One-time setup.** Clone the library repo somewhere local, then in the patcher open
**App Settings → Patch Creator Default Options** and set **Patch library repo folder** to that
clone. Git and the [GitHub CLI](https://cli.github.com/) (`gh`) must both be installed and
authenticated; the patcher uses your existing credentials and stores no token of its own.

**Each patch:**

1. Open **Utilities → Create Patch (VCDIFF)** and build the patch as usual.
2. Either turn on **Publish to Patch Library** before pressing *Create Patches*, or press
   **Publish to Library** afterwards. The button appears once a patch has been created, so you can
   publish without rebuilding.
3. Fill in your name, a pull request title and an optional description. These are remembered for
   next time, so you're not retyping them on every patch.

The patcher copies the created folder into `Patches/` on a fresh branch, commits, pushes it and
opens a pull request against the library's default branch via `gh pr create`, logging each step in
the Patch Creator log. Publishing is off by default and always confirmed.

It stops rather than guessing if:

| Situation | What happens |
| :--- | :--- |
| The folder is not a git repo, or has no `Patches/` | Refuses, so a mistyped path cannot create a repo |
| The patch folder is missing one of its three files | Refuses |
| That version is already published | Asks whether to open a PR that replaces it |
| The library has any uncommitted changes | Refuses, so a publish branch cannot sweep up work in progress |
| The local clone can't fast-forward to `origin` | Refuses, so the PR is not opened against a stale base |

A publish failure never marks patch creation as failed: the `.vcdiff` files on disk are already
good, so you can fix the problem and press **Publish to Library** again.

---

## Publish a patch by hand

Identical result, if you would rather not use the app:

```bash
cd <your clone of AS-RTX-Patch-Library>
cp -r "<new patch folder>" Patches/
git add Patches && git commit -m "Publish Actions & Stuff for RTX 1.11.1 v0.2" && git push
```

The folder must contain `encrypted.vcdiff`, `decrypted.vcdiff` and `patch_config.json`, which is
exactly what the Create Patch tool produces.

CI does the rest. Watch it with `gh run watch` in that repo, or check the Actions tab.

To verify afterwards:

```bash
node scripts/generate-patch-index.mjs --check     # payloads match the catalogue
gh release view patch-library --json assets --jq '.assets[].name'
```

---

## Retire a patch

Remove the folder and push:

```bash
git rm -r "Patches/Actions & Stuff for RTX 1.10.1 V1.0"
git commit -m "Retire 1.10.1 v1.0" && git push
```

CI regenerates the catalogue and deletes the orphaned release assets. The version disappears from
every patcher's version list. Anyone who already downloaded it keeps their local copy until they
remove it in **App Settings → Downloaded Patches**.

---

## The bundled fallback

`src-tauri/assets/Patches/` in the patcher repo holds **exactly one** patch folder, so a brand-new
offline install can still patch something. It is not how patches are delivered.

It is allowed to fall behind the library, and usually will. Only swap it when a patcher release is
happening for other reasons: `git rm -r` the old folder, copy a newer one in, and confirm that
version is already in the library. `tauri.conf.json` needs no change; its `assets/**/*` glob picks
up whatever is present.

> [!WARNING]
> Never bundle more than one patch folder. That is what made the installer 254 MB.

---

## How users receive it

A published patch appears without any action from the user. The patcher re-checks the catalogue
when its window regains focus, when the Patcher tab is opened, and every 15 minutes, and there is a
**Refresh patch list** button next to the version selectors.

In the version list each patch is marked:

| | Meaning |
| :---: | :--- |
| 📦 | Included with the app, no download needed |
| ✅ | Already downloaded, works offline |
| ⬇️ | Will be downloaded, with its size |

Downloads are verified by SHA-256 before use and kept for reuse. Users can remove them individually
or all at once in **App Settings → Downloaded Patches**, and removing one only frees disk space:
it downloads again automatically next time.

If the library cannot be reached, the patcher falls back to the last catalogue it saw, then to the
bundled patch. It never fails to start because of a network problem.

---

## Troubleshooting

**Publishing says the library has unrelated uncommitted changes.** Something else is modified in
that clone. Commit or discard it, then publish again. This guard exists so a publish commit
contains only the patch.

**CI ran but the patch is not offered in the app.** Press **Refresh patch list**. If it still does
not appear, check that `patch_config.json` has the right `packVersion` and `patchVersion`: those
two values are what the app matches against your installed pack.

**A patch downloads but fails with a checksum mismatch from xdelta.** That is the patch not
matching the pack it was applied to, not a bad download; a corrupted download is caught earlier and
re-fetched automatically. Check that the pack version selected matches the patch.

**`gh` says the release does not exist.** The `patch-library` release is created automatically on
the library repo's first CI run. Trigger the workflow manually if needed.
