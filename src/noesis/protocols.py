"""Protocol definitions for Noesis framework."""

from typing import Any, Protocol


class Tool(Protocol):
    """Protocol for callable tools.
    
    Agents implement this protocol, allowing them to be used as tools.
    """

    name: str
    description: str

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given kwargs."""
        ...


class MemoryStore(Protocol):
    """Protocol for memory storage backends."""

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
            List of memory items as dicts
        """
        ...


class ReflectionClient(Protocol):
    """Protocol for reflection/self-evaluation clients."""

    async def reflect(self, *, input: dict, output: Any, meta: dict) -> dict:
        """Reflect on an agent interaction.
        
        Args:
            input: The original input
            output: The agent's output
            meta: Additional metadata
            
        Returns:
            Reflection results as a dict
        """
        ...


class RuntimeServices(Protocol):
    """Protocol for runtime services available to handlers.
    
    Provides tool execution and memory operations.
    """

    async def call_tool(self, ctx: Any, name: str, **kwargs) -> Any:
        """Call a registered tool.
        
        Args:
            ctx: Current context
            name: Tool name
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        ...

    async def memory_put(
        self, ctx: Any, content: str, *, kind: str, meta: dict
    ) -> None:
        """Store a memory item.
        
        Args:
            ctx: Current context
            content: Content to store
            kind: Memory type
            meta: Additional metadata
        """
        ...

    async def memory_search(
        self, ctx: Any, query: str, *, kind: str | None, limit: int
    ) -> list[dict]:
        """Search memory items.
        
        Args:
            ctx: Current context
            query: Search query
            kind: Optional memory type filter
            limit: Max results
            
        Returns:
            List of memory items
        """
        ...

