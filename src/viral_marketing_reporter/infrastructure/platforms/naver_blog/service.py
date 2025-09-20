import asyncio
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
from viral_marketing_reporter.infrastructure.platforms.naver_blog.page_objects import (
    NaverBlogSearchPage,
)


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
                            "광고 URL 리다이렉트 실패",
                            event_name="ad_redirect_failed",
                            url=href,
                            error=str(e),
                        )
                else:
                    post_urls_to_check.add(href)
        return post_urls_to_check

    async def _get_matching_post_if_found(
        self, post_element: Locator, posts_to_find: list[Post]
    ) -> Post | None:
        """하나의 포스트 요소에서 찾아야 할 Post 객체가 있는지 확인합니다."""
        resolved_urls = await self._resolve_post_urls(post_element)
        for post_to_find in posts_to_find:
            if post_to_find.url in resolved_urls:
                return post_to_find
        return None

    @override
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post], output_dir: Path
    ) -> SearchResult:
        search_page = NaverBlogSearchPage(self.page)
        await search_page.goto(keyword.text)

        if await search_page.is_result_empty():
            logger.info(
                f"{keyword}에 대한 검색 결과가 없습니다.",
                event_name="result_not_found",
                keyword=keyword,
            )
            return SearchResult(found_posts=[], screenshot=None)

        top_10_posts = await search_page.get_top_10_posts()

        # 각 포스트 요소에 대해 일치하는 Post를 찾는 비동기 작업을 생성합니다.
        tasks = [
            self._get_matching_post_if_found(post_element, posts_to_find)
            for post_element in top_10_posts
        ]
        matching_results = await asyncio.gather(*tasks)

        found_posts_in_top10: list[Post] = []
        elements_to_highlight: list[Locator] = []
        for i, matching_post in enumerate(matching_results):
            if matching_post:
                found_posts_in_top10.append(matching_post)
                elements_to_highlight.append(top_10_posts[i])

        screenshot_path = None
        if found_posts_in_top10:
            highlight_tasks = [
                search_page.highlight_post(element)
                for element in elements_to_highlight
            ]
            await asyncio.gather(*highlight_tasks)

            screenshot_path = await search_page.take_screenshot_of_container(
                keyword.text, output_dir
            )

        return SearchResult(
            found_posts=found_posts_in_top10,
            screenshot=Screenshot(file_path=screenshot_path)
            if screenshot_path
            else None,
        )
