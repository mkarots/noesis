"""Built-in middlewares for Noesis framework."""

import asyncio
from typing import Any

from noesis.core import AgentResult, Context
from noesis.errors import TimeoutError as NoesisTimeoutError


async def error_middleware(
    ctx: Context,
    next_fn: Any,
) -> AgentResult:
    """Error handling middleware.
    
    Catches exceptions and converts them to AgentResult with ok=False.
    Already handled in base handler, but can be used for custom error handling.
    
    Args:
        ctx: Current context
        next_fn: Next middleware or handler
        
    Returns:
        AgentResult with error field set if exception occurred
    """
    try:
        return await next_fn()
    except Exception as e:
        ctx.add_event("error", error=str(e), type=type(e).__name__)
        return AgentResult(
            ok=False,
            error=str(e),
            state=ctx.state,
            events=ctx.events,
        )


def timeout_middleware(seconds: float):
    """Create a timeout middleware.
    
    Wraps the entire invocation with a timeout. If exceeded, returns
    AgentResult with ok=False and timeout error.
    
    Args:
        seconds: Timeout in seconds
        
    Returns:
        Middleware function
        
    Example:
        agent.use(timeout_middleware(30.0))
    """

    async def middleware(ctx: Context, next_fn: Any) -> AgentResult:
        try:
            return await asyncio.wait_for(next_fn(), timeout=seconds)
        except asyncio.TimeoutError:
            ctx.add_event("timeout", timeout_seconds=seconds)
            return AgentResult(
                ok=False,
                error=f"timeout: exceeded {seconds}s",
                state=ctx.state,
                events=ctx.events,
            )

    return middleware


def session_middleware():
    """Create a session management middleware.
    
    Responsibilities:
    - Auto-detect session_id from input or meta
    - Load session history from memory if available
    - After success, write conversation to memory as "session" kind
    
    Returns:
        Middleware function
        
    Example:
        agent.use(session_middleware())
    """

    async def middleware(ctx: Context, next_fn: Any) -> AgentResult:
        # Session ID already set in Context during creation
        # Load history if session_id present and memory available
        if ctx.session_id:
            try:
                # Use the session_id as the query to find related session items
                history = await ctx.recall(
                    query=ctx.session_id,
                    kind="session",
                    limit=50,
                )
                ctx.history = history
                ctx.add_event("session_loaded", session_id=ctx.session_id, count=len(history))
            except RuntimeError:
                # No memory store configured, skip history loading
                pass

        # Execute handler
        result = await next_fn()

        # On success, write conversation to memory
        if result.ok and ctx.session_id:
            try:
                # Store the conversation turn
                conversation_data = {
                    "input": ctx.input,
                    "output": result.output,
                    "request_id": ctx.request_id,
                }
                await ctx.remember(
                    content=str(conversation_data),
                    kind="session",
                    session_id=ctx.session_id,
                    timestamp=ctx.created_at,
                )
                ctx.add_event("session_saved", session_id=ctx.session_id)
            except RuntimeError:
                # No memory store configured, skip saving
                pass

        return result

    return middleware

