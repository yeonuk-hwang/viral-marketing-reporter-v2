from __future__ import annotations

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


class ApplicationContext:
    """애플리케이션의 브라우저 리소스를 관리합니다."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._pages: list[Page] = []

    async def __aenter__(self) -> ApplicationContext:
        data_dir = Path.home() / "Downloads" / "viral-reporter" / "chrome_profile"
        data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=data_dir,
            channel="chrome",
            headless=False,
            viewport={"width": 1920, "height": 1080},
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
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Browser context is not running.")
        page = await self._context.new_page()
        self._pages.append(page)
        return page
