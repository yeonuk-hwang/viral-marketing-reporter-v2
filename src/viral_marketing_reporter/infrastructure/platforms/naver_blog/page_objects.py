from pathlib import Path

from playwright.async_api import (
    Locator,
    Page,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)


class NaverBlogSearchPage:
    """네이버 블로그 검색 결과 페이지에 대한 상호작용을 캡슐화합니다."""

    def __init__(self, page: Page):
        self.page: Page = page
        self.post_container: Locator = page.locator(
            ".sds-comps-vertical-layout.sds-comps-full-layout.fds-ugc-single-intention-item-list-tab"
        )
        self.post_items: Locator = self.post_container.locator(
            "[data-template-id='ugcItem']"
        )

    async def goto(self, keyword: str) -> None:
        """주어진 키워드로 검색 결과 페이지로 이동합니다."""
        search_url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={keyword}"
        await self.page.goto(search_url, wait_until="domcontentloaded")

    async def is_result_container_visible(self) -> bool:
        """검색 결과 컨테이너가 보이는지 확인합니다."""
        try:
            await self.post_container.wait_for(state="visible")
            return True
        except PlaywrightTimeoutError:
            return False

    async def get_top_10_posts(self) -> list[Locator]:
        """상위 10개의 포스트 요소를 가져옵니다."""
        return (await self.post_items.all())[:10]

    async def highlight_post(self, post_element: Locator) -> None:
        """주어진 포스트 요소에 빨간색 테두리를 적용합니다."""
        await post_element.evaluate(
            '(element) => (element.style.outline = "3px solid red")'
        )

    async def take_screenshot_of_container(
        self, keyword: str, output_dir: Path
    ) -> Path:
        """결과 컨테이너의 스크린샷을 찍고 파일 경로를 반환합니다."""
        all_posts = await self.get_top_10_posts()
        if all_posts:
            for post in all_posts:
                await post.scroll_into_view_if_needed()
            await self.page.wait_for_load_state("networkidle")

        output_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{keyword.replace(' ', '_')}.png"
        screenshot_path = output_dir / file_name
        await self.post_container.screenshot(path=screenshot_path)
        return screenshot_path
