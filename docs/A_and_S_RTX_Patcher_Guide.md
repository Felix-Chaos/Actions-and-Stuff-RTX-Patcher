# A&S Minecraft RTX Community Patcher V2

Welcome to the **A&S Minecraft RTX Community Patcher V2** technical guide. This document explains how the patcher operates under the hood, how configuration drives the patching mechanism, and how users interact with the graphical backend.

For standard user installation instructions, see the [`README.md`](../README.md) at the root of the repository.

---

## 🏗️ Architecture

The Patcher is built using **Python** with a **CustomTkinter** backend, employing an **MVC (Model-View-Controller)** pattern for clean componentization:

1. **`src/models/`**: Manages data sources.
   - `configModel.py`: Loads the `patch_config.json`, storing expected folder layouts and version indicators.
   - `fileSystemModel.py`: Responsible for robust deletion, copying, parallel extraction, and generating deterministic zips/`vcdiff` commands.
   - `patcherModel.py`: Wrapper for invoking `xdelta3`, generating temporary zip paths, and orchestrating the final patching command line process.
2. **`src/views/`**: Renders the UI visually. Contains specific frames (`MainFrame`, `PatchProgressFrame`, `SettingsFrame`) that trigger user events.
3. **`src/controllers/`**: Coordinates everything. E.g. `patchController.py` searches your Marketplace cache across 5 different UWP scopes (Standard, Preview, GDK variants) to locate the precise Oreville Studios' installation format by checking manifests, Lang files, and image metadata (`pack_icon.png` hashes).

---

## 🛠️ Automated Setup via Config (`patch_config.json`)

If you want to support a new patch version of the base application before an official release is built, you simply add an object to `patch_config.json` inside the `patchVersions` key hierarchy. The `configModel.py` dynamically injects these inputs directly into the App.

There is no hard-coded application logic mapping specific Pack Versions to patches. The logic evaluates the `stats` (files and directories) contained within the raw Minecraft Bedrock `premium_cache` path and pairs them closely with known configurations.

---

## 👨‍💻 Contributing & Testing

### Development

1. **Clone the repository.**
2. **Install requirements:** `pip install -r requirements.txt`.
3. **Run normally:** `python main.py` in the root environment.

The code follows a strict **Pylint (10/10)** schema across the entire application workspace so format contributions to PEP-8 appropriately!

### Building with PyInstaller

A `build.bat` script handles PyInstaller compilation dynamically by injecting the `/assets` paths, UI images, configuration arrays, and the underlying `xdelta3` binary directly into a portable compressed `.exe`.

Double-clicking `build.bat` generates an `/out/` directory with a monolithic Windows executable file containing zero external dependencies.
