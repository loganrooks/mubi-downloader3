This is a tool to backup movies from Mubi, using your own legit account.

## Contents
- [About](#about)
- [Bugs](#bugs)
- [Installation](#installation)
- [Usage](#usage)
- [Legal](#legal-notice)

## About
- Based on [mubi-downloader](https://github.com/NDDDDDDDDD/mubi-downloader);
- Added search to whatsonmubi from within the terminal, falling back to manually setting the ID if the movie is not found (e.g. the film is not referenced on whatsonmubi);
- Added easily editable variables at the beginning of the script;
- Added checking IP origin to match country expectation from Mubi.
- All available subtitles (SRT) are backed-up as well.
- mergetomkv.py to merge the backed-up files.
- The code we've added to the original might be 💩 as it's been 🤖 assisted.

"Mubi Downloader" is a Python script that allows users to download movies from the Mubi streaming service. It uses the Mubi API to extract the video URL and decryption key, and then decrypts it using shaka-packager.

Mubi is a streaming service that offers a carefully curated selection of movies from around the world. However, the platform restricts users from downloading the movies to their devices. Fortunately, this script bypasses that restriction and allows users to download movies from MUBI for offline viewing.

## Bugs
With some foreign characters the files may fail to write at the last moment.
 1. Note the ID,
 2. Re-run the script,
 3. Enter a random string to escape the automatic title search
 4. Enter manually the title and the id, they'll be used for the filename.

## Installation
1. Clone the repository or download the zip file and extract it.
2. Install the required libraries using one of the following methods:
    * Run the 'install_requirements.bat'
    * Manually install each library specified in 'requirements.txt'.
    * Run 'pip install -r requirements.txt'
4. Download [shaka-packager](https://github.com/shaka-project/shaka-packager/releases/) and [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE/releases) into the folder.
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
2. Replace lines 12-13 with your own values (see comments in muby_downloader.py).
4. Open your terminal and navigate to the directory containing the `mubi_downloader.py` file. (or add it to PATH)
5. Run
    ```
    python mubi_downloader.py
    ```
7. Search for the movie.
8. Check if you're in the right country but wait before pressing `Enter`.
9. Open the page in your actual browser, log-in to Mubi and play the movie for at least one second.
10. Now press `Enter`.

## Merge the files
`mergetomkv.py` will merge the video, audio and srt tracks into a single uncompressed `.mkv` file.
1. Copy and paste `mergetomkv.py` into the folder of the files you want to merge;
2. Open a terminal in the folder
3.  ```
    python mergetomkv.py
    ```
4. Wait, done.

## Legal Notice
- This program is intended solely for educational and informational purposes. The authors and contributors of this program do not condone or encourage any illegal or unethical activities. Any misuse of this program for unlawful or unethical purposes is strictly prohibited.
- Users must agree to use this program only for lawful purposes and in compliance with all applicable laws and regulations. The authors and contributors of this program will not be held responsible for any misuse or illegal activity undertaken by users.
- The use of this program is at the sole discretion of the user. The authors and contributors of this program are not responsible for any damages, direct or indirect, that may occur from using this program. Users agree to indemnify and hold harmless the authors and contributors of this program from any and all claims, damages, and expenses, including attorney's fees, arising from the use of this program.
- This program is provided "as is" without warranty of any kind, either express or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, or non-infringement. The authors and contributors of this program shall not be liable for any damages, including but not limited to direct, indirect, incidental, consequential, or punitive damages arising from the use of this program or any information contained therein.
