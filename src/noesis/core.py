"""Core abstractions for Noesis framework."""

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from noesis.errors import AgentError, ToolError
from noesis.protocols import MemoryStore, RuntimeServices


@dataclass
class RuntimeEvent:
    """Structured log of events during agent execution.
    
    Attributes:
        kind: Event type (e.g., "tool_call", "memory_read", "reflection")
        data: Event-specific data
    """

    kind: str
    data: dict


@dataclass
class AgentResult:
    """Result of an agent invocation.
    
    Attributes:
        ok: Whether execution succeeded
        output: The agent's output (if successful)
        error: Error message (if failed)
        state: Final state after execution
        events: List of events that occurred during execution
    """

    ok: bool
    output: Any = None
    error: str | None = None
    state: dict = field(default_factory=dict)
    events: list[RuntimeEvent] = field(default_factory=list)


@dataclass
class Context:
    """Execution context for a single agent invocation.
    
    Passed to handlers and middlewares. Provides access to input, state,
    tools, memory, and event logging.
    
    Attributes:
        input: Original user input
        state: Mutable per-call state
        meta: Immutable metadata (tenant, auth, env, etc.)
        events: Accumulated events during execution
        session_id: Optional session identifier
        history: Auto-loaded session history (if session_id present)
        request_id: Unique request identifier
        created_at: Request timestamp
    """

    input: dict
    state: dict
    meta: dict
    events: list[RuntimeEvent]
    session_id: str | None
    history: list | None
    request_id: str
    created_at: float
    _services: RuntimeServices

    async def tool(self, name: str, **kwargs) -> Any:
        """Call a registered tool.
        
        Args:
            name: Tool name
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ToolError: If tool execution fails
        """
        return await self._services.call_tool(self, name, **kwargs)

    async def remember(self, content: str, *, kind: str = "note", **meta) -> None:
        """Store a memory item.
        
        Args:
            content: Content to remember
            kind: Memory type (default: "note")
            **meta: Additional metadata
        """
        await self._services.memory_put(self, content, kind=kind, meta=meta)

    async def recall(
        self, query: str, *, kind: str | None = None, limit: int = 5
    ) -> list[dict]:
        """Search for memory items.
        
        Args:
            query: Search query
            kind: Optional memory type filter
            limit: Maximum results (default: 5)
            
        Returns:
            List of matching memory items
        """
        return await self._services.memory_search(
            self, query, kind=kind, limit=limit
        )

    def add_event(self, kind: str, **data) -> None:
        """Add a runtime event.
        
        Args:
            kind: Event type
            **data: Event data
        """
        self.events.append(RuntimeEvent(kind=kind, data=data))


# Type aliases
HandlerFn = Callable[[Context], Awaitable[Any]]
MiddlewareFn = Callable[[Context, Callable[[], Awaitable[AgentResult]]], Awaitable[AgentResult]]
ToolFn = Callable[..., Awaitable[Any]]


class Agent:
    """Main agent abstraction.
    
    Implements the Tool protocol so agents can be used as tools.
    Responsibilities:
    - Register handler (exactly one)
    - Register tools
    - Manage middlewares
    - Provide invoke() API
    - Hold references to optional subsystems
    - Construct execution context & runtime services
    
    Args:
        name: Agent name (used as tool name when agent-as-tool)
        description: Agent description (used as tool description)
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._handler: HandlerFn | None = None
        self._tools: dict[str, Any] = {}
        self._middlewares: list[MiddlewareFn] = []
        self._memory: MemoryStore | None = None
        self._tracer: Any = None
        self._reflection_client: Any = None
        self._reflection_opts: dict = {}

    def handler(self, fn: HandlerFn) -> HandlerFn:
        """Register the agent's handler function.
        
        Args:
            fn: Handler function taking Context and returning Any
            
        Returns:
            The same function (for decorator usage)
            
        Example:
            @agent.handler
            async def handle(ctx):
                return "Hello!"
        """
        self._handler = fn
        return fn

    def tool(self, fn=None, *, name: str | None = None, description: str = ""):
        """Register a tool or agent-as-tool.
        
        Can be used as a decorator or called directly with a tool/agent.
        
        Args:
            fn: Function or Agent to register
            name: Optional tool name (defaults to function/agent name)
            description: Tool description
            
        Returns:
            The function/agent (for decorator usage)
            
        Examples:
            # As decorator
            @agent.tool
            async def my_tool(x: int) -> int:
                return x * 2
            
            # Direct registration
            agent.tool(my_function, name="custom_name")
            
            # Agent as tool
            specialized_agent = Agent("specialist")
            agent.tool(specialized_agent)
        """
        def decorator(f):
            # Handle Agent-as-tool
            if isinstance(f, Agent):
                tool_name = name or f.name
                self._tools[tool_name] = f
            else:
                tool_name = name or f.__name__
                self._tools[tool_name] = f
            return f

        if fn is None:
            return decorator
        return decorator(fn)

    def use(self, middleware: MiddlewareFn) -> None:
        """Register a middleware.
        
        Middlewares are executed in registration order.
        
        Args:
            middleware: Middleware function
            
        Example:
            async def logging_mw(ctx, next_fn):
                print("Before")
                result = await next_fn()
                print("After")
                return result
            
            agent.use(logging_mw)
        """
        self._middlewares.append(middleware)

    def use_memory(self, store: MemoryStore) -> None:
        """Configure memory storage.
        
        Args:
            store: Memory store implementation
        """
        self._memory = store

    def use_otel(self, tracer: Any) -> None:
        """Configure OpenTelemetry tracing.
        
        Args:
            tracer: OTEL tracer instance
        """
        self._tracer = tracer

    def use_reflection(self, client: Any, **opts) -> None:
        """Configure reflection/self-evaluation.
        
        Args:
            client: Reflection client implementation
            **opts: Additional reflection options
        """
        self._reflection_client = client
        self._reflection_opts = opts

    async def invoke(
        self,
        input: dict,
        *,
        state: dict | None = None,
        meta: dict | None = None,
    ) -> AgentResult:
        """Invoke the agent with given input.
        
        Args:
            input: User input
            state: Optional initial state
            meta: Optional metadata
            
        Returns:
            AgentResult with output, state, events
            
        Raises:
            AgentError: If no handler registered
        """
        if self._handler is None:
            raise AgentError("No handler registered")

        # Import here to avoid circular dependency
        from noesis.runtime import AppRuntimeServices

        # Create context
        ctx = Context(
            input=input,
            state=state or {},
            meta=meta or {},
            events=[],
            session_id=input.get("session_id") or (meta or {}).get("session_id"),
            history=None,
            request_id=str(uuid.uuid4()),
            created_at=time.time(),
            _services=AppRuntimeServices(self),
        )

        # Build middleware chain
        async def base_handler() -> AgentResult:
            try:
                output = await self._handler(ctx)
                return AgentResult(
                    ok=True,
                    output=output,
                    state=ctx.state,
                    events=ctx.events,
                )
            except AgentError as e:
                return AgentResult(
                    ok=False,
                    error=str(e),
                    state=ctx.state,
                    events=ctx.events,
                )
            except Exception as e:
                return AgentResult(
                    ok=False,
                    error=f"internal_error: {str(e)}",
                    state=ctx.state,
                    events=ctx.events,
                )

        # Chain middlewares in reverse order
        handler = base_handler
        for mw in reversed(self._middlewares):
            current_handler = handler

            async def make_handler(middleware=mw, next_fn=current_handler):
                return await middleware(ctx, next_fn)

            handler = make_handler

        return await handler()

    # Tool protocol implementation - allows agent to be used as tool
    async def __call__(self, input: dict, **kwargs) -> Any:
        """Execute agent as a tool.
        
        When used as a tool, invokes the agent and returns output.
        
        Args:
            input: Input dict
            **kwargs: Additional arguments (merged into input)
            
        Returns:
            Agent output
            
        Raises:
            ToolError: If invocation fails
        """
        # Merge kwargs into input
        full_input = {**input, **kwargs}
        result = await self.invoke(full_input)
        if not result.ok:
            raise ToolError(result.error)
        return result.output

