"""Memory store implementations for the Noesis production runtime."""

from noesis.protocols import MemoryStore

__all__ = ["InMemoryStore", "MemoryStore"]


class InMemoryStore:
    """Simple in-memory implementation of MemoryStore.

    Useful for testing and development. Not suitable for production
    as data is lost when process ends.
    """

    def __init__(self):
        """Initialize empty memory store."""
        self._items: list[dict] = []

    async def put(self, *, content: str, kind: str, meta: dict) -> None:
        """Store a memory item."""
        item = {
            "content": content,
            "kind": kind,
            **meta,
        }
        self._items.append(item)

    async def search(
        self, *, query: str, kind: str | None, limit: int
    ) -> list[dict]:
        """Search for memory items."""
        results = []

        for item in self._items:
            if kind is not None and item.get("kind") != kind:
                continue

            if query.lower() in item["content"].lower():
                results.append(item)

            if len(results) >= limit:
                break

        return results
