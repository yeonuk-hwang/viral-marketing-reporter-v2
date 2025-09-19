from typing import override

from viral_marketing_reporter.domain.model import Keyword, Post, SearchResult


class PlaywrightNaverBlogService:  # SearchPlatformService 프로토콜을 암묵적으로 구현
    @override
    def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post]
    ) -> SearchResult:
        print(f"네이버 블로그에서 '{keyword.text}' 키워드로 검색을 시작합니다... (구현 필요)")
        # TODO: Playwright를 사용한 실제 크롤링 및 스크린샷 로직 구현

        # 지금은 빈 결과를 반환합니다.
        return SearchResult(found_posts=[], screenshot=None)
