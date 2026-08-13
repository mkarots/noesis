"""Noesis — production runtime for AI agents.

Deploy any agent framework. Add production features. Compose across frameworks.
"""

from noesis.core import Agent, AgentResult, Context, RuntimeEvent
from noesis.errors import AgentError, TimeoutError, ToolError, UserError
from noesis.flow import Flow
from noesis.http import build_fastapi, serve
from noesis.memory import InMemoryStore
from noesis.middleware import error_middleware, session_middleware, timeout_middleware
from noesis.protocols import MemoryStore, ReflectionClient, RuntimeServices, Tool
from noesis.runtime import Runtime

__version__ = "0.1.0"

__all__ = [
    # Core
    "Agent",
    "Context",
    "AgentResult",
    "RuntimeEvent",
    "Runtime",
    # Transport
    "serve",
    "build_fastapi",
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
