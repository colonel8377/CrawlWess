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

    def analyze_article(self, title: str, content: str, max_retries: int = 3) -> dict:
        """
        Analyze article for score, summary and ad detection.
        Returns dict with keys: score, summary, is_ad
        Includes retry logic for JSON parsing failures.
        """
        # Truncate content if too long, but keep enough for context
        truncated_content = content[:30000] 
        
        prompt = ANALYZE_ARTICLE_PROMPT.format(title=title, content=truncated_content)

        for attempt in range(max_retries):
            content_resp = None
            try:
                response = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": ANALYZE_ARTICLE_SYS_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={ "type": "json_object" }
                )
                
                content_resp = response.choices[0].message.content
                result = json.loads(content_resp)
                
                # Basic validation of result structure
                if "score" not in result or "summary" not in result:
                     raise ValueError("Missing required keys in JSON response")
                     
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error analyzing article '{title}', content resp: {content_resp}, (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                     logger.error(f"Failed to parse JSON after {max_retries} attempts for '{title}'")
            except Exception as e:
                logger.error(f"Error analyzing article '{title}', content resp: {content_resp}, (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                     break
        
        # Fallback if all retries fail
        return {
            "score": 0,
            "summary": "AI 分析失败 (多次重试后)",
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
