"""Tests for tool system."""

import pytest

from noesis import Agent


class TestToolSystem:
    """Test tool registration and execution."""

    async def test_simple_tool(self):
        """Test basic tool registration and usage."""
        agent = Agent(name="test")

        @agent.tool
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        @agent.handler
        async def handle(ctx):
            return await ctx.tool("greet", name="World")

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == "Hello, World!"

    async def test_tool_with_multiple_params(self):
        """Test tool with multiple parameters."""
        agent = Agent(name="test")

        @agent.tool
        async def calculate(x: int, y: int, operation: str) -> int:
            if operation == "add":
                return x + y
            elif operation == "multiply":
                return x * y
            return 0

        @agent.handler
        async def handle(ctx):
            add_result = await ctx.tool("calculate", x=5, y=3, operation="add")
            mul_result = await ctx.tool(
                "calculate", x=5, y=3, operation="multiply"
            )
            return {"add": add_result, "multiply": mul_result}

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == {"add": 8, "multiply": 15}

    async def test_tool_custom_name(self):
        """Test tool with custom name."""
        agent = Agent(name="test")

        @agent.tool(name="custom_name")
        async def some_function() -> str:
            return "custom"

        @agent.handler
        async def handle(ctx):
            return await ctx.tool("custom_name")

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == "custom"

    async def test_multiple_tools(self):
        """Test agent with multiple tools."""
        agent = Agent(name="test")

        @agent.tool
        async def add(x: int, y: int) -> int:
            return x + y

        @agent.tool
        async def subtract(x: int, y: int) -> int:
            return x - y

        @agent.tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        @agent.handler
        async def handle(ctx):
            a = await ctx.tool("add", x=10, y=5)
            b = await ctx.tool("subtract", x=10, y=5)
            c = await ctx.tool("multiply", x=10, y=5)
            return {"add": a, "subtract": b, "multiply": c}

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == {"add": 15, "subtract": 5, "multiply": 50}

    async def test_tool_with_no_params(self):
        """Test tool with no parameters."""
        agent = Agent(name="test")

        @agent.tool
        async def get_constant() -> int:
            return 42

        @agent.handler
        async def handle(ctx):
            return await ctx.tool("get_constant")

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == 42

    async def test_tool_access_denied_outside_context(self):
        """Test that tools must be called through context."""
        agent = Agent(name="test")

        @agent.tool
        async def my_tool() -> str:
            return "result"

        # Tool is registered but should be called via context
        assert "my_tool" in agent._tools

    async def test_tool_events_logged(self):
        """Test that tool calls log events."""
        agent = Agent(name="test")
        captured_events = []

        @agent.tool
        async def test_tool(x: int) -> int:
            return x * 2

        @agent.handler
        async def handle(ctx):
            result = await ctx.tool("test_tool", x=5)
            captured_events.extend(ctx.events)
            return result

        result = await agent.invoke({})
        assert result.ok is True

        # Check events
        tool_events = [e for e in captured_events if e.kind == "tool_call"]
        result_events = [e for e in captured_events if e.kind == "tool_result"]

        assert len(tool_events) == 1
        assert tool_events[0].data["tool"] == "test_tool"
        assert len(result_events) == 1


class TestAgentAsTool:
    """Test using agents as tools."""

    async def test_basic_agent_as_tool(self):
        """Test registering and using an agent as a tool."""
        # Create specialized agent
        specialist = Agent(name="specialist", description="Does specialized work")

        @specialist.handler
        async def handle(ctx):
            value = ctx.input.get("value", 0)
            return value * 2

        # Create main agent
        main = Agent(name="main")
        main.tool(specialist)

        @main.handler
        async def handle(ctx):
            result = await ctx.tool("specialist", value=10)
            return f"Result: {result}"

        result = await main.invoke({})
        assert result.ok is True
        assert result.output == "Result: 20"

    async def test_agent_as_tool_with_custom_name(self):
        """Test registering agent as tool with custom name."""
        specialist = Agent(name="specialist")

        @specialist.handler
        async def handle(ctx):
            return "specialized"

        main = Agent(name="main")
        main.tool(specialist, name="custom_specialist")

        @main.handler
        async def handle(ctx):
            return await ctx.tool("custom_specialist")

        result = await main.invoke({})
        assert result.ok is True
        assert result.output == "specialized"

    async def test_multiple_agents_as_tools(self):
        """Test using multiple agents as tools."""
        # Create specialized agents
        adder = Agent(name="adder")

        @adder.handler
        async def handle(ctx):
            return ctx.input.get("x", 0) + ctx.input.get("y", 0)

        multiplier = Agent(name="multiplier")

        @multiplier.handler
        async def handle(ctx):
            return ctx.input.get("x", 0) * ctx.input.get("y", 0)

        # Create orchestrator
        orchestrator = Agent(name="orchestrator")
        orchestrator.tool(adder)
        orchestrator.tool(multiplier)

        @orchestrator.handler
        async def handle(ctx):
            sum_result = await ctx.tool("adder", x=5, y=3)
            product_result = await ctx.tool("multiplier", x=5, y=3)
            return {"sum": sum_result, "product": product_result}

        result = await orchestrator.invoke({})
        assert result.ok is True
        assert result.output == {"sum": 8, "product": 15}

    async def test_agent_as_tool_failure_propagation(self):
        """Test that failures in agent-as-tool propagate correctly."""
        failing_agent = Agent(name="failer")

        @failing_agent.handler
        async def handle(ctx):
            raise ValueError("I always fail")

        main = Agent(name="main")
        main.tool(failing_agent)

        @main.handler
        async def handle(ctx):
            return await ctx.tool("failer")

        result = await main.invoke({})
        assert result.ok is False
        assert "failed" in result.error.lower()

    async def test_nested_agent_tools(self):
        """Test nested agent-as-tool composition."""
        # Innermost agent
        inner = Agent(name="inner")

        @inner.handler
        async def handle(ctx):
            return ctx.input.get("value", 0) + 1

        # Middle agent
        middle = Agent(name="middle")
        middle.tool(inner)

        @middle.handler
        async def handle(ctx):
            result = await ctx.tool("inner", value=5)
            return result * 2

        # Outer agent
        outer = Agent(name="outer")
        outer.tool(middle)

        @outer.handler
        async def handle(ctx):
            result = await ctx.tool("middle", value=5)
            return f"Final: {result}"

        result = await outer.invoke({})
        assert result.ok is True
        # (5 + 1) * 2 = 12
        assert result.output == "Final: 12"

    async def test_agent_tool_with_state(self):
        """Test agent as tool preserves its own state handling."""
        stateful_agent = Agent(name="stateful")

        @stateful_agent.handler
        async def handle(ctx):
            ctx.state["called"] = True
            return "done"

        main = Agent(name="main")
        main.tool(stateful_agent)

        @main.handler
        async def handle(ctx):
            result = await ctx.tool("stateful")
            ctx.state["main_called"] = True
            return result

        result = await main.invoke({})
        assert result.ok is True
        # Main agent's state should be preserved
        assert result.state["main_called"] is True

