"""Integration tests for complete workflows."""

import pytest

from noesis import Agent, Flow
from noesis.memory import InMemoryStore
from noesis.middleware import session_middleware, timeout_middleware


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    async def test_simple_agent_workflow(self):
        """Test basic agent creation and invocation."""
        agent = Agent(name="greeter", description="Greets users")

        @agent.handler
        async def handle(ctx):
            name = ctx.input.get("name", "World")
            return f"Hello, {name}!"

        result = await agent.invoke({"name": "Alice"})

        assert result.ok is True
        assert result.output == "Hello, Alice!"

    async def test_agent_with_tools_and_state(self):
        """Test agent using tools and managing state."""
        agent = Agent(name="calculator")

        @agent.tool
        async def add(x: int, y: int) -> int:
            return x + y

        @agent.tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        @agent.handler
        async def handle(ctx):
            x = ctx.input.get("x", 0)
            y = ctx.input.get("y", 0)

            sum_result = await ctx.tool("add", x=x, y=y)
            ctx.state["sum"] = sum_result

            product = await ctx.tool("multiply", x=x, y=y)
            ctx.state["product"] = product

            return {"sum": sum_result, "product": product}

        result = await agent.invoke({"x": 5, "y": 3})

        assert result.ok is True
        assert result.output["sum"] == 8
        assert result.output["product"] == 15
        assert result.state["sum"] == 8
        assert result.state["product"] == 15

    async def test_agent_with_memory_and_session(self):
        """Test agent with memory and session management."""
        agent = Agent(name="chatbot")
        memory = InMemoryStore()
        agent.use_memory(memory)
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            message = ctx.input.get("message", "")

            # Remember the message
            await ctx.remember(f"User said: {message}", kind="chat")

            # Check history
            history_length = len(ctx.history) if ctx.history else 0

            return f"Got it! (History: {history_length} items)"

        # First message
        result1 = await agent.invoke(
            {"session_id": "session-1", "message": "Hello"}
        )
        assert result1.ok is True

        # Second message - should have history
        result2 = await agent.invoke(
            {"session_id": "session-1", "message": "How are you?"}
        )
        assert result2.ok is True

    async def test_multi_agent_composition(self):
        """Test multiple agents working together."""
        # Extraction agent
        extractor = Agent(name="extractor")

        @extractor.handler
        async def handle(ctx):
            text = ctx.input.get("text", "")
            return {"words": text.split(), "length": len(text)}

        # Analysis agent
        analyzer = Agent(name="analyzer")

        @analyzer.handler
        async def handle(ctx):
            words = ctx.input.get("words", [])
            return {
                "word_count": len(words),
                "avg_length": sum(len(w) for w in words) / len(words)
                if words
                else 0,
            }

        # Orchestrator agent
        orchestrator = Agent(name="orchestrator")
        orchestrator.tool(extractor)
        orchestrator.tool(analyzer)

        @orchestrator.handler
        async def handle(ctx):
            text = ctx.input.get("text", "")

            # Extract
            extraction = await ctx.tool("extractor", text=text)

            # Analyze
            analysis = await ctx.tool(
                "analyzer",
                words=extraction["words"],
            )

            return {
                "extraction": extraction,
                "analysis": analysis,
            }

        result = await orchestrator.invoke({"text": "hello world test"})

        assert result.ok is True
        assert result.output["extraction"]["length"] == 16
        assert result.output["analysis"]["word_count"] == 3

    async def test_flow_with_multiple_agents(self):
        """Test flow orchestration with multiple agents."""
        # Step 1: Input processing
        processor = Agent(name="processor")

        @processor.handler
        async def handle(ctx):
            value = ctx.input.get("value", 0)
            return value * 2

        # Step 2: Validation
        validator = Agent(name="validator")

        @validator.handler
        async def handle(ctx):
            value = ctx.input.get("prev", 0)
            if value < 0:
                raise ValueError("Negative value not allowed")
            return value

        # Step 3: Formatting
        formatter = Agent(name="formatter")

        @formatter.handler
        async def handle(ctx):
            value = ctx.input.get("prev", 0)
            return f"Result: {value}"

        # Create flow
        flow = Flow()
        flow.step("process", processor)
        flow.step("validate", validator)
        flow.step("format", formatter)

        result = await flow.run({"value": 5})

        assert result.ok is True
        assert result.output == "Result: 10"

    async def test_complex_nested_agent_composition(self):
        """Test deeply nested agent composition."""
        # Level 3: Basic calculator
        calculator = Agent(name="calculator")

        @calculator.handler
        async def handle(ctx):
            op = ctx.input.get("operation", "add")
            x = ctx.input.get("x", 0)
            y = ctx.input.get("y", 0)

            if op == "add":
                return x + y
            elif op == "multiply":
                return x * y
            return 0

        # Level 2: Advanced calculator using basic calculator
        advanced_calc = Agent(name="advanced_calc")
        advanced_calc.tool(calculator)

        @advanced_calc.handler
        async def handle(ctx):
            a = ctx.input.get("a", 0)
            b = ctx.input.get("b", 0)
            c = ctx.input.get("c", 0)

            # (a + b) * c
            sum_result = await ctx.tool("calculator", operation="add", x=a, y=b)
            final = await ctx.tool(
                "calculator", operation="multiply", x=sum_result, y=c
            )
            return final

        # Level 1: Problem solver using advanced calculator
        solver = Agent(name="solver")
        solver.tool(advanced_calc)

        @solver.handler
        async def handle(ctx):
            # Solve: (5 + 3) * 2
            result = await ctx.tool("advanced_calc", a=5, b=3, c=2)
            return f"Solution: {result}"

        result = await solver.invoke({})

        assert result.ok is True
        assert result.output == "Solution: 16"

    async def test_error_propagation_through_composition(self):
        """Test error handling through nested agents."""
        # Inner agent that fails
        failing_agent = Agent(name="failing")

        @failing_agent.handler
        async def handle(ctx):
            raise ValueError("Inner agent failed")

        # Outer agent that uses failing agent
        outer = Agent(name="outer")
        outer.tool(failing_agent)

        @outer.handler
        async def handle(ctx):
            return await ctx.tool("failing")

        result = await outer.invoke({})

        assert result.ok is False
        assert "failed" in result.error.lower()

    async def test_full_featured_agent(self):
        """Test agent with all features enabled."""
        agent = Agent(name="full_featured")

        # Add memory
        memory = InMemoryStore()
        agent.use_memory(memory)

        # Add middlewares
        agent.use(timeout_middleware(10.0))
        agent.use(session_middleware())

        # Add tools
        @agent.tool
        async def store_fact(fact: str) -> str:
            return f"Stored: {fact}"

        @agent.handler
        async def handle(ctx):
            message = ctx.input.get("message", "")

            # Use tool
            tool_result = await ctx.tool("store_fact", fact=message)

            # Use memory
            await ctx.remember(message, kind="conversation")
            memories = await ctx.recall("message", limit=5)

            # Update state
            ctx.state["processed"] = True

            return {
                "tool": tool_result,
                "memory_count": len(memories),
                "state": ctx.state,
            }

        result = await agent.invoke(
            {"session_id": "test-session", "message": "test message"}
        )

        assert result.ok is True
        assert "Stored" in result.output["tool"]
        assert result.output["state"]["processed"] is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_empty_input(self):
        """Test agent with empty input."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return "ok"

        result = await agent.invoke({})
        assert result.ok is True

    async def test_none_values_in_input(self):
        """Test agent with None values."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return ctx.input.get("value")

        result = await agent.invoke({"value": None})
        assert result.ok is True
        assert result.output is None

    async def test_large_state(self):
        """Test agent with large state."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            for i in range(1000):
                ctx.state[f"key_{i}"] = f"value_{i}"
            return "done"

        result = await agent.invoke({})
        assert result.ok is True
        assert len(result.state) == 1000

    async def test_recursive_agent_call_protection(self):
        """Test that recursive agent calls are handled."""
        agent = Agent(name="self_caller")

        @agent.handler
        async def handle(ctx):
            depth = ctx.state.get("depth", 0)
            if depth > 5:
                return f"Stopped at depth {depth}"
            ctx.state["depth"] = depth + 1
            # This would be a recursive call in practice
            return f"Depth: {depth}"

        result = await agent.invoke({})
        assert result.ok is True

    async def test_concurrent_invocations(self):
        """Test multiple concurrent invocations."""
        import asyncio

        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            await asyncio.sleep(0.01)
            return ctx.input.get("value")

        # Run multiple invocations concurrently
        tasks = [agent.invoke({"value": i}) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r.ok for r in results)
        for i, result in enumerate(results):
            assert result.output == i

