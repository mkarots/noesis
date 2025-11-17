"""Runtime services implementation."""

from typing import TYPE_CHECKING, Any

from noesis.errors import ToolError
from noesis.protocols import RuntimeServices

if TYPE_CHECKING:
    from noesis.core import Agent, Context


class AppRuntimeServices:
    """Default implementation of RuntimeServices.
    
    Provides tool execution and memory operations using the agent's
    tool registry and optional memory store.
    """

    def __init__(self, agent: "Agent"):
        """Initialize runtime services.
        
        Args:
            agent: The agent instance providing tools and memory
        """
        self._agent = agent

    async def call_tool(self, ctx: "Context", name: str, **kwargs) -> Any:
        """Call a registered tool.
        
        Args:
            ctx: Current context
            name: Tool name
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ToolError: If tool not found or execution fails
        """
        if name not in self._agent._tools:
            raise ToolError(f"Tool not found: {name}")

        tool = self._agent._tools[name]
        
        # Log tool call event
        ctx.add_event("tool_call", tool=name, kwargs=kwargs)

        try:
            # Handle Agent-as-tool (has __call__ method)
            if isinstance(tool, type(self._agent)):
                # Pass input dict to agent
                result = await tool(input=kwargs)
            else:
                # Regular function tool
                result = await tool(**kwargs)
            
            ctx.add_event("tool_result", tool=name, success=True)
            return result
        except Exception as e:
            ctx.add_event("tool_result", tool=name, success=False, error=str(e))
            raise ToolError(f"Tool '{name}' failed: {str(e)}") from e

    async def memory_put(
        self, ctx: "Context", content: str, *, kind: str, meta: dict
    ) -> None:
        """Store a memory item.
        
        Args:
            ctx: Current context
            content: Content to store
            kind: Memory type
            meta: Additional metadata
            
        Raises:
            RuntimeError: If no memory store configured
        """
        if self._agent._memory is None:
            raise RuntimeError("No memory store configured")

        ctx.add_event("memory_write", memory_kind=kind, content_length=len(content))
        
        await self._agent._memory.put(
            content=content,
            kind=kind,
            meta=meta,
        )

    async def memory_search(
        self, ctx: "Context", query: str, *, kind: str | None, limit: int
    ) -> list[dict]:
        """Search memory items.
        
        Args:
            ctx: Current context
            query: Search query
            kind: Optional memory type filter
            limit: Max results
            
        Returns:
            List of memory items
            
        Raises:
            RuntimeError: If no memory store configured
        """
        if self._agent._memory is None:
            raise RuntimeError("No memory store configured")

        ctx.add_event("memory_read", query=query, memory_kind=kind, limit=limit)
        
        results = await self._agent._memory.search(
            query=query,
            kind=kind,
            limit=limit,
        )
        
        ctx.add_event("memory_result", count=len(results))
        return results

