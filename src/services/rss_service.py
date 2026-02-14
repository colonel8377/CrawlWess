import feedparser
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.util.database import SessionLocal, Article
from src.services.ai_service import ai_service
from src.services.content_processor import content_processor
from src.services.storage_service import storage_service
from src.util.logger import logger

class RssService:
    def fetch_and_process_feed(self, rss_url: str):
        logger.info(f"Fetching RSS: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                logger.warning(f"Feed malformed for {rss_url}: {feed.bozo_exception}")
            
            subscription_name = feed.feed.get("title", "Unknown_Subscription")
            logger.info(f"Subscription: {subscription_name}, Entries: {len(feed.entries)}")
            
            # Phase 1: Fetch and Save (Download + Update DB)
            with SessionLocal() as db:
                for entry in feed.entries:
                    try:
                        self._fetch_and_save_entry(entry, subscription_name, db)
                    except Exception as e:
                        logger.error(f"Error saving entry {entry.get('title', 'Unknown')}: {e}")
                        db.rollback()
                
                # Phase 2: Analyze Pending Articles
                self.process_pending_articles(db)
                
        except Exception as e:
            logger.error(f"Error processing feed {rss_url}: {e}")

    def _fetch_and_save_entry(self, entry, subscription_name, db: Session):
        # 1. Clean ID and Link
        # ... (Extraction logic) ...
        raw_link = entry.get("link", "")
        if not raw_link and hasattr(entry, "links") and entry.links:
             for l in entry.links:
                 if l.get('rel') == 'alternate':
                     raw_link = l.get('href', "")
                     break
             if not raw_link:
                 raw_link = entry.links[0].get('href', "")

        link = raw_link.strip().replace("`", "").strip()
        
        raw_id = entry.get("id", "")
        if not raw_id:
             raw_id = entry.get("guid", "")
        
        entry_id = raw_id.strip().replace("`", "").strip()
        title = entry.get("title", "No Title").strip()
        
        if not link or not entry_id:
            logger.warning(f"Skipping entry missing link or id: {title}")
            return

        # 2. Extract Date
        publish_date = datetime.now()
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
             publish_date = datetime(*entry.updated_parsed[:6])
        elif hasattr(entry, "published_parsed") and entry.published_parsed:
             publish_date = datetime(*entry.published_parsed[:6])
             
        date_str = publish_date.strftime("%Y-%m-%d")

        # 3. Check Deduplication & Pre-Insert
        existing = db.query(Article).filter(Article.entry_id == entry_id).first()
        article = None
        
        if existing:
            # Check if MD file exists
            if storage_service.file_exists(subscription_name, date_str, title, extension="md"):
                # Already exists and file is there. 
                # Just ensure subscription_name is set if missing
                if not existing.subscription_name:
                    existing.subscription_name = subscription_name
                    db.commit()
                return # All good, skip
            else:
                logger.warning(f"Article exists in DB but MD file missing: {title}. Re-fetching...")
                article = existing
        else:
            logger.info(f"Downloading new article: {title}")
            try:
                article = Article(
                    entry_id=entry_id,
                    title=title,
                    link=link,
                    subscription_name=subscription_name,
                    publish_date=publish_date,
                    summary="", 
                    score=0,
                    is_ad=False,
                    is_processed=False, 
                    is_sent=False,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(article)
                db.commit() 
                db.refresh(article)
            except IntegrityError:
                db.rollback()
                logger.warning(f"IntegrityError for {title}, checking if we need to repair...")
                # Re-query
                existing_after_race = db.query(Article).filter(Article.entry_id == entry_id).first()
                if existing_after_race:
                    if storage_service.file_exists(subscription_name, date_str, title, extension="md"):
                        # Ensure subscription name
                        if not existing_after_race.subscription_name:
                             existing_after_race.subscription_name = subscription_name
                             db.commit()
                        return # Race winner did the job
                    else:
                        logger.warning(f"Race winner failed to save file for {title}. Re-fetching...")
                        article = existing_after_race
                else:
                    logger.error(f"IntegrityError but cannot find article: {title}")
                    return

        # 4. Fetch & Clean Content
        content_text = ""
        source_type = "rss"
        
        if hasattr(entry, "content"):
            for content in entry.content:
                if content.get('value'):
                    content_text = content.get('value')
                    break
        
        if not content_text:
             logger.info(f"No content in RSS, fetching from: {link}")
             try:
                 headers = {
                     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                 }
                 resp = requests.get(link, headers=headers, timeout=15)
                 if resp.status_code == 200:
                     content_text = resp.text
                     source_type = "fetch"
                 else:
                     logger.error(f"Failed to fetch content, status: {resp.status_code}")
             except Exception as e:
                 logger.error(f"Failed to fetch content from {link}: {e}")

        if not content_text:
            logger.warning(f"Could not get content for {title}, skipping file save.")
            return

        # 5. Save Files
        if source_type == "fetch":
             content_md = content_processor.html_to_md(content_text)
        else:
             content_md = content_processor.html_to_md(content_text)

        storage_service.save_html(subscription_name, date_str, title, content_text)
        storage_service.save_md(subscription_name, date_str, title, content_md)
        logger.info(f"Saved files for: {title}")

    def process_pending_articles(self, db: Session):
        """
        Analyze articles that have been downloaded but not processed.
        """
        # Query for pending articles
        # Limit to 10 per batch to avoid timeouts if backlog is huge
        pending_articles = db.query(Article).filter(Article.is_processed == False).limit(10).all()
        
        if not pending_articles:
            return

        logger.info(f"Found {len(pending_articles)} pending articles to analyze.")
        
        for article in pending_articles:
            try:
                self._analyze_single_article(article, db)
            except Exception as e:
                logger.error(f"Error analyzing article {article.title}: {e}")

    def _analyze_single_article(self, article: Article, db: Session):
        logger.info(f"Analyzing article: {article.title}")
        
        date_str = article.publish_date.strftime("%Y-%m-%d")
        
        # Read MD file
        # We assume file exists if record exists. 
        # If file missing, we might need to re-fetch? 
        # For now, just skip or fail.
        file_path = storage_service.get_file_path(article.subscription_name, date_str, article.title, extension="md")
        content_md = storage_service.read_file(file_path)
        
        if not content_md:
            logger.error(f"Markdown file not found for analysis: {file_path}")
            # If file is missing, maybe we should mark it as failed or try to re-download?
            # For now, let's leave it as is_processed=False so it gets picked up if file appears (unlikely)
            # Or maybe we should delete the DB record to force re-fetch?
            return

        # AI Analysis
        analysis_result = ai_service.analyze_article(article.title, content_md)
        
        # Update DB
        article.summary = analysis_result.get("summary", "No summary")
        article.score = analysis_result.get("score", 0)
        article.is_ad = analysis_result.get("is_ad", False)
        article.is_processed = True
        article.updated_at = datetime.now()
        
        db.commit()
        logger.info(f"Analysis complete: {article.title} (Score: {article.score})")
        
        # Save Summary
        storage_service.save_markdown(article.subscription_name, date_str, article.title, article.summary, is_summary=True)


rss_service = RssService()
