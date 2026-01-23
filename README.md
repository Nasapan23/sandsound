# SandSound 🎵

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

**A modern, open-source YouTube downloader with a beautiful interface**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Contributing](#-contributing) • [License](#-license)

</div>

---

## 🚀 Overview

SandSound is a desktop application for downloading YouTube videos and audio with a focus on user experience, modern design, and powerful features. Built with Python and CustomTkinter, it provides a clean, intuitive interface that makes downloading content simple and enjoyable.

### Why SandSound?

- **Modern UI** - Beautiful dark theme interface that doesn't look like it's from 2005
- **Playlist Management** - Smart playlist handling with visual progress tracking
- **Concurrent Downloads** - Download multiple files simultaneously
- **Cookie Support** - Easy authentication for age-restricted content
- **Cross-Platform** - Works on Windows, Linux, and macOS
- **Open Source** - Free, open-source, and community-driven

## ✨ Features

### Core Functionality
- 🎬 **Audio & Video Downloads** - Support for MP3, M4A, OPUS, FLAC, WAV, MP4, WebM, MKV
- 📋 **Playlist Support** - Visual table view showing each video with download status
- 🔄 **Smart Re-download** - Automatically detects and downloads only new videos from playlists
- 🍪 **Cookie Authentication** - Paste cookies directly for accessing age-restricted content
- 📊 **Download History** - Persistent tracking of downloaded content with playlist management
- ⚡ **Concurrent Downloads** - Download up to 4 files simultaneously for faster processing

### User Experience
- 🎨 **Modern Dark UI** - Clean, premium design built with CustomTkinter
- 📱 **Intuitive Interface** - Easy-to-use controls with clear visual feedback
- 🔍 **Format Selection** - Choose from multiple audio/video formats and quality settings
- 📈 **Progress Tracking** - Real-time progress updates with speed and ETA information
- ⚙️ **Customizable Settings** - Configure download directory, FFmpeg path, and more

## 📸 Screenshots

> **Note**: Screenshots coming soon! If you'd like to contribute screenshots, please see our [Contributing Guide](CONTRIBUTING.md).

## 📋 Requirements

- **Python** 3.10 or higher
- **FFmpeg** (for audio/video conversion)
  - Can be installed system-wide or configured in app settings
- **Operating System**: Windows, Linux, or macOS

## 🛠️ Installation

### Option 1: Pre-built Executable (Windows)

1. Download the latest release from the [Releases page](https://github.com/yourusername/sandsound/releases)
2. Run `SandSound-Windows-X.X.X.exe`
3. Ensure FFmpeg is installed (see [FFmpeg Setup](#ffmpeg-setup))

### Option 2: From Source

#### Prerequisites

Make sure you have Python 3.10+ installed:

```bash
python --version  # Should be 3.10 or higher
```

#### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/sandsound.git
   cd sandsound
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   cd src
   python main.py
   ```

### FFmpeg Setup

FFmpeg is required for audio conversion. You have two options:

1. **System-wide installation** (recommended)
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add to your system PATH
   - The app will auto-detect it

2. **Manual configuration**
   - Download FFmpeg
   - Open SandSound Settings
   - Point to the FFmpeg executable location

## 🎯 Usage

### Basic Usage

1. Launch SandSound
2. Paste a YouTube URL (video or playlist) into the input field
3. Select your preferred format and quality
4. Click "Download" or press Enter

### Playlist Downloads

1. Paste a playlist URL
2. The playlist bar will appear showing playlist information
3. Click "View Playlist" to see all videos
4. Select which videos to download
5. Click "Download Selected"

### Settings

Access settings via the Settings button in the top-right:
- Configure download directory
- Set FFmpeg path
- Manage cookie file
- Adjust theme preferences

## 📁 Configuration

All settings are stored in `~/.sandsound/` (or `%USERPROFILE%\.sandsound\` on Windows):

- `config.json` - Application settings (download directory, theme, etc.)
- `cookies.txt` - YouTube cookies for authentication
- `download_history.json` - Download history for smart re-downloads

## 🐛 Troubleshooting

### Common Issues

**FFmpeg not found**
- Ensure FFmpeg is installed and in your PATH, or configure the path in Settings

**Downloads fail or are slow**
- Check your internet connection
- Some videos may require cookies for authentication (add in Settings)
- Try a different format or quality setting

**Playlist button doesn't appear**
- Ensure the URL is a valid YouTube playlist
- Check that the playlist is public or you have proper authentication

**Application won't start**
- Verify Python 3.10+ is installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Review error messages in the console

### Getting Help

- Check existing [Issues](https://github.com/yourusername/sandsound/issues)
- Create a new [Issue](https://github.com/yourusername/sandsound/issues/new) with details
- Review the [Contributing Guide](CONTRIBUTING.md) for development help

## 🗺️ Roadmap

### Planned Features
- 🖼️ Thumbnail embedding in audio files
- 🔊 Audio normalization
- ⏰ Scheduled downloads
- 🌐 Multi-language support
- 📱 System tray integration
- 🔔 Download notifications

### Completed Features
- ✅ Concurrent downloads
- ✅ Download queue management
- ✅ Playlist history tracking
- ✅ Smart re-download detection

## 🤝 Contributing

We welcome contributions! SandSound is an open-source project, and we appreciate any help you can provide.

Please read our [Contributing Guide](CONTRIBUTING.md) for details on:
- How to report bugs
- How to suggest features
- Development setup
- Code style guidelines
- Pull request process

### Quick Contribution Steps

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit with clear messages (`git commit -m 'Add amazing feature'`)
5. Push to your branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - The powerful YouTube downloader library that makes this possible
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** - Beautiful modern UI components
- **[Pillow](https://python-pillow.org/)** - Image processing support
- All contributors and users who help improve SandSound

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/sandsound/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/sandsound/discussions)

---

<div align="center">

**Made with ❤️ by the SandSound community**

⭐ Star this repo if you find it useful!

</div>
