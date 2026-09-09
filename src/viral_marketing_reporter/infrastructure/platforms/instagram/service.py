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
from viral_marketing_reporter.infrastructure.exceptions import InstagramPageStateError
from viral_marketing_reporter.infrastructure.logging_utils import (
    log_function_call,
    log_step,
    log_with_context,
    PerformanceTracker,
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
    @log_with_context(platform="instagram")
    async def search_and_find_posts(
        self,
        index: int,
        keyword: Keyword,
        posts_to_find: list[Post],
        output_dir: Path,
        screenshot_all_posts: bool = False,
    ) -> SearchResult:
        from playwright.async_api import TimeoutError

        tracker = PerformanceTracker(f"instagram_search_{keyword.text}")
        tracker.start()

        with log_step(
            "Instagram 검색 및 포스트 매칭",
            keyword=keyword.text,
            index=index,
            posts_to_find_count=len(posts_to_find),
        ):
            try:
                search_page = InstagramSearchPage(self.page)
                logger.info(
                    "Instagram 검색 페이지로 이동",
                    keyword=keyword.text,
                    event_name="navigate_to_search",
                )
                await search_page.goto(keyword.text)
                tracker.checkpoint("page_loaded")

                if await search_page.is_result_empty():
                    screenshot_path = None
                    if screenshot_all_posts:
                        screenshot_path = await search_page.take_empty_result_screenshot(
                            index, keyword.text, output_dir
                        )
                    logger.info(
                        "검색 결과 없음",
                        keyword=keyword.text,
                        screenshot_created=screenshot_path is not None,
                        event_name="result_not_found",
                    )
                    tracker.end()
                    return SearchResult(
                        found_posts=[],
                        screenshot=(
                            Screenshot(file_path=screenshot_path)
                            if screenshot_path
                            else None
                        ),
                    )

                top_10_posts = await search_page.prepare_top_10_posts()
                tracker.checkpoint("top_10_posts_retrieved")
                logger.debug(
                    f"상위 포스트 {len(top_10_posts)}개 발견",
                    keyword=keyword.text,
                    post_count=len(top_10_posts),
                    event_name="posts_retrieved",
                )

                if not top_10_posts:
                    diagnostics = await search_page._get_page_diagnostics()
                    logger.warning(
                        "결과 확인 후 포스트 요소가 사라짐",
                        keyword=keyword.text,
                        **diagnostics,
                        event_name="posts_not_found",
                    )
                    tracker.end()
                    return SearchResult(found_posts=[], screenshot=None)

                # 상위 10개 포스트에서 찾아야 할 URL이 있는지 확인
                logger.debug(
                    "포스트 매칭 시작",
                    keyword=keyword.text,
                    event_name="matching_start",
                )
                tasks = [
                    self._get_matching_post_if_found(post_link, posts_to_find)
                    for post_link in top_10_posts
                ]
                matching_results = await asyncio.gather(*tasks)
                tracker.checkpoint("posts_matched")

                found_posts_in_top10: list[Post] = [
                    post for post in matching_results if post
                ]

                logger.info(
                    f"포스트 매칭 완료",
                    keyword=keyword.text,
                    found_count=len(found_posts_in_top10),
                    target_count=len(posts_to_find),
                    event_name="matching_completed",
                )

                # 스크린샷 촬영 여부 결정
                should_take_screenshot = screenshot_all_posts or found_posts_in_top10

                if should_take_screenshot:
                    logger.debug(
                        "스크린샷 촬영 시작",
                        keyword=keyword.text,
                        screenshot_all_posts=screenshot_all_posts,
                        event_name="screenshot_start",
                    )
                    screenshot_path = await search_page.take_screenshot_of_results(
                        index,
                        keyword.text,
                        output_dir,
                        highlighted_post_ids={
                            post_id
                            for post in found_posts_in_top10
                            if (post_id := self._extract_post_id(post.url))
                        },
                    )
                    tracker.checkpoint("screenshot_taken")
                    logger.info(
                        "스크린샷 촬영 완료",
                        keyword=keyword.text,
                        screenshot_path=str(screenshot_path),
                        event_name="screenshot_completed",
                    )
                else:
                    screenshot_path = None
                    logger.info(
                        "매칭된 포스트 없음 및 모든 포스트 옵션 미선택 - 스크린샷 생략",
                        keyword=keyword.text,
                        event_name="no_matches_no_screenshot",
                    )

                tracker.end()
                return SearchResult(
                    found_posts=found_posts_in_top10,
                    screenshot=(
                        Screenshot(file_path=screenshot_path)
                        if screenshot_path
                        else None
                    ),
                )
            except InstagramPageStateError as error:
                output_dir.mkdir(parents=True, exist_ok=True)
                diagnostic_path = output_dir / f"{index}_{keyword.text}_error.png"
                if not self.page.is_closed():
                    await self.page.screenshot(path=diagnostic_path, full_page=True)
                logger.exception(
                    "Instagram 페이지 상태 오류",
                    keyword=keyword.text,
                    error=str(error),
                    diagnostic_screenshot=str(diagnostic_path),
                    event_name="instagram_page_state_error",
                )
                tracker.end()
                raise
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
                    "Instagram 페이지 정리",
                    keyword=keyword.text,
                    event_name="page_cleanup",
                )
                await self.page.close()
