# Olakai Python SDK

**Automatic instrumentation for LLM monitoring and tracking** - Monitor your AI applications with zero code changes.

[![PyPI version](https://badge.fury.io/py/olakai-sdk.svg)](https://badge.fury.io/py/olakai-sdk)
[![Python](https://img.shields.io/badge/Python-3.7+-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)

---

## What's New in v1.0.0 🎉

**First stable release!** The Olakai Python SDK is now production-ready with a stable API for auto-instrumentation of LLM providers.

- ✅ **Production stable** - v1.0.0 marks the first stable release
- ✅ **Simplified payload** - Unified `customData` field replaces `customDimensions` and `customMetrics`
- ✅ **New `olakai_event()` function** - Manually send event reports when needed
- ✅ **Streamlined session management** - `chatId` removed from context; sessions managed internally via `sessionId`
- ✅ **Auto-instrument OpenAI** - One line to monitor all OpenAI calls
- ✅ **Zero code changes** - Works with existing OpenAI code

---

## Quick Start (30 seconds)

### Installation

```bash
pip install olakai-sdk
pip install openai  # Install OpenAI SDK separately
```

### Basic Usage

```python
from olakaisdk import olakai_config, instrument_openai
from openai import OpenAI

# 1. Configure Olakai (one-time setup)
olakai_config("your-olakai-api-key")

# 2. Auto-instrument OpenAI
instrument_openai()

# 3. Use OpenAI normally - monitoring happens automatically!
client = OpenAI(api_key="your-openai-key")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

# That's it! Your call is now tracked with:
# - Token counts (input/output)
# - Model name and provider
# - Latency
# - Request/response content
```

**Check your [Olakai dashboard](https://app.olakai.ai) to see the tracked data!**

---

## Features

### Automatic Tracking

After calling `instrument_openai()`, the SDK automatically captures:

- **Token usage** - Prompt tokens, completion tokens, total tokens
- **Provider** - Detected from the client `base_url` (`openai`, `openrouter`, `azure`, or the host)
- **Model information** - Which model was used (gpt-4, gpt-3.5-turbo, etc.)
- **Latency** - Request duration in milliseconds
- **Content** - Prompts and responses (configurable)
- **Errors** - Automatic error tracking with context

### Context-Based Metadata

Add user and task metadata using context managers:

```python
from olakaisdk import olakai_context

with olakai_context(
    userEmail="user@example.com",
    userId="user-123",
    task="Customer Support"
):
    # All OpenAI calls within this context include the metadata
    response = client.chat.completions.create(...)
```

**Note:** Session tracking is handled automatically via an internal `sessionId`.

### Streaming Support

Works seamlessly with OpenAI's streaming API:

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True  # Streaming is automatically handled!
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")

# Telemetry is sent after stream completes
```

---

## Installation Options

```bash
# Basic installation
pip install olakai-sdk

# With OpenAI support
pip install olakai-sdk[openai]

# For development
pip install olakai-sdk[dev]
```

**Requirements:** Python 3.7+

---

## Usage Examples

### Minimal Example

```python
from olakaisdk import olakai_config, instrument_openai
from openai import OpenAI

olakai_config("olakai-api-key")
instrument_openai()

client = OpenAI(api_key="openai-key")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### With User Context

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI

olakai_config("olakai-api-key")
instrument_openai()

client = OpenAI(api_key="openai-key")

# Add user metadata
with olakai_context(
    userEmail="customer@example.com",
    userId="customer-456",
    task="Customer Support",
    subTask="password-reset"
):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "How do I reset my password?"}
        ]
    )
    print(response.choices[0].message.content)
```

### With Custom Data

```python
with olakai_context(
    userEmail="user@example.com",
    task="Content Generation",
    customData={
        "environment": "production",
        "region": "us-east-1",
        "user_tier": "premium",
        "user_id": 12345,
        "session_length": 45.5,
        "is_premium": True
    }
):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Write a blog post"}]
    )
```

### Nested Contexts

Contexts can be nested, with inner contexts overriding outer values:

```python
# Outer context applies to all calls
with olakai_context(task="Customer Service", userEmail="support@example.com"):

    # Inner context overrides specific fields
    with olakai_context(subTask="billing-inquiry"):
        response = client.chat.completions.create(...)
        # Has task="Customer Service", subTask="billing-inquiry"

    # Back to outer context
    with olakai_context(subTask="technical-support"):
        response = client.chat.completions.create(...)
        # Has task="Customer Service", subTask="technical-support"
```

### Async Support

Works with async OpenAI calls:

```python
import asyncio
from openai import AsyncOpenAI

async def main():
    olakai_config("olakai-api-key")
    instrument_openai()

    client = AsyncOpenAI(api_key="openai-key")

    with olakai_context(userEmail="user@example.com"):
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello async world!"}]
        )
        print(response.choices[0].message.content)

asyncio.run(main())
```

---

## Configuration

### Initialize the SDK

```python
from olakaisdk import olakai_config

# Basic configuration (SaaS — defaults to app.olakai.ai)
olakai_config("your-api-key")

# On-prem deployment via host argument
olakai_config("your-api-key", host="olakai.acme.com")

# On-prem deployment via OLAKAI_HOST env var (no host arg needed)
#   $ export OLAKAI_HOST=olakai.acme.com
olakai_config("your-api-key")

# Full endpoint override (rarely needed; for non-default scheme/path)
olakai_config("your-api-key", endpoint="https://custom.olakai.ai")

# With debug logging
olakai_config("your-api-key", debug=True)
```

**Host resolution precedence:** explicit `endpoint` → explicit `host` →
`OLAKAI_HOST` env var → default `app.olakai.ai`.

### Instrumentation Options

```python
from olakaisdk import instrument_openai

# Default: capture everything
instrument_openai()

# Customize what to capture
instrument_openai(
    capture_inputs=True,      # Capture prompts/messages
    capture_outputs=True,     # Capture responses
)
```

### Privacy Controls

Disable input/output capture for sensitive data:

```python
instrument_openai(
    capture_inputs=False,    # Don't send prompts
    capture_outputs=False,   # Don't send responses
)
```

Provider API keys (OpenAI, Anthropic, Google) are never sent to Olakai.

### Delivery

Events are queued and sent by one background thread, so a monitored call
never waits on the Olakai API (sync and async code both work). Queued
events are flushed automatically at process exit. To flush earlier (for
example at the end of a serverless handler), call:

```python
from olakaisdk import olakai_flush

olakai_flush(timeout=5.0)  # True if everything was sent
```

The queue holds up to 1000 events. When it is full, new events are
dropped (a line is printed when `debug=True`).

---

## API Reference

### Primary API (v1.0.0)

#### `olakai_config(api_key, endpoint=None, debug=False, host=None)`

Initialize the Olakai SDK. Must be called before instrumentation.

**Parameters:**

- `api_key` (str): Your Olakai API key
- `endpoint` (str, optional): Full API endpoint URL. If omitted, derived
  from `host` / `OLAKAI_HOST` env var / default `https://app.olakai.ai`.
  Use this only when you need a non-default scheme or path.
- `debug` (bool, optional): Enable debug logging
- `host` (str, optional): Olakai hostname only (e.g. `"olakai.acme.com"`)
  for on-prem deployments. Falls back to the `OLAKAI_HOST` env var, then
  `"app.olakai.ai"`. Ignored if `endpoint` is provided.

---

#### `instrument_openai(capture_inputs=True, capture_outputs=True)`

Auto-instrument OpenAI SDK for monitoring.

**Parameters:**

- `capture_inputs` (bool): Capture prompt/messages
- `capture_outputs` (bool): Capture responses
- `capture_api_keys` (bool): Deprecated and ignored. Provider API keys are
  never sent. Passing `True` emits a `DeprecationWarning`.

**Raises:**

- `RuntimeError`: If SDK not configured with `olakai_config()`
- `ImportError`: If OpenAI SDK not installed

---

#### `olakai_context(**metadata)`

Context manager to add metadata to LLM calls.

**Parameters:**

- `userEmail` (str, optional): User email for tracking
- `userId` (str, optional): User ID for explicit user tracking
- `task` (str, optional): High-level task category
- `subTask` (str, optional): Specific subtask
- `customData` (dict, optional): Custom metadata (string, int, float, or bool values)

**Note:** Session tracking is handled automatically via an internal `sessionId`.

**Example:**

```python
with olakai_context(userEmail="user@example.com", userId="user-123", task="Support"):
    # Your OpenAI calls here
    pass
```

---

#### `uninstrument_openai()`

Remove OpenAI instrumentation. Restores original OpenAI behavior.

---

#### `is_instrumented()`

Check if OpenAI is currently instrumented.

**Returns:** `bool`

---

#### `olakai_event(params)`

Send manual report of AI interaction.

**Parameters:**

- `params` (OlakaiEventParams)

Where `OlakaiEventParams` has the fields:

- `prompt` (str): Interaction prompt
- `response` (str): Interaction response
- `userEmail` (str, optional): User email for tracking
- `userId` (str, optional): User ID for explicit user tracking
- `task` (str, optional): High-level task category
- `subTask` (str, optional): Specific subtask
- `customData` (dict, optional): Custom metadata (string, int, float, or bool values)
- `shouldScore` (bool, optional): Whether scoring should be applied to the data
- `tokens` (int, optional): Number of tokens used
- `requestTime` (int, optional): Time in milliseconds of the interaction
- `modelName` (str, optional): Model used (omitted from the payload when `None`)

**Example:**

```python
olakai_event(OlakaiEventParams(
    prompt="Test prompt",
    response="Test response",
    userEmail="test@example.com",
    userId="user-123",
    task="test-task"
))
```

---

#### `olakai_feedback(session_id, rating, *, turn_index=None, comment=None, user_email=None, custom_data=None)`

Report explicit user feedback (thumbs up/down) on a prior agent
interaction. Fire-and-forget, like `olakai_event()` — never raises.

Feedback is reported against a session, so `session_id` should
match the session/chat ID used when the original interaction was
reported. Optionally, `turn_index` can be used for turn-level
feedback correlation within a multi-turn conversation.

**Parameters:**

- `session_id` (str): The session/conversation ID of the interaction being rated
- `rating` (`"UP"` | `"DOWN"`): The user's feedback
- `turn_index` (int, optional): Zero-based turn index within the session
- `comment` (str, optional): Free-text comment alongside the rating
- `user_email` (str, optional): Override for the user who gave the feedback
- `custom_data` (dict, optional): Customer-defined fields for domain context

**Example:**

```python
from olakaisdk import olakai_feedback

# Thumbs-up on turn 3 of a specific chat session
olakai_feedback(
    session_id="chat_abc123",
    rating="UP",
    turn_index=3,
    comment="Very helpful answer",
)

# Thumbs-down without a comment
olakai_feedback(session_id="chat_abc123", rating="DOWN")
```

---

### Legacy API (Deprecated)

The v0.4.0 decorator-based API is still available but deprecated. Use the primary API above instead:

- `@olakai_monitor()` - Manual decorator (use `instrument_openai()` instead)
- `@olakai_supervisor()` - Alias for `olakai_monitor()` (deprecated)
- `olakai()` - Low-level API (use `olakai_event()` instead)

---

## How It Works

### Under the Hood

1. **Monkey Patching**: `instrument_openai()` wraps OpenAI's `chat.completions.create` methods
2. **Data Extraction**: Automatically extracts tokens, model, latency from responses
3. **Context Merging**: Combines context metadata with extracted data
4. **Async Telemetry**: Sends data to Olakai API without blocking your code
5. **Error Handling**: Captures errors without affecting your application

### Data Flow

```
Your Code → OpenAI API → Response
    ↓                        ↓
Olakai Context      Extract Telemetry
    ↓                        ↓
    └──→ Merge & Send to Olakai API (async)
```

---

## Migration from v0.4.0

### Old Way (v0.4.0)

```python
from olakaisdk import olakai_config, olakai_monitor
from openai import OpenAI

olakai_config("api-key")

@olakai_monitor(
    userEmail="user@example.com",
    task="Support",
    customData={"model": "gpt-4"}
)
def get_response(prompt):
    client = OpenAI(api_key="openai-key")
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

result = get_response("Hello")
```

### New Way (v0.5.0)

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI

olakai_config("api-key")
instrument_openai()  # ← One-time setup

client = OpenAI(api_key="openai-key")

def get_response(prompt):
    # No decorator needed!
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Add metadata with context when needed
with olakai_context(userEmail="user@example.com", task="Support"):
    result = get_response("Hello")
```

**Key Improvements:**

- ✅ No decorators needed
- ✅ Model name automatically captured
- ✅ Tokens automatically captured
- ✅ Works with existing OpenAI code
- ✅ Cleaner, more maintainable code

---

## Dashboard & Analytics

After setting up monitoring, visit your [Olakai dashboard](https://app.olakai.ai) to see:

- **Usage Analytics** - API calls, tokens, trends over time
- **Cost Tracking** - Per-API-key usage for ROI analysis
- **User Insights** - Individual user behavior patterns
- **Task Performance** - Monitor different tasks and success rates
- **Model Comparison** - Compare performance across models
- **Custom Data** - Visualize your custom metadata

---

## Best Practices

### Do This ✅

- **Initialize once**: Call `olakai_config()` at app startup
- **Instrument early**: Call `instrument_openai()` before creating clients
- **Use contexts**: Add metadata with `olakai_context()` for rich analytics
- **Track users**: Always include `userEmail` when possible
- **Organize tasks**: Use consistent `task` and `subTask` names
- **Custom data**: Track environment, region, features with `customData`

### Avoid This ❌

- **Don't skip configuration**: Always call `olakai_config()` first
- **Don't log secrets**: Never include passwords in prompts/responses
- **Don't instrument twice**: Check `is_instrumented()` before re-instrumenting
- **Don't use decorators**: The old `@olakai_monitor()` API is deprecated

### Security Tips

- Store API keys in environment variables
- Use `capture_inputs=False` / `capture_outputs=False` for sensitive data
- Review dashboard access controls
- Consider GDPR/privacy requirements for user tracking

---

## Troubleshooting

### SDK not initialized error

```python
RuntimeError: Olakai SDK not initialized. Call olakai_config() first.
```

**Solution:** Call `olakai_config()` before `instrument_openai()`.

---

### OpenAI not installed error

```python
ImportError: OpenAI SDK not installed. Install with: pip install openai
```

**Solution:** `pip install openai`

---

### No data in dashboard

**Possible causes:**

1. Check API key is correct
2. Enable debug mode: `olakai_config("key", debug=True)`
3. Verify network connectivity
4. Check instrumentation: `is_instrumented()` should return `True`

---

### Streaming not working

Make sure you're iterating through the entire stream:

```python
response = client.chat.completions.create(..., stream=True)

# ✅ Correct - iterate fully
for chunk in response:
    print(chunk.choices[0].delta.content)
# Telemetry sent after loop completes

# ❌ Wrong - don't break early
for chunk in response:
    if some_condition:
        break  # Telemetry won't be sent!
```

---

## Examples

See [USAGE.md](./USAGE.md) for more detailed examples and use cases.

Try the sample script:

```bash
python examples/basic_example.py
```

---

## Development

### Setup

```bash
git clone https://github.com/olakai/olakai-sdk-python
cd olakai-sdk-python
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
pytest tests/test_openai_instrumentation.py -v
```

### Code Quality

```bash
./tests/check.sh
```

---

## Support & Community

- **Documentation:** [Olakai Docs](https://app.olakai.ai/docs)
- **Support:** [support@olakai.ai](mailto:support@olakai.ai)
- **Issues:** [GitHub Issues](https://github.com/olakai/sdk-python/issues)
- **Changelog:** [CHANGELOG.md](./CHANGELOG.md)

---

## License

MIT © [Olakai](https://olakai.ai)

---

## What's Next?

- 🚀 Anthropic instrumentation (Claude support)
- 🚀 Google AI instrumentation (Gemini support)
- 🚀 Local model support (Ollama, LM Studio)
- 🚀 Enhanced streaming analytics
- 🚀 Cost optimization recommendations

---

**Ready to monitor your AI application?**

```bash
pip install olakai-sdk openai
```

```python
from olakaisdk import olakai_config, instrument_openai
olakai_config("your-api-key")
instrument_openai()
# Start building! 🚀
```

**Happy monitoring!**
