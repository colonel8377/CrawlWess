from abc import ABC, abstractmethod
import requests
from src.constant.config import settings
from src.util.logger import logger

import math

class BaseNotifier(ABC):
    @abstractmethod
    def send_message(self, title: str, content: str):
        pass

class DingTalkNotifier(BaseNotifier):
    def __init__(self):
        self.webhook_url = settings.DING_WEBHOOK
        self.MAX_CHARS = 4000 # Limit to 4000 chars (safe for 20000 bytes utf-8)

    def send_message(self, title: str, content: str):
        if not self.webhook_url:
            logger.warning("DingTalk Webhook not configured")
            return

        # Split content if too long
        chunks = self._split_content(content, self.MAX_CHARS) 
        
        for i, chunk in enumerate(chunks):
            # For subsequent chunks, we don't need the big title again, just content
            chunk_title = title if i == 0 else f"{title} (Part {i+1})"
            self._send_single_message(chunk_title, chunk)

    def _send_single_message(self, title, text):
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{text}"
            }
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200 and response.json().get("errcode") == 0:
                logger.info("DingTalk notification sent.")
            else:
                logger.error(f"DingTalk error: {response.text}")
        except Exception as e:
            logger.error(f"DingTalk send failed: {e}")

    def _split_content(self, content, chunk_size):
        return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

class TelegramNotifier(BaseNotifier):
    def __init__(self):
        self.token = settings.TG_BOT_TOKEN
        self.chat_id = settings.TG_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.MAX_CHARS = 4000 # Telegram limit is 4096 chars

    def send_message(self, title: str, content: str):
        if not self.token or not self.chat_id:
            logger.warning("Telegram Token or Chat ID not configured")
            return
        
        full_msg = f"*{title}*\n\n{content}"
        
        # Split if too long
        if len(full_msg) > self.MAX_CHARS:
             # Split the original content, not the full_msg which has title already
             # Actually, simpler to just split the full_msg
             chunks = self._split_content(full_msg, self.MAX_CHARS)
             for chunk in chunks:
                 self._send_single_message(chunk)
        else:
             self._send_single_message(full_msg)

    def _send_single_message(self, text):
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown" 
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent.")
            else:
                logger.error(f"Telegram error: {response.text}")
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    def _split_content(self, content, chunk_size):
        return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

class NotifierManager:
    def __init__(self):
        self.notifiers: list[BaseNotifier] = []
        channels = [c.strip().lower() for c in settings.NOTIFICATION_CHANNELS.split(",")]
        
        if "dingtalk" in channels:
            self.notifiers.append(DingTalkNotifier())
        if "telegram" in channels:
            self.notifiers.append(TelegramNotifier())
            
    def send_markdown(self, title: str, text: str):
        """
        Send message to all configured channels.
        """
        if not self.notifiers:
            logger.warning("No notification channels configured.")
            return

        for notifier in self.notifiers:
            notifier.send_message(title, text)

notifier = NotifierManager()
