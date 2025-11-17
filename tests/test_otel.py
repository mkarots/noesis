"""Tests for OpenTelemetry middleware."""

import pytest

from noesis import Agent
from noesis.otel import otel_middleware


class MockSpan:
    """Mock OTEL span for testing."""

    def __init__(self):
        self.attributes = {}
        self.events = []
        self.status_set = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append({"name": name, "attributes": attributes or {}})

    def set_status(self, status, description=None):
        self.status_set = {"status": status, "description": description}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockTracer:
    """Mock OTEL tracer for testing."""

    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name):
        span = MockSpan()
        self.spans.append({"name": name, "span": span})
        return span


class TestOtelMiddleware:
    """Test OTEL middleware."""

    async def test_otel_creates_span(self):
        """Test OTEL middleware creates a span."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            return "success"

        await agent.invoke({})

        assert len(tracer.spans) == 1
        assert tracer.spans[0]["name"] == "agent.handle"

    async def test_otel_adds_context_attributes(self):
        """Test OTEL adds context attributes to span."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            return "success"

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        assert "agent.request_id" in span.attributes
        assert "agent.created_at" in span.attributes
        assert span.attributes["agent.ok"] is True

    async def test_otel_adds_session_id(self):
        """Test OTEL adds session_id if present."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            return "success"

        await agent.invoke({"session_id": "session-123"})

        span = tracer.spans[0]["span"]
        assert span.attributes["agent.session_id"] == "session-123"

    async def test_otel_success_status(self):
        """Test OTEL sets success status."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            return "success"

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        assert span.status_set["status"] == 0  # StatusCode.OK

    async def test_otel_error_status(self):
        """Test OTEL sets error status on failure."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            raise ValueError("test error")

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        assert span.attributes["agent.ok"] is False
        assert "test error" in span.attributes["agent.error"]
        assert span.status_set["status"] == 1  # StatusCode.ERROR

    async def test_otel_adds_events(self):
        """Test OTEL adds runtime events as span events."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            ctx.add_event("custom_event", data="value")
            ctx.add_event("another_event", count=42)
            return "done"

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        assert len(span.events) == 2
        assert span.events[0]["name"] == "agent.custom_event"
        assert "event.data" in span.events[0]["attributes"]
        assert span.events[1]["name"] == "agent.another_event"

    async def test_otel_with_tool_calls(self):
        """Test OTEL captures tool call events."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.tool
        async def test_tool(x: int) -> int:
            return x * 2

        @agent.handler
        async def handle(ctx):
            return await ctx.tool("test_tool", x=5)

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        tool_events = [e for e in span.events if "tool" in e["name"]]
        assert len(tool_events) > 0

    async def test_otel_with_memory_operations(self):
        """Test OTEL captures memory events."""
        from noesis.memory import InMemoryStore

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            await ctx.remember("test")
            await ctx.recall("test")
            return "done"

        await agent.invoke({})

        span = tracer.spans[0]["span"]
        memory_events = [e for e in span.events if "memory" in e["name"]]
        assert len(memory_events) > 0

    async def test_otel_multiple_invocations(self):
        """Test OTEL creates separate spans for each invocation."""
        agent = Agent(name="test")
        tracer = MockTracer()
        agent.use(otel_middleware(tracer))

        @agent.handler
        async def handle(ctx):
            return "done"

        await agent.invoke({})
        await agent.invoke({})
        await agent.invoke({})

        assert len(tracer.spans) == 3
        assert all(s["name"] == "agent.handle" for s in tracer.spans)
