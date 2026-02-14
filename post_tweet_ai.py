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


# Shared rules so tweets don't sound like AI copy-paste (newbies and experienced devs should not spot it).
ANTI_AI_RULES = (
    "Never use these words/phrases: folks, remember, key takeaway, pro tip, here's the thing, the real culprit?, "
    "measure everything, moral of the story, bottom line. No sign-off line that summarizes the tweet. "
    "Avoid: three-part structure every time (setup then development then conclusion), perfectly balanced sentence lengths, "
    "every sentence carrying equal weight. When the goal is to ask a question, do not give the answer in the tweet."
)
HUMAN_STYLE = (
    "Do: one concrete technical detail (metric name, label, tool, doc path). Vary structure—question one day, "
    "one-liner the next, short scenario the next. Optional fragment or abbreviation (k8s, imo, ymmv). "
    "Optional time/context (still, again, last week). Sound like a quick post to a team channel or timeline, not a blog summary. "
    "Under 280 characters. Plain text. 1-2 hashtags only if they fit naturally. No quotes around the tweet."
)

PROMPTS = {
    "morning": (
        ANTI_AI_RULES + " " + HUMAN_STYLE + " "
        "Slot: morning. Tip or small lesson for Kubernetes/cloud-native/SRE/DevOps. "
        "No 'remember' or 'key takeaway'. One specific thing (e.g. label, doc, flag). "
        "Optional: 'still see people do X' or 'switched to Y and it helped'. Name a resource so a link can be added. "
        "Short; can be one sentence plus a fragment. "
        "Good example (match tone and specificity, do not copy): "
        '"Semantic labeling: use app.kubernetes.io/name and friends so monitoring tools actually work. kubernetes.io recommended labels."'
    ),
    "afternoon": (
        ANTI_AI_RULES + " " + HUMAN_STYLE + " "
        "Slot: afternoon. War story or hot take for Kubernetes/SRE/DevOps. "
        "Specific situation: what broke, what you changed. No punchline that sounds like a moral. "
        "Optional mild frustration or ymmv. No 'the real culprit?' style. "
        "Good example (match tone and specificity, do not copy): "
        '"To cut k8s cloud cost you have to fix over-provisioning, scaling, and discounted compute. Most orgs see 30-60% drop when they do."'
    ),
    "evening": (
        ANTI_AI_RULES + " " + HUMAN_STYLE + " "
        "Slot: evening. Scenario plus question so people reply. Kubernetes/cloud-native/SRE/DevOps. "
        "1-2 lines with concrete details (numbers, tech names), then a direct question that has an answer—do not give the answer in the tweet. "
        "Optional 'how do you handle this?' tone. "
        "Good example (match tone and specificity, do not copy): "
        '"You have 10k Lambdas hitting RDS. Too many connections. You can\'t scale max_connections. What service lets them share a small connection pool?"'
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
