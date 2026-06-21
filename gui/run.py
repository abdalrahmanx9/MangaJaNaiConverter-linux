#!/usr/bin/env python3
"""Run MangaJaNai Converter Linux GUI"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.__main__ import main

if __name__ == "__main__":
    main()
