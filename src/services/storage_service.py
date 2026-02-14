import os
import re
from datetime import datetime
from src.constant.config import settings
from src.util.logger import logger

class StorageService:
    def __init__(self):
        # Resolve absolute path relative to project root
        current_dir = os.path.dirname(os.path.abspath(__file__)) # src/services
        project_root = os.path.dirname(os.path.dirname(current_dir)) # src/ -> root
        
        self.base_dir = settings.STORAGE_DIR
        if not os.path.isabs(self.base_dir):
            self.base_dir = os.path.join(project_root, self.base_dir)
            
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create storage directory {self.base_dir}: {e}")

    def _sanitize_filename(self, name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

    def save_md(self, subscription_name: str, date_str: str, title: str, content: str):
        """
        Alias for save_markdown(..., is_summary=False)
        """
        return self.save_markdown(subscription_name, date_str, title, content, is_summary=False)

    def save_markdown(self, subscription_name: str, date_str: str, title: str, content: str, is_summary: bool = False):
        """
        Save markdown content to file.
        Structure: base_dir/{subscription_name}/{date_str}/{title}.md
        """
        safe_sub_name = self._sanitize_filename(subscription_name)
        safe_title = self._sanitize_filename(title)
        
        # Use safe_sub_name which comes from RSS feed title, and date
        folder_path = os.path.join(self.base_dir, safe_sub_name, date_str)
        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {folder_path}: {e}")
            return None
        
        filename = f"{safe_title}_summary.md" if is_summary else f"{safe_title}.md"
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Saved file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file {file_path}: {e}")
            return None

    def save_html(self, subscription_name: str, date_str: str, title: str, content: str):
        """
        Save HTML content to file.
        Structure: base_dir/{subscription_name}/{date_str}/{title}.html
        """
        safe_sub_name = self._sanitize_filename(subscription_name)
        safe_title = self._sanitize_filename(title)
        
        folder_path = os.path.join(self.base_dir, safe_sub_name, date_str)
        os.makedirs(folder_path, exist_ok=True)
        
        filename = f"{safe_title}.html"
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Saved HTML file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save HTML file {file_path}: {e}")
            return None
            
    def cleanup_old_files(self, days: int = 30):
        """
        Delete files older than `days`.
        Walks through base_dir.
        """
        logger.info(f"Starting cleanup of files older than {days} days...")
        now = datetime.now()
        count = 0
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if (now - file_mtime).days > days:
                        os.remove(file_path)
                        count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                except Exception as e:
                    logger.error(f"Error checking/deleting file {file_path}: {e}")
        
        # Remove empty directories
        for root, dirs, files in os.walk(self.base_dir, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.debug(f"Removed empty directory: {dir_path}")
                except OSError:
                    pass
                    
        logger.info(f"Cleanup completed. Deleted {count} files.")


storage_service = StorageService()
