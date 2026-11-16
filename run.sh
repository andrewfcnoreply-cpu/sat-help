#!/bin/bash
# Runs the app with the project's own Python environment (made in setup).
# Xcode can call this script too. See README.md.
cd "$(dirname "$0")"

# Download any new questions (and app updates) from GitHub first.
# This never asks for a password and never stops the app from opening:
# if it can't update (no internet, not signed in), it says so and moves on.
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then
    echo "Checking GitHub for new questions..."
    if GIT_TERMINAL_PROMPT=0 git pull --ff-only --quiet origin main 2>/dev/null; then
        echo "Up to date."
    else
        echo "Couldn't download updates right now. Starting with the questions you have."
    fi
fi

exec ./.venv/bin/python main.py
