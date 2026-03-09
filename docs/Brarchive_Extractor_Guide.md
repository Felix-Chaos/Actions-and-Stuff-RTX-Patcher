# A&S Brarchive Extractor Guide

The **Brarchive Extractor** is a standalone utility designed to dissect, edit, and repack `.brarchive` files natively integrated within the _Actions & Stuff_ or other Minecraft Bedrock add-ons.

Since version 26.3, many add-ons utilize the `.brarchive` packaging format (a custom sub-archiving binary structure) to bundle textures and localized texts securely. This tool allows modders and users to automatically decompile these assets into standard folders, edit them, and recompile them back without corrupting the original format.

---

## 🚀 Features

- **In-Place Extraction:** Auto-extracts `.brarchive` content next to their sources, replacing the binary with a `.bak` backup so you can edit and hot-reload assets dynamically in the game menu.
- **Smart Database Tracking:** Remembers every pack you dissect into jobs (via `db.json`), allowing you to restore or repack them securely.
- **Background Threading:** Fast compression operations that never lock the UI.
- **Pack Support:** Accepts raw folders, `.zip`, or `.mcpack` files out-of-the-box.

---

## 🛠️ How to Use

### 1) Standard Extraction

1. **Open the Application** (`main.py` if building yourself, or open the target `.exe`).
2. Navigate to the **"Extract"** tab.
3. Select an Input Pack: Point this to the original `.mcpack`, `.zip`, or `Folder` that contains `.brarchive` files.
4. Select an Output Folder: Choose a root directory where the modified workspace should be copied to.
5. Enter a **Custom Job Name**: Ensure this is memorable (e.g. `My_Awesome_Subpack`).
6. Click **"Extract Brarchives"**.
   - The tool will clone your pack into your destination and dissect the inner `.brarchives`.

### 2) Editing Files IN-GAME

- Once extracted, the tool renamed the original `.brarchive` to `.brarchive.bak`.
- Adjacent to the `.bak`, a new standard folder has been created containing the contents (textures, language files). You can edit these directly!
- _Pro Tip:_ Because they are now standard loose folders inside the pack array, Minecraft Bedrock will natively read these modified folders over the `.bak` file!

### 3) Repacking and Deployment

1. When you are done editing your custom textures, open the tool again and navigate to the **"Repack Jobs"** tab.
2. Find the job bearing the **Custom Job Name** you defined earlier.
3. Click **"Reverse To .mcpack"**.
4. The Extractor will iterate over all your modifications, reconstruct the binary `.brarchive`, automatically delete the loose text folders and `.bak` backups, and compress the entire working directory into a final ready-to-play `.mcpack`!

---

## 🏗️ Technical Details

The `.brarchive` structural spec translates to a simple binary descriptor format:

- A `uint64` Magic Number (`0x267052A0B125277D`)
- A padded header resolving file origins
- Zero-length padded file strings natively limited to 247 chars.

For detailed formatter information, inspect `brarchive_format.py` inside the tool source codes.
