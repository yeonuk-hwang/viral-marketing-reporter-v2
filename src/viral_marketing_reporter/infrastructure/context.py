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

    async def __aenter__(self) -> ApplicationContext:
        self._playwright = await async_playwright().start()
        # headless 모드로 실행 (자동화 감지 우회)
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
