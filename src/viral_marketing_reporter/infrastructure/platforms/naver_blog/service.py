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
from viral_marketing_reporter.infrastructure.logging_utils import (
    log_function_call,
    log_step,
    log_with_context,
    PerformanceTracker,
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
        """
        하나의 포스트 요소 내 모든 링크를 실제 URL로 변환하고,
        유효한 블로그 포스트 URL 중 가장 빈번하게 나타나는 URL 하나만 집합으로 반환합니다.
        """
        import re
        from collections import Counter

        post_urls_to_check: list[str] = []
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
                            post_urls_to_check.append(response.headers["Location"])
                    except httpx.RequestError as e:
                        logger.warning(
                            "광고 URL 리다이렉트 실패",
                            event_name="ad_redirect_failed",
                            url=href,
                            error=str(e),
                        )
                else:
                    post_urls_to_check.append(href)

        if not post_urls_to_check:
            return set()

        # 네이버 블로그 게시물 URL 패턴과 일치하는 것만 필터링합니다.
        blog_post_pattern = re.compile(r"^https://(?:m\.)?blog\.naver\.com/[^/]+/\d+$")

        valid_blog_urls = [
            url for url in post_urls_to_check if blog_post_pattern.match(url)
        ]

        if not valid_blog_urls:
            return set()

        # 가장 빈번하게 등장하는 URL을 찾아 반환합니다.
        url_counts = Counter(valid_blog_urls)
        most_common_url = url_counts.most_common(1)[0][0]
        return {most_common_url}

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
    @log_with_context(platform="naver_blog")
    async def search_and_find_posts(
        self, index: int, keyword: Keyword, posts_to_find: list[Post], output_dir: Path
    ) -> SearchResult:
        from playwright.async_api import TimeoutError

        tracker = PerformanceTracker(f"naver_blog_search_{keyword.text}")
        tracker.start()

        with log_step(
            "네이버 블로그 검색 및 포스트 매칭",
            keyword=keyword.text,
            index=index,
            posts_to_find_count=len(posts_to_find),
        ):
            try:
                search_page = NaverBlogSearchPage(self.page)
                logger.info(
                    "네이버 블로그 검색 페이지로 이동",
                    keyword=keyword.text,
                    event_name="navigate_to_search",
                )
                await search_page.goto(keyword.text)
                tracker.checkpoint("page_loaded")

                if await search_page.is_result_empty():
                    logger.info(
                        "검색 결과 없음",
                        keyword=keyword.text,
                        event_name="result_not_found",
                    )
                    tracker.end()
                    return SearchResult(found_posts=[], screenshot=None)

                top_10_posts = await search_page.get_top_10_posts()
                tracker.checkpoint("top_10_posts_retrieved")
                logger.debug(
                    f"상위 포스트 {len(top_10_posts)}개 발견",
                    keyword=keyword.text,
                    post_count=len(top_10_posts),
                    event_name="posts_retrieved",
                )

                if not top_10_posts:
                    logger.error(
                        "포스트 요소를 찾을 수 없음",
                        keyword=keyword.text,
                        event_name="posts_not_found",
                    )
                    logger.error(await search_page.page.content())
                    await search_page.page.screenshot(
                        path=(output_dir / f"{keyword.text}_error.png")
                    )
                    tracker.end()
                    return SearchResult(found_posts=[], screenshot=None)

                logger.debug(
                    "포스트 매칭 시작",
                    keyword=keyword.text,
                    event_name="matching_start",
                )
                tasks = [
                    self._get_matching_post_if_found(post_element, posts_to_find)
                    for post_element in top_10_posts
                ]
                matching_results = await asyncio.gather(*tasks)
                tracker.checkpoint("posts_matched")

                found_posts_in_top10: list[Post] = [
                    post for post in matching_results if post
                ]
                elements_to_highlight: list[Locator] = [
                    top_10_posts[i] for i, post in enumerate(matching_results) if post
                ]

                logger.info(
                    "포스트 매칭 완료",
                    keyword=keyword.text,
                    found_count=len(found_posts_in_top10),
                    target_count=len(posts_to_find),
                    event_name="matching_completed",
                )

                screenshot_path = None
                if found_posts_in_top10:
                    logger.debug(
                        "매칭된 포스트 하이라이트 적용",
                        keyword=keyword.text,
                        highlight_count=len(elements_to_highlight),
                        event_name="highlight_start",
                    )
                    highlight_tasks = [
                        search_page.highlight_element(element)
                        for element in elements_to_highlight
                    ]
                    highlight_tasks.append(
                        search_page.highlight_element(search_page.blog_tab_button)
                    )
                    await asyncio.gather(*highlight_tasks)
                    tracker.checkpoint("posts_highlighted")

                    logger.debug(
                        "스크린샷 촬영 시작",
                        keyword=keyword.text,
                        event_name="screenshot_start",
                    )
                    screenshot_path = await search_page.take_screenshot_of_results(
                        index, keyword.text, output_dir
                    )
                    tracker.checkpoint("screenshot_taken")
                    logger.info(
                        "스크린샷 촬영 완료",
                        keyword=keyword.text,
                        screenshot_path=str(screenshot_path),
                        event_name="screenshot_completed",
                    )
                else:
                    logger.info(
                        "매칭된 포스트 없음 - 스크린샷 생략",
                        keyword=keyword.text,
                        event_name="no_matches_no_screenshot",
                    )

                tracker.end()
                return SearchResult(
                    found_posts=found_posts_in_top10,
                    screenshot=Screenshot(file_path=screenshot_path)
                    if screenshot_path
                    else None,
                )
            except TimeoutError as e:
                logger.exception(
                    "페이지 로드 시간 초과",
                    keyword=keyword.text,
                    error=str(e),
                    error_type=e.__class__.__name__,
                    event_name="page_load_timeout",
                )
                tracker.end()
                raise e
            finally:
                logger.debug(
                    "네이버 블로그 페이지 정리",
                    keyword=keyword.text,
                    event_name="page_cleanup",
                )
                await self.page.close()
