# Actions & Stuff RTX Community Patcher

**A community-driven auto-patcher for the Actions & Stuff Minecraft RTX resource pack.**

This application simplifies the installation of the Actions & Stuff resource pack by automating the patching process for both Marketplace (Encrypted) and Custom/Zip (Decrypted) versions.

## Features
-   **Universal Patcher**: Supports both Encrypted (Marketplace) and Decrypted (Zip) versions.
-   **Auto-Cleanup**: Option to remove old pack versions before installing.
-   **Custom Manifest Injection**: Automatically fixes manifest issues for better compatibility.
-   **User Friendly**: Simple GUI with clear progress indicators.

## Installation & Usage

### Running from Source
1.  Ensure you have **Python 3.10+** installed.
2.  Install dependencies:
    ```bash
    pip install ttkbootstrap Pillow numpy
    ```
3.  Run the application:
    ```bash
    python main.py
    ```

### Patches
This application requires patch files relative to the `Patches/` directory.
*(Note: In the development environment, patch files should be placed in `Patches/` or configured via the app).*

## Project Structure
-   **`src/`**: Main application source code.
-   **`tools/`**: Helper scripts for creating patches and managing assets.
-   **`_archive/`**: Contains legacy versions of the patcher.

## Contributing
-   **Source Code**: The active development codebase is in this repository root.
-   **Patches**: Managed in the separate [Patches Repository](https://github.com/Felix-Chaos/A-S-Patcher-Patches).
