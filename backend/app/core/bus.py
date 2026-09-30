"""Event bus for intra-app communication."""
import asyncio
from typing import Callable, Awaitable, Any

class EventBus:
    def __init__(self):
        self.subscribers: dict[str, list[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, topic: str, handler: Callable[[Any], Awaitable[None]]):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(handler)

    async def publish(self, topic: str, data: Any):
        if topic in self.subscribers:
            for handler in self.subscribers[topic]:
                # Fire and forget or await? Usually await is safer for ordering
                # but might block. We will create a task.
                asyncio.create_task(handler(data))

bus = EventBus()
