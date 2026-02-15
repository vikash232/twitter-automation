#!/usr/bin/env python3
"""
Generate a tweet with Google Gemini and post to X.
  - With API: set TWITTER_* env vars, run normally (requires X API credits).
  - Free (no API): use --post-via-browser so the browser script posts; no X API keys or credits needed.
Content type (info/question/poll/cricket) is set by RUN_INDEX + date (rotation) or by SLOT/time for manual runs.
Env: GEMINI_API_KEY. For API posting add TWITTER_*; for browser posting run --import-from-brave once in post_tweet_browser.py.
Inspired by: https://github.com/VishwaGauravIn/twitter-auto-poster-bot-ai
"""
import itertools
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CONTENT_TYPES = ("info", "question", "poll", "cricket")


def _run_index_from_env():
    """Return RUN_INDEX 1, 2, or 3 from env, or None if unset."""
    raw = (os.environ.get("RUN_INDEX") or "").strip()
    if raw in ("1", "2", "3"):
        return int(raw)
    return None


def get_content_type(day_of_year: int, run_index: int) -> str:
    """Which content type (info, question, poll, cricket) for this day and run. Deterministic rotation."""
    skip = day_of_year % 4
    remaining = [t for i, t in enumerate(CONTENT_TYPES) if i != skip]
    perms = list(itertools.permutations(remaining))
    perm_index = (day_of_year // 4) % len(perms)
    order = perms[perm_index]
    return order[run_index - 1]


def get_slot():
    """Return content type: from RUN_INDEX + date (rotation), or from SLOT/env/time for backward compatibility."""
    run = _run_index_from_env()
    if run is not None:
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday
        return get_content_type(day_of_year, run)
    # Fallback: SLOT env or infer from UTC time (8/1/6 PM IST = 2:30/7:30/12:30 UTC)
    slot = (os.environ.get("SLOT") or "").strip().lower()
    if slot in ("morning", "afternoon", "evening"):
        return _slot_to_content_type(slot)
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    if h == 2 and m >= 25:
        return "info"
    if h == 7 and m >= 25:
        return "question"
    if h == 12 and m >= 25:
        return "poll"
    if h < 7:
        return "info"
    if h < 12:
        return "question"
    return "poll"


def _slot_to_content_type(slot: str) -> str:
    """Map legacy slot names to content types."""
    return {"morning": "info", "afternoon": "question", "evening": "poll"}.get(slot, "info")


# Shared rules so tweets don't sound like AI copy-paste (newbies and experienced devs should not spot it).
ANTI_AI_RULES = (
    "Never use these words/phrases: folks, remember, key takeaway, pro tip, here's the thing, the real culprit?, "
    "measure everything, moral of the story, bottom line. No sign-off line that summarizes the tweet. "
    "Avoid: three-part structure every time (setup then development then conclusion), perfectly balanced sentence lengths, "
    "every sentence carrying equal weight. When the goal is to ask a question, do not give the answer in the tweet. "
    "Do NOT use quotes in the tweet (no \"...\" or '...' around phrases—only backticks for code). "
    "Do NOT use time references: no yesterday, today, this morning, afternoon, last night, last week, 2am, 3 hours, recently, etc. Keep it timeless/situational."
)
HUMAN_STYLE = (
    "Do: one concrete technical detail (metric name, label, tool, doc path). Optional fragment or abbreviation (k8s, imo, ymmv). "
    "Sound like a quick post to a team channel or timeline, not a blog summary. "
    "Under 280 characters total. Plain text. 1-2 hashtags only if they fit naturally. Output the tweet only, no quotes around it."
)
# Required structure: 2 lines then bullet points then a closing line. Use newlines.
TWEET_STRUCTURE = (
    "Structure (required): (1) Two short lines of context or setup. (2) Then 2-3 bullet points (use • or -). (3) Then one closing line (question or CTA). "
    "Use actual newlines between each part. Keep each line short so the whole tweet stays under 280 characters including the reference."
)
# Include a reference link so the reader has somewhere to go.
REFERENCE_RULES = (
    "Include one reference in every tweet: a GitHub repo URL, YouTube video URL, or official doc link (e.g. kubernetes.io/docs/..., github.com/..., youtube.com/...). "
    "Put the URL at the end or on its own line. Pick a concrete resource that fits the topic (e.g. Prometheus docs, a well-known talk, CNCF project). "
    "Give the reader a clear place to learn more."
)
# Every tweet must feel different. Never repeat or near-copy.
VARIETY_RULES = (
    "Generate something different every time. Never repeat the same tweet or a near-copy. Change the opening, the scenario, the tool, and the reference every time. "
    "Rotate: different clouds (AWS, GCP, k8s), different pain (builds, config, observability, cost, security). "
    "No generic filler—each tweet should feel like a specific moment or question with a distinct link."
)
# X/Twitter formatting: backticks make code render in monospace.
X_FORMATTING = (
    "Wrap code and technical identifiers in backticks (e.g. `kubectl get pods`, `livenessProbe`). No quotation marks for emphasis."
)

# Content types: info, question, poll, cricket. Info/question/cricket have variants; poll is single.
PROMPTS_INFO = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO/LEARNING. One tweet that teaches something or shares a useful resource for Kubernetes/cloud-native/SRE/DevOps. "
    "Use the required structure: 2 lines context, then 2-3 bullets, then closing line, then a GitHub/YouTube/doc link. "
    "Example structure only (do not copy; use a different topic and link): "
    "Containers restart before app is ready?\n"
    "Use a startup probe so k8s waits.\n"
    "• Add `startupProbe` with longer initialDelaySeconds\n"
    "• Then `livenessProbe` for ongoing health\n"
    "What changed your rollout stability?\n"
    "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#startup-probe"
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO = LESSON LEARNED / MISTAKE. One tweet about a production lesson (Kubernetes/SRE/DevOps). "
    "Structure: 2 lines setup, 2-3 bullets (what broke, what you changed), closing line, then a reference link. Use backticks for config/commands. "
    "Example structure only (do not copy): 2 lines + • point • point + closing question + URL."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO = SHORT HOW-TO or SWITCH. One tweet: we switched to X / how we do Y. Structure: 2 lines, bullets, closing, link. "
    "Example structure only (do not copy): 2 lines + • • + closing + GitHub or doc URL."
)
PROMPTS_QUESTION = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK FOR OPINION/EXPERIENCE. One tweet inviting people to share what they use or their experience. Kubernetes/cloud-native/SRE/DevOps. "
    "Structure: 2 lines context, 2-3 bullets (options or angles), closing question, then a GitHub/YouTube/doc link. "
    "Example structure only (do not copy): 2 lines + • • + question + URL."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK = HOW DO YOU HANDLE. One tweet asking how others handle a specific DevOps/SRE/k8s problem. "
    "Structure: 2 lines setup, 2-3 bullets (e.g. options or pain points), closing question, then reference link. "
    "Example structure only (do not copy): 2 lines + • • + question + URL."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK = WHAT'S YOUR TAKE. One tweet asking for opinion on a tool, practice, or trend. "
    "Structure: 2 lines, bullets, closing question, link. Never repeat the same question or link. "
    "Example structure only (do not copy): 2 lines + • • + question + URL."
)
PROMPTS_CRICKET = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + VARIETY_RULES + " "
    "Type: CRICKET/SPORTS = OPINION or TAKE. One tweet about cricket: match takeaway, player form, who will win, a stat or moment. "
    "Preferred structure: 2 short lines, then 2-3 bullet points, then a closing line. Optional: link to highlights, stats, or article if it fits. "
    "No time refs (yesterday, today, last night). Under 280 chars. 1-2 hashtags if natural (#Cricket #IPL #TeamIndia). Never repeat the same take."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + VARIETY_RULES + " "
    "Type: CRICKET/SPORTS = QUESTION to engage. One tweet asking for opinion: your XI, best catch, who should open, etc. "
    "Preferred structure: 2 lines, then 2-3 bullets (e.g. options or angles), then closing question. Optional link (stats, highlights). "
    "Different situation each time. No time refs. Under 280 chars. Never repeat the same question."
)
PROMPT_POLL = (
    ANTI_AI_RULES + " " + VARIETY_RULES + " "
    "Type: POLL. Generate a Twitter poll for Kubernetes/cloud-native/SRE/DevOps. "
    "Output format (strict): Line 1 = the poll question (under 280 chars). Lines 2-5 = exactly 2 to 4 poll options, one per line, each option under 25 characters. "
    "Pick a different topic every time; never repeat the same question or option set. No time refs. Question can use backticks. Options: short, clear. No quotes. Example format:\n"
    "Preferred way to run stateful workloads on k8s?\n"
    "StatefulSet\n"
    "Operator (e.g. Strimzi)\n"
    "External DB\n"
    "Depends"
)


def _get_prompt(content_type: str, day_of_year: int, run_index: int) -> str:
    """Return the prompt string for this content type and variant (by date + run)."""
    if content_type == "info":
        idx = (day_of_year + run_index) % len(PROMPTS_INFO)
        return PROMPTS_INFO[idx]
    if content_type == "question":
        idx = (day_of_year + run_index) % len(PROMPTS_QUESTION)
        return PROMPTS_QUESTION[idx]
    if content_type == "cricket":
        idx = (day_of_year + run_index) % len(PROMPTS_CRICKET)
        return PROMPTS_CRICKET[idx]
    return PROMPT_POLL


def generate_tweet(content_type: str, day_of_year: int, run_index: int) -> str:
    from google import genai
    from google.genai.errors import ClientError

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)")

    client = genai.Client(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = _get_prompt(content_type, day_of_year, run_index)

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
        raw = response.text.strip()
    elif response.candidates and response.candidates[0].content.parts:
        raw = response.candidates[0].content.parts[0].text.strip()
    else:
        raise SystemExit("Gemini returned no text")
    raw = re.sub(r'^["\']|["\']$', '', raw)

    if content_type == "poll":
        # Poll: first line = question, rest = options (2-4, each under 25 chars)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) < 3:
            raise SystemExit("Poll needs question + at least 2 options (one per line)")
        question = lines[0][:280]
        options = [ln[:25] for ln in lines[1:5]][:4]  # max 4 options, each max 25 chars
        if len(options) < 2:
            raise SystemExit("Poll needs at least 2 options")
        return {"text": question, "options": options}
    # Info/question/cricket: plain tweet
    text = raw
    if len(text) > 280:
        text = text[:277] + "..."
    return text


def post_tweet(text: str, poll_options: list[str] | None = None) -> None:
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
        if poll_options and len(poll_options) >= 2:
            client.create_tweet(
                text=text,
                poll=dict(options=poll_options, duration_minutes=1440),  # 24h
            )
            print("Tweet posted (poll).")
        else:
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


def should_skip(day_of_year: int, run_index: int) -> bool:
    """Deterministic ~5% skip so some days have 2 tweets. Reproducible for testing."""
    h = (day_of_year * 31 + run_index) % 100
    return h < 5


def main():
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    use_browser = "--post-via-browser" in sys.argv or "--browser" in sys.argv
    now = datetime.now(timezone.utc)
    day_of_year = now.timetuple().tm_yday
    run = _run_index_from_env()
    if run is None:
        run = 1
    content_type = get_slot()
    print(f"Content type: {content_type} (day {day_of_year}, run {run})", file=sys.stderr)

    if _run_index_from_env() is not None and should_skip(day_of_year, run):
        print("Skip this run (deterministic).", file=sys.stderr)
        return

    result = generate_tweet(content_type, day_of_year, run)
    if isinstance(result, dict):
        text, poll_options = result["text"], result.get("options")
        print(text)
        if poll_options:
            for i, opt in enumerate(poll_options, 1):
                print(f"  Poll option {i}: {opt}")
    else:
        text, poll_options = result, None
        print(text)

    if dry:
        print("[dry-run] Would post the above.", file=sys.stderr)
        return
    if use_browser:
        post_via_browser(text)  # browser path: post question only (no poll)
    else:
        post_tweet(text, poll_options=poll_options if isinstance(result, dict) else None)


if __name__ == "__main__":
    main()
