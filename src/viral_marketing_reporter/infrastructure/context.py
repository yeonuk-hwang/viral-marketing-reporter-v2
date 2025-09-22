from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import Type

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .exceptions import ChromeNotFoundException


def get_chrome_executable_path() -> str:
    """
    Finds the path to the Google Chrome executable on the current OS.
    Raises ChromeNotFoundException if Chrome is not found.
    """
    if sys.platform == "darwin":  # macOS
        paths = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    elif sys.platform == "win32":  # Windows
        paths = [
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        ]
    else:
        paths = []

    for path in paths:
        if Path(path).exists():
            return path

    raise ChromeNotFoundException(
        "Google Chrome is not installed in a standard location. "
        "Please install Google Chrome to use this application."
    )


class ApplicationContext:
    """애플리케이션의 브라우저 리소스를 관리합니다."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._pages: list[Page] = []

    async def __aenter__(self) -> ApplicationContext:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch()
        self._context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        for page in self._pages:
            if not page.is_closed():
                await page.close()
        self._pages.clear()

        if self._context:
            await self._context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self.browser or not self._context:
            raise RuntimeError("Browser context is not running.")
        page = await self._context.new_page()
        self._pages.append(page)
        return page
