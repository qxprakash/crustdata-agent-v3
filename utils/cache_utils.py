import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Optional


class DocumentCache:
    def __init__(self):
        self.data_dir = Path("data")
        self.content_dir = self.data_dir / "content"
        self.metadata_dir = self.data_dir / "metadata"

    def _generate_cache_key(self, url: str) -> str:
        """Generate a unique cache key for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def get_document(self, url: str) -> Optional[Dict]:
        """Retrieve document from pre-built cache."""
        cache_key = self._generate_cache_key(url)
        content_path = self.content_dir / f"{cache_key}.txt"
        metadata_path = self.metadata_dir / f"{cache_key}.json"

        if content_path.exists() and metadata_path.exists():
            try:
                with open(content_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                return {"content": content, "metadata": metadata}
            except Exception as e:
                print(f"Error reading from cache: {e}")
                return None
        return None

    def is_cached(self, url: str) -> bool:
        """Check if a URL is in the pre-built cache."""
        cache_key = self._generate_cache_key(url)
        return (self.content_dir / f"{cache_key}.txt").exists() and (
            self.metadata_dir / f"{cache_key}.json"
        ).exists()
