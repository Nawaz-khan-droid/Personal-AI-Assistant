"""
Custom exception classes for better error handling.

Why: Custom exceptions make error handling more explicit and maintainable.
They allow catching specific error types rather than generic Exception.

Best Practice: Define exceptions at module level for consistency.
"""

from typing import Optional


class JarvisBaseException(Exception):
    """Base exception for all JARVIS-specific errors."""
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


# AI Service Errors
class AIServiceError(JarvisBaseException):
    """Base for AI service failures."""
    pass


class LLMError(AIServiceError):
    """LLM API failure (Groq)."""
    pass


class STTError(AIServiceError):
    """Speech-to-Text failure (ElevenLabs)."""
    pass


class TTSError(AIServiceError):
    """Text-to-Speech failure (ElevenLabs)."""
    pass


# Security Errors
class SecurityError(JarvisBaseException):
    """Base for security violations."""
    pass


class RateLimitError(SecurityError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after:.1f} seconds",
            code="rate_limit_exceeded"
        )


class PromptInjectionError(SecurityError):
    """Prompt injection attempt detected."""
    pass


class UnauthorizedToolError(SecurityError):
    """Attempted to execute unauthorized tool."""
    pass


# Tool Execution Errors
class ToolError(JarvisBaseException):
    """Base for tool execution failures."""
    pass


class ToolNotFoundError(ToolError):
    """Requested tool doesn't exist."""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution exceeded timeout."""
    pass


class ToolParameterError(ToolError):
    """Invalid tool parameters."""
    pass


# Input Validation Errors
class ValidationError(JarvisBaseException):
    """Input validation failed."""
    pass


class InputTooLongError(ValidationError):
    """Input exceeds maximum length."""
    pass


class InvalidInputError(ValidationError):
    """Input contains invalid characters or format."""
    pass
