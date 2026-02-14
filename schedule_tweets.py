#!/usr/bin/env python3
"""
DevOps/SRE/Cloud tweet schedule – 3 tabs per day:
  - 8 AM:  Educational (tip, pattern, or lesson)
  - 1 PM:  Hot take or war story
  - 6 PM:  Question to the community

Usage:
  python3 schedule_tweets.py              # open with placeholder prompts
  python3 schedule_tweets.py tweets.txt   # open with your pre-written tweets (one per line, use \\n for newlines)
"""

import sys
import urllib.parse
import webbrowser
from pathlib import Path

SCHEDULE = [
    ("8 AM – Educational", "we figured out the hard way that..."),
    ("1 PM – Hot take / war story", "nobody talks about how..."),
    ("6 PM – Engagement", "what do you do when..."),
]

COMPOSE_URL = "https://twitter.com/intent/tweet?text="


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.exists():
            lines = [
                line.replace("\\n", "\n").strip()
                for line in path.read_text(encoding="utf-8").split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
            texts = lines[:3]
            while len(texts) < 3:
                texts.append(SCHEDULE[len(texts)][1])
        else:
            print(f"File not found: {path}")
            sys.exit(1)
    else:
        texts = [t[1] for t in SCHEDULE]

    print("Opening 3 Twitter compose tabs. Schedule them for 8 AM, 1 PM, 6 PM.\n")
    for i, (label, default) in enumerate(SCHEDULE):
        text = texts[i] if i < len(texts) else default
        url = COMPOSE_URL + urllib.parse.quote(text, safe="")
        webbrowser.open(url)
        print(f"  {i + 1}. {label}")
    print("\nDone. Use Twitter's 'Schedule' on each tweet.")


if __name__ == "__main__":
    main()
