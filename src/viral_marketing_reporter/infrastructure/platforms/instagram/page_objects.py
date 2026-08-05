from pathlib import Path
import re
from urllib.parse import quote
from urllib.parse import urlsplit

from loguru import logger
from playwright.async_api import (
    FloatRect,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from viral_marketing_reporter.infrastructure.exceptions import (
    InstagramPageStateError,
    ScreenshotTargetMissingError,
)
from viral_marketing_reporter.infrastructure.logging_utils import (
    log_function_call,
    log_step,
    PerformanceTracker,
)


class InstagramSearchPage:
    """Instagram 키워드 검색 결과 페이지에 대한 상호작용을 캡슐화합니다."""

    POST_SELECTOR = 'a[href*="/p/"], a[href*="/reel/"]'
    SCREENSHOT_POST_COUNT = 10
    SCREENSHOT_MARGIN = 20
    ROW_Y_THRESHOLD = 20
    GRID_COLUMNS = 5
    GRID_ROWS = 2
    GRID_GAP = 4
    EMPTY_RESULT_CLIP_WIDTH = 1460
    EMPTY_RESULT_CLIP_HEIGHT = 835
    RESULT_WAIT_TIMEOUT_MS = 15_000
    SEARCH_ATTEMPTS = 2
    DIAGNOSTIC_RESOURCE_TYPES = {"document", "xhr", "fetch", "script"}

    def __init__(self, page: Page):
        self.page: Page = page
        self.network_failure_count = 0
        self.http_error_count = 0
        self.console_error_count = 0
        self.page_error_count = 0
        self._attach_diagnostic_listeners()

    def _attach_diagnostic_listeners(self) -> None:
        """민감정보를 제외한 네트워크 및 브라우저 오류를 기록합니다."""
        self.page.on("response", self._on_response)
        self.page.on("requestfailed", self._on_request_failed)
        self.page.on("console", self._on_console)
        self.page.on("pageerror", self._on_page_error)

    @staticmethod
    def _safe_url_parts(url: str) -> tuple[str, str]:
        parsed = urlsplit(url)
        return parsed.netloc, parsed.path

    @classmethod
    def _sanitize_diagnostic_text(cls, text: str) -> str:
        """메시지 속 URL에서 토큰이 포함될 수 있는 쿼리와 fragment를 제거합니다."""
        def replace_url(match: re.Match[str]) -> str:
            host, path = cls._safe_url_parts(match.group(0))
            return f"https://{host}{path}"

        sanitized = re.sub(r"https?://[^\s]+", replace_url, text)
        return sanitized[:500]

    def _on_response(self, response) -> None:
        request = response.request
        if (
            response.status < 400
            or request.resource_type not in self.DIAGNOSTIC_RESOURCE_TYPES
        ):
            return
        host, path = self._safe_url_parts(response.url)
        self.http_error_count += 1
        logger.warning(
            "Instagram HTTP 오류 응답",
            host=host,
            path=path,
            status=response.status,
            resource_type=request.resource_type,
            event_name="instagram_http_error",
        )

    def _on_request_failed(self, request) -> None:
        if request.resource_type not in self.DIAGNOSTIC_RESOURCE_TYPES:
            return
        host, path = self._safe_url_parts(request.url)
        self.network_failure_count += 1
        logger.warning(
            "Instagram 네트워크 요청 실패",
            host=host,
            path=path,
            resource_type=request.resource_type,
            failure=self._sanitize_diagnostic_text(request.failure or "unknown"),
            event_name="instagram_request_failed",
        )

    def _on_console(self, message) -> None:
        if message.type != "error":
            return
        self.console_error_count += 1
        logger.warning(
            "Instagram 브라우저 콘솔 오류",
            message=self._sanitize_diagnostic_text(message.text),
            event_name="instagram_console_error",
        )

    def _on_page_error(self, error) -> None:
        self.page_error_count += 1
        logger.warning(
            "Instagram 페이지 JavaScript 오류",
            error=self._sanitize_diagnostic_text(str(error)),
            error_type=error.__class__.__name__,
            event_name="instagram_page_error",
        )

    @log_function_call
    async def goto(self, keyword: str) -> None:
        """주어진 키워드로 검색 결과 페이지로 이동합니다."""
        normalized_keyword = keyword.strip()
        hashtag_keyword = (
            normalized_keyword
            if normalized_keyword.startswith("#")
            else f"#{normalized_keyword}"
        )
        encoded_keyword = quote(hashtag_keyword)
        search_url = f"https://www.instagram.com/explore/search/keyword/?q={encoded_keyword}"

        logger.info(
            "Instagram 검색 페이지로 이동",
            keyword=keyword,
            search_query=hashtag_keyword,
            url=search_url,
            event_name="page_navigate",
        )

        for attempt in range(1, self.SEARCH_ATTEMPTS + 1):
            if attempt == 1:
                response = await self.page.goto(
                    search_url, wait_until="load", timeout=60 * 1000
                )
            else:
                logger.info(
                    "게시물 미감지로 검색 페이지 새로고침",
                    keyword=keyword,
                    attempt=attempt,
                    event_name="search_retry",
                )
                response = await self.page.reload(wait_until="load", timeout=60 * 1000)

            logger.debug(
                "페이지 로드 완료",
                keyword=keyword,
                attempt=attempt,
                url=self.page.url,
                response_status=response.status if response else None,
                event_name="page_loaded",
            )
            try:
                await self.page.locator(self.POST_SELECTOR).first.wait_for(
                    state="visible", timeout=self.RESULT_WAIT_TIMEOUT_MS
                )
                logger.debug(
                    "검색 게시물 확인 완료",
                    keyword=keyword,
                    attempt=attempt,
                    event_name="search_result_ready",
                )
                return
            except PlaywrightTimeoutError:
                diagnostics = await self._get_page_diagnostics()
                logger.warning(
                    "검색 게시물 대기 시간 초과",
                    keyword=keyword,
                    attempt=attempt,
                    timeout_ms=self.RESULT_WAIT_TIMEOUT_MS,
                    **diagnostics,
                    event_name="search_result_wait_timeout",
                )
                self._raise_for_blocking_state(keyword, diagnostics)

        diagnostics = await self._get_page_diagnostics()
        logger.info(
            "재시도 후에도 검색 게시물 없음",
            keyword=keyword,
            attempt_count=self.SEARCH_ATTEMPTS,
            **diagnostics,
            event_name="empty_search_result",
        )

    async def _get_page_diagnostics(self) -> dict[str, object]:
        """민감한 전체 HTML 대신 문제 판별에 필요한 제한된 상태만 수집합니다."""
        body_text = await self.page.locator("body").inner_text(timeout=5_000)
        normalized_body = " ".join(body_text.split())
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "post_count": await self.page.locator(self.POST_SELECTOR).count(),
            "body_text_length": len(body_text),
            "body_excerpt": normalized_body[:500],
            "document_ready_state": await self.page.evaluate("document.readyState"),
            "browser_language": await self.page.evaluate("navigator.language"),
            "http_error_count": self.http_error_count,
            "network_failure_count": self.network_failure_count,
            "console_error_count": self.console_error_count,
            "page_error_count": self.page_error_count,
        }

    def _raise_for_blocking_state(
        self, keyword: str, diagnostics: dict[str, object]
    ) -> None:
        """빈 결과와 구분해야 하는 로그인 및 제한 페이지를 감지합니다."""
        url = str(diagnostics["url"]).lower()
        body_text = str(diagnostics["body_excerpt"]).lower()

        if "/accounts/login" in url:
            raise InstagramPageStateError("Instagram 로그인 페이지로 이동했습니다.")
        if "/challenge" in url or "/checkpoint" in url:
            raise InstagramPageStateError("Instagram 보안 확인 페이지가 감지됐습니다.")
        if any(
            text in body_text
            for text in (
                "try again later",
                "please wait a few minutes",
                "something went wrong",
            )
        ):
            raise InstagramPageStateError(
                f"Instagram 검색 제한 또는 오류 페이지가 감지됐습니다: {keyword}"
            )

    async def is_result_empty(self) -> bool:
        """검색 결과가 없는지 확인합니다."""
        return await self.page.locator(self.POST_SELECTOR).count() == 0

    @classmethod
    def _calculate_screenshot_clip(cls, boxes: list[FloatRect]) -> FloatRect:
        """게시물 수와 관계없이 5열 x 2행 크기의 캡처 영역을 계산합니다."""
        if not boxes:
            raise ScreenshotTargetMissingError(
                "포스트의 위치를 찾을 수 없어 스크린샷 영역을 계산할 수 없습니다."
            )

        first_row_y = min(box["y"] for box in boxes)
        first_row_boxes = [
            box
            for box in boxes
            if abs(box["y"] - first_row_y) < cls.ROW_Y_THRESHOLD
        ]
        first_row_boxes.sort(key=lambda box: box["x"])
        first_box = first_row_boxes[0]
        left = first_box["x"]
        post_width = first_box["width"]
        post_height = first_box["height"]

        column_pitch = (
            first_row_boxes[1]["x"] - first_box["x"]
            if len(first_row_boxes) > 1
            else post_width + cls.GRID_GAP
        )
        second_row_boxes = [
            box
            for box in boxes
            if box["y"] - first_row_y >= cls.ROW_Y_THRESHOLD
        ]
        row_pitch = (
            min(box["y"] for box in second_row_boxes) - first_row_y
            if second_row_boxes
            else post_height + cls.GRID_GAP
        )

        right = left + (cls.GRID_COLUMNS - 1) * column_pitch + post_width
        bottom = first_row_y + (cls.GRID_ROWS - 1) * row_pitch + post_height
        clip_x = max(0, left - cls.SCREENSHOT_MARGIN)

        return {
            "x": clip_x,
            "y": 0,
            "width": right + cls.SCREENSHOT_MARGIN - clip_x,
            "height": bottom,
        }

    async def get_top_10_posts(self) -> list[Locator]:
        """5열 레이아웃의 상위 10개 포스트 링크(2줄)를 가져옵니다.

        포스트와 릴스 링크를 모두 포함합니다.
        """
        post_links = await self.page.locator(self.POST_SELECTOR).all()
        return post_links[: self.SCREENSHOT_POST_COUNT]

    async def take_empty_result_screenshot(
        self, index: int, keyword: str, output_dir: Path
    ) -> Path:
        """게시물이 없는 검색 페이지를 일반 결과와 같은 크기로 저장합니다."""
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"{index}_{keyword.replace(' ', '_')}.png"
        clip: FloatRect = {
            "x": 0,
            "y": 0,
            "width": self.EMPTY_RESULT_CLIP_WIDTH,
            "height": self.EMPTY_RESULT_CLIP_HEIGHT,
        }
        await self.page.screenshot(path=screenshot_path, clip=clip)
        logger.info(
            "빈 검색 결과 스크린샷 촬영 완료",
            keyword=keyword,
            screenshot_path=str(screenshot_path),
            width=self.EMPTY_RESULT_CLIP_WIDTH,
            height=self.EMPTY_RESULT_CLIP_HEIGHT,
            file_size_bytes=screenshot_path.stat().st_size,
            event_name="empty_result_screenshot_saved",
        )
        return screenshot_path

    async def _wait_for_post_media(self) -> dict[str, int]:
        """상위 포스트의 이미지 및 비디오 첫 프레임이 렌더링될 때까지 기다립니다."""
        return await self.page.evaluate(
            """
            async ({postSelector, postCount, timeout}) => {
                const posts = [...document.querySelectorAll(postSelector)].slice(0, postCount);
                const media = posts.flatMap(post => [...post.querySelectorAll('img, video')]);

                const waitWithTimeout = (promise) => Promise.race([
                    promise,
                    new Promise(resolve => setTimeout(() => resolve(false), timeout)),
                ]);

                const waitForImage = async (img) => {
                    if (!(img.complete && img.naturalWidth > 0)) {
                        await waitWithTimeout(new Promise(resolve => {
                            img.addEventListener('load', () => resolve(true), {once: true});
                            img.addEventListener('error', () => resolve(false), {once: true});
                        }));
                    }
                    if (img.complete && img.naturalWidth > 0 && img.decode) {
                        await waitWithTimeout(img.decode().then(() => true).catch(() => false));
                    }
                    return img.complete && img.naturalWidth > 0;
                };

                const waitForVideo = async (video) => {
                    video.muted = true;
                    video.playsInline = true;
                    video.preload = 'auto';

                    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth) {
                        await waitWithTimeout(new Promise(resolve => {
                            const done = () => resolve(true);
                            video.addEventListener('loadeddata', done, {once: true});
                            video.addEventListener('canplay', done, {once: true});
                            video.addEventListener('error', () => resolve(false), {once: true});
                            video.load();
                        }));
                    }

                    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth) {
                        try {
                            await waitWithTimeout(video.play().then(() => true).catch(() => false));
                            await waitWithTimeout(new Promise(resolve => {
                                if (video.requestVideoFrameCallback) {
                                    video.requestVideoFrameCallback(() => resolve(true));
                                } else {
                                    requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
                                }
                            }));
                        } finally {
                            video.pause();
                        }
                    }
                    return video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0;
                };

                const results = await Promise.all(media.map(element =>
                    element instanceof HTMLVideoElement
                        ? waitForVideo(element)
                        : waitForImage(element)
                ));
                return {
                    total: media.length,
                    videos: media.filter(element => element instanceof HTMLVideoElement).length,
                    ready: results.filter(Boolean).length,
                };
            }
            """,
            {
                "postSelector": self.POST_SELECTOR,
                "postCount": self.SCREENSHOT_POST_COUNT,
                "timeout": 15_000,
            },
        )

    async def highlight_element(self, element: Locator) -> None:
        """주어진 요소에 빨간색 테두리를 적용합니다."""
        await element.evaluate(
            '(element) => { element.style.border = "5px solid red"; element.style.display = "block"; }'
        )

    @log_function_call
    async def take_screenshot_of_results(
        self, index: int, keyword: str, output_dir: Path
    ) -> Path:
        """검색 결과 페이지의 상위 10개 포스트 영역을 스크린샷으로 찍고 파일 경로를 반환합니다."""
        tracker = PerformanceTracker(f"instagram_screenshot_{keyword}")
        tracker.start()

        with log_step(
            "Instagram 스크린샷 촬영",
            keyword=keyword,
            index=index,
        ):
            top_10_posts = await self.get_top_10_posts()
            if not top_10_posts:
                logger.error(
                    "포스트를 찾지 못해 스크린샷 불가",
                    keyword=keyword,
                    event_name="screenshot_failed_no_posts",
                )
                raise ScreenshotTargetMissingError("포스트를 찾지 못했습니다.")

            logger.debug(
                f"상위 {len(top_10_posts)}개 포스트 발견",
                keyword=keyword,
                post_count=len(top_10_posts),
                event_name="posts_found_for_screenshot",
            )

            # 마지막 포스트로 스크롤
            logger.debug(
                "마지막 포스트로 스크롤 (lazy loading)",
                keyword=keyword,
                event_name="scroll_to_last_post",
            )
            last_post = top_10_posts[-1]
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

            # 이미지와 비디오 첫 프레임이 실제로 렌더링될 때까지 대기
            logger.debug(
                "포스트 미디어 로딩 대기 중",
                keyword=keyword,
                event_name="wait_for_media",
            )
            media_status = await self._wait_for_post_media()
            tracker.checkpoint("media_loaded")
            logger.debug(
                "포스트 미디어 로딩 완료",
                keyword=keyword,
                **media_status,
                event_name="media_loaded",
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
            for post in top_10_posts:
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

            BOTTOM_PADDING = 100  # viewport 여유 공간 (메시지 팝업 고려)
            clip = self._calculate_screenshot_clip(boxes)

            # viewport 높이: 메시지 팝업 고려하여 여유 추가
            viewport_height = clip["height"] + BOTTOM_PADDING

            logger.debug(
                "스크린샷 영역 계산 완료",
                keyword=keyword,
                total_width=clip["width"],
                clip_height=clip["height"],
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
