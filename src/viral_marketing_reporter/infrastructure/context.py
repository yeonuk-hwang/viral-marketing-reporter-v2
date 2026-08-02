from __future__ import annotations

import sys
from os import environ
from pathlib import Path
from shutil import which
from types import TracebackType
from typing import Any, Type

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from viral_marketing_reporter.domain.model import Platform


class ChromeNotInstalledError(RuntimeError):
    """Google Chrome이 설치되어 있지 않을 때 발생합니다."""


def find_google_chrome() -> str | None:
    """H.264 등 시스템 미디어 코덱을 지원하는 Google Chrome을 찾습니다."""
    configured_path = environ.get("VIRAL_REPORTER_BROWSER_PATH")
    if configured_path and Path(configured_path).is_file():
        return configured_path

    # Chrome은 Windows에서 보통 PATH에 등록되지 않으므로 기본 설치 경로도 확인합니다.
    for executable in ("google-chrome-stable", "google-chrome", "chrome"):
        if browser_path := which(executable):
            return browser_path

    windows_roots = [
        environ.get("LOCALAPPDATA"),
        environ.get("PROGRAMFILES"),
        environ.get("PROGRAMFILES(X86)"),
    ]
    for root in filter(None, windows_roots):
        chrome_path = Path(root) / "Google/Chrome/Application/chrome.exe"
        if chrome_path.is_file():
            return str(chrome_path)

    return None


def require_google_chrome() -> str:
    """설치된 Chrome 경로를 반환하고, 없으면 사용자용 설치 안내 오류를 발생시킵니다."""
    if browser_path := find_google_chrome():
        return browser_path
    raise ChromeNotInstalledError(
        "Instagram 영상 캡처에는 Google Chrome이 필요합니다. "
        "Chrome을 설치한 뒤 프로그램을 다시 실행해주세요: "
        "https://www.google.com/chrome/"
    )


class ApplicationContext:
    """애플리케이션의 브라우저 리소스를 관리합니다."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None

    async def __aenter__(self) -> ApplicationContext:
        self._playwright = await async_playwright().start()
        # headless 모드로 실행 (자동화 감지 우회)
        launch_options: dict[str, Any] = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        launch_options["executable_path"] = require_google_chrome()

        self.browser = await self._playwright.chromium.launch(
            **launch_options,
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
