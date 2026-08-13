"""Invocation runtime and runtime services for Noesis agents."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from noesis.errors import AgentError, ToolError
from noesis.protocols import RuntimeServices

if TYPE_CHECKING:
    from noesis.core import Agent, AgentResult, Context, MiddlewareFn


class AppRuntimeServices:
    """Default implementation of RuntimeServices.

    Provides tool execution and memory operations using the agent's
    tool registry and optional memory store.
    """

    def __init__(self, agent: Agent):
        """Initialize runtime services.

        Args:
            agent: The agent instance providing tools and memory
        """
        self._agent = agent

    async def call_tool(self, ctx: Context, tool_name: str, **kwargs) -> Any:
        """Call a registered tool."""
        if tool_name not in self._agent._tools:
            raise ToolError(f"Tool not found: {tool_name}")

        tool = self._agent._tools[tool_name]
        ctx.add_event("tool_call", tool=tool_name, kwargs=kwargs)

        try:
            from noesis.core import Agent

            if isinstance(tool, Agent):
                result = await tool(input=kwargs)
            else:
                result = await tool(**kwargs)

            ctx.add_event("tool_result", tool=tool_name, success=True)
            return result
        except Exception as e:
            ctx.add_event("tool_result", tool=tool_name, success=False, error=str(e))
            raise ToolError(f"Tool '{tool_name}' failed: {str(e)}") from e

    async def memory_put(
        self, ctx: Context, content: str, *, kind: str, meta: dict
    ) -> None:
        """Store a memory item."""
        if self._agent._memory is None:
            raise RuntimeError("No memory store configured")

        ctx.add_event("memory_write", memory_kind=kind, content_length=len(content))
        await self._agent._memory.put(content=content, kind=kind, meta=meta)

    async def memory_search(
        self, ctx: Context, query: str, *, kind: str | None, limit: int
    ) -> list[dict]:
        """Search memory items."""
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


class Runtime:
    """Production runtime for executing agent invocations.

    Wraps an :class:`~noesis.core.Agent` definition and runs requests through
    a middleware pipeline. Prefer configuring production concerns here rather
    than on the agent directly.

    Example:
        agent = Agent(name="support")

        @agent.handler
        async def handle(ctx):
            return "Hello!"

        runtime = Runtime(agent).with_tracing(tracer)
        runtime.use(timeout_middleware(30.0))
        result = await runtime.invoke({"message": "hi"})
        app = serve(runtime)
    """

    def __init__(self, agent: Agent):
        """Create a runtime for the given agent definition."""
        self._agent = agent
        self._middlewares: list[MiddlewareFn] = []

    @property
    def agent(self) -> Agent:
        """The wrapped agent definition."""
        return self._agent

    def use(self, middleware: MiddlewareFn) -> Runtime:
        """Register a middleware on this runtime.

        Middlewares registered here run after any middleware registered
        directly on the agent via ``agent.use()``.
        """
        self._middlewares.append(middleware)
        return self

    def with_tracing(self, tracer: Any) -> Runtime:
        """Enable OpenTelemetry tracing for this runtime.

        Registers OTEL middleware automatically; no separate ``use_otel()``
        call is required.
        """
        from noesis.otel import otel_middleware

        self._agent._tracer = tracer
        return self.use(otel_middleware(tracer))

    def with_memory(self, store: Any) -> Runtime:
        """Configure memory storage for the wrapped agent."""
        self._agent.use_memory(store)
        return self

    async def invoke(
        self,
        input: dict | None = None,
        *,
        messages: list[dict] | None = None,
        state: dict | None = None,
        meta: dict | None = None,
    ) -> AgentResult:
        """Invoke the wrapped agent through the runtime pipeline."""
        from noesis.core import AgentResult, Context

        agent = self._agent
        if agent._handler is None:
            raise AgentError("No handler registered")

        if messages is not None:
            if input is not None:
                raise AgentError("Cannot provide both 'input' and 'messages'")
            normalized_input = {"messages": messages}
        elif input is not None:
            normalized_input = input
        else:
            raise AgentError("Must provide either 'input' or 'messages'")

        ctx = Context(
            input=normalized_input,
            state=state or {},
            meta=meta or {},
            events=[],
            session_id=normalized_input.get("session_id")
            or (meta or {}).get("session_id"),
            history=None,
            request_id=str(uuid.uuid4()),
            created_at=time.time(),
            _services=AppRuntimeServices(agent),
        )

        async def base_handler() -> AgentResult:
            output = await agent._handler(ctx)
            return AgentResult(
                ok=True,
                output=output,
                state=ctx.state,
                events=ctx.events,
            )

        handler: Callable[[], Awaitable[AgentResult]] = base_handler
        for mw in reversed(agent._middlewares + self._middlewares):
            current_handler = handler

            async def make_handler(
                middleware=mw, next_fn=current_handler
            ) -> AgentResult:
                return await middleware(ctx, next_fn)

            handler = make_handler

        try:
            return await handler()
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
