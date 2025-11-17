"""Tests for flow orchestration."""

import pytest

from noesis import Agent, Flow


class TestFlow:
    """Test Flow orchestration."""

    async def test_empty_flow(self):
        """Test running an empty flow."""
        flow = Flow()
        result = await flow.run({})

        assert result.ok is False
        assert "Empty flow" in result.error

    async def test_single_step_flow(self):
        """Test flow with single step."""
        agent = Agent(name="step1")

        @agent.handler
        async def handle(ctx):
            return "result1"

        flow = Flow()
        flow.step("first", agent)

        result = await flow.run({"input": "test"})
        assert result.ok is True
        assert result.output == "result1"

    async def test_two_step_flow(self):
        """Test flow with two steps."""
        agent1 = Agent(name="step1")

        @agent1.handler
        async def handle(ctx):
            return "step1_output"

        agent2 = Agent(name="step2")

        @agent2.handler
        async def handle(ctx):
            prev = ctx.input.get("prev")
            return f"step2 received: {prev}"

        flow = Flow()
        flow.step("first", agent1)
        flow.step("second", agent2)

        result = await flow.run({})
        assert result.ok is True
        assert result.output == "step2 received: step1_output"

    async def test_multi_step_flow(self):
        """Test flow with multiple steps."""
        agents = []
        for i in range(5):
            agent = Agent(name=f"step{i}")

            @agent.handler
            async def handle(ctx, step_num=i):
                prev = ctx.input.get("prev", 0)
                return prev + step_num + 1

            agents.append(agent)

        flow = Flow()
        for i, agent in enumerate(agents):
            flow.step(f"step{i}", agent)

        result = await flow.run({})
        # 0 + 1 + 2 + 3 + 4 + 5 = 15
        assert result.ok is True
        assert result.output == 15

    async def test_flow_preserves_original_input(self):
        """Test that original input is preserved across steps."""
        agent1 = Agent(name="step1")

        @agent1.handler
        async def handle(ctx):
            return "intermediate"

        agent2 = Agent(name="step2")

        @agent2.handler
        async def handle(ctx):
            # Should have access to both prev and original input
            return {
                "prev": ctx.input.get("prev"),
                "original": ctx.input.get("original_data"),
            }

        flow = Flow()
        flow.step("first", agent1)
        flow.step("second", agent2)

        result = await flow.run({"original_data": "preserved"})
        assert result.ok is True
        assert result.output["prev"] == "intermediate"
        assert result.output["original"] == "preserved"

    async def test_flow_stops_on_error(self):
        """Test flow stops on first error."""
        agent1 = Agent(name="step1")

        @agent1.handler
        async def handle(ctx):
            return "success"

        agent2 = Agent(name="step2")

        @agent2.handler
        async def handle(ctx):
            raise ValueError("Step 2 failed")

        agent3 = Agent(name="step3")
        step3_called = False

        @agent3.handler
        async def handle(ctx):
            nonlocal step3_called
            step3_called = True
            return "step3"

        flow = Flow()
        flow.step("first", agent1)
        flow.step("second", agent2)
        flow.step("third", agent3)

        result = await flow.run({})

        assert result.ok is False
        assert "Step 2 failed" in result.error
        assert step3_called is False

    async def test_flow_method_chaining(self):
        """Test flow supports method chaining."""
        agent1 = Agent(name="a")

        @agent1.handler
        async def handle(ctx):
            return 1

        agent2 = Agent(name="b")

        @agent2.handler
        async def handle(ctx):
            return ctx.input.get("prev", 0) + 1

        flow = Flow().step("first", agent1).step("second", agent2)

        result = await flow.run({})
        assert result.ok is True
        assert result.output == 2

    async def test_flow_with_stateful_agents(self):
        """Test flow with agents that use state."""
        agent1 = Agent(name="step1")

        @agent1.handler
        async def handle(ctx):
            ctx.state["step1_processed"] = True
            return "output1"

        agent2 = Agent(name="step2")

        @agent2.handler
        async def handle(ctx):
            ctx.state["step2_processed"] = True
            return "output2"

        flow = Flow()
        flow.step("first", agent1)
        flow.step("second", agent2)

        result = await flow.run({})
        assert result.ok is True
        # Each agent maintains its own state
        assert result.state.get("step2_processed") is True

    async def test_flow_with_complex_data(self):
        """Test flow passing complex data between steps."""
        extractor = Agent(name="extractor")

        @extractor.handler
        async def handle(ctx):
            text = ctx.input.get("text", "")
            return {"words": text.split(), "count": len(text.split())}

        analyzer = Agent(name="analyzer")

        @analyzer.handler
        async def handle(ctx):
            data = ctx.input.get("prev", {})
            return {
                "word_count": data.get("count", 0),
                "first_word": data.get("words", [""])[0] if data.get("words") else "",
            }

        flow = Flow()
        flow.step("extract", extractor)
        flow.step("analyze", analyzer)

        result = await flow.run({"text": "hello world test"})
        assert result.ok is True
        assert result.output["word_count"] == 3
        assert result.output["first_word"] == "hello"


class TestFlowWithAgentTools:
    """Test flow orchestration with agent-as-tool composition."""

    async def test_flow_agents_can_use_tools(self):
        """Test agents in flow can use their own tools."""
        agent = Agent(name="with_tool")

        @agent.tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        @agent.handler
        async def handle(ctx):
            value = ctx.input.get("prev", 5)
            return await ctx.tool("multiply", x=value, y=2)

        flow = Flow()
        flow.step("compute", agent)

        result = await flow.run({"prev": 7})
        assert result.ok is True
        assert result.output == 14

    async def test_flow_with_nested_agents(self):
        """Test flow where agents use other agents as tools."""
        # Inner agent
        calculator = Agent(name="calculator")

        @calculator.handler
        async def handle(ctx):
            return ctx.input.get("x", 0) * ctx.input.get("y", 0)

        # Outer agent that uses calculator
        processor = Agent(name="processor")
        processor.tool(calculator)

        @processor.handler
        async def handle(ctx):
            value = ctx.input.get("prev", 5)
            return await ctx.tool("calculator", x=value, y=3)

        flow = Flow()
        flow.step("process", processor)

        result = await flow.run({"prev": 4})
        assert result.ok is True
        assert result.output == 12

