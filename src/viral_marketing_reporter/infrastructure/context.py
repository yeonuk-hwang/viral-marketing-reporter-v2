
from __future__ import annotations

from types import TracebackType
from typing import Type

from playwright.async_api import Browser, Page, Playwright, async_playwright


class ApplicationContext:
    """애플리케이션의 브라우저 리소스를 관리합니다."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._pages: list[Page] = []

    async def __aenter__(self) -> ApplicationContext:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=False)
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        for page in self._pages:
            await page.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self.browser:
            raise RuntimeError("Browser context is not running.")
        page = await self.browser.new_page(viewport={"width": 1920, "height": 1080})
        self._pages.append(page)
        return page
