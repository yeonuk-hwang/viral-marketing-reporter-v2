import re
from pathlib import Path

import pytest
from playwright.async_api import Page, Route

from viral_marketing_reporter.domain.model import Keyword, Post
from viral_marketing_reporter.infrastructure.platforms.naver_blog_service import (
    PlaywrightNaverBlogService,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def naver_search_html() -> str:
    return (FIXTURE_DIR / "naver_blog_search_result.html").read_text(encoding="utf-8")


async def test_finds_specific_posts_from_html_fixture(
    page: Page, naver_search_html: str
):
    """저장된 HTML 파일을 이용해 서비스가 포스트를 정확히 찾는지 테스트합니다."""

    # 1. 테스트 데이터 준비
    keyword_to_search = Keyword(text="식사대용 쉐이크")
    posts_to_find = [
        Post(url="https://m.blog.naver.com/ghzigc3833z7/223918882395"),
        Post(url="https://blog.naver.com/yjn1221/223983155229"),
        Post(url="https://blog.naver.com/jiyea_junjin/223908006151"),
        Post(url="https://blog.naver.com/theboni/224013165053"),
    ]
    expected_found_urls = {
        "https://m.blog.naver.com/ghzigc3833z7/223918882395",
        "https://blog.naver.com/yjn1221/223983155229",
        "https://blog.naver.com/jiyea_junjin/223908006151",
    }

    # 2. 네트워크 요청 가로채기 (Mocking)
    async def handle_route(route: Route):
        await route.fulfill(body=naver_search_html, content_type="text/html; charset=utf-8")

    await page.route(re.compile(r"https://search\.naver\.com/search\.naver\?.*query=식사대용\+쉐이크"), handle_route)

    # 3. 서비스 실행
    service = PlaywrightNaverBlogService(page=page)
    result = await service.search_and_find_posts(
        keyword=keyword_to_search, posts_to_find=posts_to_find
    )

    # 4. 결과 검증
    assert result is not None
    assert len(result.found_posts) == 3

    actual_found_urls = {post.url for post in result.found_posts}
    assert actual_found_urls == expected_found_urls

    assert result.screenshot is not None
    assert result.screenshot.file_path == "식사대용_쉐이크.png"