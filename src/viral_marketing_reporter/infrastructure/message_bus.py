from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Awaitable, Callable, override

from viral_marketing_reporter.application.commands import Command
from viral_marketing_reporter.domain.events import Event
from viral_marketing_reporter.domain.message_bus import Handler, Message, MessageBus


class FunctionHandler(Handler):
    """함수를 핸들러 프로토콜에 맞게 감싸는 어댑터"""

    def __init__(self, handler_func: Callable[[Message], Awaitable[None]]):
        self._handler_func = handler_func

    @override
    async def handle(self, message: Message) -> None:
        await self._handler_func(message)


class InMemoryMessageBus(MessageBus):
    """인메모리 메시지 버스 구현체"""

    def __init__(self):
        self._command_handlers: dict[type[Command], Handler] = {}
        self._event_handlers: defaultdict[type[Event], list[Handler]] = defaultdict(
            list
        )

    @override
    def register_command(self, command: type[Command], handler: Handler) -> None:
        if command in self._command_handlers:
            raise ValueError(f"Command {command.__name__} already has a handler.")
        self._command_handlers[command] = handler

    @override
    def subscribe_to_event(self, event: type[Event], handler: Handler) -> None:
        self._event_handlers[event].append(handler)

    @override
    async def handle(self, message: Command | Event) -> None:
        if isinstance(message, Event):
            for handler in self._event_handlers[type(message)]:
                await handler.handle(message)
        elif isinstance(message, Command):
            try:
                handler = self._command_handlers[type(message)]
                await handler.handle(message)
            except KeyError:
                raise ValueError(
                    f"No handler found for command {type(message).__name__}"
                )
        else:
            raise TypeError(
                f"Message must be a Command or Event, not {type(message).__name__}"
            )

