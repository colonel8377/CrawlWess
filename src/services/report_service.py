from sqlalchemy.orm import Session
from src.util.database import SessionLocal, Article
from src.services.notifier import notifier
from src.services.ai_service import ai_service
from src.constant.config import settings
from src.util.logger import logger
from datetime import datetime

class ReportService:
    def send_daily_report(self):
        logger.info("Starting daily report generation...")
        with SessionLocal() as db:
            # Query unseen high-quality articles
            # Criteria:
            # 1. Not sent yet (is_sent == False)
            # 2. Score >= threshold (e.g. 8)
            # 3. Not an Ad
            # 4. Must be processed (is_processed == True) - Ensure we only send analyzed ones
            articles = db.query(Article).filter(
                Article.is_sent == False,
                Article.score >= settings.MIN_SCORE,
                Article.is_ad == False,
                Article.is_processed == True
            ).all()

            if not articles:
                logger.info("No new high-quality articles to report.")
                return

            logger.info(f"Found {len(articles)} articles to report.")

            # Prepare data for insight generation
            articles_data = [{"title": a.title, "summary": a.summary} for a in articles]
            daily_insight = ai_service.generate_daily_insight(articles_data)

            # Format message
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            message_lines = [
                f"## 📅 今日精选日报 {today_str}", 
                "",
                f"> 💡 **总结**: {daily_insight}",
                "",
                "---",
                ""
            ]
            
            for article in articles:
                # Add date to title for clarity if needed, or just keep as is
                line = f"### [{article.title}]({article.link})  (评分: {article.score})"
                message_lines.append(line)
                message_lines.append(f"{article.summary}")
                message_lines.append("") # Empty line
            
            full_message = "\n".join(message_lines)
            
            # Send
            # Notifier handles splitting if too long
            notifier.send_markdown(f"今日精选日报 {today_str}", full_message)
            
            # Update DB
            for article in articles:
                article.is_sent = True
            db.commit()
            logger.info("Daily report sent and articles marked as sent.")

report_service = ReportService()
