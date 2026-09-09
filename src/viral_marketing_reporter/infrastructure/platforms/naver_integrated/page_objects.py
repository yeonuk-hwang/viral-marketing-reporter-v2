from pathlib import Path
from urllib.parse import quote

from playwright.async_api import ElementHandle, Locator, Page

from viral_marketing_reporter.infrastructure.exceptions import (
    ScreenshotTargetMissingError,
)


class NaverIntegratedSearchPage:
    """네이버 통합검색 결과 페이지에 대한 상호작용을 캡슐화합니다."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.main_pack: Locator = page.locator("#main_pack")

    async def goto(self, keyword: str) -> None:
        search_url = (
            "https://search.naver.com/search.naver"
            f"?where=nexearch&sm=top_hty&query={quote(keyword)}"
        )
        await self.page.goto(search_url, wait_until="domcontentloaded")
        await self.main_pack.wait_for(state="visible", timeout=60_000)

    async def result_links(self) -> list[ElementHandle]:
        """현재 DOM에 고정된 링크 핸들을 반환합니다.

        네이버가 검색 결과 DOM을 비동기로 갱신하므로 nth 기반 Locator를 보관하면
        나중에 다른 링크를 가리킬 수 있습니다.
        """
        return await self.main_pack.locator("a[href]").element_handles()

    async def influencer_content_links(self) -> list[ElementHandle]:
        return await self.main_pack.locator(
            "a[href*='in.naver.com/'][href*='/contents/']"
        ).element_handles()

    async def is_primary_result_link(self, link: ElementHandle) -> bool:
        """연관·시리즈·클러스터 링크가 아닌 실제 노출 링크인지 확인합니다."""
        return await link.evaluate(
            """anchor => {
                const heatmapTarget = (
                    anchor.getAttribute('data-heatmap-target') || ''
                ).toLowerCase();
                if (/(?:^|[._-])(series|related|cluster)(?:$|[._-])/.test(
                    heatmapTarget
                )) return false;

                let element = anchor;
                while (element && element.id !== 'main_pack') {
                    const marker = [
                        element.getAttribute('data-template-id') || '',
                        element.getAttribute('data-testid') || '',
                        element.getAttribute('data-module') || '',
                    ].join(' ').toLowerCase();
                    if (/(?:^|[ _-])(series|related|cluster)(?:$|[ _-])/.test(
                        marker
                    )) return false;
                    element = element.parentElement;
                }
                return true;
            }"""
        )

    async def load_lazy_content(self) -> None:
        """전체 페이지를 순회해 지연 로딩 이미지와 썸네일을 미리 불러옵니다."""
        await self.page.evaluate(
            """async () => {
                const delay = milliseconds => new Promise(
                    resolve => setTimeout(resolve, milliseconds)
                );
                const step = Math.max(500, Math.floor(window.innerHeight * 0.75));
                let previousHeight = 0;
                let stablePasses = 0;
                let passes = 0;

                while (stablePasses < 2 && passes < 4) {
                    passes += 1;
                    const height = document.documentElement.scrollHeight;
                    for (let y = 0; y < height; y += step) {
                        window.scrollTo(0, y);
                        await delay(80);
                    }
                    window.scrollTo(0, document.documentElement.scrollHeight);
                    await delay(250);

                    const currentHeight = document.documentElement.scrollHeight;
                    stablePasses = currentHeight === previousHeight
                        ? stablePasses + 1
                        : 0;
                    previousHeight = currentHeight;
                }
                window.scrollTo(0, 0);
                await delay(500);
            }"""
        )

    async def remove_whale_promotional_banners(self) -> None:
        """검색 결과 캡처를 가리는 네이버 웨일 설치 배너를 제거합니다."""
        await self.page.evaluate(
            """() => {
                document.querySelectorAll(
                    '._fe_whale_banner_top, ._fe_whale_banner_bottom'
                ).forEach(element => element.remove());
                document.querySelector('#header_wrap')
                    ?.classList.remove('type_whale_banner');
            }"""
        )

    async def highlight_result_for_link(self, link: ElementHandle) -> ElementHandle:
        """링크를 포함하는 가장 가까운 결과 카드에 테두리를 표시합니다."""
        await self.page.evaluate(
            """() => {
                if (document.querySelector('[data-viral-reporter-highlight-style]')) {
                    return;
                }
                const style = document.createElement('style');
                style.dataset.viralReporterHighlightStyle = 'true';
                style.textContent = `
                    [data-viral-reporter-match="true"] {
                        position: relative !important;
                        isolation: isolate;
                    }
                    [data-viral-reporter-match="true"]::after {
                        content: "";
                        position: absolute;
                        inset: 0;
                        box-sizing: border-box;
                        border: 3px solid red;
                        border-radius: inherit;
                        pointer-events: none;
                        z-index: 2147483647;
                    }
                `;
                document.head.appendChild(style);
            }"""
        )
        card = await link.evaluate_handle(
            """anchor => {
                let element = anchor;
                let fallback = anchor;
                while (element && element.id !== 'main_pack') {
                    const box = element.getBoundingClientRect();
                    if (box.width >= 450 && box.height >= 90 && box.height <= 600) {
                        if ([...element.classList].some(name =>
                            name.includes('single-intention-item-list')
                        )) break;
                        const destinations = new Set(
                            [...element.querySelectorAll('a[href]')]
                                .map(link => {
                                    try {
                                        const url = new URL(link.href);
                                        if (url.hostname === 'in.naver.com' &&
                                            new RegExp(
                                                '/contents/(?:internal/)?[0-9]+'
                                            ).test(url.pathname)) {
                                            return url.hostname + url.pathname;
                                        }
                                        if (url.hostname === 'blog.naver.com' ||
                                            url.hostname === 'm.blog.naver.com') {
                                            const parts = url.pathname.split('/').filter(Boolean);
                                            if (parts.length >= 2 && /^\\d+$/.test(parts[1])) {
                                                return 'blog.naver.com/' + parts[0] + '/' + parts[1];
                                            }
                                        }
                                        if (url.hostname === 'cafe.naver.com' ||
                                            url.hostname === 'm.cafe.naver.com') {
                                            const parts = url.pathname.split('/').filter(Boolean);
                                            if (parts.length >= 2 && /^\\d+$/.test(parts[1])) {
                                                return 'cafe.naver.com/' + parts[0] + '/' + parts[1];
                                            }
                                            const articleId = url.searchParams.get('articleid');
                                            const clubId = url.searchParams.get('clubid');
                                            if (articleId) {
                                                return 'cafe.naver.com/' + (clubId || '') + '/' + articleId;
                                            }
                                        }
                                    } catch (_) {}
                                    return null;
                                })
                                .filter(Boolean)
                        );
                        if (destinations.size > 1) break;
                        fallback = element;
                    }
                    element = element.parentElement;
                }
                fallback.dataset.viralReporterMatch = 'true';
                return fallback;
            }"""
        )
        element = card.as_element()
        if not element:
            raise ScreenshotTargetMissingError("매칭된 결과 카드를 찾지 못했습니다.")
        return element

    async def take_screenshots(
        self,
        index: int,
        keyword: str,
        output_dir: Path,
        matched_cards: list[ElementHandle],
        screenshot_all_posts: bool,
    ) -> list[Path]:
        return [
            await self.take_screenshot(
                index=index,
                keyword=keyword,
                output_dir=output_dir,
                matched_cards=matched_cards,
                screenshot_all_posts=screenshot_all_posts,
            )
        ]

    async def take_screenshot(
        self,
        index: int,
        keyword: str,
        output_dir: Path,
        matched_cards: list[ElementHandle],
        screenshot_all_posts: bool,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{index}_{keyword.replace(' ', '_')}.png"
        content_bounds = await self.page.evaluate(
            """() => {
                const mainPack = document.querySelector('#main_pack');
                if (!mainPack) return null;
                const box = mainPack.getBoundingClientRect();
                return box.width > 0 ? {width: box.width} : null;
            }"""
        )
        if not content_bounds:
            raise ScreenshotTargetMissingError(
                "통합검색 페이지의 캡처 영역을 계산하지 못했습니다."
            )
        viewport = self.page.viewport_size or {"width": 1920, "height": 1080}
        await self.page.set_viewport_size(
            {
                "width": max(700, round(content_bounds["width"])),
                "height": viewport["height"],
            }
        )
        # 폭 변경 시 네이버가 결과 카드와 이미지를 다시 렌더링합니다.
        await self.load_lazy_content()
        await self.remove_whale_promotional_banners()
        document_height = await self.page.evaluate(
            "() => document.documentElement.scrollHeight"
        )
        await self.page.set_viewport_size(
            {
                "width": max(700, round(content_bounds["width"])),
                "height": round(document_height),
            }
        )
        await self.page.screenshot(path=path)
        return path
