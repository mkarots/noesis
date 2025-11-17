"""OpenTelemetry middleware for distributed tracing."""

from typing import Any

from noesis.core import AgentResult, Context


def otel_middleware(tracer: Any):
    """Create an OpenTelemetry tracing middleware.
    
    Wraps agent invocations in OTEL spans with context attributes
    and events.
    
    Args:
        tracer: OpenTelemetry tracer instance
        
    Returns:
        Middleware function
        
    Example:
        from opentelemetry import trace
        
        tracer = trace.get_tracer(__name__)
        agent.use_otel(tracer)
        agent.use(otel_middleware(tracer))
    """

    async def middleware(ctx: Context, next_fn: Any) -> AgentResult:
        # Start a span
        with tracer.start_as_current_span("agent.handle") as span:
            # Add basic context attributes
            span.set_attribute("agent.request_id", ctx.request_id)
            span.set_attribute("agent.created_at", ctx.created_at)
            
            if ctx.session_id:
                span.set_attribute("agent.session_id", ctx.session_id)

            try:
                # Execute handler
                result = await next_fn()

                # Mark success/failure
                span.set_attribute("agent.ok", result.ok)
                
                if not result.ok:
                    span.set_attribute("agent.error", result.error or "")
                    span.set_status(
                        status=1,  # StatusCode.ERROR
                        description=result.error or "Agent execution failed",
                    )
                else:
                    span.set_status(status=0)  # StatusCode.OK
            except Exception as e:
                # Handle exceptions that weren't caught
                span.set_attribute("agent.ok", False)
                span.set_attribute("agent.error", str(e))
                span.set_status(
                    status=1,  # StatusCode.ERROR
                    description=f"Exception: {str(e)}",
                )
                raise

            # Attach events as OTEL events
            for event in ctx.events:
                # Convert event data to attributes
                attributes = {
                    f"event.{key}": str(value)
                    for key, value in event.data.items()
                }
                span.add_event(
                    name=f"agent.{event.kind}",
                    attributes=attributes,
                )

            return result

    return middleware

