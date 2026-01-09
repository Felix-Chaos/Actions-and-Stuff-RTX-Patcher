# Deterministic Zipper

This tool is a simple utility for creating "deterministic" `.zip` files from a selected folder. A deterministic archive is one that is byte-for-byte identical every time it is created from the same set of files. This is crucial for creating binary patches (e.g., with `xdelta3`), as the patching process requires the source file to be exactly the same as the one used to create the patch.

## What it Does

The `deterministic_zipper.py` script creates a `.zip` archive from a folder, but with a few key modifications to ensure consistency:

-   **Sorted File Order**: The files and directories are added to the archive in a sorted order.
-   **Consistent Timestamps**: All files in the archive are given the same, fixed timestamp (January 1, 1980).

These changes ensure that the resulting `.zip` file is always identical if the contents of the folder have not changed.

## Features

-   **Graphical User Interface**: A simple GUI for selecting the folder to compress and the location to save the output `.zip` file.
-   **Deterministic Compression**: Creates `.zip` files that are byte-for-byte identical for the same input folder.
-   **Easy to Use**: A straightforward tool for creating consistent archives.

## How to Use

1.  **Run the Script**: Execute the `deterministic_zipper.py` script. You will need to have Python installed with `tkinter` (which is usually included by default).
2.  **Select Folder and Compress**: Click the "Select Folder and Compress" button.
3.  **Choose a Folder**: In the first dialog, select the folder you want to compress.
4.  **Save the Archive**: In the second dialog, choose a name and location for the output `.zip` file.
5.  **Compression**: The script will then compress the folder and save the `.zip` file. A message will appear to confirm that the process is complete.