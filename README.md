# Twitter daily schedule helper

Automates the **3-tweets-per-day** routine from `new.txt`:

| Time  | Type                    |
|-------|-------------------------|
| 8 AM  | Educational tweet       |
| 1 PM  | Personal story / hot take |
| 6 PM  | Engagement / question   |

## Scheduling with no manual posting (recommended)

To have tweets go out at **8 AM, 1 PM, 6 PM** with zero daily manual steps:

1. **X API (paid, ~$5 for hundreds of tweets)**  
   - In [developer.x.com](https://developer.x.com) → your app → **Billing** (or **Products**) → add **Basic** or credits so posting is allowed (otherwise you get 402).  
   - In this repo: `lambda/terraform/terraform.tfvars` set `enable_auto_tweet = true` and your 4 Twitter API keys, then run `terraform apply` from `lambda/terraform`.  
   - Lambda + EventBridge are already set to run at 8 AM / 1 PM / 6 PM IST and read tweet text from SSM.

2. **Edit tweets in one place, sync to AWS**  
   - Put your 3 tweets in `tweets.txt` (one per line; lines starting with `#` are skipped).  
   - Sync to SSM so Lambda uses them:
     ```bash
     python3 sync_tweets_to_ssm.py --profile vikash-own
     ```
   - Optional: run that sync on a schedule (e.g. cron at 7 PM) so you only edit `tweets.txt` and the rest is automatic.

After that, nothing manual: EventBridge triggers Lambda at the right times, Lambda posts via the API.

**AI + GitHub Actions (like [twitter-auto-poster-bot-ai](https://github.com/VishwaGauravIn/twitter-auto-poster-bot-ai)):** Gemini generates the tweet, X API posts it, GitHub Actions runs at 8 AM / 1 PM / 6 PM IST. No server, no writing tweets. Add repo secrets: `GEMINI_API_KEY` ([get key](https://aistudio.google.com/apikey)), `TWITTER_CONSUMER_KEY`, `TWITTER_CONSUMER_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`. Workflow: `.github/workflows/twitter-ai.yml`. Local test: `pip install -r requirements-ai.txt` then `SLOT=morning python3 post_tweet_ai.py --dry-run`. **Free (no X API):** run `python3 post_tweet_ai.py --post-via-browser` so Gemini generates and the browser script posts; do `post_tweet_browser.py --import-from-brave` once first. No API credits needed. No browser, no “log in”, no opening X.

(If you prefer **free** and don’t mind a one-time browser login and cron on your Mac, see **Free auto-post** below.)

## Quick start

**Every night (takes ~5 min):**

1. Optionally edit `tweets.txt` with your 3 tweet drafts (one per line; skip lines starting with `#`).
2. Run:
   ```bash
   python3 schedule_tweets.py
   ```
   or, if you wrote drafts in `tweets.txt`:
   ```bash
   python3 schedule_tweets.py tweets.txt
   ```
3. Three Twitter compose tabs open. In each, click **Schedule** and set 8:00 AM, 1:00 PM, 6:00 PM for the next day.

## Automatic daily reminder (optional)

To get a reminder and auto-open the 3 drafts at 7 PM every day:

1. Make the script runnable:
   ```bash
   chmod +x remind_and_open.sh
   ```
2. Add a cron job (run `crontab -e` and add this line; fix the path if needed):
   ```bash
   0 19 * * * /Users/vikash/vikash-personal/twitter/remind_and_open.sh
   ```

At 7 PM you’ll get a macOS notification and (if your cron has GUI access) the 3 compose tabs will open. If they don’t, run `python3 schedule_tweets.py tweets.txt` when you see the notification.

## Free auto-post (no API, no credits): browser automation

Uses Playwright to post via the X website so you don’t pay API credits. Runs on your Mac (or any machine with a browser).

### Content style (DevOps/SRE)

Use a consistent format so each tweet is scannable and link-friendly (inspired by accounts like @NaveenS16):

| Slot       | Formula                                      | Example |
|------------|----------------------------------------------|---------|
| **Morning**  | One-line hook. What they learn or get. URL + 2–4 hashtags | *Is your homelab a mess of bookmarks? Build a single pane of glass for your servers. https://example.com/dashboard #DevOps #Homelab* |
| **Afternoon** | Hot take or short story. One line + link. Hashtags | *Nobody talks about how much time we waste on "quick" config changes. Here's how we cut that in half. https://... #SRE #Automation* |
| **Evening**   | Question or prompt. Short context + link. Hashtags | *What do you do when prod is on fire and runbooks are outdated? We started here. https://... #DevOps #IncidentResponse* |

**Tips:** Keep copy human and concise. Always add a URL when you have one (blog, GitHub, YouTube)—X will show the card. Reuse a small set of hashtags (e.g. #DevOps #SRE #Kubernetes #CloudNative) so your feed looks consistent. Put one tweet per line in `tweets.txt`; lines starting with `#` are skipped.

**Setup (already done):** A virtualenv (`.venv`) and Playwright + Chromium are installed. You only need to log in once.

**One-time: log in to X**

```bash
cd /Users/vikash/vikash-personal/twitter
chmod +x run_browser_post.sh
./run_browser_post.sh
```

When the browser opens, **log in to X** in the window. When you’re logged in, go back to the terminal and press **Enter**. Auth is saved in `.twitter_auth/`. After that, the script can post without asking again.

**Post one tweet now (free, no API):**

```bash
./run_browser_post.sh morning     # posts 1st line of tweets.txt
./run_browser_post.sh afternoon   # 2nd line
./run_browser_post.sh evening    # 3rd line
./run_browser_post.sh "your tweet here"
```

**Auto-post at 8 AM, 1 PM, 6 PM (cron):**

Edit `tweets.txt` with your 3 DevOps tweets (one per line). Then `crontab -e` and add:

```
30 2 * * * cd /Users/vikash/vikash-personal/twitter && HEADLESS=1 .venv/bin/python3 post_tweet_browser.py morning
30 7 * * * cd /Users/vikash/vikash-personal/twitter && HEADLESS=1 .venv/bin/python3 post_tweet_browser.py afternoon
30 12 * * * cd /Users/vikash/vikash-personal/twitter && HEADLESS=1 .venv/bin/python3 post_tweet_browser.py evening
```

Times are in **UTC** (2:30 UTC ≈ 8 AM IST, 7:30 UTC ≈ 1 PM IST, 12:30 UTC ≈ 6 PM IST). Your Mac must be on and awake at those times (or use a small always-on machine). `HEADLESS=1` runs the browser in the background so cron can post without a visible window.

**Brave and “Personal” profile:** **If X still shows the login page:** Run **import-from-Brave** once: quit Brave (Cmd+Q), then run `.venv/bin/python3 post_tweet_browser.py --import-from-brave`. Follow prompts; session is saved to `.twitter_auth/state.json`. After that, `./run_browser_post.sh morning` uses Chromium + that session (no need to quit Brave).

If Brave is installed (and no saved session), the script uses it by default and loads your **Brave “Personal” profile** so X is already logged in (no one-time login step). Just run:
```bash
./run_browser_post.sh morning
```
Close Brave (or at least don’t have the Personal profile open) before running, **Quit Brave (Cmd+Q) first**, or the profile is locked and you may see "browser may not be secure" on login. To use Chromium instead of Brave, run without Brave installed or set `USE_BRAVE=0`.

**Note:** This automates the website (no API). If X changes their page layout, the script may need small selector updates. Auth is stored locally; keep `.twitter_auth/` private.

## AWS Lambda reminder (profile: vikash-own)

Daily email reminder at 7 PM IST (no cron on your machine).

**Prereq:** Verify your email in SES (same region as Lambda, e.g. us-east-1):  
AWS Console → SES → Verified identities → Create identity → Email. Use that address for **From** and **To**.

### Option A: Terraform (recommended)

```bash
cd lambda/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: reminder_email, from_email (profile is vikash-own by default)
terraform init
terraform plan
terraform apply
```

Variables: `aws_profile` (default `vikash-own`), `region`, `reminder_email`, `from_email`, optional `schedule_cron` (default 7 PM IST).

### Option B: Shell script

```bash
cd lambda
chmod +x deploy.sh
REMINDER_EMAIL=you@example.com FROM_EMAIL=you@example.com ./deploy.sh
```

Override region: `AWS_REGION=ap-south-1`; different time: `CRON_UTC='cron(0 19 * * ? *)'` for 7 PM UTC.

Cost: Lambda + EventBridge + SES stay within free tier for one run per day.

### Auto-post tweets (8 AM / 1 PM / 6 PM IST)

To have Lambda post tweets automatically (no manual scheduling), you need Twitter API credentials in **Secrets Manager** (never in code or repo).

#### How to get the 4 values (X Developer Portal)

1. **Open the portal**  
   Go to [developer.x.com](https://developer.x.com) → sign in → **Developer Portal** → **Projects & Apps** → **Apps** → click your app (e.g. the one you created earlier).

2. **Consumer Key → `twitter_consumer_key`**  
   On the app page, find **OAuth 1.0** (or **Keys and tokens**).  
   - **Consumer Key** (sometimes labeled **API Key** or **Client ID**) = copy this → use as `twitter_consumer_key` in `terraform.tfvars`.

3. **Consumer Secret → `twitter_consumer_secret`**  
   Same section: **Consumer Secret** (or **API Key Secret** / **Client Secret**).  
   - Click **Regenerate** or **Reveal** if needed, then copy → use as `twitter_consumer_secret`.

4. **Access Token + Secret → `twitter_access_token` and `twitter_access_token_secret`**  
   In **Access Token and Secret** (or **User authentication**):  
   - Set permission to **Read and Write** (required to post tweets).  
   - Click **Generate** (or **Regenerate**).  
   - Copy **Access Token** → `twitter_access_token`.  
   - Copy **Access Token Secret** (shown only once) → `twitter_access_token_secret`.  
   - If you had **Read** only before, you must regenerate so the new token has **Read and Write**.

5. **Put them in `terraform.tfvars`**  
   Uncomment the 4 lines (remove the `#`) and paste your values in quotes:
   ```hcl
   twitter_consumer_key         = "paste_consumer_key_here"
   twitter_consumer_secret      = "paste_consumer_secret_here"
   twitter_access_token         = "paste_access_token_here"
   twitter_access_token_secret  = "paste_access_token_secret_here"
   ```
   Then run `terraform apply` from `lambda/terraform`. Do not commit this file (it’s in `.gitignore`).

2. **Terraform:** In `terraform.tfvars` set:
   - `enable_auto_tweet = true`
   - `twitter_consumer_key` = your Consumer Key (what the portal may call “Client ID”)
   - `twitter_consumer_secret` = your Consumer Secret
   - `twitter_access_token` = your Access Token
   - `twitter_access_token_secret` = your Access Token Secret  

   Then `terraform apply`. Credentials are stored in AWS Secrets Manager; Terraform does not write them into the repo.

3. **Tweet text:** Lambda reads from SSM `/twitter/tweets/morning`, `afternoon`, `evening`. Easiest: edit `tweets.txt` (one tweet per line), then run from the repo root:
   ```bash
   python3 sync_tweets_to_ssm.py --profile vikash-own
   ```
   Or update SSM manually with `aws ssm put-parameter --name /twitter/tweets/morning --value "..." --overwrite --profile vikash-own` (and afternoon/evening).

## Files

- **schedule_tweets.py** – Opens 3 Twitter compose tabs (placeholder or from file).
- **tweets.txt** – Draft tweets (one per line); used by browser script and by `sync_tweets_to_ssm.py` for Lambda.
- **sync_tweets_to_ssm.py** – Pushes first 3 lines of `tweets.txt` to SSM so Lambda posts them at 8 AM / 1 PM / 6 PM IST.
- **post_tweet_ai.py** – Gemini generates a DevOps/SRE tweet; posts via X API (tweepy) or, with `--post-via-browser`, via the browser script (free, no API credits). See `requirements-ai.txt`.
- **remind_and_open.sh** – Notification + runs the script; use with cron for a daily reminder.
- **lambda/** – `reminder.py` (email), `post_tweet.py` (Twitter API post), `deploy.sh`, **lambda/terraform/** (Terraform for profile `vikash-own`; optional auto-post).
