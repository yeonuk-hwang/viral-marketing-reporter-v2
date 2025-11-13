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

from viral_marketing_reporter.domain.model import Platform


class ApplicationContext:
    """애플리케이션의 브라우저 리소스를 관리합니다."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._default_context: BrowserContext | None = None  # 기본 플랫폼용 (네이버 등)
        self._pages: list[Page] = []

    async def __aenter__(self) -> ApplicationContext:
        self._playwright = await async_playwright().start()
        # headless 모드로 실행 (Instagram은 AuthManager가 별도 관리)
        self.browser = await self._playwright.chromium.launch(headless=True)

        # 기본 컨텍스트: 네이버 블로그 등 기존 플랫폼용 (1920px)
        self._default_context = await self.browser.new_context(
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

        if self._default_context:
            await self._default_context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        """기본 브라우저 컨텍스트에서 새 페이지를 생성합니다.

        Note: Instagram은 PlatformServiceFactory에서 AuthManager를 통해 별도 처리됩니다.
        """
        if not self.browser or not self._default_context:
            raise RuntimeError("Browser context is not running.")

        page = await self._default_context.new_page()
        self._pages.append(page)
        return page
