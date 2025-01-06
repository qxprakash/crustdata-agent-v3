from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
import time


class NotionLoader(BaseLoader):
    def __init__(self, url: str):
        self.url = url

    def _expand_toggle_blocks(self, driver):
        """Expands all toggle blocks in the page."""
        toggle_blocks = driver.find_elements(By.CLASS_NAME, "notion-toggle-block")
        print(f"Found {len(toggle_blocks)} toggle blocks")

        for toggle in toggle_blocks:
            try:
                # Find the button within the toggle block
                button = toggle.find_element(By.CSS_SELECTOR, "[role='button']")

                # Check if the toggle is already expanded
                aria_expanded = button.get_attribute("aria-expanded")
                if aria_expanded != "true":
                    # Scroll the toggle into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", toggle)
                    time.sleep(0.5)  # Wait for scroll to complete

                    # Click to expand
                    ActionChains(driver).move_to_element(button).click().perform()
                    time.sleep(0.2)  # Wait for expansion animation

                    print("Expanded a toggle block")
            except Exception as e:
                print(f"Error expanding toggle block: {e}")

    def _extract_content(self, driver):
        """Extracts content from the page after expanding toggles."""
        try:
            main_content = driver.find_element(By.CLASS_NAME, "notion-page-content")

            # First expand all toggle blocks
            self._expand_toggle_blocks(driver)

            # Wait a bit for all expansions to complete
            time.sleep(2)

            # Get the text content
            text = main_content.text

            # Log content statistics
            print(f"Extracted content length: {len(text)} characters")
            print(f"Content preview: {text[:200]}...")

            return text

        except Exception as e:
            print(f"Error extracting content: {e}")
            return ""

    def load(self) -> List[Document]:
        driver = None
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")

            driver = webdriver.Chrome(options=chrome_options)
            print(f"\nLoading Notion page: {self.url}")

            driver.get(self.url)

            # Wait for the main content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "notion-page-content"))
            )

            # Extract content with expanded toggles
            text = self._extract_content(driver)

            metadata = {
                "source": self.url,
                "title": driver.title,
            }

            return [Document(page_content=text, metadata=metadata)]

        except Exception as e:
            print(f"Error loading Notion page: {e}")
            return []

        finally:
            if driver:
                driver.quit()
