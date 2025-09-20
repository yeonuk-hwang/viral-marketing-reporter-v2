from types import TracebackType

from playwright.async_api import Browser, Page, Playwright, async_playwright


class SearchExecutionContext:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._pages: list[Page] = []

    async def __aenter__(self) -> "SearchExecutionContext":
        self._playwright = await async_playwright().start()
        self.browser = (
            await self._playwright.chromium.launch()
        )  # GUI 확인을 위해 headless=False로 설정
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
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
            raise RuntimeError("Context is not running.")
        page = await self.browser.new_page(viewport={"width": 1920, "height": 1080})
        self._pages.append(page)
        return page
