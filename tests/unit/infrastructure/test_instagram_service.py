from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from viral_marketing_reporter.domain.model import Keyword, Post
from viral_marketing_reporter.infrastructure.platforms.instagram.service import (
    PlaywrightInstagramService,
)


@pytest.mark.asyncio
async def test_empty_search_result_is_normal_not_found_result(tmp_path: Path) -> None:
    page = MagicMock()
    page.close = AsyncMock()
    service = PlaywrightInstagramService(page)
    search_page = MagicMock()
    search_page.goto = AsyncMock()
    search_page.is_result_empty = AsyncMock(return_value=True)

    with patch(
        "viral_marketing_reporter.infrastructure.platforms.instagram.service.InstagramSearchPage",
        return_value=search_page,
    ):
        result = await service.search_and_find_posts(
            index=1,
            keyword=Keyword(text="결과 없는 검색어"),
            posts_to_find=[Post(url="https://www.instagram.com/reel/target/")],
            output_dir=tmp_path,
        )

    assert result.found_posts == []
    assert result.screenshot is None
    search_page.get_top_10_posts.assert_not_called()
    page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_search_result_is_captured_when_all_posts_enabled(
    tmp_path: Path,
) -> None:
    page = MagicMock()
    page.close = AsyncMock()
    service = PlaywrightInstagramService(page)
    screenshot_path = tmp_path / "1_결과_없는_검색어.png"
    search_page = MagicMock()
    search_page.goto = AsyncMock()
    search_page.is_result_empty = AsyncMock(return_value=True)
    search_page.take_empty_result_screenshot = AsyncMock(
        return_value=screenshot_path
    )

    with patch(
        "viral_marketing_reporter.infrastructure.platforms.instagram.service.InstagramSearchPage",
        return_value=search_page,
    ):
        result = await service.search_and_find_posts(
            index=1,
            keyword=Keyword(text="결과 없는 검색어"),
            posts_to_find=[Post(url="https://www.instagram.com/reel/target/")],
            output_dir=tmp_path,
            screenshot_all_posts=True,
        )

    assert result.found_posts == []
    assert result.screenshot is not None
    assert result.screenshot.file_path == screenshot_path
    search_page.take_empty_result_screenshot.assert_awaited_once_with(
        1, "결과 없는 검색어", tmp_path
    )
    page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_sparse_results_without_matches_return_no_screenshot(
    tmp_path: Path,
) -> None:
    page = MagicMock()
    page.close = AsyncMock()
    service = PlaywrightInstagramService(page)
    result_posts = [MagicMock(), MagicMock()]
    result_posts[0].get_attribute = AsyncMock(return_value="/reel/unrelated-one/")
    result_posts[1].get_attribute = AsyncMock(return_value="/reel/unrelated-two/")

    search_page = MagicMock()
    search_page.goto = AsyncMock()
    search_page.is_result_empty = AsyncMock(return_value=False)
    search_page.get_top_10_posts = AsyncMock(return_value=result_posts)

    with patch(
        "viral_marketing_reporter.infrastructure.platforms.instagram.service.InstagramSearchPage",
        return_value=search_page,
    ):
        result = await service.search_and_find_posts(
            index=1,
            keyword=Keyword(text="희소 검색어"),
            posts_to_find=[Post(url="https://www.instagram.com/reel/target/")],
            output_dir=tmp_path,
        )

    assert result.found_posts == []
    assert result.screenshot is None
    search_page.take_screenshot_of_results.assert_not_called()
    page.close.assert_awaited_once()
