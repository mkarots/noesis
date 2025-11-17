"""Tests for reflection middleware."""

import pytest

from noesis import Agent
from noesis.memory import InMemoryStore
from noesis.reflection import reflection_middleware


class MockReflectionClient:
    """Mock reflection client for testing."""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {"score": 0.95, "notes": "Good response"}

    async def reflect(self, *, input, output, meta):
        self.calls.append({"input": input, "output": output, "meta": meta})
        return self.result


class TestReflectionMiddleware:
    """Test reflection middleware."""

    async def test_reflection_on_success(self):
        """Test reflection is called on successful invocation."""
        agent = Agent(name="test")
        client = MockReflectionClient()
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            return "success"

        result = await agent.invoke({"input": "test"})

        assert result.ok is True
        assert len(client.calls) == 1
        assert client.calls[0]["input"] == {"input": "test"}
        assert client.calls[0]["output"] == "success"

    async def test_reflection_not_called_on_failure(self):
        """Test reflection is not called on failed invocation."""
        agent = Agent(name="test")
        client = MockReflectionClient()
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            raise ValueError("error")

        result = await agent.invoke({})

        assert result.ok is False
        assert len(client.calls) == 0

    async def test_reflection_event_logged(self):
        """Test reflection logs event."""
        agent = Agent(name="test")
        client = MockReflectionClient(result={"score": 0.85})
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            return "done"

        result = await agent.invoke({})

        reflection_events = [e for e in result.events if e.kind == "reflection"]
        assert len(reflection_events) == 1
        assert reflection_events[0].data["result"]["score"] == 0.85

    async def test_reflection_with_memory(self):
        """Test reflection can write to memory."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        client = MockReflectionClient(result={"analysis": "good job"})
        agent.use(reflection_middleware(client, write_to_memory=True))

        @agent.handler
        async def handle(ctx):
            return "output"

        result = await agent.invoke({})

        assert result.ok is True
        # Check memory was written
        assert len(memory._items) == 1
        assert "analysis" in memory._items[0]["content"]

    async def test_reflection_without_memory_write(self):
        """Test reflection without writing to memory."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        client = MockReflectionClient()
        agent.use(reflection_middleware(client, write_to_memory=False))

        @agent.handler
        async def handle(ctx):
            return "output"

        await agent.invoke({})

        # Memory should be empty
        assert len(memory._items) == 0

    async def test_reflection_custom_memory_kind(self):
        """Test reflection with custom memory kind."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        client = MockReflectionClient()
        agent.use(
            reflection_middleware(
                client,
                write_to_memory=True,
                memory_kind="custom_reflection",
            )
        )

        @agent.handler
        async def handle(ctx):
            return "output"

        await agent.invoke({})

        assert memory._items[0]["kind"] == "custom_reflection"

    async def test_reflection_error_does_not_fail_request(self):
        """Test reflection error doesn't fail the request."""

        class FailingReflectionClient:
            async def reflect(self, *, input, output, meta):
                raise ValueError("Reflection failed")

        agent = Agent(name="test")
        client = FailingReflectionClient()
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            return "success"

        result = await agent.invoke({})

        # Request should still succeed
        assert result.ok is True
        assert result.output == "success"

        # Error event should be logged
        error_events = [e for e in result.events if e.kind == "reflection_error"]
        assert len(error_events) == 1

    async def test_reflection_with_meta(self):
        """Test reflection receives meta."""
        agent = Agent(name="test")
        client = MockReflectionClient()
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            return "output"

        await agent.invoke({}, meta={"user": "test_user"})

        assert client.calls[0]["meta"]["user"] == "test_user"

    async def test_multiple_reflections(self):
        """Test multiple invocations all trigger reflection."""
        agent = Agent(name="test")
        client = MockReflectionClient()
        agent.use(reflection_middleware(client))

        @agent.handler
        async def handle(ctx):
            return f"output {ctx.input.get('n')}"

        await agent.invoke({"n": 1})
        await agent.invoke({"n": 2})
        await agent.invoke({"n": 3})

        assert len(client.calls) == 3
        assert client.calls[0]["output"] == "output 1"
        assert client.calls[1]["output"] == "output 2"
        assert client.calls[2]["output"] == "output 3"

