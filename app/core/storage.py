import os
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
import shutil
from datetime import datetime

from .config import settings


class StorageManager:
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, file: UploadFile, analysis_id: str) -> str:
        """Save uploaded file and return path."""
        file_ext = Path(file.filename).suffix
        filename = f"{analysis_id}{file_ext}"
        filepath = self.upload_dir / filename

        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        return str(filepath)

    def delete_file(self, filepath: str) -> bool:
        """Delete a file safely."""
        try:
            path = Path(filepath)
            if path.exists() and path.parent == self.upload_dir:
                path.unlink()
                return True
        except Exception:
            pass
        return False

    def cleanup_old_files(self, hours: int = 24) -> int:
        """Delete files older than specified hours."""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        deleted = 0

        for file in self.upload_dir.glob("*"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff_time:
                    file.unlink()
                    deleted += 1

        return deleted


storage_manager = StorageManager()
