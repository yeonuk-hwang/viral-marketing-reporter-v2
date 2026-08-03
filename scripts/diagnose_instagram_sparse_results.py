"""게시물이 10개 미만인 Instagram 검색 결과의 전체 서비스 흐름을 진단합니다."""

import asyncio
import argparse
from pathlib import Path

from playwright.async_api import async_playwright

from viral_marketing_reporter.domain.model import Keyword, Post
from viral_marketing_reporter.infrastructure.context import require_google_chrome
from viral_marketing_reporter.infrastructure.platforms.instagram.service import (
    PlaywrightInstagramService,
)


KEYWORDS = [
    "블루드래곤팟타이누들키트",
    "코스트코",
    "팟타이레시피",
    "블루드래곤",
    "팟타이밀키트",
    "코스트코쇼핑리스트",
    "코스트코추천",
    "코스트코팟타이레시피",
    "팟타이",
    "태국요리",
    "간편요리",
    "오늘뭐먹지",
    "코스트코추천템",
    "코스트코추천상품",
    "초간단레시피",
]
POSTS = [
    Post(url="https://www.instagram.com/reel/DbLMnqkypHo"),
    Post(url="https://www.instagram.com/reel/DbK6-2_Jqq8"),
]
SESSION_PATH = Path.home() / "Downloads/viral-reporter/instagram_session.json"
OUTPUT_DIR = Path(".diagnostics/instagram-sparse-results")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all-keywords",
        action="store_true",
        help="사용자가 제공한 15개 키워드를 모두 검사합니다.",
    )
    args = parser.parse_args()
    keywords = KEYWORDS if args.all_keywords else KEYWORDS[:1]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=require_google_chrome(),
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
            storage_state=str(SESSION_PATH),
        )
        for index, keyword_text in enumerate(keywords, 1):
            page = await context.new_page()
            service = PlaywrightInstagramService(page)
            try:
                result = await service.search_and_find_posts(
                    index=index,
                    keyword=Keyword(text=keyword_text),
                    posts_to_find=POSTS,
                    output_dir=OUTPUT_DIR,
                )
                print(
                    f"keyword={keyword_text!r} "
                    f"found={[post.url for post in result.found_posts]} "
                    f"screenshot={result.screenshot.file_path if result.screenshot else None}"
                )
            except Exception as error:
                print(f"keyword={keyword_text!r} error={error!r}")
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
