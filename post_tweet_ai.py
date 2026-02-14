#!/usr/bin/env python3
"""
Generate a tweet with Google Gemini and post via X API (tweepy).
Slot (morning/afternoon/evening) sets the prompt style; if not set, derived from current UTC hour.
Env: GEMINI_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET.
Inspired by: https://github.com/VishwaGauravIn/twitter-auto-poster-bot-ai
"""
import os
import re
import sys
from datetime import datetime, timezone


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
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)")

    genai.configure(api_key=api_key)
    # gemini-pro is deprecated; use a current model (e.g. gemini-1.5-flash or gemini-2.0-flash)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)
    prompt = PROMPTS.get(slot, PROMPTS["morning"])
    response = model.generate_content(prompt)
    text = (response.text or "").strip()
    # Remove surrounding quotes if present
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
    client.create_tweet(text=text)
    print("Tweet posted.")


def main():
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    slot = get_slot()
    print(f"Slot: {slot}", file=sys.stderr)

    text = generate_tweet(slot)
    print(text)

    if dry:
        print("[dry-run] Would post the above.", file=sys.stderr)
        return
    post_tweet(text)


if __name__ == "__main__":
    main()
