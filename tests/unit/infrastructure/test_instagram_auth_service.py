from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from viral_marketing_reporter.infrastructure.platforms.instagram.auth_service import (
    InstagramAuthService,
)


def make_authenticated_page() -> tuple[MagicMock, AsyncMock]:
    authenticated_ui = AsyncMock()
    locator = MagicMock()
    locator.first = authenticated_ui
    page = MagicMock()
    page.goto = AsyncMock()
    page.locator.return_value = locator
    page.is_closed.return_value = False
    page.close = AsyncMock()
    return page, authenticated_ui


@pytest.mark.asyncio
async def test_saved_session_is_valid_when_authenticated_ui_is_visible(
    tmp_path: Path,
) -> None:
    page, authenticated_ui = make_authenticated_page()
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.storage_state = AsyncMock()
    service = InstagramAuthService(
        browser=MagicMock(), storage_path=tmp_path / "instagram_session.json"
    )

    assert await service._is_session_valid(context) is True
    page.locator.assert_called_once_with(service.AUTHENTICATED_UI_SELECTOR)
    authenticated_ui.wait_for.assert_awaited_once_with(
        state="visible", timeout=10_000
    )
    context.storage_state.assert_awaited_once_with(path=str(service.storage_path))
    page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_saved_session_is_invalid_when_authenticated_ui_is_missing(
    tmp_path: Path,
) -> None:
    page, authenticated_ui = make_authenticated_page()
    authenticated_ui.wait_for.side_effect = TimeoutError("not visible")
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.storage_state = AsyncMock()
    service = InstagramAuthService(
        browser=MagicMock(), storage_path=tmp_path / "instagram_session.json"
    )

    assert await service._is_session_valid(context) is False
    context.storage_state.assert_not_awaited()
    page.close.assert_awaited_once()
