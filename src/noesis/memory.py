"""Memory store interface and helpers."""

from typing import Protocol


class MemoryStore(Protocol):
    """Protocol for memory storage backends.
    
    Memory stores must implement put and search operations.
    """

    async def put(self, *, content: str, kind: str, meta: dict) -> None:
        """Store a memory item.
        
        Args:
            content: The content to store
            kind: Type of memory (e.g., "note", "session")
            meta: Additional metadata
        """
        ...

    async def search(
        self, *, query: str, kind: str | None, limit: int
    ) -> list[dict]:
        """Search for memory items.
        
        Args:
            query: Search query
            kind: Optional filter by memory type
            limit: Maximum number of results
            
        Returns:
            List of memory items as dicts with at least 'content' field
        """
        ...


class InMemoryStore:
    """Simple in-memory implementation of MemoryStore.
    
    Useful for testing and development. Not suitable for production
    as data is lost when process ends.
    """

    def __init__(self):
        """Initialize empty memory store."""
        self._items: list[dict] = []

    async def put(self, *, content: str, kind: str, meta: dict) -> None:
        """Store a memory item.
        
        Args:
            content: The content to store
            kind: Type of memory
            meta: Additional metadata
        """
        item = {
            "content": content,
            "kind": kind,
            **meta,
        }
        self._items.append(item)

    async def search(
        self, *, query: str, kind: str | None, limit: int
    ) -> list[dict]:
        """Search for memory items.
        
        Simple implementation that filters by kind and returns items
        where content contains the query string.
        
        Args:
            query: Search query (substring match)
            kind: Optional filter by memory type
            limit: Maximum number of results
            
        Returns:
            List of matching memory items
        """
        results = []
        
        for item in self._items:
            # Filter by kind if specified
            if kind is not None and item.get("kind") != kind:
                continue
            
            # Simple substring search
            if query.lower() in item["content"].lower():
                results.append(item)
                
            if len(results) >= limit:
                break
        
        return results

