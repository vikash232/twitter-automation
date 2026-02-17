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


# CRITICAL: Prepended to every prompt so the model never outputs this repeated tweet.
FORBIDDEN_PHRASE = (
    "CRITICAL—FORBIDDEN: Do NOT use the phrase 'one thing that actually moved the needle' or 'one thing that moved the needle for our SLOs' or "
    "'one thing that actually...' or any similar opening. That phrase is banned. Start with a different opening every time. "
)
# Shared rules so tweets don't sound like AI copy-paste.
ANTI_AI_RULES = (
    "Never use: folks, remember, key takeaway, pro tip, here's the thing, the real culprit?, measure everything, moral of the story, bottom line. "
    "No sign-off that summarizes the tweet. Do NOT use quotation marks around phrases—only backticks for code. "
    "Do NOT use time references: no yesterday, today, this morning, afternoon, last night, last week, 2am, 3 hours, recently. Keep it timeless."
)
HUMAN_STYLE = (
    "Write like someone thinking through a problem or lesson: punchy opening, then break it down with clear sections. "
    "Use real technical detail (tool, command, metric). Sound like a dev posting to the timeline, not a blog. "
    "Output the tweet only, no quotes around it. Total length: under 280 characters."
)
# Paragraph-style: blank lines between sections (double newline). Like Branko/Akhilesh style.
TWEET_STRUCTURE = (
    "Format (required): Use PARAGRAPH GAPS—put a blank line (double newline) between each section so the tweet has clear visual paragraphs. "
    "Structure: (1) Opening line or two (hook or problem). (2) Blank line. (3) Section label or transition (e.g. 'The fix:', 'Problem:', 'Requirement:'). "
    "(4) Blank line. (5) 2-4 short points (each on its own line; use - or • or just newlines). (6) Blank line. (7) Closing line or lesson. "
    "(8) Blank line. (9) One valid URL. (10) 1-2 hashtags. Use \\n\\n for blank lines between sections so it reads in distinct paragraphs."
)
# Real, valid URLs and correct hashtags only.
REFERENCE_RULES = (
    "Include exactly one REAL, valid URL that exists. Use only these domains (pick one that fits the topic): "
    "https://kubernetes.io/docs/..., https://docs.github.com/..., https://prometheus.io/docs/..., https://docs.docker.com/..., "
    "https://cloud.google.com/docs/..., https://docs.aws.amazon.com/..., https://www.terraform.io/docs/..., https://github.com/... "
    "Do not invent URLs. End the tweet with the URL on its own line, then 1-2 real hashtags: #DevOps #SRE #Kubernetes #Docker #Cloud #K8s #CloudNative #Terraform #GitOps (pick ones that fit)."
)
# Every tweet must feel different. Never repeat or near-copy.
VARIETY_RULES = (
    "Generate something different every time. Never repeat the same tweet or a near-copy. Change the opening line, the scenario, the tool, and the reference every time. "
    "Do NOT reuse the same opening (e.g. never repeat 'one thing that...' or similar). Rotate: different clouds (AWS, GCP, k8s), different pain (builds, config, observability, cost, security). "
    "No generic filler—each tweet should feel like a specific moment or question with a distinct link."
)
# Topic/angle rotation so each run gets a different focus (reduces repetition across days).
TOPIC_ANGLES = (
    "Focus this tweet on: build speed or CI/CD.",
    "Focus this tweet on: config management or drift.",
    "Focus this tweet on: observability or metrics (not SLOs or 'moved the needle').",
    "Focus this tweet on: cost or resource usage.",
    "Focus this tweet on: security or supply chain.",
    "Focus this tweet on: runbooks or incident response.",
    "Focus this tweet on: probes, health checks, or rollout stability.",
    "Focus this tweet on: labels, naming, or discovery.",
)
# For info tweets only: rotate which kind of data/theory so morning tweets are never the same.
INFO_CONCEPT_ANGLES = (
    "Explain or define one METRIC (what it counts, when to use it).",
    "Explain one CONCEPT (error budget, backoff, hot partition, eventual consistency).",
    "Explain HOW something works (probe order, rollout, retry logic).",
    "Give one LESSON with a concrete data point or threshold.",
    "Define or contrast two terms (SLI vs SLO, rate vs latency).",
    "Explain a failure mode and the data that would have caught it.",
)
# X/Twitter formatting: backticks make code render in monospace.
X_FORMATTING = (
    "Wrap code and technical identifiers in backticks (e.g. `kubectl get pods`, `livenessProbe`). No quotation marks for emphasis."
)
# Morning/info tweets: include real data or theory so folks can read and learn. Never repetitive.
INFO_DATA_THEORY = (
    "Include DATA or THEORY in every info tweet: define a metric (e.g. what `apiserver_requests_total` actually counts), "
    "explain a concept (error budget, backoff, hot partition, eventual consistency), or give one concrete technical detail (formula, threshold, how it works). "
    "Write so readers can learn something—not just a tip, but something they can read and retain. "
    "Never repeat: use a different concept, metric, or topic every time. Rotate through: SLO vs SLI, rate vs latency, partition key design, probe types, "
    "label conventions, retry/backoff theory, observability metrics, config drift, cost drivers—pick one and explain it briefly with paragraph gaps."
)

# Content types: info, question, poll, cricket. Info = morning-style, with data/theory. Style = paragraph gaps + valid URL + hashtags.
PROMPTS_INFO = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + INFO_DATA_THEORY + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO/LEARNING (morning-style). One tweet that TEACHES with data or theory (Kubernetes/cloud-native/SRE/DevOps). Use paragraph gaps. "
    "Include at least one: metric definition, concept explanation, or how-it-works detail so folks can read and learn. "
    "Example format (use a DIFFERENT concept and URL every time—never repeat the same topic):\n"
    "What does `container_memory_working_set_bytes` actually measure?\n\n"
    "The data:\n\n"
    "- Resident set + dirty memory. What the kernel could reclaim without swap.\n"
    "- OOMKill uses this. Not RSS alone.\n\n"
    "Use it for memory limits and alerts.\n\n"
    "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/\n"
    "#Kubernetes #SRE"
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + INFO_DATA_THEORY + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO = LESSON LEARNED (with data). One tweet about a mistake or production lesson. Include one concrete data point or concept (metric, threshold, why it failed). "
    "Use paragraph gaps. Never repeat the same lesson or metric. Structure: hook, then 'The data:' or 'What we learned:', then 2-3 points with substance, then URL, then hashtags."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + INFO_DATA_THEORY + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: INFO = CONCEPT or HOW-IT-WORKS. One tweet that explains one concept: error budget, backoff, hot partition, SLI vs SLO, probe order, etc. "
    "Give enough detail that someone can read and understand. Use paragraph gaps. Different concept every time. End with real URL and hashtags."
)
PROMPTS_QUESTION = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK FOR OPINION/EXPERIENCE. One tweet inviting replies (what they use, their experience). Use paragraph gaps. End with real URL and hashtags. "
    "Example format: scenario or question\\n\\nRequirement or options\\n\\n- point\\n- point\\n\\nClosing question\\n\\nURL\\n#Hashtag"
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK = HOW DO YOU HANDLE. One tweet: scenario, then 'Problem:' or 'Requirement:', then 2-3 points, then how do you solve it? Use paragraph gaps. URL + hashtags at end. "
    "Example format: hook\\n\\nlabel\\n\\npoints\\n\\nquestion\\n\\nURL\\n#Hashtag"
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + REFERENCE_RULES + " " + VARIETY_RULES + " " + X_FORMATTING + " "
    "Type: ASK = WHAT'S YOUR TAKE. One tweet asking for opinion. Paragraph gaps. Real URL and 1-2 hashtags. Never repeat the same question or link. "
    "Example format: hook\\n\\npoints\\n\\nquestion\\n\\nURL\\n#Hashtag"
)
# Cricket = T20 World Cup 2026. Focus on the ongoing tournament and daily matches.
PROMPTS_CRICKET = (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + VARIETY_RULES + " "
    "Type: CRICKET = T20 WORLD CUP 2026. One tweet about the ongoing T20 World Cup 2026: today's matches, a match result, key player performance, or a standout moment from the tournament. "
    "Write as if matches are happening every day—takeaway from a game, who stood out, key stat, or turning point. Use paragraph gaps. "
    "End with 1-2 hashtags: #T20WorldCup2026 #T20WorldCup #Cricket #TeamIndia (or other team hashtags as relevant). Optional: valid URL (ICC, highlights, scorecard). Never repeat the same take."
), (
    ANTI_AI_RULES + " " + HUMAN_STYLE + " " + TWEET_STRUCTURE + " " + VARIETY_RULES + " "
    "Type: CRICKET = T20 WORLD CUP 2026 QUESTION. One tweet engaging fans about the ongoing T20 World Cup 2026: who wins today's match? your XI for the next game? best performance so far? prediction for the knockouts? "
    "Use paragraph gaps. End with #T20WorldCup2026 #T20WorldCup #Cricket or team hashtag. Different match or angle each time. Never repeat the same question."
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
    prefix = FORBIDDEN_PHRASE
    angle = TOPIC_ANGLES[(day_of_year * 3 + run_index) % len(TOPIC_ANGLES)]
    suffix = f"\n\n{angle} Do not use the same opening or topic as a generic SLO/observability tweet."
    if content_type == "info":
        idx = (day_of_year + run_index) % len(PROMPTS_INFO)
        info_angle = INFO_CONCEPT_ANGLES[(day_of_year * 3 + run_index) % len(INFO_CONCEPT_ANGLES)]
        return prefix + PROMPTS_INFO[idx] + suffix + f" This info tweet must: {info_angle}"
    if content_type == "question":
        idx = (day_of_year + run_index) % len(PROMPTS_QUESTION)
        return prefix + PROMPTS_QUESTION[idx] + suffix
    if content_type == "cricket":
        idx = (day_of_year + run_index) % len(PROMPTS_CRICKET)
        return prefix + PROMPTS_CRICKET[idx] + "\n\nBase this on T20 World Cup 2026: a specific match, result, player, or moment from the ongoing tournament. Vary which match or team you talk about."
    if content_type == "poll":
        return prefix + PROMPT_POLL + f"\n\n{angle}"
    return prefix + PROMPT_POLL


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
