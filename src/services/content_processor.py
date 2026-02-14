import re
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from src.util.logger import logger

class ContentProcessor:
    @staticmethod
    def html_to_md(html_content: str) -> str:
        """
        Convert HTML to Markdown, removing images.
        """
        if not html_content:
            return ""

        # First use BeautifulSoup to remove images/figures entirely if we want to be sure
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove images
        for img in soup.find_all('img'):
            img.decompose()
            
        # Remove figures
        for figure in soup.find_all('figure'):
            figure.decompose()

        clean_html = str(soup)

        if md:
            # Convert to markdown
            markdown_text = md(clean_html, heading_style="ATX")
        else:
            # Fallback to simple text extraction if markdownify not installed
            logger.warning("markdownify not installed, falling back to simple text extraction")
            markdown_text = soup.get_text(separator="\n\n")

        # Basic cleanup of excessive newlines
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text).strip()
        
        return markdown_text

content_processor = ContentProcessor()
