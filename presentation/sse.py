"""SSE stream dùng chung — hub có subscribe()/unsubscribe() trả queue thread-safe."""
from __future__ import annotations

import asyncio
import json
import queue
from typing import Any, AsyncIterator, Callable, Tuple

from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# item trong queue → (event name, data)
ToFrame = Callable[[Any], Tuple[str, Any]]


def sse_response(hub: Any, to_frame: ToFrame) -> StreamingResponse:
    async def _stream() -> AsyncIterator[str]:
        q = hub.subscribe()
        try:
            while True:
                try:
                    item = await asyncio.to_thread(q.get, True, 15.0)
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                event, data = to_frame(item)
                payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                yield f"event: {event}\ndata: {payload}\n\n"
        finally:
            hub.unsubscribe(q)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
