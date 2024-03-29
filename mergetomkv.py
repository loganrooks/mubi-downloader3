import os
import subprocess

# Get the MP4 file in the current directory
mp4file = next((f for f in os.listdir() if f.endswith('.mp4')), None)

# Get the parent directory name
parentdir = os.path.basename(os.getcwd())

# Initialize variables for stream mapping
videomap = "-map 0:v"
audiomap = ""
subtitlemap = ""
subtitleinputs = ""
subtitlemetadata = ""

# Add audio stream mapping
audioidx = 1
audioinputs = ""
for a in os.listdir():
    if a.endswith('.m4a'):
        audioinputs += f' -i "{a}"'
        audiomap += f" -map {audioidx}:a"
        audioidx += 1

# Add subtitle stream mapping
subtitleidx = 2
subtitleinputs = ""
for s in os.listdir():
    if s.endswith('.srt'):
        subtitleinputs += f' -i "{s}"'
        # Extract language from file name
        language = s.split('.')[1]
        # Check if subtitle file name ends with .copy.srt
        if s.endswith('.copy.srt'):
            subtitlemetadata += f' -metadata:s:s:{subtitleidx-2} language={language} -metadata:s:s:{subtitleidx-2} title="(SDH)"'
        else:
            subtitlemetadata += f' -metadata:s:s:{subtitleidx-2} language={language}'
        subtitlemap += f" -map {subtitleidx}"
        subtitleidx += 1

# Constructing FFmpeg command
command = f'ffmpeg -i "{mp4file}" {audioinputs} {subtitleinputs} {audiomap} {subtitlemap} {videomap} -c:v copy -c:a copy -c:s srt {subtitlemetadata} "{parentdir}.mkv"'
subprocess.run(command, shell=True)