<table>
<tr>
<td width="180" align="center">
<img width="160" alt="Actions & Stuff RTX Patcher Logo" src="./A&S Patcher/assets/resources/as_rtx_simple_logo_.png" />
</td>
<td>

## A&S Minecraft RTX Community Patcher

*Community-built patching tool for RTX-compatible Actions & Stuff on Bedrock Edition*

[![Release](https://img.shields.io/github/v/release/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=flat-square&color=blue&label=Release)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/releases)
[![Stars](https://img.shields.io/github/stars/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=flat-square&color=yellow)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/stargazers)
[![Issues](https://img.shields.io/github/issues/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=flat-square)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/issues)
[![Pylint](https://img.shields.io/github/actions/workflow/status/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/pylint.yml?label=Pylint&style=flat-square&color=blue)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/actions/workflows/pylint.yml)
[![Discord](https://img.shields.io/discord/1432653252171661364?logo=discord&style=flat-square&label=Discord)](https://discord.gg/YrMMmN2kc7)
[![FAQ](https://img.shields.io/badge/📖_FAQ-5865F2?style=flat-square)](https://discord.com/channels/691547840463241267/1360688874388455504/1376325634246049792)
[![BetterRTX](https://img.shields.io/badge/💬_BetterRTX-5865F2?style=flat-square)](https://discord.gg/5kK4EMRbd3)
[![Discord Thread](https://img.shields.io/badge/📢_Discord_Thread-5865F2?style=flat-square)](https://discord.com/channels/691547840463241267/1360688874388455504)

[![Download Latest](https://img.shields.io/badge/Download-Latest_Release-2ea44f?style=for-the-badge&logo=github)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/releases/latest)

</td>
</tr>
</table>

---

- 🔧 Converts the **Actions & Stuff** Marketplace pack into an **RTX-compatible version**
- 💡 Adds full **BetterRTX lighting**, reflections, and **PBR materials**
- 📦 Supports **Marketplace auto-detect**, `.zip`, and `.mcpack` input formats
- 🔒 Does **not redistribute** any original pack assets — your copy, your patch

---

> [!WARNING]
> This is a **community-driven RTX enhancement project** for _Actions & Stuff_ by **Oreville Studios**.
> The patcher **applies fixes and RTX enhancements to your own copy** of A&S — it does **not** distribute any part of the original resource pack.
>
> We kindly ask all users **not to share their patched copies** of A&S Enhanced for RTX publicly.

---

## 📁 Repository Overview

| Repository | Description | Link |
| :--- | :--- | :---: |
| **A&S RTX Patcher** | Main patcher — Marketplace & Zip support, GUI, automated patching | [This Repo](https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher) |
| **Archive** | All binary patch files (`.xdelta` / `.vcdiff`) and the legacy V1 patcher source | [Repo](https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher-Archive) |
| **External Tools** | Brarchive extractor, and other tools for the patcher! | [Repo](https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher-External_Tools) |

---

## 💾 Downloads

<div align="center">

[![Latest Stable](https://img.shields.io/badge/Download-Latest_Release-2ea44f?style=for-the-badge&logo=github)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/releases/latest)
[![Beta](https://img.shields.io/badge/Download-Beta-orange?style=for-the-badge&logo=github)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/releases/tag/V2.0.4b)

</div>

---

## ⚙️ Requirements

| Requirement | Details |
| :--- | :--- |
| [**BetterRTX**](https://bedrock.graphics/) | Must be installed |
| [**Actions & Stuff**](https://www.minecraft.net/en-us/marketplace/pdp/oreville-studios/actions--stuff-1.6/61c7a786-d7ad-49e0-a710-817121cd9795) | Marketplace, `.zip`, or `.mcpack` format |

---

## 🚀 How to Use

### Main Menu

When you launch the patcher, you'll see two cards:

**Patching**

| Button | Description |
| :--- | :--- |
| ⚡ **Patch from Marketplace** | Auto-detects your installed A&S Marketplace copy and patches it for RTX |
| 📦 **Patch from Local File** | Select a `.zip` or `.mcpack` manually *(Advanced Mode only)* |

**Maintenance**

| Button | Description |
| :--- | :--- |
| 🧹 **Clean Old Versions** | Scans for and removes previously patched packs to free space |
| 🎮 **Adjust Settings for RTX** | Applies recommended video settings for RTX (disables mob dithering, etc.) |
| ⚙️ **Adjust All Settings** | Full settings editor *(Advanced Mode only)* |

> The **Advanced Mode** switch in the bottom-right corner reveals hidden options: _Patch from Local File_ and _Adjust All Settings_.

---

### Patching Screen

After selecting a patching mode, you'll see the patching screen:

| Element | Description |
| :--- | :--- |
| **Start** | Begins the patching process |
| **Back** | Returns to the main menu (warns you if patching is in progress) |
| **Open Folder** | Opens the output folder containing the generated `.mcpack` *(appears after patching)* |
| ☑️ **Clean old versions before patching** | Automatically removes previous patches before creating a new one |
| **Process Log** | Live output of the patching process *(Advanced Mode only)* |
| 📋 **Copy Log** | Copies the process log to clipboard *(Advanced Mode only)* |

**Advanced Mode** adds these extra controls to the patching screen:

| Control | Description |
| :--- | :--- |
| **Patch Method** | Choose between `Zip (Manual)` or `Custom` mode |
| **Target Version** | Select a specific patch version from the dropdown instead of latest |
| **Source (Folder/Zip)** | Override the source pack path *(Custom mode only)* |
| **Output Filename** | Set a custom `.mcpack` output filename *(Custom mode only)* |
| **Patch File (.vcdiff)** | Use a specific `.vcdiff` patch file *(Custom mode only)* |

---

### Menu Bar

| Menu | Options |
| :--- | :--- |
| **Creator Tools** | Run bundled scripts for patch development |
| **Dependencies** | Manage and install required dependencies |
| **Help** | Links to documentation and support |

---

### 🎮 After Patching — In-Game Setup

> **⚠️ Important:** Disable **"Mob Dithering"** in Video Settings to avoid visual glitches, or use the **Adjust Settings for RTX** button in the patcher.

Set your **Resource Pack load order** (Top → Bottom):

| # | Pack | |
| :---: | :--- | :--- |
| 1 | **A&S for RTX** | ✅ Always on top |
| 2 | **RTX Pack** | Kelly's / Vanilla RTX / etc. |
| 3 | *Other Resource Packs* | Optional |
| 4 | *Actions & Stuff (Original)* | ⚠️ Optional — not recommended |


---

### 🧰 Building from Source

**Prerequisites:** Python 3.10+, `pip`

**1.** Clone and navigate to the patcher directory:

```bash
git clone https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher.git
cd "A-S-Minecraft-RTX-Community-Patcher/A&S Patcher"
```

**2.** Run the build script:

```bash
build.bat
```

The build manager will check for missing dependencies (`PyInstaller`, `Pillow`, `ttkbootstrap`) and offer to install them automatically.

**3.** Choose from the build menu:

| Option | Description |
| :--- | :--- |
| **Build — Release** | Builds a windowed `.exe` (no console) |
| **Build — Debug** | Builds with console output for debugging |
| **Version Editor** | Update version numbers across the project |
| **Clean Artifacts** | Remove `build/`, `dist/`, and `.spec` files |

The output executable will be in `dist/AnS_RTX_Patcher_V2.exe`.

> You can also run the patcher directly without building: `python main.py`

---

## 🙌 Contributors

| Name / Handle | Role | Contact |
| :--- | :--- | :--- |
| **@J4vi3r6003** | Patch development, subpacks, bug fixes | Discord: `error90099900#0000` |
| **@Felix-Chaos** | Project maintenance, patcher updates, releases | [GitHub](https://github.com/Felix-Chaos) · Discord: `felixchaos` |
| **Demente Parker** | Original creator, source files provider | Discord: `demente_parker` · [Ko-fi](https://ko-fi.com/dementeparker) |
| **Community Testers** | Bug reporting, testing, feedback | Various Discord contributors |

> Contributions welcome! Open a PR or join the [BetterRTX Discord](https://discord.gg/5kK4EMRbd3) / [ChaosDev Projects](https://discord.gg/YrMMmN2kc7).

---

## 👤 Original Creator & Support

This project is a **community fork** maintained for public development.  
The **original creator** who made the source files available is **Demente Parker**.

- Discord: `demente_parker` · ID: `498173069517651998`
- 💙 Support him on Ko-fi: [ko-fi.com/dementeparker](https://ko-fi.com/dementeparker)

> Donations go **directly to the original creator**. This repository is **non-profit** and exists solely for community collaboration.

---

## 🧠 Tools Used

- [**xdelta3**](https://github.com/jmacd/xdelta) — Binary patch creation and application
- [**Blockbench**](https://www.blockbench.net/) — Model editing & RTX material setup

---

> [!NOTE]
> **Disclaimer:** This patcher is provided by the community for **educational and personal use only**.
> It is **not affiliated with or endorsed** by Oreville Studios or Mojang/Microsoft.
> All original assets remain property of their respective owners.
>
> 🤖 The overhaul of this project, including code refactoring, UI improvements, and the automated build system, was developed with the assistance of **Google DeepMind's AI models** to accelerate development for the community.

---

<div align="center">

⭐ **Thank you for being part of the A&S RTX community!**  
Your support, testing, and feedback keep this project alive — together we make RTX shine brighter. 💎

</div>
