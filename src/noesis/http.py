"""FastAPI HTTP runtime for agents."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from noesis.core import Agent, AgentResult


class InvokeRequest(BaseModel):
    """Request model for /invoke endpoint."""

    input: dict = Field(..., description="User input")
    state: dict | None = Field(None, description="Optional initial state")
    meta: dict | None = Field(None, description="Optional metadata")


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


def build_fastapi(agent: Agent) -> FastAPI:
    """Build a FastAPI app for the given agent.
    
    Creates a FastAPI application with:
    - POST /invoke: Invoke the agent
    - GET /health: Health check
    
    Args:
        agent: Agent instance
        
    Returns:
        FastAPI application
        
    Example:
        agent = Agent(name="my_agent")
        
        @agent.handler
        async def handle(ctx):
            return "Hello!"
        
        app = build_fastapi(agent)
        # Run with: uvicorn main:app
    """
    app = FastAPI(
        title=f"Noesis Agent: {agent.name}",
        description=agent.description or "Agent API",
        version="0.1.0",
    )

    @app.post("/invoke", response_model=InvokeResponse)
    async def invoke(request: InvokeRequest) -> InvokeResponse:
        """Invoke the agent with given input.
        
        Args:
            request: Invoke request with input, state, meta
            
        Returns:
            Agent result with output, error, state
        """
        result: AgentResult = await agent.invoke(
            input=request.input,
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
        """Health check endpoint.
        
        Returns:
            Health status and agent name
        """
        return HealthResponse(
            status="ok",
            agent=agent.name,
        )

    return app

