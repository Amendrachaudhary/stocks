"""
OpenQuant-FNO: Telethon Session & Channel Event Listener
======================================================
Asynchronous Telegram event consumer capturing raw message streams from monitored
trading channels with sub-millisecond dispatch to the quantitative execution layer.
"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional
from telethon import TelegramClient, events

logger = logging.getLogger("openquant.telegram")


class TelegramListener:
    """
    Manages the Telethon client lifecycle, event subscription, and incoming message routing.
    """

    def __init__(
        self,
        session_path: str,
        api_id: int,
        api_hash: str,
        target_channels: list,
        on_message_callback: Callable[[str, str], Coroutine[Any, Any, None]]
    ):
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        self.target_channels = target_channels
        self.on_message_callback = on_message_callback
        self.client: Optional[TelegramClient] = None
        self._is_running = False

    async def start(self):
        """Initializes and connects the Telethon client session."""
        if not self.api_id or not self.api_hash:
            raise ValueError(
                "API_ID or API_HASH missing. Please configure them in your .env file."
            )

        if self.client:
            await self.stop()

        logger.info(f"[TELEGRAM] Initializing Telethon client session at: {self.session_path}")
        self.client = TelegramClient(
            self.session_path,
            self.api_id,
            self.api_hash,
            connection_retries=None,
            retry_delay=3,
            auto_reconnect=True
        )

        await self.client.start()
        self._is_running = True

        me = await self.client.get_me()
        user_display = getattr(me, "username", None) or getattr(me, "first_name", "Authenticated User")
        logger.info(f"[TELEGRAM] Successfully connected as: @{user_display}")

        # Register event handler for target channels
        channels = self.target_channels if self.target_channels else None
        logger.info(f"[TELEGRAM] Subscribing to target channels: {channels or 'ALL CHANNELS'}")

        @self.client.on(events.NewMessage(chats=channels))
        async def _handler(event):
            try:
                raw_text = event.raw_text or ""
                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', 'Unknown Channel')
                
                # Check for image media attachment
                ocr_text = ""
                if event.media:
                    import tempfile
                    import os
                    from core.ocr_helper import extract_text_from_image
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                            tmp_path = tmp.name
                        path = await event.download_media(file=tmp_path)
                        if path and os.path.exists(path):
                            ocr_text = extract_text_from_image(path)
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                    except Exception as me_err:
                        logger.debug(f"[TELEGRAM] Image OCR extraction skipped: {me_err}")

                logger.info(f"[TELEGRAM] Message received from [{chat_title}]: {raw_text[:60]}... (OCR: {ocr_text[:40]}...)")
                
                # Dispatch to execution callback asynchronously
                asyncio.create_task(self.on_message_callback(raw_text, str(chat_title), ocr_text))
            except Exception as exc:
                logger.error(f"[TELEGRAM] Error processing message event: {exc}", exc_info=True)

        logger.info("[TELEGRAM] Event listener registered successfully.")

        # Catch up recent messages (within last 15 minutes) to ensure zero dropped signals
        try:
            from datetime import datetime as dt_cls
            import tempfile
            import os
            from core.ocr_helper import extract_text_from_image

            now_ts = dt_cls.utcnow()
            for ch in (self.target_channels or []):
                try:
                    entity = await self.client.get_entity(ch)
                    recent_msgs = await self.client.get_messages(entity, limit=5)
                    for msg in reversed(recent_msgs):
                        if msg.text or msg.media:
                            age_sec = (now_ts - msg.date.replace(tzinfo=None)).total_seconds()
                            if age_sec < 900:  # 15 minutes
                                chat_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(ch))
                                catchup_ocr = ""
                                if msg.media:
                                    try:
                                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                                            tmp_p = tmp.name
                                        d_path = await self.client.download_media(msg, file=tmp_p)
                                        if d_path and os.path.exists(d_path):
                                            catchup_ocr = extract_text_from_image(d_path)
                                            try:
                                                os.remove(d_path)
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                logger.info(f"[TELEGRAM CATCHUP] Replaying message ({int(age_sec)}s ago): {(msg.text or '')[:50]}...")
                                asyncio.create_task(self.on_message_callback(msg.text or "", str(chat_title), catchup_ocr))
                except Exception as ce:
                    logger.debug(f"[TELEGRAM CATCHUP] Channel {ch} catchup skipped: {ce}")
        except Exception as e:
            logger.debug(f"[TELEGRAM CATCHUP] Catchup error: {e}")

    async def run_until_disconnected(self):
        """Awaits client event loop until disconnection."""
        if self.client:
            await self.client.run_until_disconnected()

    async def stop(self):
        """Disconnects the client cleanly and releases session locks."""
        if self.client:
            logger.info("[TELEGRAM] Disconnecting client session...")
            try:
                if self.client.is_connected():
                    await self.client.disconnect()
            except Exception as e:
                logger.warning(f"[TELEGRAM] Error during client disconnect: {e}")
            finally:
                self.client = None
                self._is_running = False
                logger.info("[TELEGRAM] Disconnected successfully.")
