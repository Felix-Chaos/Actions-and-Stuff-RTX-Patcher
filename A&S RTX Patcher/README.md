# A&S RTX Patcher

This directory contains the primary patcher tool for **Actions & Stuff: Enhanced for RTX**. This tool is designed to apply community-made patches to your official copy of the "Actions & Stuff" resource pack, enabling RTX features and fixing visual issues.

## ⚠️ Important Notice

This patcher is an early-stage community project and has not been fully polished for end-users. It is currently under active development to support future versions of the "Actions & Stuff" resource pack.

## Features

-   **Easy to Use**: A simple graphical interface for patching your resource pack.
-   **Marketplace Patching**: Automatically finds and patches the "Actions & Stuff" pack from the Minecraft Marketplace.
-   **File Patching**: Supports patching from a `.zip` or `.mcpack` file.
-   **Self-Contained**: The patcher is a single executable (`AnSRTXPatcher.exe`) that includes all necessary tools.

## Requirements

-   [BetterRTX](https://bedrock.graphics/) must be installed.
-   A legally owned copy of the **Actions & Stuff** resource pack from the Minecraft Marketplace or as a `.zip`/`.mcpack` file.

## 🧩 Project Progress 1.6 Patcher

| Task | Status |
|------|--------|
| 🚀 **Project Start** | ✅ Finished |
| 📂 **Updated Files and Folders** | ✅ Finished |
| 🔍 **Updated Search Criteria in Script for 1.6** | ✅ Finished |
| 🧭 **Updating Paths / Removing outdated paths** | 🟡 Working on it |
| 🧱 **Creating Patch files** | ⏳ Soon |
| 📦 **Releasing the Patcher** | ⏳ Soon |
---

## How to Use

1.  **Run the Patcher**: Extract the contents of the release and run `AnSRTXPatcher.exe`.
2.  **Choose a Patching Method**:
    -   **Patch from Marketplace**: The patcher will automatically locate your Marketplace installation of "Actions & Stuff".
    -   **Patch from .zip/.mcpack**: You will be prompted to select the `.zip` or `.mcpack` file you wish to patch.
3.  **Wait for Compression**: The patcher will prepare the files for patching. This may take a few moments.
4.  **Apply the Patch**: Click the **Patch** button once it becomes available.
5.  **Install the Pack**: The patched pack will be saved as `Actions & Stuff Enhanced RTX.mcpack` in the same directory as the patcher. Double-click this file to install it in Minecraft.
6.  **Enable the Pack**: In Minecraft, enable the "Actions & Stuff Enhanced RTX" pack and ensure it is at the top of your resource pack list.

## Files in this Directory

-   `AnSRTXPatcher.py`: The main Python script for the patcher.
-   `AnSRTXPatcher.spec`: The PyInstaller specification file used to build the executable.
-   `AnSPatchericon.ico` / `AnSPatchericon.png`: Icons for the patcher.
-   `build_patcher.bat`: A batch script to build the patcher from the source.
-   `xdelta3/`: Contains the `xdelta3` tool used for applying binary patches.
-   `build/`: This directory is created during the build process and contains temporary files.