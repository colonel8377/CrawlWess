import os

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App
    APP_ENV: str = "production"
    
    # RSS
    RSS_URLS: str # Required from Env
    
    # AI
    OPENAI_API_KEY: str # Required from Env
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str
    
    # Database
    DB_PATH: str = "data/news.db"
    
    # Notification
    NOTIFICATION_CHANNELS: str = "dingtalk"
    DING_WEBHOOK: Optional[str] = None
    TG_BOT_TOKEN: Optional[str] = None
    TG_CHAT_ID: Optional[str] = None
    
    # Auth
    ADMIN_PASSWORD: str # Required from Env
    
    # Scheduling
    PUSH_TIME: str = "09:00"
    MIN_SCORE: int = 8
    
    # Storage
    STORAGE_DIR: str = "data/articles"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore" # Ignore extra env vars

settings = Settings()
