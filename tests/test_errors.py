"""Tests for error hierarchy."""

import pytest

from noesis.errors import AgentError, TimeoutError, ToolError, UserError


class TestErrorHierarchy:
    """Test error class hierarchy."""

    def test_agent_error_is_exception(self):
        """Test AgentError is an Exception."""
        error = AgentError("test")
        assert isinstance(error, Exception)

    def test_user_error_is_agent_error(self):
        """Test UserError inherits from AgentError."""
        error = UserError("test")
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_tool_error_is_agent_error(self):
        """Test ToolError inherits from AgentError."""
        error = ToolError("test")
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_timeout_error_is_agent_error(self):
        """Test TimeoutError inherits from AgentError."""
        error = TimeoutError("test")
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_error_messages(self):
        """Test error messages are preserved."""
        msg = "Something went wrong"
        assert str(AgentError(msg)) == msg
        assert str(UserError(msg)) == msg
        assert str(ToolError(msg)) == msg
        assert str(TimeoutError(msg)) == msg

    def test_catch_agent_error(self):
        """Test catching AgentError catches all subclasses."""
        errors = [
            UserError("user"),
            ToolError("tool"),
            TimeoutError("timeout"),
        ]

        for error in errors:
            with pytest.raises(AgentError):
                raise error

    def test_catch_specific_error(self):
        """Test catching specific error types."""
        with pytest.raises(ToolError):
            raise ToolError("tool error")

        with pytest.raises(UserError):
            raise UserError("user error")

        with pytest.raises(TimeoutError):
            raise TimeoutError("timeout error")

