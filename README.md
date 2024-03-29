<img src="https://mubi.com/MUBI-logo.png" alt="Mubi Logo" width="200"/>

This is a tool to backup movies from Mubi, using your own legit account.

## Table of Contents
- [Introduction](#Introduction)
- [Installation](#installation)
- [Usage](#usage)
- [Legal Notice](#legal-notice)

## About this fork:
- Added crawling from Whatsonmubi to search from within the terminal;
- Fallback to setting manually the ID if the movie is not found (e.g. the film is not referenced on whatsonmubi);
- Added easily editable variables at the beginning of the script;
- Added checking IP origin to match expectation from Mubi.
- All available subtitles (SRT) are backed-up as well.
- TODO: There is another script to merge all the files into an uncompressed .mkv with embedded SRTs.
- The code we've added to the original might be 💩 as it's been 🤖 assisted.

## Known bugs
### With some foreign characters the files may fail to write at the last moment.
- Note the ID,
- Re-run the script,
- Enter a random string to escape the automatic title search
- Enter manually the title and the id, they'll be used for the filename.
 
## Mubi Downloader (Original)
"Mubi Downloader" is a Python script that allows users to download movies from the Mubi streaming service. It uses the Mubi API to extract the video URL and decryption key, and then decrypts it using shaka-packager.

## Introduction
Mubi is a streaming service that offers a carefully curated selection of movies from around the world. However, the platform restricts users from downloading the movies to their devices. Fortunately, this script bypasses that restriction and allows users to download movies from MUBI for offline viewing.

## Installation
1. Clone the repository or download the zip file.
2. Install the required libraries using one of the following methods:
    * Run the 'install_requirements.bat'
    * Manually install each library specified in 'requirements.txt'.
    * Run 'pip install -r requirements.txt'
    * (Note: this part might be buggy, you might have to edit requirements.txt, or install one at a time).
4. Install [shaka-packager](https://github.com/shaka-project/shaka-packager/releases/tag/v2.6.1) and [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE/releases).
5. Once installed, add the folders where the tools are installed to your system's `PATH` environment variable. 

   - On Windows:

     1. Open the Start menu and search for "Environment Variables".
     2. Click "Edit the system environment variables".
     3. Click the "Environment Variables" button.
     4. Under "System variables", scroll down and find "Path", then click "Edit".
     5. Click "New" and enter the path to the folder where each tool is installed.
     6. Click "OK" to close all the windows.

## Usage

1. Open the `mubi_downloader.py` file in a text editor.
2. Replace lines 12-13 with your own values (see comments in code to find them).
4. Open your terminal and navigate to the directory containing the `mubi_downloader.py` file. (or add it to PATH)
5. Run the following command in your terminal:

    ```
    python mubi_downloader.py
    ```

6. Follow the terminal questions and your movie will download.
7. You have to open the page in your actual browser and play the movie for at least one second otherwise it'll not work.

## Legal Notice
- This program is intended solely for educational and informational purposes. The authors and contributors of this program do not condone or encourage any illegal or unethical activities. Any misuse of this program for unlawful or unethical purposes is strictly prohibited.
- Users must agree to use this program only for lawful purposes and in compliance with all applicable laws and regulations. The authors and contributors of this program will not be held responsible for any misuse or illegal activity undertaken by users.
- The use of this program is at the sole discretion of the user. The authors and contributors of this program are not responsible for any damages, direct or indirect, that may occur from using this program. Users agree to indemnify and hold harmless the authors and contributors of this program from any and all claims, damages, and expenses, including attorney's fees, arising from the use of this program.
- This program is provided "as is" without warranty of any kind, either express or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, or non-infringement. The authors and contributors of this program shall not be liable for any damages, including but not limited to direct, indirect, incidental, consequential, or punitive damages arising from the use of this program or any information contained therein.
