from dataclasses import dataclass

from viral_marketing_reporter.domain.model import Platform


@dataclass(frozen=True)
class TaskDTO:
    """UI에서 전달되는 개별 작업 데이터"""

    keyword: str
    urls: list[str]
    platform: Platform


@dataclass(frozen=True)
class StartSearchCommand:
    """검색 시작을 요청하는 커맨드"""

    tasks: list[TaskDTO]
