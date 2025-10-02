from pathlib import Path

from playwright.async_api import (
    FloatRect,
    Locator,
    Page,
)

from viral_marketing_reporter.infrastructure.exceptions import (
    ScreenshotTargetMissingError,
)


class NaverBlogSearchPage:
    """네이버 블로그 검색 결과 페이지에 대한 상호작용을 캡슐화합니다."""

    def __init__(self, page: Page):
        self.page: Page = page
        self.main_pack_container: Locator = page.locator("#main_pack")
        self.post_items: Locator = self.page.locator("[data-template-id='ugcItem']")
        self.blog_tab_button: Locator = page.get_by_role("tab", name="블로그")

    async def goto(self, keyword: str) -> None:
        """주어진 키워드로 검색 결과 페이지로 이동합니다."""
        search_url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={keyword}"
        await self.page.goto(search_url)

    async def is_result_empty(self) -> bool:
        """검색 결과가 없는지 확인합니다."""
        no_results_locator = self.page.get_by_text(r"에 대한 검색결과가 없습니다")
        return await no_results_locator.is_visible()

    async def get_top_10_posts(self) -> list[Locator]:
        """상위 10개의 포스트 요소를 가져옵니다."""
        return (await self.post_items.all())[:10]

    async def highlight_element(self, element: Locator) -> None:
        """주어진 요소에 빨간색 테두리를 적용합니다."""
        await element.evaluate('(element) => (element.style.outline = "3px solid red")')

    async def take_screenshot_of_results(
        self, index: int, keyword: str, output_dir: Path
    ) -> Path:
        """페이지 상단부터 마지막 포스트까지의 영역을 스크린샷으로 찍고 파일 경로를 반환합니다."""
        top_10_posts = await self.get_top_10_posts()
        if not top_10_posts:
            raise ScreenshotTargetMissingError("상위 10개의 포스트를 찾지 못했습니다.")

        last_post = top_10_posts[-1]

        await last_post.scroll_into_view_if_needed()
        await self.page.wait_for_load_state("load", timeout=60 * 1000)
        await self.page.evaluate("window.scrollTo(0, 0)")

        main_pack_box = await self.main_pack_container.bounding_box()
        if not main_pack_box:
            raise ScreenshotTargetMissingError(
                "메인 컨테이너(#main_pack)의 위치를 찾을 수 없어 스크린샷 영역을 계산할 수 없습니다."
            )

        last_post_box = await last_post.bounding_box()
        if not last_post_box:
            raise ScreenshotTargetMissingError(
                "마지막 포스트의 위치를 찾을 수 없어 스크린샷 영역을 계산할 수 없습니다."
            )

        SCREENSHOT_HEIGHT_MARGIN = 20
        require_height = (
            last_post_box["y"] + last_post_box["height"] + SCREENSHOT_HEIGHT_MARGIN
        )

        # screenshot이 viewport 크기만큼만 찍히기 때문에 viewport를 필요한 만큼 일시적으로 늘려줘야 함
        original_viewport = self.page.viewport_size
        if original_viewport and original_viewport["height"] < require_height:
            await self.page.set_viewport_size(
                {"width": original_viewport["width"], "height": int(require_height)}
            )

        clip: FloatRect = {
            "x": main_pack_box["x"],
            "y": 0,
            "width": main_pack_box["width"],
            "height": require_height,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{index}_{keyword.replace(' ', '_')}.png"
        screenshot_path = output_dir / file_name

        await self.page.screenshot(path=screenshot_path, clip=clip)

        if original_viewport:
            await self.page.set_viewport_size(original_viewport)

        return screenshot_path
