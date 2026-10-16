# Changelog

All notable changes to the Olakai Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-10-16

### Security

- **Provider API keys are never sent.** The OpenAI, Anthropic, and Google
  instrumentations no longer put the provider key in
  `customData.api_key` (success and error paths). `capture_api_keys` is
  deprecated and ignored; passing `True` emits a `DeprecationWarning`.

### Fixed

- **Sync clients now report events.** Telemetry no longer needs a running
  event loop. Every send (instrumentation, `olakai_event()`,
  `olakai_feedback()`, `olakai_monitor` / `olakai_supervisor`) goes
  through one bounded queue drained by a daemon thread, with the existing
  retry/backoff. Callers never block, and async callers no longer wait on
  the Olakai API inside the event loop. When the queue (1000 events) is
  full, new events are dropped (logged with `debug=True`). The queue is
  re-created after `os.fork()`. The control (blocking) API is unchanged.
- **Provider detection for OpenAI-compatible clients.** `customData.provider`
  comes from the client `base_url`: `openrouter.ai` -> `openrouter`,
  `*.openai.azure.com` -> `azure`, `api.openai.com` or unset -> `openai`,
  any other host -> the host name.

### Added

- `olakai_flush(timeout=5.0) -> bool` waits until queued events are sent
  and returns `True` if the queue drained. It is registered with `atexit`,
  so short-lived scripts deliver their events.
- `OlakaiEventParams.modelName` (optional). Sent as `modelName`; omitted
  when `None`.

## [1.6.0] - 2026-05-04

### Added

- **On-prem host configuration.** `olakai_config()` now accepts a `host`
  keyword argument (hostname only, e.g. `"olakai.acme.com"`) and falls
  back to the `OLAKAI_HOST` environment variable when neither `host` nor
  `endpoint` is provided. Useful for self-hosted Olakai deployments.
  - Resolution precedence: explicit `endpoint` → explicit `host` →
    `OLAKAI_HOST` env var → default `app.olakai.ai`.
  - The resolved endpoint is used to derive monitoring, control, and
    feedback URLs — single point of configuration.
  - `endpoint` parameter is now `Optional[str]` (was a positional default).
  - Legacy `init_olakai_client()` accepts a bare hostname (e.g.
    `"olakai.acme.com"`) for `domain`, and falls back to `OLAKAI_HOST`
    when `domain` is omitted.
- **Robust URL parsing for `host` and `OLAKAI_HOST`.** Inputs are now
  parsed with `urllib.parse.urlparse`, accepting either a bare hostname
  (`olakai.acme.com`) or a full URL (`https://olakai.acme.com/api/v1`).
  For full URLs, only the origin is kept — paths, queries, and trailing
  slashes are stripped. Explicit `endpoint` retains any embedded path
  (back-compat) but trailing slashes are stripped.
- **Loopback hosts default to `http://`.** Bare `localhost`,
  `127.0.0.1`, and `[::1]` (with optional port) now resolve to `http://`
  instead of `https://`. Local Olakai dev servers don't usually have TLS,
  so the previous default produced TLS handshake failures. Pass an
  explicit `https://` prefix to override.

### Changed

- **Fire-and-forget telemetry never raises.** `send_to_api_simple()`
  now swallows transport, retry, and HTTP errors and returns ``None``
  on any failure (matching `send_feedback_to_api()` and the TypeScript
  SDK contract). Previously a failed monitoring call could escape into
  user code through the instrumentation layer's error handler.

### Fixed

- `init_olakai_client()` now imports `olakai_config` from `..config`
  (previously imported from `..core` where it does not live — would have
  raised `ImportError` when called).
- `get_olakai_client()` now imports `get_config` from `..config`
  (same latent bug — worked only by accident because `core.py` re-imports
  the symbol).
- `host`/`OLAKAI_HOST` containing a scheme prefix (e.g.
  `"https://olakai.acme.com"`) no longer produces malformed URLs
  (`https://https://olakai.acme.com`).
- Trailing slashes in `endpoint`, `host`, or `OLAKAI_HOST` no longer
  produce double slashes (`https://acme.com//api/monitoring/prompt`)
  in derived URLs.
- Empty-string `endpoint` (e.g. from a missing-defaulted env var) now
  falls through to `host` / `OLAKAI_HOST` / default instead of producing
  relative URLs like `/api/monitoring/prompt`.
- Userinfo (`user:pass@`) in `host` / `OLAKAI_HOST` URLs is now stripped
  during normalization, keeping credentials out of the resolved endpoint
  and out of debug logs. IPv6 brackets and explicit ports are preserved.
- `host` / `OLAKAI_HOST` URLs with non-http(s) schemes (e.g. `ftp://`,
  `file://`) now raise `URLConfigurationError` at config time instead
  of failing with a less-actionable error at request time.
- `endpoint` is now validated symmetrically with `host`: it must be a
  full URL with an http(s) scheme. Non-http(s) schemes and bare
  hostnames passed via `endpoint` raise `URLConfigurationError` at
  config time. (Previously `endpoint="ftp://x"` or
  `endpoint="bare-host"` would silently produce malformed requests.)
  The legacy `init_olakai_client(api_key, domain=...)` shim is
  affected too: a `domain` value containing `://` but using a
  non-http(s) scheme now raises at config time.
- URL-validation errors are now raised as `URLConfigurationError`
  (already part of the SDK exception hierarchy under `OlakaiSDKError`),
  not bare `ValueError`. Customers can catch all init errors via the
  shared `OlakaiSDKError` base class.

### Example

```python
# SaaS (default)
olakai_config("your-api-key")

# On-prem via host arg
olakai_config("your-api-key", host="olakai.acme.com")

# On-prem via env var: OLAKAI_HOST=olakai.acme.com
olakai_config("your-api-key")
```

## [1.5.0] - 2026-04-14

### Changed

- **`olakai_feedback()`** now posts to the dedicated
  `/api/monitoring/feedback` endpoint instead of wrapping
  `olakai_event()` and routing through `/api/monitoring/prompt`.
  The wire payload is minimal and native:
  `{sessionId, rating, turnIndex?, comment?, email?}` — no more
  `[feedback]` sentinel prompt, no more `customData` markers.
  Public `olakai_feedback(...)` signature is unchanged.
- The backend resolves the target interaction via session inference
  (most recent `PromptRequest` with `chatId == sessionId`) and
  stores the feedback in the `UserFeedback` table with a proper
  FK — no `PromptRequest` phantom rows are created.

### Migration

No code changes required. Upgrade to `1.5.0` and `olakai_feedback()`
will automatically use the new endpoint. Requires the backend
changes that ship the `/api/monitoring/feedback` endpoint.

### Notes

- The `custom_data` keyword argument is still accepted for signature
  backward compatibility but is no longer forwarded to the server —
  the dedicated endpoint owns the schema.

## [1.4.0] - 2026-04-07

### Added

- `olakai_feedback()` - New function for reporting explicit user feedback
  (thumbs up/down) on a prior agent interaction. Fire-and-forget, never
  raises. Wraps the existing monitoring pipeline with a well-known
  `eventType="feedback"` convention in `customData`, so no server
  changes are required.

## [1.0.0] - 2025-01-07

### 🎉 First Stable Release

This release marks the first stable version of the Olakai Python SDK, signaling production readiness for auto-instrumentation of LLM providers.

### Changed

- Version bump to 1.0.0 for production stability
- **Breaking**: Replaced `customDimensions` and `customMetrics` with unified `customData` field for simpler payload structure
- **Breaking**: Remove chatId from `OlakaiEventParams`; chat/session information is now managed internally

### Added

- `olakai_event()` - New function for manually sending event reports

### Stability

The v1.0.0 API is now stable. The primary API consists of:

- `olakai_config()` - Initialize the SDK
- `instrument_openai()` - Auto-instrument OpenAI SDK
- `olakai_context()` - Add metadata to tracked calls
- `uninstrument_openai()` - Remove instrumentation
- `is_instrumented()` - Check instrumentation status
- `olakai_event()` - Send event report manually

---

## [0.6.0] - 2024-12-30

### Added

- **`userId` field** - Added `userId` parameter to `olakai_context()` for explicit user tracking
- **`userId` in types** - Added `userId` to `OlakaiContextData`, `OlakaiEventParams`, `MonitorOptions`, and `MonitorPayload`

### Changed

- Updated `OlakaiContextData.merge()` to include `userId` in context merging
- Updated `OlakaiContextData.to_dict()` to include `userId` in payload output
- Type definitions now align with backend monitoring API expectations

### Compatibility

- Backwards compatible with existing code
- New `userId` field is optional (defaults to `None`)

## [0.5.0] - 2024-11-19

### 🎉 Major Release: Auto-Instrumentation

This is a major refactor introducing automatic instrumentation for LLM providers. The SDK now focuses on server-side Python applications with zero-configuration monitoring.

### Added

- **Auto-instrumentation for OpenAI** - One-line setup with `instrument_openai()`
- **Context-based metadata** - `olakai_context()` for adding user/session metadata
- **Streaming support** - Automatic handling of OpenAI streaming responses
- **Automatic data extraction** - Tokens, model names, API keys, latency
- **Thread-safe context management** - Using Python's contextvars
- **Privacy controls** - Configure what data to capture (inputs, outputs, API keys)
- **Comprehensive documentation** - New README, USAGE.md, and examples
- **Sample scripts** - basic_example.py and advanced_example.py

### Changed

- **Breaking**: Complete API redesign focused on auto-instrumentation
- **Breaking**: Version bumped to 0.5.0 (not backward compatible with 0.4.x)
- **Simplified**: Removed batching and local storage (server-focused)
- **Improved**: Better error handling and debugging
- **Enhanced**: Richer telemetry with automatic LLM-specific data

### Deprecated

- `@olakai_monitor()` decorator - Use `instrument_openai()` instead
- `olakai_report()` - Use auto-instrumentation instead
- `olakai()` low-level API - Use auto-instrumentation instead

These will be removed in v1.0.0.

### Migration Guide

**Old way (v0.4.0):**

```python
from olakaisdk import olakai_config, olakai_monitor

olakai_config("api-key")

@olakai_monitor(userEmail="user@example.com", task="Support")
def get_response(prompt):
    # Your OpenAI call
    pass
```

**New way (v0.5.0):**

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context

olakai_config("api-key")
instrument_openai()  # One-time setup

# No decorator needed!
with olakai_context(userEmail="user@example.com", task="Support"):
    # Your OpenAI calls are automatically tracked
    pass
```

### Technical Details

**New Architecture:**

- `config.py` - Global configuration management
- `context.py` - Thread-safe context manager using contextvars
- `instrumentation/` - Provider-specific instrumentation (OpenAI)
- `extractors/` - Data extraction from LLM responses

**Test Coverage:**

- 35+ passing tests
- Config tests
- Context tests
- Instrumentation tests
- Extractor tests

### What's Next

Planned for future releases:

- Anthropic (Claude) instrumentation
- Google AI (Gemini) instrumentation
- Local model support (Ollama, LM Studio)
- Enhanced streaming analytics
- Cost optimization recommendations

---

## [0.4.0] - 2024-10-24

### Changed

- Simplified API with `olakai_config()` and `@olakai_monitor()`
- Removed complex initialization options
- Removed batching and priority queuing
- Introduced `customDimensions` and `customMetrics`

### Removed

- `init_olakai_client()` - replaced with `olakai_config()`
- `sanitize` option
- `priority` option
- `batchSize` option
- `enableStorage` option

---

## [0.3.x] - 2024-10-20

### Features

- Initial release with `@olakai_supervisor()` decorator
- Batch processing
- Local storage
- Priority queuing
- Complex configuration

---

## Release Notes

### v0.5.0 Highlights

This release transforms the Olakai SDK into an automatic instrumentation library specifically designed for server-side LLM monitoring. Key improvements:

1. **Zero-friction DX**: Just call `instrument_openai()` once and forget about it
2. **Richer telemetry**: Automatic capture of tokens, costs, models, API keys
3. **Better ergonomics**: Context managers instead of decorators
4. **Server-focused**: Removed client-side features like batching
5. **Extensible**: Clean architecture for adding more LLM providers

### Breaking Changes

v0.5.0 is **not backward compatible** with v0.4.0. The API has been completely redesigned. Please refer to the migration guide above.

### Support

- Documentation: [README.md](./README.md)
- Usage Guide: [USAGE.md](./USAGE.md)
- Examples: [examples/](./examples/)
- Issues: [GitHub Issues](https://github.com/olakai/sdk-python/issues)
- Email: [support@olakai.ai](mailto:support@olakai.ai)
