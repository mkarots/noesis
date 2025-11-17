# Noesis Agent Framework V3

A minimal, composable agent framework built on simplicity, modularity, and extensibility.

## Design Principles

- **Simplicity**: Everything understandable in one sitting
- **Composability**: Features added through middlewares and registries
- **Modularity**: Memory, tools, OTEL, reflection, and sessions are optional
- **Extensibility**: Clear interfaces, no globals, no magic
- **Single Object UX**: Interact mainly with a single `Agent`

## Quick Start

```python
from noesis import Agent

# Create an agent
agent = Agent(name="my_agent", description="A helpful agent")

# Register a handler
@agent.handler
async def handle(ctx):
    return f"Hello from {agent.name}!"

# Invoke the agent
result = await agent.invoke({"message": "hi"})
print(result.output)  # "Hello from my_agent!"
```

## Features

- **Tool System**: Register functions as tools, use agents as tools
- **Middleware Engine**: Composable request/response pipeline
- **Optional Subsystems**: Memory, Reflection, OpenTelemetry
- **HTTP Runtime**: FastAPI integration with `/invoke` and `/health`
- **Flow Orchestration**: Sequential agent composition
- **Comprehensive Testing**: Full test coverage included

## Installation

```bash
pip install -e .

# With OpenTelemetry support
pip install -e ".[otel]"

# For development
pip install -e ".[dev]"
```

## Core Concepts

### Agent

The main abstraction. Implements the Tool protocol so agents can be used as tools.

```python
agent = Agent(name="calculator", description="Does math")

@agent.tool
async def add(a: int, b: int) -> int:
    return a + b

@agent.handler
async def handle(ctx):
    result = await ctx.tool("add", a=5, b=3)
    return f"Result: {result}"
```

### Context

Passed to handlers and middlewares. Provides access to tools, memory, and events.

```python
@agent.handler
async def handle(ctx):
    # Call tools
    result = await ctx.tool("my_tool", param="value")
    
    # Access memory (if configured)
    await ctx.remember("Important fact")
    memories = await ctx.recall("query")
    
    # Add events
    ctx.add_event("custom", data={"key": "value"})
    
    return result
```

### Middlewares

Composable request/response pipeline. Built-in middlewares include error handling, timeout, and session management.

```python
async def logging_middleware(ctx, next_fn):
    print(f"Request: {ctx.request_id}")
    result = await next_fn()
    print(f"Status: {result.ok}")
    return result

agent.use(logging_middleware)
```

### Agent as Tool

Agents implement the Tool protocol and can be used as tools in other agents:

```python
specialized_agent = Agent(name="specialist", description="Specialized task")

@specialized_agent.handler
async def handle(ctx):
    return "Specialized result"

main_agent = Agent(name="main")
main_agent.tool(specialized_agent)  # Register agent as tool

@main_agent.handler
async def handle(ctx):
    result = await ctx.tool("specialist", input={"task": "do something"})
    return result
```

## HTTP Runtime

```python
from noesis import Agent
from noesis.http import build_fastapi

agent = Agent(name="api_agent")

@agent.handler
async def handle(ctx):
    return {"message": "Hello, world!"}

# Create FastAPI app
app = build_fastapi(agent)

# Run with: uvicorn main:app
```

Endpoints:
- `POST /invoke`: Invoke the agent
- `GET /health`: Health check

## Testing

```bash
pytest
```

## License

MIT

