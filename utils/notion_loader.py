from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
import time


class NotionLoader(BaseLoader):
    def __init__(self, url: str):
        self.url = url

    def load(self) -> List[Document]:
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            driver = webdriver.Chrome(options=chrome_options)
            print(f"\nLoading Notion page: {self.url}")

            driver.get(self.url)
            # Wait for the content to load (adjust timeout as needed)
            time.sleep(5)  # Give JavaScript time to render

            # Wait for specific Notion content elements
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "notion-page-content"))
            )

            # Get the main content
            content = driver.find_element(By.CLASS_NAME, "notion-page-content")
            text = content.text

            print(f"Extracted content length: {len(text)} characters")
            print(f"Content preview: {text[:200]}...")

            metadata = {
                "source": self.url,
                "title": driver.title,
            }

            driver.quit()

            return [Document(page_content=text, metadata=metadata)]

        except Exception as e:
            print(f"Error loading Notion page: {e}")
            return []
