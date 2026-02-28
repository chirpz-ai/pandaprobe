"""Universal LLM engine for PandaProbe.

Provides a single entry point (``LLMEngine``) that routes requests to
any supported provider via LiteLLM.  The engine validates credentials
at call time and returns clear errors when a provider is unavailable.
"""

from app.infrastructure.llm.engine import LLMEngine

__all__ = ["LLMEngine"]
