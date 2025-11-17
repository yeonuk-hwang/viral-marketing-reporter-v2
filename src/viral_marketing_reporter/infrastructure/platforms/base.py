from pathlib import Path
from typing import Protocol

from viral_marketing_reporter.domain.model import Keyword, Post, SearchResult


class SearchPlatformService(Protocol):
    async def search_and_find_posts(
        self,
        index: int,
        keyword: Keyword,
        posts_to_find: list[Post],
        output_dir: Path,
        screenshot_all_posts: bool = False,
    ) -> SearchResult:
        """키워드로 플랫폼을 검색하고, 찾아야 할 포스트가 상위 10개 안에 있는지 확인합니다.

        Args:
            index: 작업 인덱스
            keyword: 검색 키워드
            posts_to_find: 찾아야 할 포스트 목록
            output_dir: 스크린샷 저장 디렉토리
            screenshot_all_posts: True면 모든 포스트의 스크린샷 촬영, False면 매칭된 포스트만
        """
        ...
