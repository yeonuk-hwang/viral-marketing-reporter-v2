"""Instagram 검색 그리드의 비디오 렌더링 상태를 진단합니다."""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from viral_marketing_reporter.infrastructure.platforms.instagram.page_objects import (
    InstagramSearchPage,
)
from viral_marketing_reporter.infrastructure.context import require_google_chrome


KEYWORD = "코스트코"
TARGET_ID = "DMzlYdFBhqP"
OUTPUT_DIR = Path(".diagnostics/instagram-video")
STORAGE_STATE = Path.home() / "Downloads/viral-reporter/instagram_session.json"


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, object]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=require_google_chrome()
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
            storage_state=str(STORAGE_STATE),
        )
        page = await context.new_page()

        page.on(
            "requestfailed",
            lambda request: failures.append(
                {"url": request.url, "failure": request.failure}
            ),
        )

        search_page = InstagramSearchPage(page)
        await search_page.goto(KEYWORD)
        posts = await search_page.get_top_10_posts()
        await posts[-1].scroll_into_view_if_needed()
        await page.wait_for_timeout(2_000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(2_000)

        before = await collect_state(page)
        wait_result = await search_page._wait_for_post_media()
        await page.wait_for_timeout(1_000)
        after = await collect_state(page)

        await page.screenshot(path=OUTPUT_DIR / "grid.png", full_page=True)
        target_post = None
        for post in posts:
            if TARGET_ID in ((await post.get_attribute("href")) or ""):
                target_post = post
                break
        if target_post is None:
            raise RuntimeError(f"Target post not found: {TARGET_ID}")
        await search_page.highlight_element(target_post)
        await search_page.take_screenshot_of_results(1, KEYWORD, OUTPUT_DIR)
        for index, post in enumerate(posts, 1):
            await post.screenshot(path=OUTPUT_DIR / f"post-{index}.png")

        report = {
            "before": before,
            "wait_result": wait_result,
            "after": after,
            "request_failures": failures,
        }
        (OUTPUT_DIR / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await browser.close()

    target = next(
        (post for post in after["posts"] if TARGET_ID in (post["href"] or "")), None
    )
    print(json.dumps({"wait_result": wait_result, "target": target}, ensure_ascii=False, indent=2))
    print(f"Report: {OUTPUT_DIR / 'report.json'}")


async def collect_state(page):
    return await page.evaluate(
        """
        ({selector}) => ({
            posts: [...document.querySelectorAll(selector)].slice(0, 10).map((post, index) => ({
                index: index + 1,
                href: post.getAttribute('href'),
                box: post.getBoundingClientRect().toJSON(),
                html: post.innerHTML.slice(0, 1000),
                media: [...post.querySelectorAll('img, video')].map(element => ({
                    tag: element.tagName,
                    src: element.currentSrc || element.src || null,
                    box: element.getBoundingClientRect().toJSON(),
                    complete: element instanceof HTMLImageElement ? element.complete : null,
                    naturalWidth: element instanceof HTMLImageElement ? element.naturalWidth : null,
                    readyState: element instanceof HTMLVideoElement ? element.readyState : null,
                    networkState: element instanceof HTMLVideoElement ? element.networkState : null,
                    videoWidth: element instanceof HTMLVideoElement ? element.videoWidth : null,
                    videoHeight: element instanceof HTMLVideoElement ? element.videoHeight : null,
                    paused: element instanceof HTMLVideoElement ? element.paused : null,
                    error: element instanceof HTMLVideoElement && element.error
                        ? {code: element.error.code, message: element.error.message}
                        : null,
                })),
            })),
            allVideos: [...document.querySelectorAll('video')].map(video => ({
                src: video.currentSrc || video.src,
                readyState: video.readyState,
                videoWidth: video.videoWidth,
                box: video.getBoundingClientRect().toJSON(),
                closestPost: video.closest(selector)?.getAttribute('href') || null,
            })),
        })
        """,
        {"selector": InstagramSearchPage.POST_SELECTOR},
    )


if __name__ == "__main__":
    asyncio.run(main())
