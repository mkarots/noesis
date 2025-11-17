"""Noesis Agent Framework V3

A minimal, composable agent framework.
"""

from noesis.core import Agent, AgentResult, Context, RuntimeEvent
from noesis.errors import AgentError, TimeoutError, ToolError, UserError
from noesis.flow import Flow
from noesis.memory import InMemoryStore
from noesis.middleware import error_middleware, session_middleware, timeout_middleware
from noesis.protocols import MemoryStore, ReflectionClient, RuntimeServices, Tool

__version__ = "0.1.0"

__all__ = [
    # Core
    "Agent",
    "Context",
    "AgentResult",
    "RuntimeEvent",
    # Protocols
    "Tool",
    "MemoryStore",
    "ReflectionClient",
    "RuntimeServices",
    # Errors
    "AgentError",
    "UserError",
    "ToolError",
    "TimeoutError",
    # Flow
    "Flow",
    # Memory
    "InMemoryStore",
    # Middleware
    "error_middleware",
    "timeout_middleware",
    "session_middleware",
]
