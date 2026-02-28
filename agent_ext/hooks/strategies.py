"""Execution strategies for parallel middleware and guardrails."""
from __future__ import annotations

from enum import Enum


class AggregationStrategy(Enum):
    """How to aggregate results from parallel middleware.

    - ALL_MUST_PASS: all must succeed
    - FIRST_SUCCESS: first non-error result
    - RACE: first to complete (even if error)
    - COLLECT_ALL: return all results as a list
    """
    ALL_MUST_PASS = "all_must_pass"
    FIRST_SUCCESS = "first_success"
    RACE = "race"
    COLLECT_ALL = "collect_all"


class GuardrailTiming(Enum):
    """When guardrails execute relative to the agent/LLM call.

    - BLOCKING: guardrail completes before agent starts (traditional)
    - CONCURRENT: guardrail runs alongside LLM, fail-fast on violation
    - ASYNC_POST: guardrail runs after LLM (monitoring only, non-blocking)
    """
    BLOCKING = "blocking"
    CONCURRENT = "concurrent"
    ASYNC_POST = "async_post"
