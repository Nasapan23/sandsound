# SandSound

A modern YouTube downloader with a clean, intuitive interface.

## Why I Built This

I created SandSound because existing open-source YouTube downloaders frustrated me. They either had:
- Cluttered, ugly UIs that felt like they were designed in 2005
- Missing features that should be standard
- Poor configuration options
- No playlist management

This is my personal tool that I'm building to fit **my own needs**. It will continue to evolve as I need more features.

## Features

- **Audio & Video Downloads** - MP3, M4A, OPUS, FLAC, WAV, MP4, WebM, MKV
- **Playlist Support** - Visual table view showing each song with status
- **Smart Re-download** - Only downloads new songs added to playlists
- **Cookie Support** - Paste cookies directly for age-restricted content
- **Modern Dark UI** - Clean, premium design that doesn't hurt your eyes
- **Persistent History** - Tracks what you've downloaded

## Requirements

- Python 3.10+
- FFmpeg (for audio conversion)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/sandsound.git
cd sandsound

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## FFmpeg Setup

FFmpeg is required for audio conversion. Either:
1. Install it system-wide and add to PATH, or
2. Download from the app's Settings and point to the executable

## Usage

```bash
cd src
python main.py
```

## Configuration

All settings are stored in `~/.sandsound/`:
- `config.json` - App settings
- `cookies.txt` - YouTube cookies
- `download_history.json` - Download history for smart re-downloads

## Roadmap

This is a personal project, so features will be added as I need them. Some things I might add:
- Concurrent downloads
- Download queue management
- Thumbnail embedding
- Audio normalization
- Scheduled downloads

## License

MIT - Do whatever you want with it.

---

*Built out of frustration with existing tools. Finally, a YouTube downloader that doesn't suck.*