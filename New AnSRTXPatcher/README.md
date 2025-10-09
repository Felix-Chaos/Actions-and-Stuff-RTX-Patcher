# AnS RTX Patcher Guide

This tool allows you to patch "Actions & Stuff" to be compatible with RTX. It provides a simple graphical interface to patch the game from either the official Minecraft Marketplace version or a decrypted .zip or .mcpack file.


### Features



* **Patch from Marketplace:** Automatically finds your official Marketplace installation of "Actions & Stuff" and patches it.
* **Patch from .zip/.mcpack:** Allows you to patch a decrypted version of the pack from a local file.
* **Clean Old Versions:** Removes old versions of the patched pack to prevent conflicts.
* **Custom Patch Support:** Can be used with any patch pack distributed as a .zip file containing the necessary .vcdiff files and a patch_config.json.


## How to Use


### Video Tutorial

For a visual guide on how to use the patcher, watch this video:

[Watch the Tutorial](https://www.google.com/search?q=https://cdn.discordapp.com/attachments/1425032971542462495/1425580233225928894/Desktop_2025.10.08_-_14.26.01.06.mp4?ex%3D68e81a8d%26is%3D68e6c90d%26hm%3De1d07a26b5bb8e1da5e3442988ae7cc93bb84c7fc1f94564f9e9d190a98a9fb8%26)


### Patching from the Marketplace



1. **Launch the Patcher:** Open AnSRTXPatcher.exe.
2. **Select Patch File:** When prompted, select the .zip file provided by the patch creator. This file contains the necessary .vcdiff patches and configuration.
3. **Main Menu:** From the main menu, click **Patch from Marketplace**.
4. **Wait for Compression:** The patcher will search for your Minecraft installation and compress the necessary files. The UI will remain responsive, and a progress bar will show the status. This may take a minute.
5. **Patch:** Once the "Patch" button is enabled, click it to begin the patching process.
6. **Install:** After a successful patch, you will be prompted to install the pack. Click "Yes" to open the .mcpack file, which will automatically import it into Minecraft.


### Patching from a .zip/.mcpack File

This option is for users who have a decrypted, non-Marketplace version of "Actions & Stuff."



1. **Launch the Patcher:** Open AnSRTXPatcher.exe.
2. **Select Patch File:** Select the .zip file containing the patch data.
3. **Main Menu:** Click **Patch from .zip/.mcpack**.
4. **Choose Your Pack:** Select the decrypted "Actions & Stuff" .zip or .mcpack file you want to patch.
5. **Patch:** The tool will prepare the file and enable the "Patch" button. Click it to start.
6. **Install:** Once complete, you will be prompted to install the pack.


### Cleaning Old Versions

Use this utility to remove any old or conflicting versions of the patched pack before installing an update.



1. **Launch the Patcher:** Open AnSRTXPatcher.exe.
2. **Select Patch File:** Select the .zip file containing the patch data.
3. **Main Menu:** Click **Clean Old Versions for Update**.
4. **Confirm Deletion:** The patcher will scan for and list any old pack folders it finds. Click **Confirm Deletion** to remove them.


## For Patch Creators

This patcher is designed to be adaptable for your own custom patches. To create and distribute your own patch, you will need:



* A licensed copy of "Actions & Stuff" from the Minecraft Marketplace.
* A decrypted version of the pack.
* Your modified "Actions & Stuff" fixed for RTX.


### Creating a Patch

1. Get the Original Source Files:

You need two "original" files to create patches against. You must generate these using the patcher itself to ensure they are compressed correctly.



* **Actions & Stuff encrypted.zip**: Run "Patch from Marketplace". A temporary folder (temp_mp_patcher) will be created containing this file. **Copy it** before finishing the patch process.
* **Actions & Stuff decrypted.zip**: Run "Patch from .zip/.mcpack" and select an original, unmodified .mcpack file. A temporary folder (temp_zip_patcher) will be created containing this file. **Copy it** before finishing the patch process.

    **Important:** This step is necessary because xdelta3 requires the source file to be a perfect, byte-for-byte match. Different zip programs create slightly different archives. This patcher uses **deterministic compression** (fixing file order and timestamps) to guarantee that the zip files it creates are always identical, allowing the patches to apply correctly.


    Alternatively you can use a deterministic compression script like the one used by this patcher. [Get the Deterministic Compression Script](https://www.google.com/search?q=https://github.com/Felix-Chaos/A-S-Minecraft-RTX-Community-Patcher/tree/main/tools/Folder%2520Zip%2520(Determenistic))


2. Create Your Modified Pack:

Unzip one of the original packs, make your RTX modifications, and re-zip the contents into a new file (e.g., MyModifiedPack.zip). This is your target file.

3. Generate the .vcdiff Patch Files:

Use the xdelta3 command-line tool to create a patch file for each version.

# For patching the Marketplace version \
`xdelta3 -e -s "Actions & Stuff encrypted.zip" MyModifiedPack.zip "Actions & Stuff encrypted.zip.vcdiff"` \
 \
# For patching a decrypted .zip/.mcpack \
`xdelta3 -e -s "Actions & Stuff decrypted.zip" MyModifiedPack.zip "Actions & Stuff decrypted.zip.vcdiff"` \


4. Configure patch_config.json:

Create a patch_config.json file. This file tells the patcher key information. Important: Use forward slashes / for paths.
```
{ \
    "paths": { \
        "minecraft_uwp": "%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState", \
        "minecraft_beta": "%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState" \
    }, \
    "marketplace_pack_stats": { \
        "v1": { \
            "files": 16661, \
            "dirs": 301 \
        } \
    } \
} \
```



* The paths section tells the patcher where to look for the official Marketplace version of Minecraft.
* The marketplace_pack_stats are used to find the encrypted pack in the premium_cache folder. You can get these numbers by checking the properties of the Marketplace version folder of the pack.

5. Package Your Patch for Distribution:

Create the final .zip file that you will give to your users. It must contain only the following three files:



* Actions & Stuff encrypted.zip.vcdiff
* Actions & Stuff decrypted.zip.vcdiff
* patch_config.json

**Disclaimer:** Creating and distributing patches requires that the end-user owns a legitimate copy of "Actions & Stuff." Distributing the full, patched pack is piracy. This tool is intended to enable users to modify their legally owned copies of the pack.
