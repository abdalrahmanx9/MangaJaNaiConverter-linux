#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/backend/src/.venv/bin/activate"
cd "$DIR/gui"
"$DIR/backend/src/.venv/bin/python3" launch_gui.py
