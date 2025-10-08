# New AnS RTX Patcher

This tool allows you to patch "Actions & Stuff" to be compatible with RTX. It provides a simple graphical interface to patch the game from either the official Minecraft Marketplace version or a decrypted `.zip`/`.mcpack` file.

## Features

- **Patch from Marketplace:** Automatically finds your Marketplace installation of "Actions & Stuff" and patches it.
- **Patch from .zip/.mcpack:** Allows you to patch a decrypted version of the pack from a local file.
- **Clean Old Versions:** Removes old versions of the patched pack to prevent conflicts.
- **Custom Patch Support:** Can be used with custom `patch_config.json` and `.vcdiff` files, allowing creators to distribute their own patches.

## How to Use

### Video Tutorial

For a visual guide on how to use the patcher, watch this video:

[Watch the Tutorial](https://cdn.discordapp.com/attachments/1425032971542462495/1425580233225928894/Desktop_2025.10.08_-_14.26.01.06.mp4?ex=68e81a8d&is=68e6c90d&hm=e1d07a26b5bb8e1da5e3442988ae7cc93bb84c7fc1f94564f9e9d190a98a9fb8&)

### Patching from the Marketplace

1.  **Launch the Patcher:** Open `AnSRTXPatcher.exe`.
2.  **Select Patch File:** When prompted, select the `.zip` file that contains the patch data. This file should include the necessary `.vcdiff` patches and the `patch_config.json`.
3.  **Main Menu:** From the main menu, click **Patch from Marketplace**.
4.  **Wait for Compression:** The patcher will search for your Minecraft installation and compress the necessary files. This may take a few moments.
5.  **Patch:** Once the "Patch" button is enabled, click it to begin the patching process.
6.  **Install:** After a successful patch, you will be prompted to install the pack. Click "Yes" to open the `.mcpack` file, which will import it into Minecraft.

### Patching from a .zip/.mcpack File

This option is for users who have a decrypted version of "Actions & Stuff."

1.  **Launch the Patcher:** Open `AnSRTXPatcher.exe`.
2.  **Select Patch File:** Select the `.zip` file containing the patch data.
3.  **Main Menu:** Click **Patch from .zip/.mcpack**.
4.  **Choose Your Pack:** Select the decrypted "Actions & Stuff" `.zip` or `.mcpack` file you want to patch.
5.  **Patch:** The tool will prepare the file and enable the "Patch" button. Click it to start.
6.  **Install:** Once complete, you will be prompted to install the pack.

### Cleaning Old Versions

Use this utility to remove any old or conflicting versions of the patched pack before installing an update.

1.  **Launch the Patcher:** Open `AnSRTXPatcher.exe`.
2.  **Select Patch File:** Select the `.zip` file containing the patch data.
3.  **Main Menu:** Click **Clean Old Versions for Update**.
4.  **Confirm Deletion:** The patcher will scan for and list any old pack folders it finds. Click **Confirm Deletion** to remove them.

## For Patch Creators

This patcher is designed to be adaptable for your own custom patches. To create and distribute your own patch, you will need the following:

-   A licensed copy of "Actions & Stuff" from the Minecraft Marketplace.
-   A decrypted version of the pack to create your patch from.

### Creating a Patch

1.  **Get the Original Files:**
    -   You need two versions of the "Actions & Stuff" pack:
        -   The **original, unmodified** decrypted pack (let's call it `original.zip`).
        -   Your **modified** version of the pack with your RTX fixes (let's call it `modified.zip`).

2.  **Generate the .vcdiff Patch:**
    -   Use the `xdelta3` command-line tool to create a patch file. The command is:
        ```bash
        xdelta3 -e -s original.zip modified.zip your_patch.vcdiff
        ```

3.  **Configure `patch_config.json`:**
    -   Create a `patch_config.json` file. This file tells the patcher key information. For example:
        ```json
        {
          "patches": {
            "decrypted": "your_patch.vcdiff"
          },
          "marketplace_pack_stats": {
            "v1": {
              "files": 16661,
              "dirs": 301
            }
          }
        }
        ```
    -   The `decrypted` key should point to your `.vcdiff` file.
    -   The `marketplace_pack_stats` are used to find the encrypted pack in the Marketplace cache. You can get these numbers by checking the properties of the extracted, unmodified Marketplace version of the pack.

4.  **Package Your Patch:**
    -   Create a `.zip` file containing:
        -   `your_patch.vcdiff`
        -   `patch_config.json`
        -   The `xdelta3` directory (including the executable).
    -   Distribute this `.zip` file to your users. They will select this file when the patcher prompts them to "Select Patch File."

**Disclaimer:** Creating and distributing patches requires that the end-user owns a legitimate copy of "Actions & Stuff." Distributing the full, patched pack is piracy. This tool is intended to enable users to modify their legally owned copies of the pack.