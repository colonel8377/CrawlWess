import feedparser
from datetime import datetime
from sqlalchemy.orm import Session
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
            
            with SessionLocal() as db:
                for entry in feed.entries:
                    self._process_entry(entry, subscription_name, db)
                
        except Exception as e:
            logger.error(f"Error processing feed {rss_url}: {e}")

    def _process_entry(self, entry, subscription_name, db: Session):
        link = entry.get("link")
        title = entry.get("title")
        
        if not link or not title:
            return

        # Check if exists
        existing = db.query(Article).filter(Article.link == link).first()
        if existing:
            return

        logger.info(f"Processing new article: {title}")

        # Extract content
        # Try 'content' list first, then 'summary_detail', then 'description'
        content_html = ""
        if "content" in entry:
            content_html = entry.content[0].value
        elif "summary_detail" in entry:
            content_html = entry.summary_detail.value
        else:
            content_html = entry.get("description", "")

        # Extract Date
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            publish_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            publish_date = datetime(*entry.updated_parsed[:6])
        else:
            publish_date = datetime.now()
            
        date_str = publish_date.strftime("%Y-%m-%d")

        # 0. Save HTML
        storage_service.save_html(subscription_name, date_str, title, content_html)

        # 1. Convert to MD and clean
        content_md = content_processor.html_to_md(content_html)
        
        # 2. Save Article MD
        storage_service.save_markdown(subscription_name, date_str, title, content_md, is_summary=False)

        # 3. AI Analyze
        # Use content_md for analysis.
        analysis = ai_service.analyze_article(title, content_md)
        
        score = analysis.get("score", 0)
        summary = analysis.get("summary", "")
        is_ad = analysis.get("is_ad", False)
        
        # 4. Save Summary MD
        if summary:
            storage_service.save_markdown(subscription_name, date_str, title, summary, is_summary=True)

        # 5. Save to DB
        new_article = Article(
            link=link,
            title=title,
            subscription_name=subscription_name,
            publish_date=publish_date,
            score=score,
            summary=summary,
            is_ad=is_ad,
            is_processed=True,
            is_sent=False
        )
        db.add(new_article)
        db.commit()
        logger.info(f"Processed and saved: {title} (Score: {score})")

rss_service = RssService()
