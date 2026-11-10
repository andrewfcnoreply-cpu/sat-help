#!/bin/bash
# Runs the app with the project's own Python environment (made in setup).
# Xcode can call this script too. See README.md.
cd "$(dirname "$0")"
exec ./.venv/bin/python main.py
