#!/usr/bin/env python3
"""
Generate a tweet with Google Gemini and post to X.
  - With API: set TWITTER_* env vars, run normally (requires X API credits).
  - Free (no API): use --post-via-browser so the browser script posts; no X API keys or credits needed.
Slot (morning/afternoon/evening) sets the prompt style.
Env: GEMINI_API_KEY. For API posting add TWITTER_*; for browser posting run --import-from-brave once in post_tweet_browser.py.
Inspired by: https://github.com/VishwaGauravIn/twitter-auto-poster-bot-ai
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def get_slot():
    """Return morning, afternoon, or evening from SLOT env or from current UTC time (8/1/6 PM IST = 2:30/7:30/12:30 UTC)."""
    slot = (os.environ.get("SLOT") or "").strip().lower()
    if slot in ("morning", "afternoon", "evening"):
        return slot
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    if h == 2 and m >= 25:
        return "morning"
    if h == 7 and m >= 25:
        return "afternoon"
    if h == 12 and m >= 25:
        return "evening"
    # Default by hour if run at different time
    if h < 7:
        return "morning"
    if h < 12:
        return "afternoon"
    return "evening"


PROMPTS = {
    "morning": (
        "Generate a single tweet for DevOps, SRE, or cloud engineering. "
        "Style: educational tip or something you learned (e.g. observability, Kubernetes, Terraform, CI/CD). "
        "Sound like a human practitioner. Under 280 characters, plain text, no hashtags unless one fits naturally. No quotes around the tweet."
    ),
    "afternoon": (
        "Generate a single tweet for DevOps/SRE audience. "
        "Style: short hot take or personal story (e.g. what actually caused an outage, a mistake that taught you something). "
        "Human and specific. Under 280 characters, plain text. No quotes around the tweet."
    ),
    "evening": (
        "Generate a single tweet for DevOps/SRE audience. "
        "Style: engaging question or prompt to spark replies (e.g. what do you do when..., how do you..., what's your take on...). "
        "Human and concise. Under 280 characters, plain text. No quotes around the tweet."
    ),
}


def generate_tweet(slot: str) -> str:
    from google import genai
    from google.genai.errors import ClientError

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)")

    client = genai.Client(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = PROMPTS.get(slot, PROMPTS["morning"])

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            break
        except ClientError as e:
            if getattr(e, "status_code", None) == 429 and attempt < max_retries - 1:
                wait = 20
                print(f"Rate limited (429). Waiting {wait}s before retry {attempt + 2}/{max_retries}...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise

    # Extract text from response (new SDK)
    if response.text:
        text = response.text.strip()
    elif response.candidates and response.candidates[0].content.parts:
        text = response.candidates[0].content.parts[0].text.strip()
    else:
        raise SystemExit("Gemini returned no text")
    text = re.sub(r'^["\']|["\']$', '', text)
    if len(text) > 280:
        text = text[:277] + "..."
    return text


def post_tweet(text: str) -> None:
    import tweepy

    key = os.environ.get("TWITTER_CONSUMER_KEY") or os.environ.get("CONSUMER_KEY")
    secret = os.environ.get("TWITTER_CONSUMER_SECRET") or os.environ.get("CONSUMER_SECRET")
    token = os.environ.get("TWITTER_ACCESS_TOKEN") or os.environ.get("ACCESS_TOKEN")
    token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET") or os.environ.get("ACCESS_TOKEN_SECRET")
    if not all([key, secret, token, token_secret]):
        raise SystemExit(
            "Set TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET"
        )

    client = tweepy.Client(
        consumer_key=key,
        consumer_secret=secret,
        access_token=token,
        access_token_secret=token_secret,
    )
    try:
        client.create_tweet(text=text)
        print("Tweet posted.")
    except tweepy.errors.HTTPException as e:
        if e.response.status_code == 402:
            print("402 Payment Required: Your X account has no API credits. Add credits at https://developer.x.com (Billing / Products).", file=sys.stderr)
            raise SystemExit(1) from e
        raise


def post_via_browser(text: str) -> None:
    """Post using the browser script (no X API, no credits). Requires saved session from post_tweet_browser.py --import-from-brave."""
    script_dir = Path(__file__).resolve().parent
    browser_script = script_dir / "post_tweet_browser.py"
    if not browser_script.exists():
        raise SystemExit("post_tweet_browser.py not found. Run from repo root.")
    # Pass literal tweet text; browser script posts it
    proc = subprocess.run(
        [sys.executable, str(browser_script), text],
        cwd=str(script_dir),
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    print("Tweet posted (via browser).")


def main():
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    use_browser = "--post-via-browser" in sys.argv or "--browser" in sys.argv
    slot = get_slot()
    print(f"Slot: {slot}", file=sys.stderr)

    text = generate_tweet(slot)
    print(text)

    if dry:
        print("[dry-run] Would post the above.", file=sys.stderr)
        return
    if use_browser:
        post_via_browser(text)
    else:
        post_tweet(text)


if __name__ == "__main__":
    main()
