"""Generate the dashboard screenshot used in the README.

Dev-only. Needs the web extras plus Playwright:

    pip install -r requirements-web.txt playwright
    python -m playwright install chromium
    python scripts/screenshots.py

Serves the app on a background thread and screenshots one real search. This
does hit the live job boards (a few seconds).
"""

from __future__ import annotations

import os
import sys
import threading
import time

os.environ.setdefault("REQUEST_DELAY", "0.5")
os.makedirs("docs", exist_ok=True)
sys.path.insert(0, os.getcwd())

from webapp.app import app  # noqa: E402

PORT = 5056
threading.Thread(target=lambda: app.run(port=PORT, use_reloader=False), daemon=True).start()
time.sleep(1.5)

from playwright.sync_api import sync_playwright  # noqa: E402

URL = f"http://127.0.0.1:{PORT}/?keyword=engineer&location=remote&limit=12"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1160, "height": 900}, device_scale_factor=2)
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.screenshot(path="docs/dashboard.png", full_page=True)
    print("wrote docs/dashboard.png")
    browser.close()
