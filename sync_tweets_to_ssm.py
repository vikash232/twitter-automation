#!/usr/bin/env python3
"""
Sync first 3 tweet lines from tweets.txt to SSM parameters for Lambda.
Skips blank lines and lines starting with #. Uses same order as post_tweet_browser: 1=morning, 2=afternoon, 3=evening.
Usage: python3 sync_tweets_to_ssm.py [--profile vikash-own]
"""
import argparse
import subprocess
import sys
from pathlib import Path

TWEETS_FILE = Path(__file__).resolve().parent / "tweets.txt"
SSM_PREFIX = "/twitter/tweets"


def main():
    parser = argparse.ArgumentParser(description="Sync tweets.txt to SSM for Lambda auto-post")
    parser.add_argument("--profile", default="vikash-own", help="AWS CLI profile")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    if not TWEETS_FILE.exists():
        print(f"Create {TWEETS_FILE} with one tweet per line (skip # lines).", file=sys.stderr)
        sys.exit(1)

    lines = [
        line.strip()
        for line in TWEETS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if len(lines) < 3:
        print(f"Need at least 3 tweet lines in {TWEETS_FILE}. Found {len(lines)}.", file=sys.stderr)
        sys.exit(1)

    morning, afternoon, evening = lines[0], lines[1], lines[2]
    for name, value in [
        ("morning", morning),
        ("afternoon", afternoon),
        ("evening", evening),
    ]:
        cmd = [
            "aws", "ssm", "put-parameter",
            "--name", f"{SSM_PREFIX}/{name}",
            "--value", value,
            "--overwrite",
            "--type", "String",
            "--profile", args.profile,
            "--region", args.region,
        ]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(r.returncode)
        print(f"Updated {SSM_PREFIX}/{name}")

    print("Done. Lambda will use these at 8 AM / 1 PM / 6 PM IST.")


if __name__ == "__main__":
    main()
