"""
Slack Integration — Send messages via Slack Incoming Webhooks.

Set SLACK_WEBHOOK_URL in .env or environment to enable.
"""

import os
import json
import logging
import urllib.request
from typing import Dict, List, Optional
from pathlib import Path

log = logging.getLogger("jarvis-slack")


class SlackNotifier:
    """Send messages to Slack channels via Incoming Webhooks."""

    def __init__(self, webhook_url: str = None):
        self._url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")

    def is_configured(self) -> bool:
        return bool(self._url)

    def send(self, text: str, channel: str = None, blocks: List[Dict] = None,
             username: str = "JARVIS", icon_emoji: str = ":robot_face:") -> Dict:
        if not self._url:
            return {"ok": False, "error": "SLACK_WEBHOOK_URL not configured"}

        payload = {
            "text": text,
            "username": username,
            "icon_emoji": icon_emoji,
        }
        if channel:
            payload["channel"] = channel
        if blocks:
            payload["blocks"] = blocks

        try:
            req = urllib.request.Request(
                self._url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"ok": True, "status": resp.status}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_incident(self, title: str, severity: str, summary: str,
                      channel: str = None) -> Dict:
        color = {"P0": "#ef4444", "P1": "#f59e0b", "P2": "#3b82f6"}.get(severity, "#64748b")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":rotating_light: {title}", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{__import__('time').strftime('%Y-%m-%d %H:%M UTC')}"},
                ]
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            {"type": "divider"},
        ]
        return self.send(text=f"[{severity}] {title}: {summary}", channel=channel, blocks=blocks)

    def send_update(self, channel: str, message: str) -> Dict:
        return self.send(text=message, channel=channel)


_notifier = None

def get_slack(webhook_url: str = None) -> SlackNotifier:
    global _notifier
    if _notifier is None:
        _notifier = SlackNotifier(webhook_url)
    return _notifier
