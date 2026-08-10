"""Ambient Messaging Bridge — WhatsApp & Telegram bot integration."""

import os
import json
import asyncio
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bridge", tags=["messaging_bridge"])

# ── Message types ─────────────────────────────────────────────────────────────
@dataclass
class IncomingMessage:
    source: str          # "whatsapp" | "telegram" | "webhook"
    sender: str
    text: str
    raw: dict = field(default_factory=dict)


# ── Response handlers ─────────────────────────────────────────────────────────
class MessagingBridge:
    """Bidirectional messaging bridge for ambient communication channels."""

    def __init__(self):
        self._handlers: list[Callable] = []
        self._whatsapp_token: Optional[str] = None
        self._telegram_token: Optional[str] = None
        self._telegram_chat_id: Optional[str] = None
        self._running = False
        self._load_config()

    def _load_config(self):
        self._whatsapp_token = os.getenv("WHATSAPP_API_TOKEN")
        self._telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self._telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def on_message(self, handler: Callable):
        """Register a handler for incoming messages."""
        self._handlers.append(handler)

    async def handle_whatsapp(self, sender: str, text: str, raw: dict) -> dict:
        msg = IncomingMessage(source="whatsapp", sender=sender, text=text, raw=raw)
        return await self._dispatch(msg)

    async def handle_telegram(self, sender: str, text: str, raw: dict) -> dict:
        msg = IncomingMessage(source="telegram", sender=sender, text=text, raw=raw)
        return await self._dispatch(msg)

    async def handle_webhook(self, payload: dict) -> dict:
        msg = IncomingMessage(source="webhook",
                              sender=payload.get("sender", "unknown"),
                              text=payload.get("text", ""),
                              raw=payload)
        return await self._dispatch(msg)

    async def _dispatch(self, msg: IncomingMessage) -> dict:
        logger.info(f"Bridge message from {msg.source}/{msg.sender}: {msg.text[:80]}")
        responses = []
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(msg)
                else:
                    result = handler(msg)
                if result:
                    responses.append(result)
            except Exception as e:
                logger.error(f"Bridge handler error: {e}")
        return {"dispatched": len(self._handlers), "responses": responses}

    async def send_whatsapp(self, to: str, text: str) -> bool:
        if not self._whatsapp_token:
            logger.warning("WhatsApp token not configured")
            return False
        try:
            import aiohttp
            url = f"https://api.whatsapp.com/send?phone={to}&text={text}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return False

    async def send_telegram(self, text: str, chat_id: Optional[str] = None) -> bool:
        cid = chat_id or self._telegram_chat_id
        if not self._telegram_token or not cid:
            logger.warning("Telegram not configured")
            return False
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"chat_id": cid, "text": text}) as resp:
                    data = await resp.json()
                    return data.get("ok", False)
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def start_polling(self):
        """Poll Telegram for updates (simplified long-polling)."""
        if not self._telegram_token:
            logger.warning("Telegram polling: no token configured")
            return

        self._running = True
        offset = 0
        import aiohttp

        while self._running:
            try:
                url = f"https://api.telegram.org/bot{self._telegram_token}/getUpdates"
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={"offset": offset, "timeout": 30}) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            for update in data.get("result", []):
                                offset = update["update_id"] + 1
                                msg = update.get("message", {})
                                text = msg.get("text", "")
                                sender = msg.get("from", {}).get("username", "unknown")
                                if text:
                                    await self.handle_telegram(sender, text, update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self._running = False


bridge = MessagingBridge()


# ── API Routes ─────────────────────────────────────────────────────────────────
@router.post("/webhook")
async def webhook_receive(request: Request):
    payload = await request.json()
    return await bridge.handle_webhook(payload)


@router.post("/send")
async def bridge_send(request: Request):
    body = await request.json()
    channel = body.get("channel", "telegram")
    to = body.get("to", "")
    text = body.get("text", "")

    if channel == "whatsapp":
        success = await bridge.send_whatsapp(to, text)
    elif channel == "telegram":
        success = await bridge.send_telegram(text, to or None)
    else:
        raise HTTPException(400, f"Unknown channel: {channel}")

    return {"success": success, "channel": channel}


@router.get("/status")
async def bridge_status():
    return {
        "whatsapp_configured": bool(bridge._whatsapp_token),
        "telegram_configured": bool(bridge._telegram_token),
        "telegram_chat_id": bool(bridge._telegram_chat_id),
        "handlers": len(bridge._handlers),
        "polling": bridge._running,
    }
