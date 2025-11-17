"""Reflection middleware for self-evaluation."""

from typing import Any

from noesis.core import AgentResult, Context
from noesis.protocols import ReflectionClient


def reflection_middleware(
    client: ReflectionClient,
    *,
    write_to_memory: bool = False,
    memory_kind: str = "reflection",
):
    """Create a reflection middleware.
    
    Calls the reflection client after successful invocations to enable
    self-evaluation and learning.
    
    Args:
        client: ReflectionClient implementation
        write_to_memory: Whether to write reflection results to memory
        memory_kind: Memory kind for reflection results (default: "reflection")
        
    Returns:
        Middleware function
        
    Example:
        class MyReflectionClient:
            async def reflect(self, *, input, output, meta):
                return {"score": 0.95, "notes": "Good response"}
        
        agent.use_reflection(MyReflectionClient())
        agent.use(reflection_middleware(MyReflectionClient()))
    """

    async def middleware(ctx: Context, next_fn: Any) -> AgentResult:
        # Execute handler
        result = await next_fn()

        # Only reflect on successful invocations
        if not result.ok:
            return result

        try:
            # Call reflection client
            reflection_result = await client.reflect(
                input=ctx.input,
                output=result.output,
                meta=ctx.meta,
            )

            # Add reflection event
            ctx.add_event("reflection", result=reflection_result)

            # Optionally write to memory
            if write_to_memory:
                try:
                    reflection_text = str(reflection_result)
                    await ctx.remember(
                        content=reflection_text,
                        kind=memory_kind,
                        request_id=ctx.request_id,
                    )
                except RuntimeError:
                    # No memory store configured
                    pass

        except Exception as e:
            # Don't fail the request if reflection fails
            ctx.add_event("reflection_error", error=str(e))

        return result

    return middleware

