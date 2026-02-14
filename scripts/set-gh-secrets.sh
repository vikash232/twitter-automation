#!/usr/bin/env bash
# Set GitHub Actions secrets for vikash232/twitter-automation from env vars.
# Run from repo root. Requires: gh auth login as vikash232 (personal).
#
# Export these first (or paste when prompted):
#   GEMINI_API_KEY, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,
#   TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET

set -e
cd "$(dirname "$0")/.."

REPO="${GH_REPO:-vikash232/twitter-automation}"

for name in GEMINI_API_KEY TWITTER_CONSUMER_KEY TWITTER_CONSUMER_SECRET TWITTER_ACCESS_TOKEN TWITTER_ACCESS_TOKEN_SECRET; do
  val="${!name}"
  if [[ -z "$val" ]]; then
    echo "Missing $name (export it or paste when prompted)."
    gh secret set "$name" --repo "$REPO"
  else
    echo -n "$val" | gh secret set "$name" --repo "$REPO"
    echo "Set $name"
  fi
done
echo "Done. Run a workflow: gh workflow run 'Tweet (AI)' --repo $REPO"
