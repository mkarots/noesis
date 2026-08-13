# Noesis

Production runtime for AI agents.

Define an agent, run it through a middleware pipeline, serve it over HTTP. Memory, sessions, and tracing are optional.

```python
from noesis import Agent, Runtime, serve

agent = Agent(name="support")

@agent.handler
async def handle(ctx):
    return {"reply": "Hello!"}

runtime = Runtime(agent)
app = serve(runtime)  # POST /invoke, GET /health
```

## Installation

```bash
pip install -e .

# With OpenTelemetry support
pip install -e ".[otel]"

# For development
pip install -e ".[dev]"
```

## Core concepts

**Agent** is the definition: name, handler, tools.  
**Runtime** is the execution layer: invoke, middleware, tracing, memory.  
**serve()** is the HTTP transport.

`agent.invoke()` still works. It creates a default `Runtime` for you.

## Quick start

```python
from noesis import Agent

agent = Agent(name="my_agent", description="A helpful agent")

@agent.handler
async def handle(ctx):
    return f"Hello from {agent.name}!"

result = await agent.invoke({"message": "hi"})
print(result.output)  # "Hello from my_agent!"
```

OpenAI-style messages are also supported:

```python
result = await agent.invoke(
    messages=[{"role": "user", "content": "what is the weather in sf"}]
)
```

## Runtime

Use `Runtime` when you want production concerns on the invocation path:

```python
from noesis import Agent, Runtime, serve
from noesis.middleware import timeout_middleware

agent = Agent(name="support")

@agent.handler
async def handle(ctx):
    return "Hello!"

runtime = (
    Runtime(agent)
    .use(timeout_middleware(30.0))
    .with_tracing(tracer)   # auto-registers OTEL middleware
    .with_memory(store)
)

result = await runtime.invoke({"message": "hi"})
app = serve(runtime)
```

`Runtime.with_tracing(tracer)` registers OpenTelemetry middleware. You do not need a separate `use_otel()` call.

## HTTP

```python
from noesis import Agent, Runtime, serve

agent = Agent(name="api_agent")

@agent.handler
async def handle(ctx):
    return {"message": "Hello, world!"}

app = serve(Runtime(agent))
# uvicorn main:app
```

`serve()` accepts an `Agent` or a `Runtime`. `build_fastapi()` is kept as an alias.

Endpoints:

- `POST /invoke` — body is `{ "input": {...} }` or `{ "messages": [...] }`, plus optional `state` and `meta`
- `GET /health` — `{ "status": "ok", "agent": "<name>" }`

## Tools

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

Agents implement the tool protocol, so one agent can call another:

```python
specialized = Agent(name="specialist")

@specialized.handler
async def handle(ctx):
    return "Specialized result"

main = Agent(name="main")
main.tool(specialized)

@main.handler
async def handle(ctx):
    return await ctx.tool("specialist", task="do something")
```

## Context

Handlers and middleware receive a `Context`:

```python
@agent.handler
async def handle(ctx):
    result = await ctx.tool("my_tool", param="value")
    await ctx.remember("Important fact")
    memories = await ctx.recall("query")
    ctx.add_event("custom", data={"key": "value"})
    return result
```

`ctx.messages` returns the OpenAI-style list when the input used `messages=`.

## Middleware

Middleware wraps the invocation pipeline. Built-ins: timeout, session, error handling.

```python
from noesis.middleware import timeout_middleware

runtime = Runtime(agent).use(timeout_middleware(30.0))
```

Custom middleware:

```python
async def logging_middleware(ctx, next_fn):
    print(f"Request: {ctx.request_id}")
    result = await next_fn()
    print(f"Status: {result.ok}")
    return result

runtime.use(logging_middleware)
```

`agent.use(...)` still works and runs before runtime-level middleware.

## Testing

```bash
pytest
```

## License

MIT
