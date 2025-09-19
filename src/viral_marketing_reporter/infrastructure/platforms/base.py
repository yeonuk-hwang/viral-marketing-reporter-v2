from typing import Protocol

from viral_marketing_reporter.domain.model import Keyword, Post, SearchResult


class SearchPlatformService(Protocol):
    async def search_and_find_posts(
        self, keyword: Keyword, posts_to_find: list[Post]
    ) -> SearchResult:
        """키워드로 플랫폼을 검색하고, 찾아야 할 포스트가 상위 10개 안에 있는지 확인합니다."""
        ...
