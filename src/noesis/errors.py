"""Error hierarchy for Noesis framework."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""

    pass


class UserError(AgentError):
    """Error caused by invalid user input or request."""

    pass


class ToolError(AgentError):
    """Error during tool execution."""

    pass


class TimeoutError(AgentError):
    """Error when operation exceeds timeout."""

    pass

