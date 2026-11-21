#!/usr/bin/env python3
"""Offline ping (runs on GitHub Actions every ~30 min, NOT on the laptop).

If someone messaged the bot in a private chat and the laptop hasn't picked it up (it's off), send the owner a
Telegram message. Read-only towards the bot's queue: getUpdates WITHOUT an offset never confirms (removes) anything,
so the laptop still gets every message when it comes back. While the laptop is on, its own long poll makes this call
fail with 409 Conflict (or find nothing waiting) and we stop quietly.

Env (GitHub secrets): TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID. State: STATE_FILE (highest update_id already reported,
kept between runs by actions/cache) so the same message isn't reported twice.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))
MIN_AGE_S = 180  # a message the laptop would have taken within seconds; older + still waiting = laptop is off
STATE_FILE = os.environ.get("STATE_FILE", "state/last_reported")


def api(token: str, method: str, params: dict) -> dict:
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=json.dumps(params).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"ok": False, "error_code": e.code}


def waiting(updates: list[dict], owner: int, now: float, last: int) -> list[dict]:
    """Private-chat messages from people other than the owner, old enough, not reported yet. (Button taps carry no
    time of their own, so they can't tell 'laptop off' from 'not polled yet': they're handled later, not reported.)"""
    out = []
    for u in updates:
        m = u.get("message") or {}
        who = m.get("from") or {}
        if u.get("update_id", 0) <= last or (m.get("chat") or {}).get("type") != "private":
            continue
        if not who.get("id") or who["id"] == owner:
            continue
        date = m.get("date") or now
        if now - date < MIN_AGE_S:
            continue  # the laptop may simply not have polled yet
        out.append({"id": u["update_id"], "name": who.get("first_name") or "Someone", "date": date})
    return out


def text_for(items: list[dict]) -> str:
    by: dict[str, list[float]] = {}
    for it in items:
        by.setdefault(it["name"], []).append(it["date"])
    parts = []
    for name, dates in by.items():
        first = datetime.fromtimestamp(min(dates), SGT).strftime("%a %H:%M")
        parts.append(f"{name} ({len(dates)} message{'s' if len(dates) != 1 else ''}, first {first})")
    return ("💤 Your laptop seems to be off, and the bot has messages waiting from " + ", ".join(parts) + ".\n"
            "Telegram keeps them for 24 h: turn the laptop on to handle them.")


def main() -> int:
    token, owner = os.environ["TELEGRAM_BOT_TOKEN"], int(os.environ["TELEGRAM_OWNER_ID"])
    try:
        last = int(open(STATE_FILE).read().strip() or 0)
    except (OSError, ValueError):
        last = 0
    r = api(token, "getUpdates", {"timeout": 0, "limit": 100})  # no offset: nothing gets confirmed/removed
    if not r.get("ok"):
        print("laptop is polling (409): it's on" if r.get("error_code") == 409 else f"getUpdates failed: {r}")
        return 0
    items = waiting(r.get("result", []), owner, time.time(), last)
    if not items:
        print(f"nothing new waiting ({len(r.get('result', []))} queued)")
        return 0
    s = api(token, "sendMessage", {"chat_id": owner, "text": text_for(items)})
    if not s.get("ok"):
        print(f"sendMessage failed: {s.get('error_code')}")
        return 1
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(str(max(it["id"] for it in items)))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("changed=1\n")
    print(f"pinged the owner about {len(items)} waiting message(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
