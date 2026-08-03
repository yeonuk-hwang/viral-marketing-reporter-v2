from unittest.mock import AsyncMock, MagicMock

import pytest

from viral_marketing_reporter.infrastructure.platforms.instagram.page_objects import (
    InstagramSearchPage,
)


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


@pytest.mark.parametrize("post_count", [1, 2, 3, 10])
def test_screenshot_clip_supports_partial_result_grids(post_count: int) -> None:
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

    expected_columns = min(post_count, 5)
    assert clip["x"] == 0
    assert clip["width"] == 36.0 + expected_columns * 284.0
    assert clip["height"] == boxes[-1]["y"] + boxes[-1]["height"]
