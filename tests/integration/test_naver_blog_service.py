import re
from pathlib import Path

import pytest
from playwright.async_api import Page, Route

from viral_marketing_reporter.domain.model import Keyword, Post
from viral_marketing_reporter.infrastructure.platforms.naver_blog.service import (
    PlaywrightNaverBlogService,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"


@pytest.fixture
def naver_blog_search_html() -> str:
    return (FIXTURE_DIR / "naver_blog_search_result.html").read_text(encoding="utf-8")


@pytest.fixture
def naver_blog_search_no_result_html() -> str:
    return (FIXTURE_DIR / "naver_blog_search_no_result.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def naver_blog_search_less_than_10_result_html() -> str:
    return (FIXTURE_DIR / "naver_blog_search_less_than_10.html").read_text(
        encoding="utf-8"
    )


async def test_finds_specific_posts_from_html_fixture(
    page: Page, naver_blog_search_html: str
):
    """저장된 HTML 파일을 이용해 서비스가 포스트를 정확히 찾는지 테스트합니다."""
    output_dir = SCREENSHOT_DIR
    index = 1
    keyword = Keyword(text="식사대용 쉐이크")
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
    expected_screenshot_path = output_dir / "1_식사대용_쉐이크.png"

    search_url_pattern = re.compile(r"https://search\.naver\.com/search\.naver\?.*")

    async def handle_route(route: Route):
        await route.fulfill(
            body=naver_blog_search_html, content_type="text/html; charset=utf-8"
        )

    await page.route(search_url_pattern, handle_route)

    service = PlaywrightNaverBlogService(page=page)
    result = await service.search_and_find_posts(
        index=index,
        keyword=keyword,
        posts_to_find=posts_to_find,
        output_dir=output_dir,
    )

    assert result is not None
    assert len(result.found_posts) == 3
    actual_found_urls = {post.url for post in result.found_posts}
    assert actual_found_urls == expected_found_urls
    assert result.screenshot is not None
    assert Path(result.screenshot.file_path) == expected_screenshot_path
    assert expected_screenshot_path.exists()


async def test_no_results_found(
    page: Page, naver_blog_search_no_result_html: str
):
    """검색 결과가 없는 페이지에서 아무것도 찾지 않고 스크린샷도 생성하지 않는지 검증합니다."""
    output_dir = SCREENSHOT_DIR
    keyword = Keyword(text="MABBDDASD")
    posts_to_find = [Post(url="https://blog.naver.com/some/post")]

    search_url_pattern = re.compile(r"https://search\.naver\.com/search\.naver\?.*")

    async def handle_route(route: Route):
        await route.fulfill(
            body=naver_blog_search_no_result_html,
            content_type="text/html; charset=utf-8",
        )

    await page.route(search_url_pattern, handle_route)

    service = PlaywrightNaverBlogService(page=page)
    result = await service.search_and_find_posts(
        index=1, keyword=keyword, posts_to_find=posts_to_find, output_dir=output_dir
    )

    assert result is not None
    assert len(result.found_posts) == 0
    assert result.screenshot is None
    assert not (output_dir / "MABBDDASD.png").exists()


async def test_less_than_10_results_found(
    page: Page, naver_blog_search_less_than_10_result_html: str
):
    """10개 미만의 검색 결과에서도 정확히 포스트를 찾아내는지 검증합니다."""
    output_dir = SCREENSHOT_DIR
    keyword = Keyword(text="playwright 동시성 문제")
    posts_to_find = [
        Post(url="https://blog.naver.com/genycho/223734017762"),
        Post(url="https://blog.naver.com/jeremiahjun/223993755718"),
        Post(url="https://blog.naver.com/bkpark777/223944594259"),
        Post(url="https://blog.naver.com/nonexistent/post"),
    ]
    expected_found_urls = {
        "https://blog.naver.com/genycho/223734017762",
        "https://blog.naver.com/jeremiahjun/223993755718",
        "https://blog.naver.com/bkpark777/223944594259",
    }
    expected_screenshot_path = output_dir / "1_playwright_동시성_문제.png"

    search_url_pattern = re.compile(r"https://search\.naver\.com/search\.naver\?.*")

    async def handle_route(route: Route):
        await route.fulfill(
            body=naver_blog_search_less_than_10_result_html,
            content_type="text/html; charset=utf-8",
        )

    await page.route(search_url_pattern, handle_route)

    service = PlaywrightNaverBlogService(page=page)
    result = await service.search_and_find_posts(
        index=1,
        keyword=keyword,
        posts_to_find=posts_to_find,
        output_dir=output_dir,
    )

    assert result is not None
    assert len(result.found_posts) == 3
    actual_found_urls = {post.url for post in result.found_posts}
    assert actual_found_urls == expected_found_urls
    assert result.screenshot is not None
    assert Path(result.screenshot.file_path) == expected_screenshot_path
    assert expected_screenshot_path.exists()