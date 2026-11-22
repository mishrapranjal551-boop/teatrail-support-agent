"""Visits Tara's live page like a real visitor, so Streamlit Cloud doesn't put it to sleep.

If the app is already asleep, it clicks Streamlit's wake-up button and waits for it to start.
Run by .github/workflows/keep-awake.yml every 6 hours. Uses no Gemini requests:
it only opens the page, it never sends a chat message.
"""

import re
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://teatrail-tara.streamlit.app"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(15_000)  # give the sleep screen or the app time to appear

    wake = page.get_by_role("button", name=re.compile("get this app back up", re.I))
    if wake.count():
        print("Tara was asleep: clicking the wake-up button.")
        wake.first.click()
        page.wait_for_timeout(90_000)  # waking takes about a minute
        print("Wake-up requested.")
    else:
        print("Tara is awake. Visit counted.")
    browser.close()
