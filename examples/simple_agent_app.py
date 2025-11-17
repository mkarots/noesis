"""
Simple example agent application ready for Docker deployment.

Usage:
    uvicorn examples.simple_agent_app:app --host 0.0.0.0 --port 8000
"""

from noesis import Agent
from noesis.http import build_fastapi
from noesis.middleware import timeout_middleware

# Create agent
agent = Agent(name="simple_agent", description="A simple production-ready agent")

# Add timeout middleware
agent.use(timeout_middleware(30.0))

# Register tools
@agent.tool
async def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

@agent.tool
async def calculate(x: int, y: int, operation: str = "add") -> int:
    """Perform basic arithmetic."""
    if operation == "add":
        return x + y
    elif operation == "subtract":
        return x - y
    elif operation == "multiply":
        return x * y
    elif operation == "divide":
        return x // y if y != 0 else 0
    return 0

# Register handler
@agent.handler
async def handle(ctx):
    """Main agent handler."""
    action = ctx.input.get("action", "greet")
    
    if action == "greet":
        name = ctx.input.get("name", "World")
        result = await ctx.tool("greet", name=name)
        return {"message": result}
    
    elif action == "calculate":
        x = ctx.input.get("x", 0)
        y = ctx.input.get("y", 0)
        op = ctx.input.get("operation", "add")
        result = await ctx.tool("calculate", x=x, y=y, operation=op)
        return {"result": result, "operation": op}
    
    else:
        return {"error": "Unknown action", "available": ["greet", "calculate"]}

# Build FastAPI app
app = build_fastapi(agent)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

