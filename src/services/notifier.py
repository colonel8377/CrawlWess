from abc import ABC, abstractmethod
import requests
from src.constant.config import settings
from src.util.logger import logger

import math

class BaseNotifier(ABC):
    @abstractmethod
    def send_message(self, title: str, content: str):
        pass

    def _split_smartly(self, content, chunk_size):
        """
        Smart split that respects Markdown headers and paragraphs.
        It tries to split at the nearest '###' or newline before the limit.
        """
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        current_chunk = ""
        
        lines = content.split('\n')
        
        for line in lines:
            # Check if adding this line exceeds limit
            # +1 for newline character
            if len(current_chunk) + len(line) + 1 > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    # Single line is longer than chunk_size (unlikely but possible)
                    # Force split
                    sub_chunks = [line[i:i+chunk_size] for i in range(0, len(line), chunk_size)]
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1]
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

class DingTalkNotifier(BaseNotifier):
    def __init__(self):
        self.webhook_url = settings.DING_WEBHOOK
        self.MAX_CHARS = 3500 # Safe limit

    def send_message(self, title: str, content: str):
        if not self.webhook_url:
            logger.warning("DingTalk Webhook not configured")
            return

        # Split content smartly
        chunks = self._split_smartly(content, self.MAX_CHARS) 
        
        for i, chunk in enumerate(chunks):
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

class TelegramNotifier(BaseNotifier):
    def __init__(self):
        self.token = settings.TG_BOT_TOKEN
        self.chat_id = settings.TG_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.MAX_CHARS = 4000 

    def send_message(self, title: str, content: str):
        if not self.token or not self.chat_id:
            logger.warning("Telegram Token or Chat ID not configured")
            return
        
        full_msg = f"*{title}*\n\n{content}"
        
        chunks = self._split_smartly(full_msg, self.MAX_CHARS)
        for chunk in chunks:
            self._send_single_message(chunk)

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
