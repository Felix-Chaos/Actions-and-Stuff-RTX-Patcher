---

<img width="804" height="264" alt="Favicon" src="https://github.com/user-attachments/assets/c1d10c7b-2f6b-40f7-bb27-fc03d0007c01" />

---

# 🎮 A&S Minecraft RTX Community Patcher

[![GitHub release](https://img.shields.io/github/v/release/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=for-the-badge&color=blue)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/releases)
[![GitHub issues](https://img.shields.io/github/issues/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=for-the-badge)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/issues)
[![GitHub stars](https://img.shields.io/github/stars/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher?style=for-the-badge&color=yellow)](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/stargazers)

---

## ⚠️ Important Notice

This is the **new home** of the **Fuzed Patcher**, a community-driven RTX enhancement for *Actions & Stuff* by **Oreville Studios**.
This repository now hosts the unified application that supports both Marketplace (Encrypted) and Zip (Decrypted) versions.

**Legacy versions** have been archived.

---

## 💡 What Is *A&S RTX Patcher*?

**A&S RTX Patcher** is a tool that converts the original *Actions & Stuff* Minecraft Marketplace pack into an **RTX-compatible version** for Windows Bedrock Edition.

It works by:
* Combining your **official Marketplace copy** (or local `.zip`/`.mcpack`) with **community RTX modifications**.
* Generating a **new patched version** with full **BetterRTX lighting** and PBR materials.
* Supporting both **singleplayer and multiplayer** environments.

---

## 📁 Repository Structure

We have split the project into three repositories to separate code, data, and distribution:

| Repository | Purpose | Description |
| :--- | :--- | :--- |
| **[A-S-Minecraft-RTX-Community-Patcher](https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher)** | **Main / Distribution** | Hosts the ready-to-run Fuzed Patcher application and archived legacy versions. |
| **[A-S-Patcher-Fuzed](https://github.com/Felix-Chaos/A-S-Patcher-Fuzed)** | **App Source Code** | The active development repository for the Python application code (clean, no large assets). |
| **[A-S-Patcher-Patches](https://github.com/Felix-Chaos/A-S-Patcher-Patches)** | **Patch Data** | Stores the heavy `.xdelta` patch files and tools to generate them. |

---

## 🚀 How to Use

### Option 1 — Run from this Repository (Recommended)
1.  **Download** or Clone this repository.
2.  Ensure you have **Python 3.10+**.
3.  Install dependencies: `pip install ttkbootstrap Pillow numpy`
4.  Run `python main.py`.

### Option 2 — Developer Setup
If you want to contribute to the code or manage patches:
*   Work in **[A-S-Patcher-Fuzed](https://github.com/Felix-Chaos/A-S-Patcher-Fuzed)** for UI/Logic changes.
*   Work in **[A-S-Patcher-Patches](https://github.com/Felix-Chaos/A-S-Patcher-Patches)** for version updates.

---

## 🧩 Project Progress

| Task | Status |
| :--- | :--- |
| 🚀 **Fuzed Patcher Integration** | ✅ Complete |
| ♻️ **Repository Restructuring** | ✅ Complete |
| 🧹 **Legacy Archival** | ✅ Complete |
| 📦 **1.7+ Support** | ⏳ In Progress |

---

## 👤 Creator & Support

This project is a **community fork** maintained for public RTX development.
The **original creator**, who made the source files available, is:

**Demente Parker**
*   Discord: `demente_parker`
*   💙 Support him: [ko-fi.com/demente_parker](https://ko-fi.com/demeneteparker)

> Donations are optional and go **directly to the creator**.

---

## 🧠 Tools Used
*   [**xdelta3**](https://github.com/jmacd/xdelta) — Binary patch creation
*   [**Blockbench**](https://www.blockbench.net/) — Model editing

---

## ⚖️ Disclaimer
This patcher is provided by the community for **educational and personal use only**. It is **not affiliated** with Oreville Studios or Mojang/Microsoft. All original assets remain property of their respective owners.
