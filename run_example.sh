#!/bin/bash
# Run example demonstrating Noesis Agent Framework features

set -e

echo "🚀 Running Noesis Agent Framework Example..."
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found."
    exit 1
fi

# Create and run example inline
cat > /tmp/noesis_example_$$.py << 'EOF'
"""Example usage of Noesis Agent Framework."""

import asyncio

from noesis import Agent, InMemoryStore, session_middleware, timeout_middleware


# Create a simple agent
greeter = Agent(name="greeter", description="Greets users")


@greeter.handler
async def handle(ctx):
    name = ctx.input.get("name", "World")
    return f"Hello, {name}!"


# Create an agent with tools
calculator = Agent(name="calculator", description="Does math")


@calculator.tool
async def add(x: int, y: int) -> int:
    return x + y


@calculator.tool
async def multiply(x: int, y: int) -> int:
    return x * y


@calculator.handler
async def handle(ctx):
    operation = ctx.input.get("operation", "add")
    x = ctx.input.get("x", 0)
    y = ctx.input.get("y", 0)
    
    if operation == "add":
        result = await ctx.tool("add", x=x, y=y)
    else:
        result = await ctx.tool("multiply", x=x, y=y)
    
    return f"{operation}({x}, {y}) = {result}"


# Create an agent with memory
chatbot = Agent(name="chatbot")
memory = InMemoryStore()
chatbot.use_memory(memory)
chatbot.use(timeout_middleware(30.0))
chatbot.use(session_middleware())


@chatbot.handler
async def handle(ctx):
    message = ctx.input.get("message", "")
    await ctx.remember(f"User: {message}", kind="chat")
    return f"Got it! You said: {message}"


# Agent as tool
orchestrator = Agent(name="orchestrator")
orchestrator.tool(greeter)
orchestrator.tool(calculator)


@orchestrator.handler
async def handle(ctx):
    greeting = await ctx.tool("greeter", name="Alice")
    calc = await ctx.tool("calculator", operation="multiply", x=5, y=3)
    return f"{greeting} | {calc}"


async def main():
    # Test simple agent
    result = await greeter.invoke({"name": "Noesis"})
    print(f"✓ Greeter: {result.output}")
    
    # Test agent with tools
    result = await calculator.invoke({"operation": "add", "x": 10, "y": 5})
    print(f"✓ Calculator: {result.output}")
    
    # Test agent with memory
    result = await chatbot.invoke({
        "session_id": "test-123",
        "message": "Hello!"
    })
    print(f"✓ Chatbot: {result.output}")
    
    # Test agent composition
    result = await orchestrator.invoke({})
    print(f"✓ Orchestrator: {result.output}")
    
    print("\n🎉 All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
EOF

# Run the example
python /tmp/noesis_example_$$.py

# Clean up
rm /tmp/noesis_example_$$.py

