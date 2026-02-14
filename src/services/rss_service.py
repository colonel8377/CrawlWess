import feedparser
import requests
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
        # 1. Clean ID and Link
        # ID Format: <id>3957156820-2247507429_1</id>
        # Link Format: <link href=" `https://mp.weixin.qq.com/s/0dLk0zx-jz8MTUnmHEtekg` "/>
        
        # Extract Link
        # feedparser might put the href in .link or .links
        raw_link = entry.get("link", "")
        if not raw_link and hasattr(entry, "links") and entry.links:
             # sometimes link is a list of dicts
             for l in entry.links:
                 if l.get('rel') == 'alternate':
                     raw_link = l.get('href', "")
                     break
             if not raw_link:
                 raw_link = entry.links[0].get('href', "")

        link = raw_link.strip().replace("`", "").strip()
        
        # Extract ID
        raw_id = entry.get("id", "")
        if not raw_id:
             raw_id = entry.get("guid", "")
        
        entry_id = raw_id.strip().replace("`", "").strip()
        
        title = entry.get("title", "No Title").strip()
        
        if not link or not entry_id:
            logger.warning(f"Skipping entry missing link or id: {title}")
            return

        # 2. Check Deduplication
        # "sqlite要知道哪些 提取摘要评分了，哪些发送过了"
        # We query by entry_id to see if we have seen this article.
        existing = db.query(Article).filter(Article.entry_id == entry_id).first()
        
        if existing:
            # If exists, we might need to update processing status if it failed before?
            # For now, user says "Every day we only extract+summarize articles that haven't been extracted"
            # So if it exists, we assume we processed it or are in the middle of it.
            # But what if it failed analysis last time?
            if not existing.is_processed:
                logger.info(f"Retrying analysis for existing article: {title}")
                # We can continue to analysis part
                pass 
            else:
                logger.info(f"Article already processed: {title}")
                return
        else:
            logger.info(f"Processing new article: {title}")
            # Create partial article record first? Or wait until analysis?
            # Better to wait until we have content.

        # 3. Extract Date (updated > published)
        # "updated就是发表日期...而且updated是包括小时+分钟的，为什么不存进去？"
        # feedparser parses updated into updated_parsed (struct_time)
        publish_date = datetime.now()
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
             publish_date = datetime(*entry.updated_parsed[:6])
        elif hasattr(entry, "published_parsed") and entry.published_parsed:
             publish_date = datetime(*entry.published_parsed[:6])
             
        date_str = publish_date.strftime("%Y-%m-%d")

        # 4. Extract Content
        # "如果有content:encoded， 直接用... 如果没有，fetch html，转成md"
        content_text = ""
        source_type = "rss" # or "fetch"
        
        # Try content:encoded (usually in entry.content)
        if hasattr(entry, "content"):
            for content in entry.content:
                # content:encoded is often parsed as text/html or text/plain
                if content.get('value'):
                    content_text = content.get('value')
                    break
        
        # If no content in RSS, fetch from URL
        if not content_text:
             logger.info(f"No content in RSS, fetching from: {link}")
             try:
                 # Fetch with headers to mimic browser
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
            logger.warning(f"Could not get content for {title}, skipping.")
            return

        # 5. Clean Content
        # "fetch html，转成md; 这两步之后都要清洗"
        # "content:encoded就是html解析好后的文本；但是你要把里面的网页url+图片等清洗一下"
        # So regardless of source, we assume it's HTML-ish and needs conversion/cleaning?
        # User said "If content:encoded, use directly... clean 1) images 2) [图片]"
        # If fetched, "fetch html -> md -> clean"
        
        if source_type == "fetch":
             # Strict cleaning for fetched HTML
             content_md = content_processor.html_to_md(content_text)
        else:
             # For RSS content, it might contain HTML tags (like <p>, <br>) even if it's "parsed text"
             # It's safer to run it through html_to_md as well to ensure consistent Markdown output
             # unless user strictly implies it's ALREADY text.
             # "content:encoded就是html解析好后的文本" -> This usually means it contains HTML entities.
             # Let's use html_to_md to be safe and get clean markdown.
             # Wait, user said: "content:encoded就是html解析好后的文本；但是你要把里面的网页url+图片等清洗一下。"
             # If I use html_to_md, it strips tags.
             content_md = content_processor.html_to_md(content_text)

        # 6. Save Metadata and Files
        # Save Raw/HTML
        storage_service.save_html(subscription_name, date_str, title, content_text)
        # Save MD
        storage_service.save_md(subscription_name, date_str, title, content_md)

        # 7. AI Analysis
        # "基于文章质量打分（判断是不是广告+有没有深度）0-10分 + 总结100字左右实质内容"
        analysis_result = ai_service.analyze_article(title, content_md)
        
        # 8. Save to DB
        # If existing (failed previous run), update it
        if existing:
            article = existing
            article.title = title
            article.link = link
            article.publish_date = publish_date
            article.summary = analysis_result.get("summary", "No summary")
            article.score = analysis_result.get("score", 0)
            article.is_ad = analysis_result.get("is_ad", False)
            article.is_processed = True
            # is_sent remains False (or whatever it was)
        else:
            article = Article(
                entry_id=entry_id,
                title=title,
                link=link,
                publish_date=publish_date,
                summary=analysis_result.get("summary", "No summary"),
                score=analysis_result.get("score", 0),
                is_ad=analysis_result.get("is_ad", False),
                is_processed=True,
                is_sent=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(article)
        
        db.commit()
        logger.info(f"Article processed and saved: {title} (Score: {article.score})")
        storage_service.save_md(subscription_name, date_str, title, content_md)
        
        # Save Summary MD
        storage_service.save_markdown(subscription_name, date_str, title, analysis_result.get("summary", ""), is_summary=True)
        
        # 3. AI Analyze
        analysis = ai_service.analyze_article(title, content_md)
        
        score = analysis.get("score", 0)
        summary = analysis.get("summary", "")
        is_ad = analysis.get("is_ad", False)
        
        # 4. Save Summary MD
        if summary:
            storage_service.save_markdown(subscription_name, date_str, title, summary, is_summary=True)

        # 5. Save to DB
        new_article = Article(
            entry_id=entry_id,
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
