#!/bin/bash
# Run the free browser-based tweet poster. Uses .venv (already set up).
# Use Brave instead of Chromium: USE_BRAVE=1 ./run_browser_post.sh ...
cd "$(dirname "$0")"
.venv/bin/python3 post_tweet_browser.py "$@"
