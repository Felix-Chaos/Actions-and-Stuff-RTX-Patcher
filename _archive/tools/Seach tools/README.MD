# Search Tools

This directory contains a collection of Python scripts with graphical user interfaces (GUIs) designed to help with searching and analyzing files within a project.

## Tools

### 1. Extension Conflict Finder (`repeat names search.py`)

This tool scans a selected folder and identifies files that have the same base name but different extensions. This can be useful for finding potential conflicts or redundant files in your project.

#### Features

-   **GUI**: A simple interface for selecting the folder to scan.
-   **Conflict Detection**: Finds all files with the same name but different extensions (e.g., `my_texture.png` and `my_texture.tga`).
-   **Detailed Results**: Displays the results in a table showing the base filename, the different extensions found, and the relative paths where the files are located.

#### How to Use

1.  **Run the Script**: Execute `repeat names search.py`. You will need Python with `ttkbootstrap` installed.
2.  **Select a Folder**: Click the "Browse" button and choose the folder you want to scan.
3.  **View Results**: The tool will automatically scan the folder and display any conflicts in the main window.

### 2. JSON Searcher (`search json files.py`)

This tool searches for specific keywords within `.json` files in a given folder. If a `.json` file contains any of the specified keywords, it is copied to a designated output folder.

#### Features

-   **GUI**: An easy-to-use interface for selecting input and output folders and specifying search terms.
-   **Keyword Search**: Searches for one or more comma-separated keywords (case-insensitive).
-   **File Copying**: Automatically copies any matching `.json` files to the output folder.
-   **Log Output**: Shows a log of the files that were found and copied.

#### How to Use

1.  **Run the Script**: Execute `search json files.py`. You will need Python with `ttkbootstrap` installed.
2.  **Select Input Folder**: Choose the folder containing the `.json` files you want to search.
3.  **Select Output Folder**: Choose the folder where you want to save the matching files.
4.  **Enter Keywords**: Type the keywords you want to search for, separated by commas.
5.  **Start Search**: Click the "Start Search" button to begin the process. The results will be displayed in the log window.