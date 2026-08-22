<table>
<tr>
<td width="180" align="center">
<img width="140" alt="A&S RTX Patcher Logo" src="../assets/as_rtx_simple_logo_.png" />
</td>
<td>

## 📖 A&S RTX Patcher Wiki / Full Feature Guide

*Every tab, every toggle, and when to actually use them*

[![Back to Main README](https://img.shields.io/badge/←_Back_to_README-333?style=flat-square)](../README.md)
[![Download Latest](https://img.shields.io/badge/⬇_Download-Latest_Release-2ea44f?style=flat-square&logo=github)](https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/latest)
[![Discord](https://img.shields.io/discord/1432653252171661364?logo=discord&style=flat-square&label=Discord)](https://discord.gg/YrMMmN2kc7)

</td>
</tr>
</table>

This guide covers the current Tauri-based patcher (the app that ships as `Actions and Stuff RTX Patcher.exe`). If you just want the quick install steps, the [main README](../README.md) is enough. Come here when you want to know what a specific button, toggle, or tab actually does.

---

## Table of Contents

- [How patching works](#-how-patching-works)
- [Patch Modes](#-patch-modes)
  - [Marketplace (default)](#-marketplace-default)
  - [Zip / McPack (Advanced Mode)](#-zip--mcpack-advanced-mode)
  - [Custom Patch (Advanced Mode)](#-custom-patch-advanced-mode)
- [Extract Brarchives](#-extract-brarchives)
- [Tools Reference](#-tools-reference)
  - [🧹 Cleaner](#-cleaner)
  - [🎛️ RTX Settings](#-rtx-settings)
  - [🛠️ Utilities](#-utilities)
    - [Deterministic ZIP Packer](#deterministic-zip-packer)
    - [Extract ZIP / MCPack](#extract-zip--mcpack)
    - [Create Patch (VCDIFF)](#create-patch-vcdiff)
    - [Extract Brarchives (standalone)](#extract-brarchives-standalone)
  - [💬 Support](#-support)
  - [📦 Release Builder (maintainers only)](#-release-builder-maintainers-only)
  - [⚙️ App Settings](#-app-settings-reference)
- [Troubleshooting](#-troubleshooting)

---

## 🔍 How Patching Works

The patcher never redistributes any original Actions & Stuff asset. Instead it ships small binary diffs (`.vcdiff`, applied with [xdelta3](https://github.com/jmacd/xdelta)) that transform **your own legally-owned copy** into the RTX-enhanced version:

```
Your A&S Copy → xdelta3 + .vcdiff patch → A&S Enhanced for RTX (.mcpack)
```

Two `.vcdiff` files exist per patch version, because there are two possible starting points:

| File | Diffed against | Used by |
| :--- | :--- | :--- |
| `encrypted.vcdiff` | Your raw, still-DRM-encrypted Marketplace cache | **Marketplace** mode |
| `decrypted.vcdiff` | An already-decrypted/plain pack (a `.zip`/`.mcpack` you downloaded or extracted yourself) | **Zip / McPack** mode |

Both patches reconstruct the exact same final pack. The tool just picks whichever one matches the format of the pack you're feeding it, so it never has to touch DRM-protected bytes it can't otherwise read.

---

## 🚀 Patch Modes

Pick a mode on the **Patcher** tab. The first is always available; the other two require **Advanced Mode** (bottom-left toggle in the sidebar).

### 🏪 Marketplace (default)

Auto-detects your purchased Actions & Stuff pack directly from Minecraft's `premium_cache` (works for the Microsoft Store/UWP and GDK/Xbox app installs). This is the mode almost everyone should use, no manual file picking required.

1. Choose **Auto-Detect** or **Manual Select** for the target patch/pack version.
2. Optionally leave **Delete older patched versions automatically** on to keep old installs from piling up.
3. Click **Apply RTX Patch**.

### 📂 Zip / McPack (Advanced Mode)

For when you already have Actions & Stuff as a `.zip` or `.mcpack` file (e.g. downloaded rather than pulled from the Marketplace cache). The patcher extracts it, strips Mojang's licensing metadata (`contents.json`, `signatures.json`, etc.), injects its own manifest, and applies `decrypted.vcdiff`.

### 🔧 Custom Patch (Advanced Mode)

Lets you manually point at a specific **source** pack (folder or zip), **target** output path, and a specific `.vcdiff` **patch file**, bypassing the normal auto-detection entirely. Useful for testing a patch you (or a patch developer) just built with the [Create Patch tool](#create-patch-vcdiff), or for applying an older/specific patch version by hand.

> [!TIP]
> After any mode finishes, click **Install Pack** to copy the result straight into your Minecraft `resource_packs` folder, no manual extraction needed.

---

## 📦 Extract Brarchives

Some Actions & Stuff source material ships assets bundled inside a custom container format instead of as normal loose files: a `__brarchive` folder containing `*.brarchive` files, each of which is really several real files packed together with a small binary header.

**What it does:** recursively scans the target folder for `__brarchive` directories, unpacks every `.brarchive` file back into a normal file at the path it's named after (stripping the `.brarchive` suffix), then deletes the now-empty archive containers and any leftover `.brarchive` pointer files.

**Where it exists:** **Utilities → Extract Brarchives**, a standalone tool you point at any folder directly. Handy for inspecting what's inside a `__brarchive` folder.

If a folder doesn't have a `__brarchive` anywhere in it, running this is a harmless no-op, which is why it's still marked **Beta**.

---

## 🧰 Tools Reference

Everything below lives behind the sidebar tabs. **Advanced Mode** (bottom-left toggle) is required to see the **Utilities** menu and a few of the Patcher-tab controls.

### 🧹 Cleaner

Scans every detected Minecraft install (Microsoft Store/UWP, GDK/Xbox app, and per-world `resource_packs`/`development_resource_packs` folders) for leftover Actions & Stuff pack directories from previous patches, and lets you delete the ones you select. Use this if you've patched several times and want to reclaim disk space, or before re-patching to avoid stale duplicate packs showing up in-game.

### 🎛️ RTX Settings

Reads and writes your Minecraft `options.txt` directly, so you can flip RTX-relevant graphics settings (`graphics_mode`, `graphics_api`, ray tracing/deferred view distance, upscaling mode & percentage, etc.) without hunting through Minecraft's in-game menus. **Set Best Settings** applies the recommended RTX configuration in one click; **Apply Settings** saves whatever you've edited manually. Pick which `options.txt` profile to target first if you have more than one Minecraft install/user profile.

### 🛠️ Utilities

Standalone tools that don't run the full patch pipeline, useful for patch developers or troubleshooting.

#### Deterministic ZIP Packer

Compresses a folder into a `.zip`/`.mcpack` with fixed timestamps (Jan 1 1980) and no compression (stored). Two runs over identical input always produce a byte-identical archive; this determinism is what makes the xdelta diffs reproducible and small, so it's used internally everywhere the patcher creates a zip for diffing.

#### Extract ZIP / MCPack

Extracts any `.zip` or `.mcpack` archive to a folder, automatically unwrapping a single redundant top-level folder if the archive has one (e.g. `MyPack-main/...` becomes just the pack contents).

#### Create Patch (VCDIFF)

This is how new patch versions actually get built, for custom/new patches. It's a maintainer/patch-developer tool, not something regular users need. It needs four inputs:

| Input | What goes here |
| :--- | :--- |
| **1. Target Folder** | Your finished, modified "Actions & Stuff RTX" pack, the result you want end users to end up with |
| **2. Source Decrypted Folder** | A vanilla, already-decrypted baseline copy of the same Actions & Stuff version (no DRM) |
| **3. Source Encrypted Folder** | The same vanilla version, but straight from `premium_cache`, still DRM-encrypted |
| **Output Directory** | Where the finished `.vcdiff` files and `patch_config.json` get written |

Plus **Pack Version** / **Patch Version** (used to name the output folder and populate `patch_config.json`), and one toggle:

| Toggle | Effect |
| :--- | :--- |
| **Inject Custom Manifest** | Writes the patcher's own `manifest.json` into both the decrypted baseline and the target folder before diffing, so the shipped pack always ends up with the correct custom pack identity |

Clicking **Create Patches** produces `encrypted.vcdiff`, `decrypted.vcdiff`, and a `patch_config.json` (pack/patch version + validation stats used by Marketplace auto-detection) in a new `Actions & Stuff for RTX <pack version> V<patch version>` folder under your chosen output directory.

#### Extract Brarchives (standalone)

Same brarchive extraction described [above](#-extract-brarchives), pointed at any folder you choose, independent of a patch run. Good for just inspecting/unpacking a `__brarchive` folder without doing anything else.

### 💬 Support

Discord invite links (community + BetterRTX), and the **Bug Report** form. The bug reporter can optionally attach your application log, the pack you patched, a Minecraft content log (with usernames scrubbed from file paths), recent GPU driver events, and a hardware summary (GPU/CPU/RAM/BetterRTX preset), all opt-in per checkbox, and all tied to a random install ID rather than anything personally identifying. See **App Settings → Privacy** for the underlying telemetry consent controls.

### 📦 Release Builder (maintainers only)

Version bump + build automation for cutting a new patcher release: edit the app version, build MSI/NSIS installers and/or a portable `.exe`, and sort the resulting artifacts into a `Releases/vX.Y.Z` folder with the updater manifest signature injected automatically. Not relevant unless you're publishing a new patcher build.

### ⚙️ App Settings Reference

| Group | Setting | Effect |
| :--- | :--- | :--- |
| General | Default Patcher Mode | Which patch mode is pre-selected on launch |
| General | Enable Advanced Mode UI | Reveals Zip/Custom patch modes, the Utilities tab, and other advanced controls |
| General | Opt-in to Beta Updates | Lets the in-app updater offer beta/alpha releases, not just stable |
| Patcher Behaviors | Clean Old Patch Remnants | Runs the Cleaner scan automatically before every patch |
| Patch Creator Defaults | Inject Custom Manifest | Default state of the matching toggle in the [Create Patch tool](#create-patch-vcdiff) |
| Bug Reporter Defaults | Include Application Log / Pack / Content Log / Driver Events / Hardware Info | Default state of the matching checkboxes on the bug report form |
| Privacy | Telemetry consent, Delete My Data | Opt in/out of anonymous hardware pings, and erase your server-side data (rotates your local install ID) |

---

## 🩹 Troubleshooting

- **A texture/model/sound looks broken or purple after patching.** Use the Bug Report form (Support tab) with the content log and hardware info included; this gives us the most actionable diagnostics.
- **Nothing happens when I click Apply RTX Patch.** Check the process log (Advanced Mode) for the actual error, and confirm you own a legitimate copy of Actions & Stuff in one of the supported formats.
- **Just patched but Minecraft still shows the old pack.** Make sure your resource pack load order matches the [README's setup section](../README.md), and run the Cleaner to remove stale duplicates.
- **Still stuck?** Ask in the [Discord](https://discord.gg/YrMMmN2kc7) or check the pinned [FAQ thread](https://discord.com/channels/691547840463241267/1360688874388455504/1376325634246049792).

---

<div align="center">

[![Back to Main README](https://img.shields.io/badge/←_Back_to_README-333?style=for-the-badge)](../README.md)

</div>
