#!/bin/bash
# Wrapper for the daily reels job — sets a minimal-env-safe PATH/HOME so it works
# under launchd/cron (which don't inherit your shell profile). Renders + uploads
# the day's batch of science reels to YouTube (The Science Drop), unlisted.
export HOME="/Users/ruzbeh.i"
export PATH="/Users/ruzbeh.i/.nvm/versions/node/v22.22.1/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "/Users/ruzbeh.i/IdeaProjects/SIdeProjects/Agentic Company" || exit 1
mkdir -p logs workspace/content/state
echo "=== daily_reels run $(date) ===" >> logs/daily_reels.log
# Auto-publish PUBLIC; the social-media team (review + compliance gate) is the
# safety net that holds anything risky before it goes live.
# --images: one premium cinematic hero image per reel (Imagen primary → Pollinations
# fallback → motion-graphics fallback, so a flaky provider never yields a blank frame).
exec .venv/bin/python scripts/daily_reels.py --count 6 --privacy public --images >> logs/daily_reels.log 2>&1
