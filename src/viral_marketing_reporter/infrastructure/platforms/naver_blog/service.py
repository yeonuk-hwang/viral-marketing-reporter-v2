from pathlib import Path
from typing import Final, override

import httpx
from playwright.async_api import Page

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
        async with httpx.AsyncClient() as client:
            for post_element in top_10_posts:
                post_urls_to_check: set[str] = set()
                all_links = await post_element.locator("a").all()

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
                        except httpx.RequestError:
                            pass
                    else:
                        post_urls_to_check.add(href)

                for post_to_find in posts_to_find:
                    if post_to_find.url in post_urls_to_check:
                        found_posts_in_top10.append(post_to_find)
                        await search_page.highlight_post(post_element)
                        break

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

