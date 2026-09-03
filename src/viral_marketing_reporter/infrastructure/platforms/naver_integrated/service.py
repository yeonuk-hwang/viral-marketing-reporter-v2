import asyncio
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from loguru import logger
from playwright.async_api import ElementHandle, Page

from viral_marketing_reporter.domain.model import Keyword, Post, Screenshot, SearchResult
from viral_marketing_reporter.infrastructure.platforms.base import SearchPlatformService
from viral_marketing_reporter.infrastructure.platforms.naver_integrated.page_objects import (
    NaverIntegratedSearchPage,
)


BLOG_POST_PATTERN = re.compile(
    r"^https?://(?:m\.)?blog\.naver\.com/([^/?#]+)/([0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
CAFE_POST_PATTERN = re.compile(
    r"^https?://(?:m\.)?cafe\.naver\.com/([^/?#]+)/([0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
INFLUENCER_CONTENT_PATTERN = re.compile(r"^/[^/]+/contents/(?:internal/)?\d+/?$")


def normalize_naver_blog_url(url: str) -> str | None:
    """네이버 블로그 URL을 모바일/쿼리와 무관한 게시물 키로 변환합니다."""
    match = BLOG_POST_PATTERN.match(url.strip())
    if not match:
        return None
    return f"{match.group(1).lower()}/{match.group(2)}"


def normalize_naver_post_url(url: str) -> str | None:
    """네이버 블로그·카페 URL을 서비스 내 게시물 키로 변환합니다."""
    if key := normalize_naver_blog_url(url):
        return key
    match = CAFE_POST_PATTERN.match(url.strip())
    if not match:
        return None
    return f"{match.group(1).lower()}/{match.group(2)}"


class PlaywrightNaverIntegratedSearchService(SearchPlatformService):
    def __init__(self, page: Page) -> None:
        self.page = page

    async def _direct_matches(
        self, search_page: NaverIntegratedSearchPage, target_keys: set[str]
    ) -> dict[str, list[ElementHandle]]:
        matches: dict[str, list[ElementHandle]] = {}
        for link in await search_page.result_links():
            href = await link.get_attribute("href")
            if (
                href
                and await link.is_visible()
                and await search_page.is_primary_result_link(link)
                and (key := normalize_naver_post_url(href)) in target_keys
            ):
                matches.setdefault(key, []).append(link)
        return matches

    async def _resolve_influencer_url(
        self, client: httpx.AsyncClient, href: str
    ) -> str | None:
        parsed = urlsplit(href)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname != "in.naver.com"
            or not INFLUENCER_CONTENT_PATTERN.match(parsed.path)
        ):
            return None
        try:
            response = await client.get(href, follow_redirects=True, timeout=8)
            return normalize_naver_blog_url(str(response.url))
        except httpx.HTTPError as error:
            logger.warning(
                "인플루언서 원문 URL 확인 실패",
                event_name="influencer_redirect_failed",
                url=href,
                error=str(error),
            )
            return None

    async def _resolve_target_posts(
        self, posts_to_find: list[Post]
    ) -> dict[str, Post]:
        """블로그 및 인플루언서 입력 URL을 게시물 키로 변환합니다."""
        resolved: list[str | None] = [None] * len(posts_to_find)
        influencer_inputs: list[tuple[int, str]] = []

        for index, post in enumerate(posts_to_find):
            if key := normalize_naver_post_url(post.url):
                resolved[index] = key
            else:
                influencer_inputs.append((index, post.url))

        if influencer_inputs:
            async with httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                keys = await asyncio.gather(
                    *(
                        self._resolve_influencer_url(client, url)
                        for _, url in influencer_inputs
                    )
                )
            for (index, _), key in zip(influencer_inputs, keys, strict=True):
                resolved[index] = key

        return {
            key: post
            for post, key in zip(posts_to_find, resolved, strict=True)
            if key
        }

    async def _influencer_matches(
        self,
        search_page: NaverIntegratedSearchPage,
        target_keys: set[str],
    ) -> dict[str, list[ElementHandle]]:
        links = await search_page.influencer_content_links()
        visible_links: list[tuple[str, ElementHandle]] = []
        for link in links:
            if (
                await link.is_visible()
                and await search_page.is_primary_result_link(link)
                and (href := await link.get_attribute("href"))
            ):
                visible_links.append((href, link))

        unique_hrefs = list(dict.fromkeys(href for href, _ in visible_links))

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resolved = await asyncio.gather(
                *(self._resolve_influencer_url(client, href) for href in unique_hrefs)
            )
        key_by_href = dict(zip(unique_hrefs, resolved, strict=True))

        matches: dict[str, list[ElementHandle]] = {}
        for href, link in visible_links:
            key = key_by_href[href]
            if key and key in target_keys:
                matches.setdefault(key, []).append(link)
        return matches

    async def search_and_find_posts(
        self,
        index: int,
        keyword: Keyword,
        posts_to_find: list[Post],
        output_dir: Path,
        screenshot_all_posts: bool = False,
    ) -> SearchResult:
        search_page = NaverIntegratedSearchPage(self.page)
        try:
            await search_page.goto(keyword.text)
            await search_page.load_lazy_content()
            target_by_key = await self._resolve_target_posts(posts_to_find)
            target_keys = set(target_by_key)

            matches = await self._direct_matches(search_page, target_keys)
            influencer_matches = await self._influencer_matches(
                search_page, target_keys
            )
            for key, links in influencer_matches.items():
                matches.setdefault(key, []).extend(links)

            matched_cards: list[ElementHandle] = []
            verified_match_keys: set[str] = set()
            influencer_resolution_cache: dict[str, str | None] = {}
            async with httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                for expected_key, links in matches.items():
                    for link in links:
                        if not await link.is_visible():
                            continue
                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        actual_key = normalize_naver_post_url(href)
                        if actual_key is None:
                            if href not in influencer_resolution_cache:
                                influencer_resolution_cache[href] = (
                                    await self._resolve_influencer_url(client, href)
                                )
                            actual_key = influencer_resolution_cache[href]

                        # 검색 결과 DOM이 갱신됐거나 다른 링크를 가리키면 강조하지 않습니다.
                        if actual_key != expected_key:
                            logger.warning(
                                "강조 직전 게시물 링크 불일치",
                                event_name="integrated_match_revalidation_failed",
                                expected_key=expected_key,
                                actual_key=actual_key,
                                href=href,
                            )
                            continue

                        matched_cards.append(
                            await search_page.highlight_result_for_link(link)
                        )
                        verified_match_keys.add(expected_key)
            screenshot_paths: list[Path] = []
            if matched_cards or screenshot_all_posts:
                screenshot_paths = await search_page.take_screenshots(
                    index=index,
                    keyword=keyword.text,
                    output_dir=output_dir,
                    matched_cards=matched_cards,
                    screenshot_all_posts=screenshot_all_posts,
                )

            return SearchResult(
                found_posts=[
                    target_by_key[key]
                    for key in target_by_key
                    if key in verified_match_keys
                ],
                screenshot=Screenshot(file_path=screenshot_paths[0])
                if screenshot_paths
                else None,
                screenshots=[Screenshot(file_path=path) for path in screenshot_paths],
            )
        finally:
            await self.page.close()
