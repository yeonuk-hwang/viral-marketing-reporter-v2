from pathlib import Path
from typing import Final, override

import httpx
from loguru import logger
from playwright.async_api import Locator, Page

from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    Screenshot,
    SearchResult,
)
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService

from .page_objects import NaverBlogSearchPage


class PlaywrightNaverBlogService(SearchPlatformService):
    AD_HELP_URL: Final = (
        "https://help.naver.com/alias/search/integration_m/integration_m68"
    )
    page: Page

    def __init__(self, page: Page) -> None:
        self.page = page

    async def _resolve_post_urls(self, post_element: Locator) -> set[str]:
        """하나의 포스트 요소 내 모든 링크를 실제 URL로 변환하여 집합으로 반환합니다."""
        post_urls_to_check: set[str] = set()
        all_links = await post_element.locator("a").all()

        async with httpx.AsyncClient() as client:
            for link in all_links:
                href = await link.get_attribute("href")
                if not href:
                    continue

                if "ader.naver.com" in href:
                    try:
                        response = await client.get(
                            href, follow_redirects=False, timeout=3
                        )
                        if (
                            response.status_code == 307
                            and "Location" in response.headers
                        ):
                            post_urls_to_check.add(response.headers["Location"])
                    except httpx.RequestError as e:
                        logger.warning(
                            f"광고 URL 리다이렉트 확인 중 에러 발생: {href}, 오류: {e}"
                        )

                else:
                    post_urls_to_check.add(href)
        return post_urls_to_check

    @override
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post], output_dir: Path
    ) -> SearchResult:
        search_page = NaverBlogSearchPage(self.page)
        await search_page.goto(keyword.text)

        if not await search_page.is_result_container_visible():
            return SearchResult(found_posts=[], screenshot=None)

        top_10_posts = await search_page.get_top_10_posts()

        found_posts_in_top10: list[Post] = []
        for post_element in top_10_posts:
            resolved_urls = await self._resolve_post_urls(post_element)
            for post_to_find in posts_to_find:
                if post_to_find.url in resolved_urls:
                    found_posts_in_top10.append(post_to_find)
                    await search_page.highlight_post(post_element)
                    break  # 다음 post_element로 넘어감

        screenshot_path = None
        if found_posts_in_top10:
            screenshot_path = await search_page.take_screenshot_of_container(
                keyword.text, output_dir
            )

        return SearchResult(
            found_posts=found_posts_in_top10,
            screenshot=Screenshot(file_path=screenshot_path)
            if screenshot_path
            else None,
        )

