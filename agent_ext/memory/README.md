# Memory — Context Management

Automatic conversation history management with safe cutoff and optional LLM summarization.

## Features

- **Sliding Window**: Message-count or token-aware trimming (zero LLM cost)
- **Safe Cutoff**: Never splits tool call/response pairs
- **Token Counting**: Approximate or custom (tiktoken)
- **Summarization**: LLM-powered dossier compression (pluggable summarize_fn)
- **Triggers**: Trim only when thresholds are hit

## Quick Start

```python
from agent_ext.memory import SlidingWindowMemory

# Message-count mode (default)
memory = SlidingWindowMemory(max_messages=50)

# Token-aware mode
memory = SlidingWindowMemory(
    max_tokens=100_000,
    trigger_tokens=80_000,  # only trim when over 80k tokens
)

# With custom token counter
import tiktoken
enc = tiktoken.get_encoding("o200k_base")

def count_tokens(messages):
    return sum(len(enc.encode(str(m))) for m in messages)

memory = SlidingWindowMemory(max_tokens=50_000, token_counter=count_tokens)
```

## Safe Cutoff

The system never splits tool call/response pairs when trimming:

```python
from agent_ext.memory import find_safe_cutoff, is_safe_cutoff_point

# Find safe place to cut keeping last 20 messages
cutoff_index = find_safe_cutoff(messages, messages_to_keep=20)
trimmed = messages[cutoff_index:]
```

## Summarization

```python
from agent_ext.memory import SummarizingMemory, SummarizeConfig

def my_summarize_fn(ctx, text, base_dossier):
    # Use LLM to update the dossier
    base_dossier.summary = f"Updated summary of: {text[:500]}..."
    return base_dossier

memory = SummarizingMemory(
    cfg=SummarizeConfig(max_messages=80, keep_last_n=30),
    summarize_fn=my_summarize_fn,
)
```
