from pathlib import Path
from urllib.parse import quote

from loguru import logger
from playwright.async_api import (
    FloatRect,
    Locator,
    Page,
)

from viral_marketing_reporter.infrastructure.exceptions import (
    ScreenshotTargetMissingError,
)
from viral_marketing_reporter.infrastructure.logging_utils import (
    log_function_call,
    log_step,
    PerformanceTracker,
)


class InstagramSearchPage:
    """Instagram 키워드 검색 결과 페이지에 대한 상호작용을 캡슐화합니다."""

    def __init__(self, page: Page):
        self.page: Page = page

    @log_function_call
    async def goto(self, keyword: str) -> None:
        """주어진 키워드로 검색 결과 페이지로 이동합니다."""
        encoded_keyword = quote(keyword)
        search_url = f"https://www.instagram.com/explore/search/keyword/?q={encoded_keyword}"

        logger.info(
            "Instagram 검색 페이지로 이동",
            keyword=keyword,
            url=search_url,
            event_name="page_navigate",
        )

        await self.page.goto(search_url, wait_until="load", timeout=60 * 1000)
        logger.debug(
            "페이지 로드 완료",
            keyword=keyword,
            event_name="page_loaded",
        )

        # 포스트가 로드될 때까지 명시적으로 대기
        logger.debug(
            "포스트 요소 대기 중",
            keyword=keyword,
            event_name="wait_for_posts",
        )
        await self.page.locator('a[href*="/p/"], a[href*="/reel/"]').first.wait_for(
            state="visible", timeout=60 * 1000
        )
        logger.debug(
            "포스트 요소 로드 완료",
            keyword=keyword,
            event_name="posts_visible",
        )

    async def is_result_empty(self) -> bool:
        """검색 결과가 없는지 확인합니다."""
        # Instagram에서 결과가 없을 때 표시되는 메시지 확인
        no_results_locator = self.page.get_by_text("No results found")
        return await no_results_locator.is_visible()

    async def get_top_9_posts(self) -> list[Locator]:
        """상위 9개의 포스트 링크를 가져옵니다.

        Instagram은 한 줄에 3개씩 표시되므로 상위 9개 = 3줄입니다.
        """
        # 포스트와 릴스 링크를 모두 선택
        post_links = await self.page.locator('a[href*="/p/"], a[href*="/reel/"]').all()
        return post_links[:9]

    async def highlight_element(self, element: Locator) -> None:
        """주어진 요소에 빨간색 테두리를 적용합니다."""
        await element.evaluate(
            '(element) => { element.style.border = "5px solid red"; element.style.display = "block"; }'
        )

    @log_function_call
    async def take_screenshot_of_results(
        self, index: int, keyword: str, output_dir: Path
    ) -> Path:
        """검색 결과 페이지의 상위 9개 포스트 영역을 스크린샷으로 찍고 파일 경로를 반환합니다."""
        tracker = PerformanceTracker(f"instagram_screenshot_{keyword}")
        tracker.start()

        with log_step(
            "Instagram 스크린샷 촬영",
            keyword=keyword,
            index=index,
        ):
            top_9_posts = await self.get_top_9_posts()
            if not top_9_posts:
                logger.error(
                    "포스트를 찾지 못해 스크린샷 불가",
                    keyword=keyword,
                    event_name="screenshot_failed_no_posts",
                )
                raise ScreenshotTargetMissingError("포스트를 찾지 못했습니다.")

            logger.debug(
                f"상위 {len(top_9_posts)}개 포스트 발견",
                keyword=keyword,
                post_count=len(top_9_posts),
                event_name="posts_found_for_screenshot",
            )

            # 마지막 포스트로 스크롤
            logger.debug(
                "마지막 포스트로 스크롤 (lazy loading)",
                keyword=keyword,
                event_name="scroll_to_last_post",
            )
            last_post = top_9_posts[-1]
            await last_post.scroll_into_view_if_needed()
            await self.page.wait_for_timeout(2000)  # lazy loading 대기
            tracker.checkpoint("scrolled_to_bottom")

            # 페이지 최상단으로 스크롤
            logger.debug(
                "페이지 최상단으로 스크롤",
                keyword=keyword,
                event_name="scroll_to_top",
            )
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(2000)  # 스크롤 안정화 및 이미지 로딩 대기
            tracker.checkpoint("scrolled_to_top")

            # 이미지들이 실제로 렌더링될 때까지 대기
            logger.debug(
                "이미지 로딩 대기 중",
                keyword=keyword,
                event_name="wait_for_images",
            )
            await self.page.evaluate("""
                async () => {
                    const images = document.querySelectorAll('img');
                    const timeout = 5000;
                    const start = Date.now();

                    for (const img of images) {
                        while (Date.now() - start < timeout) {
                            // 이미지가 로드되고 실제 크기를 가지고 있는지 확인
                            if (img.complete && img.naturalWidth > 0) {
                                break;
                            }
                            await new Promise(resolve => setTimeout(resolve, 100));
                        }
                    }
                }
            """)
            tracker.checkpoint("images_loaded")
            logger.debug(
                "이미지 로딩 완료",
                keyword=keyword,
                event_name="images_loaded",
            )

            # 최종 안정화 대기
            await self.page.wait_for_timeout(1000)

            # 모든 포스트의 bounding box 가져오기
            logger.debug(
                "포스트 위치 정보 수집 중",
                keyword=keyword,
                event_name="collect_bounding_boxes",
            )
            boxes = []
            for post in top_9_posts:
                box = await post.bounding_box()
                if box:
                    boxes.append(box)

            if not boxes:
                logger.error(
                    "포스트 위치를 찾을 수 없음",
                    keyword=keyword,
                    event_name="screenshot_failed_no_boxes",
                )
                raise ScreenshotTargetMissingError(
                    "포스트의 위치를 찾을 수 없어 스크린샷 영역을 계산할 수 없습니다."
                )

            logger.debug(
                f"{len(boxes)}개 포스트의 위치 정보 수집 완료",
                keyword=keyword,
                box_count=len(boxes),
                event_name="boxes_collected",
            )

            first_post_box = boxes[0]
            last_post_box = boxes[-1]

            # 첫 번째 줄의 포스트들을 찾기 (y 좌표가 비슷한 포스트들)
            Y_THRESHOLD = 20  # y 좌표 허용 오차
            first_row_boxes = [
                box for box in boxes
                if abs(box["y"] - first_post_box["y"]) < Y_THRESHOLD
            ]

            # 첫 번째 줄에서 가장 오른쪽 포스트 찾기
            rightmost_box = max(
                first_row_boxes,
                key=lambda box: box["x"] + box["width"]
            )

            SCREENSHOT_MARGIN = 20
            BOTTOM_PADDING = 100  # viewport 여유 공간 (메시지 팝업 고려)

            # 전체 너비 계산: 첫 번째 포스트부터 첫 줄의 가장 오른쪽 포스트까지
            total_width = (
                rightmost_box["x"] + rightmost_box["width"] - first_post_box["x"]
            )

            # clip 높이: 9번째(마지막) 포스트까지만
            clip_height = last_post_box["y"] + last_post_box["height"]

            # viewport 높이: 메시지 팝업 고려하여 여유 추가
            viewport_height = clip_height + BOTTOM_PADDING

            logger.debug(
                "스크린샷 영역 계산 완료",
                keyword=keyword,
                total_width=total_width,
                clip_height=clip_height,
                viewport_height=viewport_height,
                event_name="screenshot_dimensions_calculated",
            )

            # viewport를 필요한 높이만큼 조정
            original_viewport = self.page.viewport_size
            if original_viewport and original_viewport["height"] < viewport_height:
                logger.debug(
                    "Viewport 높이 조정",
                    keyword=keyword,
                    original_height=original_viewport["height"],
                    new_height=int(viewport_height),
                    event_name="viewport_resized",
                )
                await self.page.set_viewport_size(
                    {"width": original_viewport["width"], "height": int(viewport_height)}
                )
                tracker.checkpoint("viewport_adjusted")

            # 스크린샷 영역 설정 (페이지 최상단부터 9번째 포스트까지)
            clip: FloatRect = {
                "x": first_post_box["x"] - SCREENSHOT_MARGIN,
                "y": 0,  # 최상단부터 (키워드 포함)
                "width": total_width + SCREENSHOT_MARGIN * 2,
                "height": clip_height,
            }

            output_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{index}_{keyword.replace(' ', '_')}.png"
            screenshot_path = output_dir / file_name

            logger.debug(
                "스크린샷 촬영 중",
                keyword=keyword,
                output_path=str(screenshot_path),
                event_name="screenshot_capture_start",
            )
            await self.page.screenshot(path=screenshot_path, clip=clip)
            tracker.checkpoint("screenshot_captured")

            # viewport 원상복구
            if original_viewport:
                await self.page.set_viewport_size(original_viewport)
                logger.debug(
                    "Viewport 원상복구",
                    keyword=keyword,
                    event_name="viewport_restored",
                )

            logger.info(
                "스크린샷 촬영 완료",
                keyword=keyword,
                screenshot_path=str(screenshot_path),
                file_size_bytes=screenshot_path.stat().st_size,
                event_name="screenshot_saved",
            )

            tracker.end()
            return screenshot_path
