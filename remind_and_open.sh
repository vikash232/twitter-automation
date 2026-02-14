#!/bin/bash
# Daily reminder to schedule tomorrow's tweets, then open the 3 compose tabs.
# Schedule this to run at 7 PM: crontab -e → add:  0 19 * * * /Users/vikash/vikash-personal/twitter/remind_and_open.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# macOS notification (only works when run from a login context, e.g. cron with full path)
/usr/bin/osascript -e 'display notification "Opening 3 tweet drafts for 8a, 1p, 6p. Schedule them in Twitter." with title "Twitter: schedule tomorrow"'

python3 "$DIR/schedule_tweets.py" "$DIR/tweets.txt"
