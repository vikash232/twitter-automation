#!/usr/bin/env python3
"""
Post a tweet by automating the X (Twitter) website. No API, no credits.
First run: you log in in the browser; we save auth. Next runs: we reuse it and post.

Usage:
  python3 post_tweet_browser.py              # post first line of tweets.txt
  python3 post_tweet_browser.py morning     # post line 1 (8 AM)
  python3 post_tweet_browser.py afternoon  # post line 2 (1 PM)
  python3 post_tweet_browser.py evening    # post line 3 (6 PM)
  python3 post_tweet_browser.py "your tweet text here"
  python3 post_tweet_browser.py --dry-run morning   # print what would be posted, no browser
  python3 post_tweet_browser.py --import-from-brave # one-time: copy X session from Brave → then use Chromium

  Recommended: Quit Brave, run --import-from-brave once to save your X session. After that, run
  ./run_browser_post.sh morning (Chromium + saved session; no need to quit Brave each time).
  crontab: 0 8 * * * .../post_tweet_browser.py morning
"""
import os
import sys
from pathlib import Path

AUTH_DIR = Path(__file__).resolve().parent / ".twitter_auth"
STATE_FILE = AUTH_DIR / "state.json"
TWEETS_FILE = Path(__file__).resolve().parent / "tweets.txt"
X_URL = "https://x.com/home"

# Brave executable paths (Chromium-based; Playwright can drive it)
BRAVE_PATHS = [
    Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),  # macOS
    Path(os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")),
    Path("/usr/bin/brave-browser"),   # Linux
    Path("/usr/bin/brave"),           # Linux
]

# Brave user data dir (where profiles live)
BRAVE_USER_DATA_DIRS = [
    Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser",
    Path.home() / "Library/Application Support/Brave Software/Brave-Browser",
    Path.home() / ".config/BraveSoftware/Brave-Browser",
]


def get_brave_personal_profile_dir():
    """Find the profile directory name for Brave's 'Personal' profile (Default, Profile 1, etc.)."""
    import json
    for data_dir in BRAVE_USER_DATA_DIRS:
        local_state = data_dir / "Local State"
        if not local_state.exists():
            continue
        try:
            raw = local_state.read_text(encoding="utf-8")
            data = json.loads(raw)
            info = data.get("profile", {}).get("info_cache") or data.get("profile_info_cache") or {}
            for profile_dir, info_dict in info.items():
                if isinstance(info_dict, dict) and info_dict.get("name") == "Personal":
                    return str(data_dir), profile_dir
            # Fallback: first profile (often Default) if no "Personal" name
            if info:
                first = next(iter(info.keys()))
                return str(data_dir), first
        except Exception:
            continue
    return None, None


def get_tweet_text(slot_or_text):
    if not slot_or_text:
        slot_or_text = "morning"
    slot_or_text = slot_or_text.strip().lower()
    if slot_or_text in ("morning", "1", "8am"):
        line_idx = 0
    elif slot_or_text in ("afternoon", "2", "1pm"):
        line_idx = 1
    elif slot_or_text in ("evening", "3", "6pm"):
        line_idx = 2
    else:
        return slot_or_text  # use as literal tweet text
    if not TWEETS_FILE.exists():
        raise SystemExit(f"Create {TWEETS_FILE} with one tweet per line (skip # lines).")
    lines = [
        line.strip()
        for line in TWEETS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if line_idx >= len(lines):
        raise SystemExit(f"Not enough lines in {TWEETS_FILE} (need at least {line_idx + 1}).")
    return lines[line_idx]


def do_import_from_brave():
    """One-time: launch Brave Personal profile, go to X, save session to state.json. Then use Chromium + that state forever."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: pip3 install -r requirements-browser.txt && playwright install chromium")
        raise SystemExit(1)

    brave_path = None
    for path in BRAVE_PATHS:
        if path.exists():
            brave_path = str(path)
            break
    if not brave_path:
        print("Brave not found. Install Brave and log in to X there, then run --import-from-brave.")
        raise SystemExit(1)

    brave_user_data_dir, brave_profile_dir = get_brave_personal_profile_dir()
    if not brave_user_data_dir or not brave_profile_dir:
        print("Could not find Brave 'Personal' profile.")
        raise SystemExit(1)

    AUTH_DIR.mkdir(exist_ok=True)
    state_path = str(STATE_FILE)

    print("Quit Brave completely (Cmd+Q), then press Enter here to continue...")
    input()

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                brave_user_data_dir,
                executable_path=brave_path,
                headless=False,
                args=[f"--profile-directory={brave_profile_dir}"],
            )
        except Exception as e:
            if "profile" in str(e).lower() or "singleton" in str(e).lower():
                print("Brave is still running. Quit it (Cmd+Q) and run --import-from-brave again.")
            raise SystemExit(1) from e

        page = context.new_page()
        page.goto(X_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        if "/flow/login" in page.url or "login" in page.url.lower():
            print("X is not logged in in this Brave profile. Log in to X in the opened window, then press Enter here.")
            input()
            page.goto(X_URL, wait_until="networkidle", timeout=15000)
        context.storage_state(path=state_path)
        context.close()
    print("Session saved to", STATE_FILE)
    print("From now on run: ./run_browser_post.sh morning  (uses Chromium + this session; no need to quit Brave)")


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: pip3 install -r requirements-browser.txt && playwright install chromium")
        raise SystemExit(1)

    if "--import-from-brave" in sys.argv:
        do_import_from_brave()
        return

    args = [a for a in sys.argv[1:] if a != "--dry-run" and a != "-n"]
    dry_run = "--dry-run" in sys.argv[1:] or "-n" in sys.argv[1:]
    raw = " ".join(args).strip() if args else None
    text = get_tweet_text(raw)
    if len(text) > 280:
        raise SystemExit("Tweet longer than 280 characters.")
    if not text:
        raise SystemExit("No tweet text.")
    if dry_run:
        print("[dry-run] Would post:", repr(text))
        return

    AUTH_DIR.mkdir(exist_ok=True)
    state_path = str(STATE_FILE)

    use_brave = os.environ.get("USE_BRAVE", "").lower() in ("1", "true", "yes")
    brave_path = None
    if use_brave:
        for path in BRAVE_PATHS:
            if path.exists():
                brave_path = str(path)
                break
        if brave_path:
            print("Using Brave browser:", brave_path)
        else:
            print("USE_BRAVE=1 but Brave not found; using Chromium.")
    else:
        # Default: use Brave if installed (so you can use your usual Brave profile/cookies)
        for path in BRAVE_PATHS:
            if path.exists():
                brave_path = str(path)
                break

    # Prefer saved session (Chromium) when it exists — no need to quit Brave every time
    brave_user_data_dir, brave_profile_dir = None, None
    if brave_path and not STATE_FILE.exists():
        brave_user_data_dir, brave_profile_dir = get_brave_personal_profile_dir()
        if brave_user_data_dir and not os.environ.get("HEADLESS"):
            print("Tip: Quit Brave (Cmd+Q) first so the script can use your Personal profile and skip login.")
    elif STATE_FILE.exists():
        # Use Chromium + saved session (from --import-from-brave or first-run login)
        brave_user_data_dir, brave_profile_dir = None, None

    headless = os.environ.get("HEADLESS", "0") == "1"
    browser = None  # only set when using launch() (not launch_persistent_context)

    with sync_playwright() as p:
        context = None
        if brave_user_data_dir and brave_profile_dir and brave_path:
            try:
                if not headless:
                    print("Using Brave Personal profile (X already logged in).")
                context = p.chromium.launch_persistent_context(
                    brave_user_data_dir,
                    executable_path=brave_path,
                    headless=headless,
                    args=[f"--profile-directory={brave_profile_dir}"],
                )
            except Exception as e:
                err = str(e).lower()
                if "profile" in err and ("in use" in err or "singleton" in err or "singletonlock" in err):
                    print("Brave is running — the script needs exclusive access to your Personal profile.")
                    print("Quit Brave completely (Cmd+Q or Brave → Quit), then run again.")
                    if STATE_FILE.exists():
                        print("Or we can use saved login (Chromium). Retrying with Chromium...")
                        brave_user_data_dir, brave_profile_dir = None, None
                        context = None
                    else:
                        raise SystemExit(1)
                else:
                    raise
        if context is None:
            # Chromium path: reduce "automation" signals so Twitter/Google login is less likely to be blocked
            launch_opts = {
                "headless": headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            }
            if brave_path:
                launch_opts["executable_path"] = brave_path
            browser = p.chromium.launch(**launch_opts)
            if STATE_FILE.exists():
                context = browser.new_context(storage_state=state_path)
            else:
                # No saved session — would need to log in in this automated browser (X often blocks this)
                print("No saved X session. Logging in inside this window often fails (X blocks automated browsers).")
                print("Recommended: quit Brave (Cmd+Q), then run:")
                print("  .venv/bin/python3 post_tweet_browser.py --import-from-brave")
                print("That copies your existing Brave login once; after that you never log in again here.")
                print("")
                try:
                    ok = input("Continue anyway and try to log in here? [y/N]: ").strip().lower()
                    if ok != "y":
                        browser.close()
                        raise SystemExit(0)
                except EOFError:
                    browser.close()
                    raise SystemExit(0)
                # Realistic user agent so "Sign in with Google" / X are less likely to block
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                )
                print("Log in to X in the browser that just opened, then press Enter here.")
                page = context.new_page()
                page.goto(X_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                input("After you've logged in, press Enter here to save auth and exit...")
                context.storage_state(path=state_path)
                print("Auth saved. Next runs will post without asking to log in.")
                context.close()
                browser.close()
                return

        page = context.new_page()
        try:
            page.goto(X_URL, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2000)

            # Compose box: try common selectors (X changes these sometimes)
            composer = page.locator(
                '[data-testid="tweetTextarea_0"], '
                'div[contenteditable="true"][aria-label*="Post"], '
                'div[contenteditable="true"][aria-label*="Tweet"], '
                '[data-testid="tweetTextarea_0"]'
            ).first
            composer.wait_for(state="visible", timeout=10000)
            composer.click()
            page.wait_for_timeout(500)
            composer.fill(text)
            page.wait_for_timeout(500)

            # Post button
            post_btn = page.locator(
                '[data-testid="tweetButtonInline"], '
                '[data-testid="tweetButton"], '
                'button:has-text("Post")'
            ).first
            post_btn.wait_for(state="visible", timeout=5000)
            post_btn.click()
            page.wait_for_timeout(3000)
            print("Posted:", text[:60] + "..." if len(text) > 60 else text)
        finally:
            if not (brave_user_data_dir and brave_profile_dir):
                context.storage_state(path=state_path)
            context.close()
            if browser:
                browser.close()


if __name__ == "__main__":
    main()
