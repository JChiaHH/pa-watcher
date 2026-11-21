# pa-watcher

Pings the owner on Telegram when someone messages the assistant bot while the laptop (which runs the bot) is off.
Runs on GitHub Actions every ~5 min (public repo: free). keepalive.yml stops GitHub from pausing the schedule. Read-only towards the bot's message queue: it never removes messages, so the
laptop still handles them when it's back on.

Secrets (Settings → Secrets and variables → Actions): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`.
Source of truth: `personal-agent/watcher/` (copy changes here).
