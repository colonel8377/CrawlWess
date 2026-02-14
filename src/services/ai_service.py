from openai import OpenAI
import json
from src.constant.config import settings
from src.util.logger import logger
from src.constant.prompts import (
    ANALYZE_ARTICLE_PROMPT, 
    ANALYZE_ARTICLE_SYS_PROMPT, 
    DAILY_INSIGHT_PROMPT, 
    DAILY_INSIGHT_SYS_PROMPT
)

class AIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )

    def analyze_article(self, title: str, content: str) -> dict:
        """
        Analyze article for score, summary and ad detection.
        Returns dict with keys: score, summary, is_ad
        """
        # Truncate content if too long, but keep enough for context
        truncated_content = content[:30000] 
        
        prompt = ANALYZE_ARTICLE_PROMPT.format(title=title, content=truncated_content)

        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": ANALYZE_ARTICLE_SYS_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing article '{title}': {e}")
            return {
                "score": 0,
                "summary": "AI 分析失败",
                "is_ad": False
            }

    def generate_daily_insight(self, articles_data: list[dict]) -> str:
        """
        Generate a daily insight summary based on a list of articles.
        articles_data: list of dicts with 'title' and 'summary'.
        """
        if not articles_data:
            return "今天没有高分文章。"

        articles_text = ""
        for i, art in enumerate(articles_data, 1):
            articles_text += f"{i}. 标题: {art['title']}\n   摘要: {art['summary']}\n\n"

        # Truncate if too many articles
        articles_text = articles_text[:50000]

        prompt = DAILY_INSIGHT_PROMPT.format(articles_text=articles_text)

        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": DAILY_INSIGHT_SYS_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating daily insight: {e}")
            return "由于错误无法生成今日点评。"

ai_service = AIService()
