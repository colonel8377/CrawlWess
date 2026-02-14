import re
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from src.util.logger import logger

class ContentProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text content by removing specific patterns like image URLs and placeholders.
        """
        if not text:
            return ""

        # 1. Remove WeChat specific image placeholders: ! `url`
        text = re.sub(r'!\s*`http[^`]+`', '', text)
        
        # 2. Remove user specified pattern: ![图片] (https://网址)
        # Matches ![...](http...)
        text = re.sub(r'!\[.*?\]\s*\(https?://[^)]+\)', '', text)
        
        # 3. Remove [图片] placeholders
        text = text.replace("[图片]", "")

        # 4. Remove ALL URLs (as requested: "url你都要抓出来去掉")
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'http?://\S+', '', text)

        # 5. Remove empty lines and excessive whitespace
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            lines.append(line)
        
        cleaned_text = '\n\n'.join(lines)
        
        return cleaned_text

    @staticmethod
    def html_to_md(html_content: str) -> str:
        """
        Convert HTML to Markdown, removing images, links, and cleaning up format.
        Strict cleaning.
        """
        if not html_content:
            return ""

        # 1. BeautifulSoup Cleaning
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove generally unwanted tags
        for tag in soup(["script", "style", "iframe", "object", "embed", "param", "meta", "link", "noscript"]):
            tag.decompose()

        # Remove visual elements
        for tag in soup(["img", "figure", "picture", "canvas", "svg", "video", "audio", "source", "track"]):
            tag.decompose()
            
        # Remove structural clutter / ads / sidebars (Heuristic)
        # Remove elements with class/id containing specific keywords
        unwanted_keywords = ['ad', 'advertisement', 'banner', 'footer', 'sidebar', 'nav', 'menu', 'related', 'social', 'share']
        for tag in soup.find_all(True):
            # Check class
            if tag.get('class'):
                classes = tag.get('class')
                if isinstance(classes, list):
                    classes = ' '.join(classes)
                if any(keyword in classes.lower() for keyword in unwanted_keywords):
                    tag.decompose()
                    continue
            
            # Check ID
            if tag.get('id'):
                id_val = tag.get('id')
                if any(keyword in id_val.lower() for keyword in unwanted_keywords):
                    tag.decompose()
                    continue

        # Unwrap links (keep text, remove <a> tag)
        for a in soup.find_all('a'):
            a.replace_with(a.get_text())

        clean_html = str(soup)

        # 2. Convert to Markdown
        if md:
            # strip all tags that might have been missed or are structural but we just want text
            # keeping h1-h6, p, ul, ol, li, blockquote, pre, code, strong, em
            markdown_text = md(clean_html, heading_style="ATX", strip=['img', 'a', 'div', 'span'])
        else:
            logger.warning("markdownify not installed, falling back to simple text extraction")
            markdown_text = soup.get_text(separator="\n\n")

        # 3. Post-processing Cleanup
        return ContentProcessor.clean_text(markdown_text)

content_processor = ContentProcessor()
