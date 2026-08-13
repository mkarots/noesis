"""HTTP transport for the Noesis production runtime."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field, model_validator

from noesis.core import Agent, AgentResult
from noesis.runtime import Runtime


class InvokeRequest(BaseModel):
    """Request model for /invoke endpoint."""

    input: dict | None = Field(None, description="User input dict")
    messages: list[dict] | None = Field(None, description="OpenAI-style messages list")
    state: dict | None = Field(None, description="Optional initial state")
    meta: dict | None = Field(None, description="Optional metadata")

    @model_validator(mode="after")
    def validate_input_or_messages(self):
        """Validate that either input or messages is provided."""
        if self.input is None and self.messages is None:
            raise ValueError("Must provide either 'input' or 'messages'")
        if self.input is not None and self.messages is not None:
            raise ValueError("Cannot provide both 'input' and 'messages'")
        return self


class InvokeResponse(BaseModel):
    """Response model for /invoke endpoint."""

    ok: bool = Field(..., description="Whether execution succeeded")
    output: Any = Field(None, description="Agent output")
    error: str | None = Field(None, description="Error message if failed")
    state: dict = Field(default_factory=dict, description="Final state")


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""

    status: str = Field(..., description="Health status")
    agent: str = Field(..., description="Agent name")


def _resolve_runtime(agent_or_runtime: Agent | Runtime) -> tuple[Runtime, Agent]:
    """Return a runtime and its agent definition."""
    if isinstance(agent_or_runtime, Runtime):
        return agent_or_runtime, agent_or_runtime.agent
    return Runtime(agent_or_runtime), agent_or_runtime


def serve(agent_or_runtime: Agent | Runtime) -> FastAPI:
    """Serve an agent over HTTP.

    Preferred entry point for exposing agents as a production HTTP API.
    Accepts either an :class:`~noesis.core.Agent` or a configured
    :class:`~noesis.runtime.Runtime`.

    Example:
        runtime = Runtime(agent).with_tracing(tracer)
        app = serve(runtime)
    """
    runtime, agent = _resolve_runtime(agent_or_runtime)

    app = FastAPI(
        title=f"Noesis Agent: {agent.name}",
        description=agent.description or "Agent API",
        version="0.1.0",
    )

    @app.post("/invoke", response_model=InvokeResponse)
    async def invoke(request: InvokeRequest) -> InvokeResponse:
        """Invoke the agent with given input."""
        result: AgentResult = await runtime.invoke(
            input=request.input,
            messages=request.messages,
            state=request.state,
            meta=request.meta,
        )

        return InvokeResponse(
            ok=result.ok,
            output=result.output,
            error=result.error,
            state=result.state,
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(status="ok", agent=agent.name)

    return app


def build_fastapi(agent_or_runtime: Agent | Runtime) -> FastAPI:
    """Build a FastAPI app for the given agent or runtime.

    Alias for :func:`serve`. Prefer ``serve()`` in new code.
    """
    return serve(agent_or_runtime)
