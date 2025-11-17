"""Tests for HTTP runtime."""

import pytest
from fastapi.testclient import TestClient

from noesis import Agent
from noesis.http import build_fastapi


class TestHttpRuntime:
    """Test FastAPI HTTP runtime."""

    def test_build_fastapi_creates_app(self):
        """Test build_fastapi creates a FastAPI app."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return "hello"

        app = build_fastapi(agent)
        assert app is not None
        assert app.title == "Noesis Agent: test"

    def test_health_endpoint(self):
        """Test /health endpoint."""
        agent = Agent(name="test_agent")

        @agent.handler
        async def handle(ctx):
            return "ok"

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "agent": "test_agent"}

    def test_invoke_endpoint_success(self):
        """Test /invoke endpoint with successful invocation."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            msg = ctx.input.get("message", "")
            return f"Echo: {msg}"

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {"message": "hello"}})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["output"] == "Echo: hello"
        assert data["error"] is None

    def test_invoke_endpoint_with_state(self):
        """Test /invoke with state parameter."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            ctx.state["processed"] = True
            return ctx.state

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post(
            "/invoke",
            json={"input": {}, "state": {"initial": "value"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["state"]["initial"] == "value"
        assert data["state"]["processed"] is True

    def test_invoke_endpoint_with_meta(self):
        """Test /invoke with meta parameter."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return ctx.meta.get("user")

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post(
            "/invoke",
            json={"input": {}, "meta": {"user": "alice"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["output"] == "alice"

    def test_invoke_endpoint_error(self):
        """Test /invoke with handler error."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            raise ValueError("Something went wrong")

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {}})

        assert response.status_code == 200  # Still 200, error in response body
        data = response.json()
        assert data["ok"] is False
        assert "Something went wrong" in data["error"]

    def test_invoke_endpoint_with_tools(self):
        """Test /invoke with agent that uses tools."""
        agent = Agent(name="test")

        @agent.tool
        async def add(x: int, y: int) -> int:
            return x + y

        @agent.handler
        async def handle(ctx):
            x = ctx.input.get("x", 0)
            y = ctx.input.get("y", 0)
            return await ctx.tool("add", x=x, y=y)

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {"x": 5, "y": 3}})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["output"] == 8

    def test_invoke_endpoint_complex_output(self):
        """Test /invoke with complex output."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return {
                "status": "success",
                "data": {"items": [1, 2, 3], "count": 3},
                "nested": {"deep": {"value": True}},
            }

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {}})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["output"]["status"] == "success"
        assert data["output"]["data"]["count"] == 3
        assert data["output"]["nested"]["deep"]["value"] is True

    def test_multiple_requests(self):
        """Test handling multiple requests."""
        agent = Agent(name="test")
        call_count = {"value": 0}

        @agent.handler
        async def handle(ctx):
            call_count["value"] += 1
            return f"Call {call_count['value']}"

        app = build_fastapi(agent)
        client = TestClient(app)

        for i in range(1, 4):
            response = client.post("/invoke", json={"input": {}})
            assert response.json()["output"] == f"Call {i}"

    def test_invoke_without_state_or_meta(self):
        """Test /invoke works with only input."""
        agent = Agent(name="test")

        @agent.handler
        async def handle(ctx):
            return "minimal"

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {}})

        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestHttpWithMiddleware:
    """Test HTTP runtime with middlewares."""

    def test_http_with_timeout_middleware(self):
        """Test HTTP endpoint with timeout middleware."""
        import asyncio

        from noesis.middleware import timeout_middleware

        agent = Agent(name="test")
        agent.use(timeout_middleware(0.1))

        @agent.handler
        async def handle(ctx):
            await asyncio.sleep(0.5)
            return "done"

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {}})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "timeout" in data["error"]

    def test_http_with_session_middleware(self):
        """Test HTTP endpoint with session middleware."""
        from noesis.memory import InMemoryStore
        from noesis.middleware import session_middleware

        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)
        agent.use(session_middleware())

        @agent.handler
        async def handle(ctx):
            return f"Session: {ctx.session_id}"

        app = build_fastapi(agent)
        client = TestClient(app)

        response = client.post(
            "/invoke",
            json={"input": {"session_id": "http-session"}},
        )

        assert response.status_code == 200
        assert "http-session" in response.json()["output"]


class TestHttpWithAgentAsTools:
    """Test HTTP runtime with agent-as-tool composition."""

    def test_http_with_nested_agents(self):
        """Test HTTP endpoint with agents using other agents as tools."""
        # Create specialized agent
        calculator = Agent(name="calculator")

        @calculator.handler
        async def handle(ctx):
            return ctx.input.get("x", 0) + ctx.input.get("y", 0)

        # Create main agent
        main = Agent(name="main")
        main.tool(calculator)

        @main.handler
        async def handle(ctx):
            x = ctx.input.get("x", 0)
            y = ctx.input.get("y", 0)
            result = await ctx.tool("calculator", x=x, y=y)
            return f"Calculation result: {result}"

        app = build_fastapi(main)
        client = TestClient(app)

        response = client.post("/invoke", json={"input": {"x": 10, "y": 5}})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["output"] == "Calculation result: 15"

