#!/usr/bin/env python3
"""
MangaJaNai Converter - Linux GUI Launcher
Launches the PyQt6-based GUI for manga upscaling with ROCm GPU acceleration.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.__main__ import main

if __name__ == "__main__":
    main()
