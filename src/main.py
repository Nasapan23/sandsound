"""
SandSound - YouTube Downloader
Application entry point.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.ui.app import SandSoundApp


def main() -> None:
    """Application entry point."""
    # Initialize configuration
    config = Config()

    # Create and run application
    app = SandSoundApp(config)
    app.mainloop()


if __name__ == "__main__":
    main()
