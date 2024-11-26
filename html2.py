import os
import re
import click
import datetime
from src.utils import printc
from lib_resume_builder_AIHawk.utils import HTML_to_PDF
import requests
from urllib.request import urlopen
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from src.utils import chromeBrowserOptions


url = 'https://www.metacareers.com/jobs/3489873754638185/'


def init_browser(options = None) -> webdriver.Chrome:
    try:
        if options is None:
            options = chromeBrowserOptions()
        mgr = ChromeDriverManager().install()
        service = ChromeService(mgr)
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")

# Open the URL and read the content
# with urlopen(url) as response:
#     content = re.sub(r'<[^>]+>', '', response.read().decode('utf-8'))
#     print(content)  # Decode bytes to string
#

# response = requests.get(url)
# if response.status_code==200:
#     print(response.text)
def wait_for_page_load(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
    except TimeoutException:
        print("Page load timed out.")

with init_browser() as browser:
    browser.get(url)
    wait_for_page_load(browser)

    body = browser.find_element(By.TAG_NAME, "body")
    print(body.text)
    print('10')

