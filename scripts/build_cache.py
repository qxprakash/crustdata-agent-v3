import os
import sys
import hashlib
from pathlib import Path
import json

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from utils.notion_loader import NotionLoader
from utils.constants import DEFAULT_RAG_URLS


def build_cache():
    # Create cache directories
    data_dir = Path("data")
    content_dir = data_dir / "content"
    metadata_dir = data_dir / "metadata"

    for directory in [data_dir, content_dir, metadata_dir]:
        directory.mkdir(exist_ok=True)

    # Process each default URL
    for url_data in DEFAULT_RAG_URLS:
        url = url_data["url"]
        print(f"Processing {url}")

        try:
            # First try loading from URL
            loader = NotionLoader(url, cache_enabled=False)
            docs = loader.load()

            if not docs and "fallback_file" in url_data:
                # If URL fails, use fallback file
                with open(url_data["fallback_file"], "r") as f:
                    content = f.read()
                    docs = [
                        Document(
                            page_content=content,
                            metadata={"source": url, "title": url.split("/")[-1]},
                        )
                    ]

            if docs:
                # Generate cache key
                cache_key = hashlib.sha256(url.encode()).hexdigest()

                # Save content - properly access Document attributes
                content_path = content_dir / f"{cache_key}.txt"
                with open(content_path, "w", encoding="utf-8") as f:
                    f.write(docs[0].page_content)  # Use page_content attribute

                # Save metadata
                metadata_path = metadata_dir / f"{cache_key}.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(docs[0].metadata, f)  # Use metadata attribute

                print(f"Cached {url}")

        except Exception as e:
            print(f"Error processing {url}: {e}")


if __name__ == "__main__":
    build_cache()
