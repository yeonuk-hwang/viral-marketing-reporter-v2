
import asyncio
from collections import defaultdict
from typing import Callable, Coroutine, Type

from viral_marketing_reporter.application.commands import Command
from viral_marketing_reporter.domain.events import Event

Message = Command | Event

_event_handlers: defaultdict[Type[Event], list[Callable[..., Coroutine]]] = defaultdict(list)
_command_handlers: dict[Type[Command], Callable[..., Coroutine]] = {}


def subscribe_to_event(event: Type[Event], handler: Callable[..., Coroutine]):
    """이벤트에 대한 핸들러를 등록합니다."""
    _event_handlers[event].append(handler)


def register_command(command: Type[Command], handler: Callable[..., Coroutine]):
    """커맨드에 대한 핸들러를 등록합니다. 커맨드는 오직 하나의 핸들러만 가질 수 있습니다."""
    if command in _command_handlers:
        raise ValueError(f"Command {command.__name__} already has a handler.")
    _command_handlers[command] = handler


async def handle(message: Message):
    """커맨드 또는 이벤트를 적절한 핸들러에게 전달합니다."""
    if isinstance(message, Event):
        # 이벤트인 경우, 등록된 모든 핸들러를 실행합니다.
        for handler in _event_handlers[type(message)]:
            await handler(message)
    elif isinstance(message, Command):
        # 커맨드인 경우, 등록된 단일 핸들러를 실행합니다.
        try:
            handler = _command_handlers[type(message)]
            await handler(message)
        except KeyError:
            raise ValueError(f"No handler found for command {type(message).__name__}")
    else:
        raise TypeError(f"Message must be a Command or Event, not {type(message).__name__}")
