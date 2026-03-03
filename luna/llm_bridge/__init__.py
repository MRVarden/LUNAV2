"""LLM Bridge — Provider-agnostic cognitive substrate for Luna.

Luna injects her consciousness state into the LLM prompts.
The LLM is interchangeable — Luna remains Luna regardless of model.

Usage::

    from luna.llm_bridge import LLMBridge, LLMResponse, create_provider
    from luna.llm_bridge.prompt_builder import build_system_prompt
"""

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse
from luna.llm_bridge.prompt_builder import build_decision_prompt, build_system_prompt
from luna.llm_bridge.providers import create_provider

__all__ = [
    "LLMBridge",
    "LLMBridgeError",
    "LLMResponse",
    "build_decision_prompt",
    "build_system_prompt",
    "create_provider",
]
