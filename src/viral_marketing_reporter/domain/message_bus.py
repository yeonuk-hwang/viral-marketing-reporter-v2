from typing import Any, Protocol

from viral_marketing_reporter.application.commands import Command
from viral_marketing_reporter.domain.events import Event


class Handler(Protocol):
    """모든 핸들러가 구현해야 하는 프로토콜"""

    async def handle(self, message: Command | Event) -> None:
        ...


class MessageBus(Protocol):
    """메시지 버스의 추상 인터페이스"""

    def register_command(self, command: type[Command], handler: Handler) -> None:
        ...

    def subscribe_to_event(self, event: type[Event], handler: Handler) -> None:
        ...

    async def handle(self, message: Command | Event) -> None:
        ...