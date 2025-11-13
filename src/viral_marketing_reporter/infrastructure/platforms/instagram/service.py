import asyncio
import re
from pathlib import Path
from typing import Final, override

from loguru import logger
from playwright.async_api import Locator, Page

from viral_marketing_reporter.domain.model import (
    Keyword,
    Post,
    Screenshot,
    SearchResult,
)
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.instagram.page_objects import (
    InstagramSearchPage,
)


class PlaywrightInstagramService(SearchPlatformService):
    """Instagram 검색 서비스 구현"""

    INSTAGRAM_URL: Final = "https://www.instagram.com/"
    page: Page

    def __init__(self, page: Page) -> None:
        self.page = page

    def _extract_post_id(self, url: str) -> str | None:
        """Instagram 포스트 URL에서 포스트 ID를 추출합니다.

        예시:
        - https://www.instagram.com/p/CS4L_ooFfJb/ -> CS4L_ooFfJb
        - https://www.instagram.com/reel/CS4L_ooFfJB/ -> CS4L_ooFfJB
        """
        pattern = re.compile(r"/(p|reel)/([\w-]+)/?")
        match = pattern.search(url)
        return match.group(2) if match else None

    async def _get_matching_post_if_found(
        self, post_link: Locator, posts_to_find: list[Post]
    ) -> Post | None:
        """포스트 링크가 찾아야 할 포스트 목록에 있는지 확인합니다."""
        href = await post_link.get_attribute("href")
        if not href:
            return None

        # 상대 경로를 절대 경로로 변환
        if href.startswith("/"):
            href = f"https://www.instagram.com{href}"

        # 현재 링크의 포스트 ID 추출
        current_post_id = self._extract_post_id(href)
        if not current_post_id:
            return None

        # 찾아야 할 포스트들과 비교
        for post_to_find in posts_to_find:
            target_post_id = self._extract_post_id(post_to_find.url)
            if target_post_id and current_post_id == target_post_id:
                return post_to_find

        return None

    @override
    async def search_and_find_posts(
        self, index: int, keyword: Keyword, posts_to_find: list[Post], output_dir: Path
    ) -> SearchResult:
        from playwright.async_api import TimeoutError

        try:
            search_page = InstagramSearchPage(self.page)
            await search_page.goto(keyword.text)

            if await search_page.is_result_empty():
                logger.info(
                    f"{keyword}에 대한 검색 결과가 없습니다.",
                    event_name="result_not_found",
                    keyword=keyword,
                )
                return SearchResult(found_posts=[], screenshot=None)

            top_9_posts = await search_page.get_top_9_posts()

            if not top_9_posts:
                logger.error(f"{keyword.text}에 대해서 포스트를 찾을 수 없습니다.")
                logger.error(await search_page.page.content())
                await search_page.page.screenshot(
                    path=(output_dir / f"{keyword}_error.png")
                )
                return SearchResult(found_posts=[], screenshot=None)

            # 상위 9개 포스트에서 찾아야 할 URL이 있는지 확인
            tasks = [
                self._get_matching_post_if_found(post_link, posts_to_find)
                for post_link in top_9_posts
            ]
            matching_results = await asyncio.gather(*tasks)

            found_posts_in_top9: list[Post] = [
                post for post in matching_results if post
            ]
            elements_to_highlight: list[Locator] = [
                top_9_posts[i] for i, post in enumerate(matching_results) if post
            ]

            # 매칭된 포스트가 있으면 하이라이트 적용
            if found_posts_in_top9:
                highlight_tasks = [
                    search_page.highlight_element(element)
                    for element in elements_to_highlight
                ]
                await asyncio.gather(*highlight_tasks)

            # 스크린샷은 매칭 여부와 관계없이 무조건 촬영
            screenshot_path = await search_page.take_screenshot_of_results(
                index, keyword.text, output_dir
            )

            return SearchResult(
                found_posts=found_posts_in_top9,
                screenshot=Screenshot(file_path=screenshot_path),
            )
        except TimeoutError as e:
            logger.exception(
                f"페이지 로드 시간 초과: {keyword.text}",
                event_name="page_load_timeout",
                keyword=keyword.text,
            )
            raise e
        finally:
            await self.page.close()
