from abc import ABC, abstractmethod
import requests
from src.constant.config import settings
from src.util.logger import logger

class BaseNotifier(ABC):
    @abstractmethod
    def send_message(self, title: str, content: str):
        pass

class DingTalkNotifier(BaseNotifier):
    def __init__(self):
        self.webhook_url = settings.DING_WEBHOOK

    def send_message(self, title: str, content: str):
        if not self.webhook_url:
            logger.warning("DingTalk Webhook not configured")
            return

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
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

    def send_message(self, title: str, content: str):
        if not self.token or not self.chat_id:
            logger.warning("Telegram Token or Chat ID not configured")
            return
        
        full_msg = f"*{title}*\n\n{content}"
        
        payload = {
            "chat_id": self.chat_id,
            "text": full_msg,
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
