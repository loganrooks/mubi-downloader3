# Mubi Downloader

A tool to download movies from Mubi.

## Features

- Interactive browser selection (Chrome, Firefox, Edge)
- WSL2 support for accessing Windows browser cookies
- Automatic video and audio track merging
- Subtitle downloading and processing

## Requirements

- Python 3.8 or higher
- FFmpeg (for merging media files)
- A valid Mubi subscription and login in your browser

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/mubi-downloader2.git
cd mubi-downloader2
```

2. Make the script executable:
```bash
chmod +x mubi-downloader.sh
```

## Usage

Run the script:
```bash
./mubi-downloader.sh
```

### Command Line Options

```bash
./mubi-downloader.sh [options]

Options:
  -b, --browser {chrome,firefox,edge}  Browser to extract cookies from
  -o, --output OUTPUT                  Output directory for downloaded files
  -v, --verbose                        Enable verbose logging
```

If no browser is specified, you'll be presented with an interactive menu to choose one.

### Examples

1. Basic usage (interactive browser selection):
```bash
./mubi-downloader.sh
```

2. Specify browser and output directory:
```bash
./mubi-downloader.sh --browser chrome --output my_movies
```

3. Enable verbose logging:
```bash
./mubi-downloader.sh --verbose
```

## WSL2 Support

When running in WSL2, the tool automatically detects Windows browser paths and can access cookies from Windows browsers. No additional configuration is needed - just run the tool as normal.

The tool will:
1. Try to find your Windows user profile
2. Locate browser cookie files
3. Automatically use the correct paths for cookie extraction

## Troubleshooting

1. If you get a "No cookies found" error:
   - Make sure you're logged into Mubi in your browser
   - Try specifying a different browser with --browser

2. In WSL2, if browser detection fails:
   - Your Windows username may be different from what's expected
   - Check that you can access /mnt/c/Users/[your-windows-username]

## Contributing

Feel free to submit issues and enhancement requests!
