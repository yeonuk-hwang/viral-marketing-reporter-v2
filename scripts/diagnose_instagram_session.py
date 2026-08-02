"""저장된 Instagram 세션이 headless Chrome에서 유효하게 판정되는지 확인합니다."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from viral_marketing_reporter.infrastructure.context import require_google_chrome
from viral_marketing_reporter.infrastructure.platforms.instagram.auth_service import (
    InstagramAuthService,
)


SESSION_PATH = Path.home() / "Downloads/viral-reporter/instagram_session.json"


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=require_google_chrome(),
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
            storage_state=str(SESSION_PATH),
        )
        service = InstagramAuthService(browser=browser, storage_path=SESSION_PATH)
        valid = await service._is_session_valid(context)
        print(f"saved_session_valid={valid}")
        await context.close()
        await browser.close()

    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
