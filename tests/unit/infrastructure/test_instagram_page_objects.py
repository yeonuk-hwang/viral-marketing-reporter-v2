from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from viral_marketing_reporter.infrastructure.exceptions import InstagramPageStateError
from viral_marketing_reporter.infrastructure.platforms.instagram.page_objects import (
    InstagramSearchPage,
)


def _page_without_search_posts(url: str = "https://www.instagram.com/explore/search/keyword/"):
    post_locator = MagicMock()
    post_locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
    post_locator.count = AsyncMock(return_value=0)
    body_locator = MagicMock()
    body_locator.inner_text = AsyncMock(return_value="No matching content")
    page = MagicMock()
    page.url = url
    page.goto = AsyncMock()
    page.reload = AsyncMock()
    page.title = AsyncMock(return_value="Instagram")
    page.evaluate = AsyncMock(
        side_effect=lambda expression: (
            "complete" if expression == "document.readyState" else "en-GB"
        )
    )
    page.locator.side_effect = lambda selector: (
        post_locator if selector == InstagramSearchPage.POST_SELECTOR else body_locator
    )
    return page, post_locator


@pytest.mark.asyncio
async def test_goto_retries_then_accepts_empty_result_without_text() -> None:
    page, post_locator = _page_without_search_posts()
    search_page = InstagramSearchPage(page)

    await search_page.goto("희소 검색어")

    page.goto.assert_awaited_once()
    page.reload.assert_awaited_once()
    assert post_locator.first.wait_for.await_count == 2
    assert await search_page.is_result_empty() is True


@pytest.mark.asyncio
async def test_goto_raises_for_login_page_instead_of_treating_it_as_empty() -> None:
    page, _ = _page_without_search_posts("https://www.instagram.com/accounts/login/")
    search_page = InstagramSearchPage(page)

    with pytest.raises(InstagramPageStateError, match="로그인 페이지"):
        await search_page.goto("희소 검색어")

    page.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_result_screenshot_uses_fixed_grid_size(tmp_path: Path) -> None:
    page = MagicMock()

    async def save_screenshot(*, path: Path, clip: dict[str, int]) -> None:
        path.touch()

    page.screenshot = AsyncMock(side_effect=save_screenshot)
    search_page = InstagramSearchPage(page)

    screenshot_path = await search_page.take_empty_result_screenshot(
        2, "결과 없음", tmp_path
    )

    assert screenshot_path == tmp_path / "2_결과_없음.png"
    page.screenshot.assert_awaited_once_with(
        path=screenshot_path,
        clip={"x": 0, "y": 0, "width": 1460, "height": 835},
    )


def test_diagnostic_listeners_count_api_and_browser_errors() -> None:
    page = MagicMock()
    search_page = InstagramSearchPage(page)
    request = MagicMock()
    request.resource_type = "fetch"
    request.url = "https://www.instagram.com/api/v1/search/?token=secret"
    request.failure = "net::ERR_FAILED"
    response = MagicMock()
    response.status = 429
    response.url = request.url
    response.request = request
    console_message = MagicMock()
    console_message.type = "error"
    console_message.text = "failed https://www.instagram.com/api/?token=secret"

    search_page._on_response(response)
    search_page._on_request_failed(request)
    search_page._on_console(console_message)
    search_page._on_page_error(RuntimeError("script failed"))

    assert search_page.http_error_count == 1
    assert search_page.network_failure_count == 1
    assert search_page.console_error_count == 1
    assert search_page.page_error_count == 1
    assert search_page._safe_url_parts(request.url) == (
        "www.instagram.com",
        "/api/v1/search/",
    )
    assert "secret" not in search_page._sanitize_diagnostic_text(
        console_message.text
    )
    registered_events = {call.args[0] for call in page.on.call_args_list}
    assert registered_events == {"response", "requestfailed", "console", "pageerror"}


def test_diagnostic_listeners_ignore_success_and_media_responses() -> None:
    search_page = InstagramSearchPage(MagicMock())
    successful_request = MagicMock(resource_type="fetch")
    successful_response = MagicMock(
        status=200,
        url="https://www.instagram.com/api/v1/search/",
        request=successful_request,
    )
    media_request = MagicMock(resource_type="image")
    media_response = MagicMock(
        status=404,
        url="https://cdninstagram.com/image.jpg",
        request=media_request,
    )

    search_page._on_response(successful_response)
    search_page._on_response(media_response)

    assert search_page.http_error_count == 0


@pytest.mark.asyncio
async def test_get_top_10_posts_limits_results_to_two_five_column_rows() -> None:
    posts = [MagicMock() for _ in range(12)]
    locator = MagicMock()
    locator.all = AsyncMock(return_value=posts)
    page = MagicMock()
    page.locator.return_value = locator

    search_page = InstagramSearchPage(page)

    assert await search_page.get_top_10_posts() == posts[:10]
    page.locator.assert_called_once_with(InstagramSearchPage.POST_SELECTOR)


@pytest.mark.asyncio
async def test_wait_for_post_media_waits_for_video_frame() -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(return_value={"total": 10, "videos": 3, "ready": 10})
    search_page = InstagramSearchPage(page)

    result = await search_page._wait_for_post_media()

    assert result == {"total": 10, "videos": 3, "ready": 10}
    script, options = page.evaluate.await_args.args
    assert "requestVideoFrameCallback" in script
    assert "loadeddata" in script
    assert options == {
        "postSelector": InstagramSearchPage.POST_SELECTOR,
        "postCount": 10,
        "timeout": 15_000,
    }


@pytest.mark.parametrize("post_count", [1, 2, 3, 5, 10])
def test_screenshot_clip_uses_fixed_two_row_grid(post_count: int) -> None:
    boxes = [
        {
            "x": 20.0 + (index % 5) * 284.0,
            "y": 83.0 + (index // 5) * 378.0,
            "width": 280.0,
            "height": 374.0,
        }
        for index in range(post_count)
    ]

    clip = InstagramSearchPage._calculate_screenshot_clip(boxes)

    assert clip["x"] == 0
    assert clip["width"] == 1456.0
    assert clip["height"] == 835.0


def test_screenshot_clip_infers_grid_from_single_post() -> None:
    clip = InstagramSearchPage._calculate_screenshot_clip(
        [{"x": 20.0, "y": 83.0, "width": 280.0, "height": 374.0}]
    )

    assert clip == {"x": 0, "y": 0, "width": 1456.0, "height": 835.0}
