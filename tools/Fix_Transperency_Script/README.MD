# Transparency Cleaner

This tool is a simple utility designed to clean up transparency in image files (`.tga` and `.png`). 
Its Inteded to be used after Photoshop have been used to clean up Textures from transperency (as shown in the video) to set the pixels to the right color fromat.


## Features

-   **Graphical User Interface**: A simple and easy-to-use GUI for selecting input and output folders.
-   **Batch Processing**: Processes all `.tga` and `.png` files in the selected input folder.
-   **Log Output**: Displays a log of the files that have been processed and indicates whether the operation was successful.
-   **Preserves Transparency**: The script only modifies the color of transparent pixels, it does not make them opaque.

## How to Use

1.  **Run the Script**: Execute the `clean_transparency.py` script. You will need to have Python installed with the following libraries: `ttkbootstrap`, `Pillow` (PIL), and `numpy`.
2.  **Select Input Folder**: Click the "Browse" button next to the "Input Folder" field and select the folder containing the images you want to clean.
3.  **Select Output Folder**: Click the "Browse" button next to the "Output Folder" field and select the folder where you want to save the cleaned images.
4.  **Start Cleaning**: Click the "Clean Transparency" button to begin the process.
5.  **Monitor the Log**: The log at the bottom of the window will show the progress of the operation.

The cleaned images will be saved as `.png` files in the specified output folder.