# Release runbook (instructions for the agent)

How to turn the current `feature/remote-patch-library` work into the next published
release. Follow this top to bottom. Do not skip the gates in section 1: they are the
difference between a working release and one that cannot patch anything.

**Target version: `2.3.0`.** A feature release, not a patch bump: patch delivery moved
out of the installer. If the user names a different number, use theirs everywhere below.

---

## 0. Context you need before starting

Patch payloads no longer live only in this repo. They are published from a **separate
repo**, `Felix-Chaos/AS-RTX-Patch-Library`, whose `Patches/` folder set is the single
source of truth. CI there derives `patch_index.json` and the release assets from it.

The patcher reads:

```
https://github.com/Felix-Chaos/AS-RTX-Patch-Library/releases/download/patch-library/patch_index.json
```

That repo has its own release list and never interacts with this repo's `V2.2.x` tags
or `updater.json`. Do not merge the two release flows.

---

## 1. Pre-release gates

Each of these must be true before building. Verify, do not assume.

### 1a. Trim the bundled patches to the current latest only

The whole point of the release. `src-tauri/assets/Patches/` must contain **exactly one**
folder: the newest patch, kept as an offline fallback for a fresh install with no
network. Everything else downloads on demand.

```bash
ls -1 "src-tauri/assets/Patches"          # expect exactly one folder
```

If more than one is present, remove the others, but **only after** confirming each is in
the library with a matching hash:

```bash
cd B:/Dokumente/GitHub/AS-RTX-Patch-Library
node scripts/generate-patch-index.mjs --check      # must exit 0
gh release view patch-library --json assets --jq '.assets[].name'
```

Then, in this repo:

```bash
git rm -r "src-tauri/assets/Patches/<each older folder>"
```

This is reversible (`git checkout main -- "<folder>"`), and a second copy exists in
`Actions-and-Stuff-RTX-Patcher-Archive`. `tauri.conf.json` needs no change: its
`"resources": ["assets/**/*"]` glob simply picks up whatever is present.

### 1b. Every retired patch is reachable remotely

Launch the dev build with networking and confirm the version list still offers every
pack version, including the ones no longer bundled. Then pick one that is **not**
bundled and run a full patch. It must download, verify, and apply.

### 1c. Offline still works

Disconnect networking and run Marketplace/Auto against the bundled pack. The catalogue
fetch must degrade quietly to the disk cache (or empty) and the patch must still apply
from the bundled folder, with no download attempted.

### 1d. Compiles and runs

```bash
cd src-tauri && cargo check && cargo clippy && cargo fmt --check
```

Per `AGENTS.md`, never commit Rust that has not been checked.

### 1e. Known-incomplete work

These were planned but are **not** done. Either finish them or confirm with the user
that the release ships without them:

- `docs/PATCH_LIBRARY.md`, the human runbook for publishing a patch. The library repo's
  own `README.md` covers the same ground, so this is a duplicate-for-convenience.

Publishing from the Patch Creator UI **is** done: set the library repo folder in
App Settings, then either enable "Publish to Patch Library" before creating a patch or
use the "Publish to Library" button afterwards. It copies the folder into `Patches/`,
commits and pushes; CI in the library repo does the rest.

---

## 2. Version bump

Three files must agree. `prepare_release.yml` reads `package.json`, so a mismatch there
tags the wrong version.

| File | Field | Value |
|---|---|---|
| `package.json` | `version` | `2.3.0` |
| `src-tauri/tauri.conf.json` | `version` | `2.3.0-0` |
| `src-tauri/tauri.conf.json` | `app.windows[0].title` | `Actions & Stuff RTX Patcher v2.3.0` |

The window title is hardcoded and has been left stale in past releases. Fix it as part
of the bump.

`src-tauri/Cargo.toml`'s `version = "0.1.0"` is deliberately not synced. Leave it.

## 3. Changelog

`version_log.md` at the repo root is already written for 2.3.0. It is **untracked and
gitignored on purpose**, so it never appears in a diff.

If the version number changes or more work lands, rewrite it under the `AGENTS.md`
rules: overwrite completely so it holds only this version, `## [X.X.X]` header,
`### Added / Changed / Fixed / Removed`, plain user-facing English, and never any
updater signature, hash, or auto-generated key.

## 4. Merge to main

```bash
git checkout main
git merge --no-ff feature/remote-patch-library
```

Do not push a tag yet. Confirm `main` builds first.

## 5. Build and publish

Two paths exist; the project has used the manual one.

**Manual (what past releases did):** run the **Prepare Release** workflow via
`workflow_dispatch` with `release_type`, `pack_version`, `patch_version` and
`prerelease`. It reads the version from `package.json`, builds a tag such as `V2.3.0b`,
and creates a **draft**. Then paste the `version_log.md` content into the draft body,
attach the built installer and portable zip, and publish. VirusTotal fires on publish.

**Automatic:** pushing a `v*` tag triggers `release.yml`, which builds with
`tauri-action` and creates its own draft using the signing secrets.

Do not run both for one version: they create separate releases with different tag shapes
(`V2.3.0b` vs `v2.3.0`).

## 6. Updater

After publishing, update `updater.json` at the repo root so existing installs are
offered the update: `version`, `pub_date`, the `platforms.windows-x86_64.url` pointing at
the new release asset, and its `signature`.

Take the signature from the build output. Never paste it into `version_log.md` or into
any chat reply.

## 7. Post-release checks

- Install the published build on a clean machine (or a VM) and confirm the installer is
  roughly 227 MB smaller than 2.2.14.
- On that fresh install, confirm the bundled patch works offline, and that a
  non-bundled version downloads.
- Confirm `patch-library` in the other repo is untouched by this release, and that this
  repo's release list gained exactly one entry.

## 8. After this release: shipping a patch needs no release at all

This is the point of the change. To publish a new patch:

```bash
cd B:/Dokumente/GitHub/AS-RTX-Patch-Library
cp -r "<new patch folder>" Patches/
git add Patches && git commit -m "Publish <pack> v<patch>" && git push
```

CI hashes it, uploads it, regenerates the catalogue. Every installed patcher offers it
within a minute. No installer, no version bump, no updater entry, no release here.

Retiring a patch is `git rm -r "Patches/<folder>"` and a push.

Only refresh the bundled fallback (section 1a) when a patcher release is happening for
other reasons. It is allowed to lag behind the library indefinitely.

---

## Do not

- Publish patch `.vcdiff` files to this repo's releases. They belong in the library repo.
- Delete the `patch-library` release or its assets. Every installed patcher reads it.
- Bundle more than one patch folder "just in case". That re-inflates the installer.
- Hand-edit `patch_index.json`. It is generated; edit `Patches/` and let CI regenerate.
