"""Tests for runtime services."""

import pytest

from noesis import Agent, ToolError
from noesis.memory import InMemoryStore
from noesis.runtime import AppRuntimeServices


class TestAppRuntimeServices:
    """Test AppRuntimeServices."""

    @pytest.fixture
    def agent(self):
        """Create test agent with tools."""
        agent = Agent(name="test")

        @agent.tool
        async def add(x: int, y: int) -> int:
            return x + y

        @agent.tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        return agent

    @pytest.fixture
    def services(self, agent):
        """Create runtime services."""
        return AppRuntimeServices(agent)

    @pytest.fixture
    def context(self, agent):
        """Create a mock context."""
        from noesis.core import Context

        services = AppRuntimeServices(agent)
        return Context(
            input={},
            state={},
            meta={},
            events=[],
            session_id=None,
            history=None,
            request_id="test",
            created_at=0.0,
            _services=services,
        )

    async def test_call_tool_success(self, services, context):
        """Test successful tool call."""
        result = await services.call_tool(context, "add", x=5, y=3)
        assert result == 8

        # Check events were logged
        assert len(context.events) == 2
        assert context.events[0].kind == "tool_call"
        assert context.events[0].data["tool"] == "add"
        assert context.events[1].kind == "tool_result"
        assert context.events[1].data["success"] is True

    async def test_call_tool_not_found(self, services, context):
        """Test calling nonexistent tool."""
        with pytest.raises(ToolError, match="Tool not found: nonexistent"):
            await services.call_tool(context, "nonexistent")

    async def test_call_tool_failure(self, agent, context):
        """Test tool execution failure."""

        @agent.tool
        async def failing_tool():
            raise ValueError("Tool failed")

        services = AppRuntimeServices(agent)

        with pytest.raises(ToolError, match="Tool 'failing_tool' failed"):
            await services.call_tool(context, "failing_tool")

        # Check error event was logged
        error_events = [e for e in context.events if e.kind == "tool_result"]
        assert len(error_events) > 0
        assert error_events[-1].data["success"] is False

    async def test_call_agent_as_tool(self):
        """Test calling another agent as a tool."""
        # Create sub-agent
        sub_agent = Agent(name="sub")

        @sub_agent.handler
        async def handle(ctx):
            return ctx.input.get("value", 0) * 2

        # Create main agent with sub-agent as tool
        main_agent = Agent(name="main")
        main_agent.tool(sub_agent)

        # Create services and context
        services = AppRuntimeServices(main_agent)
        from noesis.core import Context

        ctx = Context(
            input={},
            state={},
            meta={},
            events=[],
            session_id=None,
            history=None,
            request_id="test",
            created_at=0.0,
            _services=services,
        )

        # Call sub-agent as tool
        result = await services.call_tool(ctx, "sub", value=5)
        assert result == 10

    async def test_memory_put_without_store(self, services, context):
        """Test memory put without configured store."""
        with pytest.raises(RuntimeError, match="No memory store configured"):
            await services.memory_put(context, "test", kind="note", meta={})

    async def test_memory_search_without_store(self, services, context):
        """Test memory search without configured store."""
        with pytest.raises(RuntimeError, match="No memory store configured"):
            await services.memory_search(context, "test", kind=None, limit=5)

    async def test_memory_put_with_store(self, agent, context):
        """Test memory put with store."""
        memory = InMemoryStore()
        agent.use_memory(memory)
        services = AppRuntimeServices(agent)

        await services.memory_put(
            context,
            "test content",
            kind="note",
            meta={"author": "test"},
        )

        # Check event was logged
        write_events = [e for e in context.events if e.kind == "memory_write"]
        assert len(write_events) == 1
        assert write_events[0].data["kind"] == "note"

        # Verify content was stored
        assert len(memory._items) == 1
        assert memory._items[0]["content"] == "test content"
        assert memory._items[0]["kind"] == "note"

    async def test_memory_search_with_store(self, agent, context):
        """Test memory search with store."""
        memory = InMemoryStore()
        agent.use_memory(memory)
        services = AppRuntimeServices(agent)

        # Add some items
        await memory.put(content="first item", kind="note", meta={})
        await memory.put(content="second item", kind="note", meta={})

        # Search
        results = await services.memory_search(
            context,
            query="first",
            kind="note",
            limit=5,
        )

        assert len(results) == 1
        assert results[0]["content"] == "first item"

        # Check events
        read_events = [e for e in context.events if e.kind == "memory_read"]
        result_events = [e for e in context.events if e.kind == "memory_result"]
        assert len(read_events) == 1
        assert len(result_events) == 1
        assert result_events[0].data["count"] == 1

