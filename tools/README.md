# Tools

This directory contains a variety of helper tools and scripts used in the development and packaging of the "Actions & Stuff: Enhanced for RTX" patcher. Each subdirectory contains a specific tool with its own detailed documentation.

## Tools Overview

| Tool | Description | Link |
| --- | --- | --- |
| **Transparency Cleaner** | A GUI tool to fix transparency issues in `.tga` and `.png` textures by cleaning up semi-transparent pixels that can cause visual artifacts in Minecraft with RTX. | [Documentation](./Fix_Transperency_Script/README.MD) |
| **Deterministic Zipper** | A GUI tool to create byte-for-byte identical `.zip` archives from a folder. This is essential for creating reliable binary patches with `xdelta3`. | [Documentation](./Folder Zip Determenistic/README.MD) |
| **Search Tools** | A collection of GUI-based search utilities, including a tool to find filename conflicts and a tool to search for keywords within `.json` files. | [Documentation](./Seach tools/README.MD) |
| **xdelta3 GUI** | A graphical user interface for the `xdelta3` command-line tool, which is used to create and apply binary patches. | [Documentation](./xdelta3/README.MD) |