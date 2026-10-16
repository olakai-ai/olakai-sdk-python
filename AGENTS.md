# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Olakai Python SDK v1.0.0 is an **auto-instrumentation SDK** for monitoring LLM usage in server-side Python applications. It automatically tracks OpenAI API calls with zero code changes, capturing tokens, costs, models, and custom metadata.

**Key Concepts (v1.0.0):**

- **Auto-instrumentation**: Monkey-patches OpenAI SDK to automatically track all calls
- **Context-based metadata**: Use `olakai_context()` to add user/custom data
- **Manual event reporting**: Use `olakai_event()` to send custom event reports
- **User feedback reporting**: Use `olakai_feedback()` to report thumbs up/down on a prior interaction
- **Unified customData**: Single `customData` field for all custom metadata (replaces `customDimensions`/`customMetrics`)
- **Streaming support**: Buffers streaming responses and sends telemetry when complete
- **Server-focused**: Designed for backend applications (FastAPI, Flask, Django)
- **Thread-safe**: Uses Python's contextvars for async safety
- **Privacy controls**: Configure what data to capture (inputs, outputs)

## Commands

### Development Setup

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Or install directly with pytest
/usr/bin/python3 -m pip install pytest pytest-cov pytest-asyncio --user
```

### Testing

```bash
# Run all tests
/usr/bin/python3 -m pytest

# Run specific test modules
/usr/bin/python3 -m pytest tests/test_config.py -v
/usr/bin/python3 -m pytest tests/test_context.py -v
/usr/bin/python3 -m pytest tests/test_openai_instrumentation.py -v

# Run specific test
/usr/bin/python3 -m pytest tests/test_config.py::test_olakai_config_basic -v

# Run with verbose output
/usr/bin/python3 -m pytest -v
```

### Code Quality

```bash
# Run all checks (formatting, linting, type checking, tests)
./tests/check.sh

# Format code with ruff
ruff format --line-length 80 src/olakaisdk tests

# Lint with ruff
ruff check --fix src/olakaisdk tests

# Type check with mypy
mypy --ignore-missing-imports src/olakaisdk tests
```

### Building & Publishing

```bash
# Build distribution packages
python -m build

# Check built packages
twine check dist/*

# Upload to PyPI (requires credentials)
twine upload dist/*
```

### Running Examples

```bash
# Set API keys
export OLAKAI_API_KEY=your-olakai-key
export OPENAI_API_KEY=your-openai-key

# Run basic example
/usr/bin/python3 examples/basic_example.py

# Run advanced example
/usr/bin/python3 examples/advanced_example.py
```

## Architecture (v1.0.0)

### Module Structure

```
src/olakaisdk/
├── __init__.py              # Public API exports (v1.0.0 + legacy)
├── config.py                # Global configuration (olakai_config, get_config)
├── context.py               # Context manager (olakai_context, thread-safe)
├── instrumentation/         # Provider-specific instrumentation
│   ├── __init__.py
│   ├── base.py              # Base instrumentation interface
│   └── openai.py            # OpenAI monkey patching (instrument_openai)
├── extractors/              # Data extraction from LLM responses
│   ├── __init__.py
│   ├── base_extractor.py    # Base extractor interface
│   └── openai_extractor.py  # Extract tokens, model, API key, etc.
├── client/                  # API communication
│   ├── __init__.py
│   ├── api.py               # HTTP client with retry logic
│   └── client.py
├── shared/                  # Common types and exceptions
│   ├── __init__.py
│   ├── types.py             # OlakaiConfig, MonitorPayload, etc.
│   └── exceptions.py
├── core.py                  # Core API (olakai, olakai_event, olakai_feedback, olakai_monitor)
└── monitor/                 # Legacy decorator (olakai_supervisor)
    ├── __init__.py
    └── decorator.py

tests/
├── __init__.py
├── test_basic.py            # Basic tests
├── test_config.py           # Config module tests
├── test_context.py          # Context module tests
├── test_openai_instrumentation.py  # Instrumentation tests
└── check.sh                 # Code quality script

examples/
├── README.md
├── basic_example.py         # Basic usage demonstration
└── advanced_example.py      # Real-world use cases
```

### Key Files

**`src/olakaisdk/config.py`**

- Global configuration management via `_global_config`
- `olakai_config(api_key, endpoint=None, debug=False, host=None)`: Initialize SDK
- `_resolve_endpoint(endpoint, host)`: Resolves the API URL with precedence:
  explicit `endpoint` → explicit `host` → `OLAKAI_HOST` env var →
  default `https://app.olakai.ai`. Used to support on-prem deployments.
- `get_config()`: Get current configuration
- `require_config()`: Get config or raise error
- `is_initialized()`: Check if SDK is configured

**`src/olakaisdk/context.py`**

- Thread-safe context storage using `contextvars`
- `OlakaiContextData`: Dataclass for context metadata (userEmail, userId, task, subTask, customData)
- `olakai_context(**metadata)`: Context manager for adding metadata
- `get_current_context()`: Get current context (used by instrumentation)
- Supports nested contexts with merging
- Note: `chatId` removed in v1.0.0; session tracking via `config.sessionId`

**`src/olakaisdk/instrumentation/openai.py`**

- Monkey patches OpenAI SDK methods
- `instrument_openai()`: Wrap OpenAI's chat.completions.create
- `uninstrument_openai()`: Restore original methods
- `is_instrumented()`: Check instrumentation status
- Handles sync, async, and streaming responses
- Fire-and-forget telemetry (non-blocking)

**`src/olakaisdk/extractors/openai_extractor.py`**

- `OpenAIExtractor`: Extract telemetry from OpenAI responses
- Extracts: tokens (input/output), model, provider (from base_url), latency
- Merges with context metadata
- Privacy controls for redacting data

**`src/olakaisdk/shared/types.py`**

- `OlakaiConfig`: SDK configuration (api_key, endpoint, debug, sessionId as UUID)
- `OlakaiEventParams`: Event parameters (prompt, response, userEmail, sessionId, taskExecutionId, task, subTask, customData, shouldScore, tokens, requestTime, modelName)
- `MonitorPayload`: API payload (customData replaces customDimensions/customMetrics)
- Response types

### Design Patterns

**Monkey Patching for Auto-Instrumentation**

- Wraps `openai.resources.chat.completions.Completions.create`
- Stores original methods in module-level variables
- Restores originals on `uninstrument_openai()`

**Context Manager Pattern**

- `olakai_context()` uses Python's contextvar for thread safety
- Supports nesting with automatic merging
- Context survives async boundaries

**Streaming Buffering**

- Wraps streaming generators/async generators
- Buffers all chunks while yielding to user
- Sends telemetry after stream completes
- Reconstructs complete response from chunks

**Fire-and-Forget Telemetry**

- All sends go through one bounded queue (`client/api.py`) drained by a
  daemon thread; callers never block (sync or async). Drop-newest when full.
- `olakai_flush(timeout)` waits for the queue; registered with `atexit`
- Queued sends: 5 s timeout, 1 retry; worker restarts if it dies;
  state reset in forked children (`os.register_at_fork`)
- Control (blocking) API calls do not use the queue
- Errors in telemetry don't affect user code

## Important Implementation Details

### Host Resolution (on-prem support)

Both `olakai_config()` and the legacy `init_olakai_client()` resolve the
target Olakai host with this precedence:

1. **Explicit `endpoint`** (full URL) — wins over everything; rare path,
   reserved for non-default scheme/path.
2. **Explicit `host`** (hostname only, e.g. `"olakai.acme.com"`) — preferred
   for on-prem deployments. The SDK prepends `https://`.
3. **`OLAKAI_HOST` env var** — same semantics as the `host` arg; lets ops
   set the on-prem host without code changes.
4. **Default** — `app.olakai.ai` (SaaS).

The resolved endpoint is used in `client/api.py` to build
`/api/monitoring/prompt`, `/api/control/prompt`, and
`/api/monitoring/feedback` URLs. This mirrors the TypeScript SDK's
`host` / `OLAKAI_HOST` behavior.

### Thread Safety

The SDK uses `contextvars.ContextVar` for thread-safe context storage. This ensures:

- Each async task has its own context
- Nested contexts work correctly
- No race conditions in multi-threaded applications

### Streaming Support

Streaming responses are handled specially:

1. Detect `stream=True` in kwargs
2. Wrap the generator/async generator
3. Buffer chunks while yielding to user
4. Reconstruct complete response from buffered chunks
5. Send telemetry after stream completes

**Note**: Token counts are not available during streaming (OpenAI limitation). The backend will calculate them.

### API Key Tracking

The SDK never sends provider API keys (removed in 1.7.0). The
`capture_api_keys` parameter is deprecated and ignored.

### Error Handling

- Instrumentation errors are logged but don't break user code
- Error telemetry is sent with `errorMessage` field
- Retry logic in `client/api.py` (exponential backoff, max 3 retries)

## Naming Conventions

- **Functions**: Snake case (e.g., `olakai_config`, `instrument_openai`)
- **Classes/Types**: PascalCase (e.g., `OlakaiConfig`, `OpenAIExtractor`)
- **Private module vars**: Leading underscore (e.g., `_global_config`)
- **Internal functions**: Leading underscore (e.g., `_trace_openai_call_sync`)

## Common Patterns

### Adding a New LLM Provider

1. Create `instrumentation/provider_name.py`
2. Implement `instrument_provider_name()` function
3. Create `extractors/provider_name_extractor.py`
4. Export from `instrumentation/__init__.py`
5. Export from main `__init__.py`
6. Add tests in `tests/test_openai_instrumentation.py`

Example structure:

```python
# instrumentation/anthropic.py
def instrument_anthropic():
    # Monkey patch Anthropic SDK
    pass

# extractors/anthropic_extractor.py
class AnthropicExtractor(BaseExtractor):
    def extract(self, ...):
        # Extract tokens, model, etc.
        pass
```

### Adding a New Context Field

1. Add field to `OlakaiContextData` in `context.py`
2. Update `merge()` method if needed
3. Update extractor to use the field
4. Add tests in `tests/test_context.py`

### Debugging Instrumentation

Enable debug mode to see what's happening:

```python
from olakaisdk import olakai_config, is_instrumented

olakai_config("key", debug=True)  # Enables debug logging
instrument_openai()

print(f"Instrumented: {is_instrumented()}")
# Debug output shows: "[Olakai] OpenAI SDK instrumented successfully"
```

## Testing Strategy

### Unit Tests

- `test_config.py`: Config module (9 tests)
- `test_context.py`: Context manager (12 tests)
- `test_openai_instrumentation.py`: Instrumentation and extractors (8 tests)

All tests use mocks to avoid network calls.

### Running Tests

```bash
# All new tests (should pass)
/usr/bin/python3 -m pytest tests/test_config.py tests/test_context.py tests/test_openai_instrumentation.py -v

# Legacy tests (some fail - expected due to breaking changes)
/usr/bin/python3 -m pytest tests/test_basic.py -v
```

### Test Coverage

Current: 35 passing tests covering:

- Configuration management
- Context nesting and merging
- Data extraction from responses
- Privacy controls (redaction)
- Error handling

## Migration Notes (v0.5.0 → v1.0.0)

### Breaking Changes

- **`customDimensions` and `customMetrics` replaced** with unified `customData` field
- **`chatId` removed** from `OlakaiContextData` and `olakai_context()`; session tracking now uses internal `sessionId` (UUID)
- **`olakai_report()` renamed** to `olakai_event()` with simplified signature: `olakai_event(params: OlakaiEventParams)`
- **`olakai()` signature changed**: now takes only `params` (removed `event_type` and `event_name`)

### Added

- `olakai_event()` - New function for manually sending event reports
- `sessionId` - Auto-generated UUID in `OlakaiConfig` for session tracking

### Changed

- Version: 0.5.0 → 1.0.0
- Stable production-ready API

## Package Distribution

- **Package name**: `olakai-sdk` (PyPI)
- **Import name**: `olakaisdk`
- **Version**: 1.0.0
- **Python**: 3.7+
- **Dependencies**: `requests>=2.25.0`, `typing-extensions>=3.7.4` (for Python < 3.8)
- **Optional**: `openai>=1.0.0` (for OpenAI instrumentation)

## Future Enhancements

Planned for future releases:

- **Anthropic instrumentation**: `instrument_anthropic()` for Claude
- **Google AI instrumentation**: `instrument_google()` for Gemini
- **Local models**: Support for Ollama, LM Studio
- **Enhanced streaming**: Real-time token tracking
- **Cost optimization**: Automatic recommendations

## Documentation

- **README.md**: User-facing documentation and API reference
- **USAGE.md**: Detailed usage guide with examples
- **CHANGELOG.md**: Version history and migration guides
- **examples/**: Sample scripts demonstrating usage
- **CLAUDE.md**: This file (development guide)
