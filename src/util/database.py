from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from src.constant.config import settings
from src.util.logger import logger
import os

# Ensure DB directory exists
# Resolve absolute path relative to project root if not absolute
current_dir = os.path.dirname(os.path.abspath(__file__)) # src/util
project_root = os.path.dirname(os.path.dirname(current_dir)) # project root

db_path = settings.DB_PATH
if not os.path.isabs(db_path):
    db_path = os.path.join(project_root, db_path)

db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create database directory {db_dir}, falling back to local sqlite.db: {e}")
        db_path = "news.db"

DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entry_id = Column(String, unique=True, index=True, nullable=True) # RSS Entry ID
    link = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    subscription_name = Column(String, index=True)
    publish_date = Column(DateTime, nullable=True) # RSS publish date
    
    # Analysis
    score = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    is_ad = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Status
    is_processed = Column(Boolean, default=False) # AI analysis done
    is_sent = Column(Boolean, default=False) # Sent in daily report

def init_db():
    logger.info(f"Initializing database...")
    logger.info(f"Database URL: {engine.url}")
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
