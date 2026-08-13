"""Tests for core abstractions."""

import pytest

from noesis import Agent, AgentError, AgentResult, Context, RuntimeEvent, ToolError
from noesis.runtime import AppRuntimeServices


class TestRuntimeEvent:
    """Test RuntimeEvent dataclass."""

    def test_create_event(self):
        """Test creating a runtime event."""
        event = RuntimeEvent(kind="test", data={"key": "value"})
        assert event.kind == "test"
        assert event.data == {"key": "value"}

    def test_event_with_empty_data(self):
        """Test event with no data."""
        event = RuntimeEvent(kind="test", data={})
        assert event.kind == "test"
        assert event.data == {}


class TestAgentResult:
    """Test AgentResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = AgentResult(ok=True, output="success")
        assert result.ok is True
        assert result.output == "success"
        assert result.error is None
        assert result.state == {}
        assert result.events == []

    def test_error_result(self):
        """Test error result."""
        result = AgentResult(ok=False, error="something went wrong")
        assert result.ok is False
        assert result.error == "something went wrong"
        assert result.output is None

    def test_result_with_state_and_events(self):
        """Test result with state and events."""
        events = [RuntimeEvent(kind="test", data={})]
        result = AgentResult(
            ok=True,
            output="output",
            state={"key": "value"},
            events=events,
        )
        assert result.state == {"key": "value"}
        assert len(result.events) == 1
        assert result.events[0].kind == "test"


class TestContext:
    """Test Context."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Agent(name="test_agent")

        @agent.tool
        async def test_tool(x: int) -> int:
            return x * 2

        return agent

    @pytest.fixture
    def context(self, mock_agent):
        """Create a test context."""
        services = AppRuntimeServices(mock_agent)
        ctx = Context(
            input={"message": "test"},
            state={},
            meta={},
            events=[],
            session_id=None,
            history=None,
            request_id="test-request-id",
            created_at=1234567890.0,
            _services=services,
        )
        return ctx

    def test_context_creation(self, context):
        """Test context creation."""
        assert context.input == {"message": "test"}
        assert context.state == {}
        assert context.meta == {}
        assert context.events == []
        assert context.session_id is None
        assert context.history is None
        assert context.request_id == "test-request-id"

    def test_add_event(self, context):
        """Test adding events to context."""
        context.add_event("test", data="value")
        assert len(context.events) == 1
        assert context.events[0].kind == "test"
        assert context.events[0].data == {"data": "value"}

    async def test_tool_call_success(self, context):
        """Test successful tool call."""
        result = await context.tool("test_tool", x=5)
        assert result == 10

    async def test_tool_call_nonexistent(self, context):
        """Test calling nonexistent tool."""
        with pytest.raises(ToolError, match="Tool not found"):
            await context.tool("nonexistent")

    async def test_memory_without_store(self, context):
        """Test memory operations without store configured."""
        with pytest.raises(RuntimeError, match="No memory store"):
            await context.remember("test")

        with pytest.raises(RuntimeError, match="No memory store"):
            await context.recall("test")


class TestAgent:
    """Test Agent class."""

    def test_agent_creation(self):
        """Test creating an agent."""
        agent = Agent(name="test", description="Test agent")
        assert agent.name == "test"
        assert agent.description == "Test agent"

    def test_agent_creation_without_description(self):
        """Test creating agent without description."""
        agent = Agent(name="test")
        assert agent.name == "test"
        assert agent.description == ""

    def test_handler_registration(self):
        """Test registering a handler."""
        agent = Agent(name="test")

        @agent.handler
        async def my_handler(ctx):
            return "handled"

        assert agent._handler is not None
        assert agent._handler == my_handler

    def test_tool_registration_as_decorator(self):
        """Test registering tool as decorator."""
        agent = Agent(name="test")

        @agent.tool
        async def my_tool(x: int) -> int:
            return x * 2

        assert "my_tool" in agent._tools
        assert agent._tools["my_tool"] == my_tool

    def test_tool_registration_with_custom_name(self):
        """Test registering tool with custom name."""
        agent = Agent(name="test")

        @agent.tool(name="custom_name")
        async def my_tool(x: int) -> int:
            return x * 2

        assert "custom_name" in agent._tools
        assert agent._tools["custom_name"] == my_tool

    def test_tool_registration_direct(self):
        """Test direct tool registration."""
        agent = Agent(name="test")

        async def my_tool(x: int) -> int:
            return x * 2

        agent.tool(my_tool)
        assert "my_tool" in agent._tools

    def test_agent_as_tool_registration(self):
        """Test registering another agent as tool."""
        main_agent = Agent(name="main")
        sub_agent = Agent(name="sub", description="Sub agent")

        main_agent.tool(sub_agent)

        assert "sub" in main_agent._tools
        assert main_agent._tools["sub"] == sub_agent

    async def test_invoke_without_handler(self):
        """Test invoking agent without handler."""
        agent = Agent(name="test")

        with pytest.raises(AgentError, match="No handler registered"):
            await agent.invoke({})

    async def test_invoke_basic(self):
        """Test basic invocation."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return "Hello!"

        result = await agent.invoke({"input": "test"})
        assert result.ok is True
        assert result.output == "Hello!"
        assert result.error is None

    async def test_invoke_with_state(self):
        """Test invocation with state."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            ctx.state["processed"] = True
            return ctx.state

        result = await agent.invoke({"input": "test"}, state={"initial": True})
        assert result.ok is True
        assert result.state["initial"] is True
        assert result.state["processed"] is True

    async def test_invoke_with_error(self):
        """Test invocation that raises error."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            raise ValueError("Test error")

        result = await agent.invoke({})
        assert result.ok is False
        assert "Test error" in result.error

    async def test_invoke_with_agent_error(self):
        """Test invocation that raises AgentError."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            raise AgentError("Custom error")

        result = await agent.invoke({})
        assert result.ok is False
        assert result.error == "Custom error"

    async def test_agent_as_tool_call(self):
        """Test calling agent as a tool."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return f"Handled: {ctx.input.get('message')}"

        # Call agent as tool
        result = await agent(input={"message": "hello"})
        assert result == "Handled: hello"

    async def test_agent_as_tool_call_with_kwargs(self):
        """Test calling agent as tool with kwargs."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return ctx.input.get("x", 0) + ctx.input.get("y", 0)

        result = await agent(input={}, x=5, y=3)
        assert result == 8

    async def test_agent_as_tool_call_failure(self):
        """Test calling agent as tool when it fails."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            raise ValueError("Failed!")

        with pytest.raises(ToolError):
            await agent(input={})

    def test_middleware_registration(self):
        """Test registering middleware."""
        agent = Agent(name="test")

        async def my_middleware(ctx, next_fn):
            return await next_fn()

        agent.use(my_middleware)
        assert len(agent._middlewares) == 1
        assert agent._middlewares[0] == my_middleware

    async def test_middleware_execution_order(self):
        """Test middleware execution order."""
        agent = Agent(name="test")
        execution_order = []

        async def mw1(ctx, next_fn):
            execution_order.append("mw1_before")
            result = await next_fn()
            execution_order.append("mw1_after")
            return result

        async def mw2(ctx, next_fn):
            execution_order.append("mw2_before")
            result = await next_fn()
            execution_order.append("mw2_after")
            return result

        agent.use(mw1)
        agent.use(mw2)

        @agent.handler
        async def handle(ctx):
            execution_order.append("handler")
            return "done"

        await agent.invoke({})

        assert execution_order == [
            "mw1_before",
            "mw2_before",
            "handler",
            "mw2_after",
            "mw1_after",
        ]

    async def test_session_id_from_input(self):
        """Test session_id extracted from input."""
        agent = Agent(name="test")
        captured_session = None

        @agent.handler
        async def handle(ctx):
            nonlocal captured_session
            captured_session = ctx.session_id
            return "ok"

        await agent.invoke({"session_id": "session-123"})
        assert captured_session == "session-123"

    async def test_session_id_from_meta(self):
        """Test session_id extracted from meta."""
        agent = Agent(name="test")
        captured_session = None

        @agent.handler
        async def handle(ctx):
            nonlocal captured_session
            captured_session = ctx.session_id
            return "ok"

        await agent.invoke({}, meta={"session_id": "meta-session"})
        assert captured_session == "meta-session"

    def test_use_memory(self):
        """Test configuring memory store."""
        agent = Agent(name="test")

        class MockMemory:
            async def put(self, *, content, kind, meta):
                pass

            async def search(self, *, query, kind, limit):
                return []

        memory = MockMemory()
        agent.use_memory(memory)
        assert agent._memory == memory

    def test_use_otel(self):
        """Test configuring OTEL registers tracing middleware."""
        agent = Agent(name="test")

        class MockTracer:
            pass

        tracer = MockTracer()
        agent.use_otel(tracer)
        assert agent._tracer == tracer
        assert len(agent._middlewares) == 1

    def test_use_reflection(self):
        """Test configuring reflection."""
        agent = Agent(name="test")

        class MockReflection:
            async def reflect(self, *, input, output, meta):
                return {}

        client = MockReflection()
        agent.use_reflection(client, option="value")
        assert agent._reflection_client == client
        assert agent._reflection_opts == {"option": "value"}

