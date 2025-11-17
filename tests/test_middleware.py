"""Tests for middleware system."""

import asyncio

import pytest

from noesis import Agent
from noesis.middleware import error_middleware, session_middleware, timeout_middleware


class TestMiddlewareSystem:
    """Test middleware registration and execution."""

    async def test_basic_middleware(self):
        """Test basic middleware execution."""
        agent = Agent(name="test")
        called = []

        async def logging_middleware(ctx, next_fn):
            called.append("before")
            result = await next_fn()
            called.append("after")
            return result

        agent.use(logging_middleware)

        @agent.handler
        async def handle(ctx):
            called.append("handler")
            return "done"

        await agent.invoke({})
        assert called == ["before", "handler", "after"]

    async def test_middleware_execution_order(self):
        """Test middleware executes in registration order."""
        agent = Agent(name="test")
        order = []

        async def mw1(ctx, next_fn):
            order.append("mw1_before")
            result = await next_fn()
            order.append("mw1_after")
            return result

        async def mw2(ctx, next_fn):
            order.append("mw2_before")
            result = await next_fn()
            order.append("mw2_after")
            return result

        async def mw3(ctx, next_fn):
            order.append("mw3_before")
            result = await next_fn()
            order.append("mw3_after")
            return result

        agent.use(mw1)
        agent.use(mw2)
        agent.use(mw3)

        @agent.handler
        async def handle(ctx):
            order.append("handler")
            return "done"

        await agent.invoke({})
        assert order == [
            "mw1_before",
            "mw2_before",
            "mw3_before",
            "handler",
            "mw3_after",
            "mw2_after",
            "mw1_after",
        ]

    async def test_middleware_can_modify_result(self):
        """Test middleware can modify the result."""
        agent = Agent(name="test")

        async def modifying_middleware(ctx, next_fn):
            result = await next_fn()
            result.output = f"Modified: {result.output}"
            return result

        agent.use(modifying_middleware)

        @agent.handler
        async def handle(ctx):
            return "original"

        result = await agent.invoke({})
        assert result.output == "Modified: original"

    async def test_middleware_can_modify_context(self):
        """Test middleware can modify context."""
        agent = Agent(name="test")

        async def context_middleware(ctx, next_fn):
            ctx.state["added_by_middleware"] = True
            return await next_fn()

        agent.use(context_middleware)

        @agent.handler
        async def handle(ctx):
            return ctx.state.get("added_by_middleware")

        result = await agent.invoke({})
        assert result.output is True

    async def test_middleware_short_circuit(self):
        """Test middleware can short-circuit execution."""
        agent = Agent(name="test")
        handler_called = False

        async def short_circuit_middleware(ctx, next_fn):
            from noesis import AgentResult

            return AgentResult(ok=True, output="short-circuited")

        agent.use(short_circuit_middleware)

        @agent.handler
        async def handle(ctx):
            nonlocal handler_called
            handler_called = True
            return "handler"

        result = await agent.invoke({})
        assert result.output == "short-circuited"
        assert handler_called is False

    async def test_middleware_error_handling(self):
        """Test middleware can handle errors."""
        agent = Agent(name="test")

        async def error_handling_middleware(ctx, next_fn):
            try:
                return await next_fn()
            except Exception:
                from noesis import AgentResult

                return AgentResult(ok=False, error="caught by middleware")

        agent.use(error_handling_middleware)

        @agent.handler
        async def handle(ctx):
            raise ValueError("handler error")

        result = await agent.invoke({})
        assert result.ok is False
        assert result.error == "caught by middleware"


class TestErrorMiddleware:
    """Test error middleware."""

    async def test_error_middleware_passes_success(self):
        """Test error middleware passes through successful results."""
        agent = Agent(name="test")
        agent.use(error_middleware)

        @agent.handler
        async def handle(ctx):
            return "success"

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == "success"

    async def test_error_middleware_catches_exceptions(self):
        """Test error middleware catches exceptions."""
        agent = Agent(name="test")
        agent.use(error_middleware)

        @agent.handler
        async def handle(ctx):
            raise ValueError("test error")

        result = await agent.invoke({})
        assert result.ok is False
        assert "test error" in result.error


class TestTimeoutMiddleware:
    """Test timeout middleware."""

    async def test_timeout_middleware_passes_fast_execution(self):
        """Test timeout middleware allows fast execution."""
        agent = Agent(name="test")
        agent.use(timeout_middleware(1.0))

        @agent.handler
        async def handle(ctx):
            return "fast"

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == "fast"

    async def test_timeout_middleware_stops_slow_execution(self):
        """Test timeout middleware stops slow execution."""
        agent = Agent(name="test")
        agent.use(timeout_middleware(0.1))

        @agent.handler
        async def handle(ctx):
            await asyncio.sleep(1.0)
            return "slow"

        result = await agent.invoke({})
        assert result.ok is False
        assert "timeout" in result.error
        assert "0.1" in result.error

    async def test_timeout_middleware_logs_event(self):
        """Test timeout middleware logs event."""
        agent = Agent(name="test")
        agent.use(timeout_middleware(0.05))

        @agent.handler
        async def handle(ctx):
            await asyncio.sleep(0.2)
            return "done"

        result = await agent.invoke({})
        timeout_events = [e for e in result.events if e.kind == "timeout"]
        assert len(timeout_events) == 1
        assert timeout_events[0].data["timeout_seconds"] == 0.05

    async def test_multiple_timeout_values(self):
        """Test different timeout values."""
        # Fast enough
        agent1 = Agent(name="test1")
        agent1.use(timeout_middleware(0.5))

        @agent1.handler
        async def handle(ctx):
            await asyncio.sleep(0.1)
            return "done"

        result1 = await agent1.invoke({})
        assert result1.ok is True

        # Too slow
        agent2 = Agent(name="test2")
        agent2.use(timeout_middleware(0.05))

        @agent2.handler
        async def handle(ctx):
            await asyncio.sleep(0.2)
            return "done"

        result2 = await agent2.invoke({})
        assert result2.ok is False
        assert "timeout" in result2.error


class TestSessionMiddleware:
    """Test session middleware."""

    async def test_session_middleware_without_session_id(self):
        """Test session middleware with no session_id."""
        agent = Agent(name="test")
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return f"session: {ctx.session_id}, history: {ctx.history}"

        result = await agent.invoke({})
        assert result.ok is True
        assert "session: None" in result.output

    async def test_session_middleware_with_session_id(self):
        """Test session middleware loads history."""
        from noesis.memory import InMemoryStore

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)
        agent.use(session_middleware())

        # Populate memory with session data
        await memory.put(
            content="previous turn",
            kind="session",
            meta={"session_id": "session-123"},
        )

        @agent.handler
        async def handle(ctx):
            return f"history length: {len(ctx.history) if ctx.history else 0}"

        result = await agent.invoke({"session_id": "session-123"})
        assert result.ok is True
        # History should be loaded
        assert "1" in result.output or "0" in result.output

    async def test_session_middleware_saves_conversation(self):
        """Test session middleware saves conversation."""
        from noesis.memory import InMemoryStore

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return "response"

        await agent.invoke({"session_id": "session-456", "message": "hello"})

        # Check that conversation was saved
        results = await memory.search(query="session-456", kind="session", limit=10)
        assert len(results) > 0

    async def test_session_middleware_events(self):
        """Test session middleware logs events."""
        from noesis.memory import InMemoryStore

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return "done"

        result = await agent.invoke({"session_id": "session-789"})

        # Check for session events
        saved_events = [e for e in result.events if e.kind == "session_saved"]
        assert len(saved_events) == 1

    async def test_session_middleware_without_memory(self):
        """Test session middleware gracefully handles no memory."""
        agent = Agent(name="test")
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return "done"

        # Should not crash without memory store
        result = await agent.invoke({"session_id": "session-999"})
        assert result.ok is True


class TestMiddlewareComposition:
    """Test combining multiple middlewares."""

    async def test_error_and_timeout_middleware(self):
        """Test error and timeout middleware together."""
        agent = Agent(name="test")
        agent.use(error_middleware)
        agent.use(timeout_middleware(0.1))

        @agent.handler
        async def handle(ctx):
            await asyncio.sleep(0.5)
            return "done"

        result = await agent.invoke({})
        assert result.ok is False
        assert "timeout" in result.error

    async def test_all_builtin_middlewares(self):
        """Test all built-in middlewares together."""
        from noesis.memory import InMemoryStore

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        agent.use(error_middleware)
        agent.use(timeout_middleware(5.0))
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return f"Hello from session {ctx.session_id}"

        result = await agent.invoke({"session_id": "full-test"})
        assert result.ok is True
        assert "full-test" in result.output

