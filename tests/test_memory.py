"""Tests for memory subsystem."""

import pytest

from noesis import Agent
from noesis.memory import InMemoryStore


class TestInMemoryStore:
    """Test InMemoryStore implementation."""

    async def test_create_store(self):
        """Test creating an empty store."""
        store = InMemoryStore()
        assert store._items == []

    async def test_put_single_item(self):
        """Test storing a single item."""
        store = InMemoryStore()
        await store.put(content="test content", kind="note", meta={"author": "test"})

        assert len(store._items) == 1
        assert store._items[0]["content"] == "test content"
        assert store._items[0]["kind"] == "note"
        assert store._items[0]["author"] == "test"

    async def test_put_multiple_items(self):
        """Test storing multiple items."""
        store = InMemoryStore()
        await store.put(content="first", kind="note", meta={})
        await store.put(content="second", kind="note", meta={})
        await store.put(content="third", kind="session", meta={})

        assert len(store._items) == 3

    async def test_search_by_content(self):
        """Test searching by content substring."""
        store = InMemoryStore()
        await store.put(content="hello world", kind="note", meta={})
        await store.put(content="goodbye world", kind="note", meta={})
        await store.put(content="hello universe", kind="note", meta={})

        results = await store.search(query="hello", kind=None, limit=10)
        assert len(results) == 2
        assert all("hello" in r["content"].lower() for r in results)

    async def test_search_by_kind(self):
        """Test filtering search by kind."""
        store = InMemoryStore()
        await store.put(content="note one", kind="note", meta={})
        await store.put(content="note two", kind="note", meta={})
        await store.put(content="session one", kind="session", meta={})

        results = await store.search(query="one", kind="note", limit=10)
        assert len(results) == 1
        assert results[0]["content"] == "note one"

    async def test_search_limit(self):
        """Test search result limit."""
        store = InMemoryStore()
        for i in range(10):
            await store.put(content=f"item {i}", kind="note", meta={})

        results = await store.search(query="item", kind=None, limit=5)
        assert len(results) == 5

    async def test_search_case_insensitive(self):
        """Test search is case insensitive."""
        store = InMemoryStore()
        await store.put(content="Hello World", kind="note", meta={})

        results = await store.search(query="hello", kind=None, limit=10)
        assert len(results) == 1

        results = await store.search(query="WORLD", kind=None, limit=10)
        assert len(results) == 1

    async def test_search_no_results(self):
        """Test search with no matches."""
        store = InMemoryStore()
        await store.put(content="something", kind="note", meta={})

        results = await store.search(query="nonexistent", kind=None, limit=10)
        assert len(results) == 0

    async def test_search_empty_store(self):
        """Test searching empty store."""
        store = InMemoryStore()
        results = await store.search(query="anything", kind=None, limit=10)
        assert len(results) == 0


class TestMemoryIntegration:
    """Test memory integration with agents."""

    async def test_agent_remember(self):
        """Test agent can remember items."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        @agent.handler
        async def handle(ctx):
            await ctx.remember("important fact", kind="note")
            return "remembered"

        result = await agent.invoke({})
        assert result.ok is True
        assert len(memory._items) == 1
        assert memory._items[0]["content"] == "important fact"

    async def test_agent_recall(self):
        """Test agent can recall items."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        # Pre-populate memory
        await memory.put(content="stored fact", kind="note", meta={})

        @agent.handler
        async def handle(ctx):
            results = await ctx.recall("stored")
            return results

        result = await agent.invoke({})
        assert result.ok is True
        assert len(result.output) == 1
        assert result.output[0]["content"] == "stored fact"

    async def test_agent_remember_with_metadata(self):
        """Test remembering with custom metadata."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        @agent.handler
        async def handle(ctx):
            await ctx.remember(
                "fact with metadata",
                kind="note",
                author="agent",
                timestamp=12345,
            )
            return "done"

        await agent.invoke({})
        assert memory._items[0]["author"] == "agent"
        assert memory._items[0]["timestamp"] == 12345

    async def test_agent_recall_with_kind_filter(self):
        """Test recall with kind filter."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        await memory.put(content="note item", kind="note", meta={})
        await memory.put(content="session item", kind="session", meta={})

        @agent.handler
        async def handle(ctx):
            return await ctx.recall("item", kind="note")

        result = await agent.invoke({})
        assert len(result.output) == 1
        assert result.output[0]["kind"] == "note"

    async def test_agent_recall_with_limit(self):
        """Test recall with custom limit."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        for i in range(10):
            await memory.put(content=f"item {i}", kind="note", meta={})

        @agent.handler
        async def handle(ctx):
            return await ctx.recall("item", limit=3)

        result = await agent.invoke({})
        assert len(result.output) == 3

    async def test_memory_events_logged(self):
        """Test memory operations log events."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        @agent.handler
        async def handle(ctx):
            await ctx.remember("test")
            await ctx.recall("test")
            return "done"

        result = await agent.invoke({})
        
        write_events = [e for e in result.events if e.kind == "memory_write"]
        read_events = [e for e in result.events if e.kind == "memory_read"]
        result_events = [e for e in result.events if e.kind == "memory_result"]

        assert len(write_events) == 1
        assert len(read_events) == 1
        assert len(result_events) == 1

    async def test_multiple_memory_operations(self):
        """Test multiple memory operations in one invocation."""
        agent = Agent(name="test")
        memory = InMemoryStore()
        agent.use_memory(memory)

        @agent.handler
        async def handle(ctx):
            await ctx.remember("first", kind="note")
            await ctx.remember("second", kind="note")
            results = await ctx.recall("first")
            return len(results)

        result = await agent.invoke({})
        assert result.ok is True
        assert result.output == 1
        assert len(memory._items) == 2


class TestMemoryProtocol:
    """Test memory protocol compliance."""

    async def test_custom_memory_store(self):
        """Test using a custom memory store implementation."""

        class CustomMemoryStore:
            """Custom memory store for testing."""

            def __init__(self):
                self.puts = []
                self.searches = []

            async def put(self, *, content, kind, meta):
                self.puts.append({"content": content, "kind": kind, **meta})

            async def search(self, *, query, kind, limit):
                self.searches.append({"query": query, "kind": kind, "limit": limit})
                return [{"content": "custom result"}]

        agent = Agent(name="test")
        custom_memory = CustomMemoryStore()
        agent.use_memory(custom_memory)

        @agent.handler
        async def handle(ctx):
            await ctx.remember("test content", kind="custom")
            results = await ctx.recall("test")
            return results

        result = await agent.invoke({})

        # Verify custom store was used
        assert len(custom_memory.puts) == 1
        assert custom_memory.puts[0]["content"] == "test content"
        assert len(custom_memory.searches) == 1
        assert custom_memory.searches[0]["query"] == "test"
        assert result.output[0]["content"] == "custom result"

