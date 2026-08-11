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

    async def result_links(self) -> list[Locator]:
        return await self.main_pack.locator("a[href]").all()

    async def influencer_content_links(self) -> list[Locator]:
        return await self.main_pack.locator(
            "a[href*='in.naver.com/'][href*='/contents/']"
        ).all()

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

    async def highlight_result_for_link(self, link: Locator) -> ElementHandle:
        """링크를 포함하는 가장 가까운 결과 카드에 테두리를 표시합니다."""
        card = await link.evaluate_handle(
            """anchor => {
                let element = anchor;
                let fallback = anchor;
                while (element && element.id !== 'main_pack') {
                    const box = element.getBoundingClientRect();
                    if (box.width >= 450 && box.height >= 90 && box.height <= 900) {
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
                fallback.style.outline = '3px solid red';
                fallback.style.outlineOffset = '3px';
                fallback.dataset.viralReporterMatch = 'true';
                return fallback;
            }"""
        )
        element = card.as_element()
        if not element:
            raise ScreenshotTargetMissingError("매칭된 결과 카드를 찾지 못했습니다.")
        return element

    async def group_cards_by_area(
        self, matched_cards: list[ElementHandle]
    ) -> list[list[ElementHandle]]:
        """#main_pack의 직계 결과 블록을 기준으로 매칭 카드를 그룹화합니다."""
        grouped: dict[int, list[ElementHandle]] = {}
        for card in matched_cards:
            area_index = await card.evaluate(
                """card => {
                    const main = document.querySelector('#main_pack');
                    let block = card;
                    while (block.parentElement && block.parentElement !== main) {
                        block = block.parentElement;
                    }
                    return [...main.children].indexOf(block);
                }"""
            )
            grouped.setdefault(area_index, []).append(card)
        return list(grouped.values())

    async def take_screenshots(
        self,
        index: int,
        keyword: str,
        output_dir: Path,
        matched_cards: list[ElementHandle],
        screenshot_all_posts: bool,
    ) -> list[Path]:
        groups = (
            await self.group_cards_by_area(matched_cards)
            if matched_cards
            else [[]]
        )
        paths: list[Path] = []
        for area_number, cards in enumerate(groups, start=1):
            for card in cards:
                await card.evaluate(
                    "card => card.dataset.viralReporterCapture = 'true'"
                )
            try:
                await self.page.evaluate(
                    """() => {
                        for (const card of document.querySelectorAll(
                            '[data-viral-reporter-match="true"]'
                        )) {
                            card.style.outlineColor =
                                card.dataset.viralReporterCapture === 'true'
                                    ? 'red'
                                    : 'transparent';
                        }
                    }"""
                )
                paths.append(
                    await self.take_screenshot(
                        index=index,
                        keyword=keyword,
                        output_dir=output_dir,
                        matched_cards=cards,
                        screenshot_all_posts=screenshot_all_posts,
                        area_number=area_number if len(groups) > 1 else None,
                    )
                )
            finally:
                for card in cards:
                    await card.evaluate(
                        "card => delete card.dataset.viralReporterCapture"
                    )
        return paths

    async def take_screenshot(
        self,
        index: int,
        keyword: str,
        output_dir: Path,
        matched_cards: list[ElementHandle],
        screenshot_all_posts: bool,
        area_number: int | None = None,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        area_suffix = f"_영역{area_number}" if area_number else ""
        path = output_dir / f"{index}_{keyword.replace(' ', '_')}{area_suffix}.png"
        await self.page.screenshot(path=path, full_page=True)
        return path
