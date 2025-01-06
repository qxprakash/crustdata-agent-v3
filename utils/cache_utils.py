import os
import json
import hashlib
from pathlib import Path
import streamlit as st
from datetime import datetime, timezone
from typing import Dict, List, Optional


class DocumentCache:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Create subdirectories
        self.content_dir = self.cache_dir / "content"
        self.metadata_dir = self.cache_dir / "metadata"
        self.content_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)

    def _generate_cache_key(self, url: str) -> str:
        """Generate a unique cache key for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def _get_metadata_path(self, cache_key: str) -> Path:
        return self.metadata_dir / f"{cache_key}.json"

    def _get_content_path(self, cache_key: str) -> Path:
        return self.content_dir / f"{cache_key}.txt"

    def save_document(self, url: str, content: str, metadata: Dict) -> None:
        """Save document content and metadata to cache."""
        cache_key = self._generate_cache_key(url)

        # Save content
        content_path = self._get_content_path(cache_key)
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Save metadata with timestamp
        metadata_path = self._get_metadata_path(cache_key)
        metadata_with_timestamp = {
            **metadata,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata_with_timestamp, f)

    def get_document(self, url: str) -> Optional[Dict]:
        """Retrieve document from cache if it exists."""
        cache_key = self._generate_cache_key(url)
        content_path = self._get_content_path(cache_key)
        metadata_path = self._get_metadata_path(cache_key)

        if content_path.exists() and metadata_path.exists():
            try:
                with open(content_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                return {"content": content, "metadata": metadata}
            except Exception as e:
                st.error(f"Error reading from cache: {e}")
                return None
        return None

    def is_cached(self, url: str) -> bool:
        """Check if a URL is cached."""
        cache_key = self._generate_cache_key(url)
        return (
            self._get_content_path(cache_key).exists()
            and self._get_metadata_path(cache_key).exists()
        )
