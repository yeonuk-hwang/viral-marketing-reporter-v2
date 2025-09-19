import asyncio
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


class PlaywrightNaverBlogService(SearchPlatformService):
    AD_HELP_URL: Final = (
        "https://help.naver.com/alias/search/integration_m/integration_m68"
    )
    page: Page

    def __init__(self, page: Page) -> None:
        self.page = page

    @override
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post]
    ) -> SearchResult:
        search_url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={keyword.text}"
        await self.page.goto(search_url, wait_until="domcontentloaded")

        container = self.page.locator(
            ".sds-comps-vertical-layout.sds-comps-full-layout.fds-ugc-single-intention-item-list-tab"
        )
        if not await container.is_visible():
            return SearchResult(found_posts=[], screenshot=None)

        top_10_posts = (await container.locator("[data-template-id='ugcItem']").all())[
            :10
        ]

        found_posts_in_top10: list[Post] = []
        async with httpx.AsyncClient() as client:
            for post_element in top_10_posts:
                post_urls_to_check: set[str] = set()
                all_links = await post_element.locator("a").all()

                for link in all_links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    # 광고 리다이렉트 URL 처리
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
                        await post_element.evaluate(
                            '(element) => (element.style.outline = "3px solid red")'
                        )
                        break

        screenshot_path = None
        if found_posts_in_top10:
            for post_element in top_10_posts:
                await post_element.scroll_into_view_if_needed()
                await asyncio.sleep(0.1)
            await self.page.wait_for_load_state("networkidle")
            screenshot_path = f"{keyword.text.replace(' ', '_')}.png"
            await container.screenshot(path=screenshot_path)

        return SearchResult(
            found_posts=found_posts_in_top10,
            screenshot=Screenshot(file_path=screenshot_path)
            if screenshot_path
            else None,
        )

